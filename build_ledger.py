#!/usr/bin/env python3
"""Authoritative NFT movement ledger from raw ERC-721/1155 Transfer events.

Marketplace feeds (OpenSea/Blur) cover only ~26% of legs — they are used ONLY for
price enrichment downstream, NOT as the source of legs. The source of truth is
on-chain Transfer logs where one of our three wallets is `from` or `to`.

Design
  - publicnode (50k block-range cap) as primary, with RPC failover + exponential
    backoff across a pool; rotate on 429/timeout/error.
  - One getLogs per (contract, direction, 50k-chunk); topics use an OR-array of the
    three padded wallet addresses so all wallets are caught in a single call.
  - JSON-RPC batching: many chunk requests per HTTP round-trip.
  - Resumable disk cache keyed by (contract, direction, chunk) -> logs. A crash
    mid-run loses nothing; rerun continues.
  - Scans BOTH signatures: ERC-721 Transfer(addr,addr,uint256) [tokenId indexed,
    4 topics] and ERC-1155 TransferSingle/TransferBatch [ids/values in data].

Output: transfer_ledger.jsonl — one line per leg:
  {wallet, dir(in|out), collection, contract, standard, token, qty, block, ts,
   tx, counterparty}

Stop condition is enforced by the separate reconcile step: net(in-out) per token
must equal balanceOf. This script just builds the complete ledger.
"""
import json
import os
import time
import random
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(ROOT, "analysis", "logcache")
OUT = os.path.join(ROOT, "transfer_ledger.jsonl")
os.makedirs(CACHE_DIR, exist_ok=True)

WALLETS = [
    "0x028296d8bf1995549d5b9446622cf565bbd0a26e",
    "0x400f2bd92098c386cea677d6e7f832eb25c6e3cf",
    "0x8e8d6246c45d0e7f68172e85573546d90fc2e062",
]
WSET = {w.lower() for w in WALLETS}
WTOPICS = ["0x" + w[2:].rjust(64, "0") for w in WALLETS]  # padded for topic filter

T_ERC721 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
T_SINGLE = "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"
T_BATCH = "0x4a39dc06d4c0dbc64b70af90fd698a233a518aa5d07e595d983b8c0526c8f7fb"

# Conservative LOWER-BOUND deploy blocks (a too-low bound only wastes empty chunks;
# a too-high bound silently truncates early legs and breaks the invariant). These
# sit at/below each collection's real launch; reconcile will flag any that are still
# too high.
DEPLOYS = {
    "azuki": ("0xed5af388653567af2f388e6224dc7c4b3241c544", 13_300_000),
    "bitmappunks": ("0xbbbba1ee822c9b8fc134dea6adfc26603a9cbbbb", 17_600_000),
    "boredapeyachtclub": ("0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d", 12_280_000),
    "clonex": ("0x49cf6f5d44e70224e2e23fdcdd2c053f30ada28b", 13_700_000),
    "degods-eth": ("0x8821bee2ba0df28761afff119d66390d594cd280", 17_000_000),
    "doodles-official": ("0x8a90cab2b38dba80c64b7734e58ee1db38b8992e", 13_400_000),
    "lilpudgys": ("0x524cab2ec69124574082676e6f654a18df49a048", 15_100_000),
    "meebits": ("0x7bd29408f11d2bfc23c34f18275bbf23bb716bc7", 12_750_000),
    "mutant-ape-yacht-club": ("0x60e4d786628fea6478f785a6d7e704777c86a7c6", 13_080_000),
    "otherside-koda": ("0xe012baf811cf9c05c408e879c399960d1f305903", 15_480_000),
    "persona": ("0xbabafdd8045740449a42b788a26e9b3a32f88ac1", 17_200_000),
    "pudgypenguins": ("0xbd3531da5cf5857e7cfaa92426877b022e612cf8", 13_900_000),
    "rektguy": ("0xb852c6b5892256c264cc2c888ea462189154d8d7", 14_750_000),
    "sappy-seals": ("0x364c828ee171616a39897688a831c2499ad972ec", 14_100_000),
    "the-dooplicator": ("0x466cfcd0525189b573e794f554b8a751279213ac", 13_980_000),
    "y00ts-eth": ("0xfd1b0b0dfa524e1fd42e7d51155a663c581bbd50", 17_800_000),
}

RPCS = [
    "https://ethereum-rpc.publicnode.com",
    "https://rpc.mevblocker.io",
    "https://eth.llamarpc.com",
    "https://eth.drpc.org",  # only good for small ranges; kept for failover
]
CHUNK = 50_000
_blk_ts = {}  # block -> timestamp cache


def rpc_batch(calls, max_tries=6):
    """calls: list of (method, params). Returns list of results (None on fail).
    Failover across RPCS with exponential backoff + jitter."""
    payload = [
        {"jsonrpc": "2.0", "id": i, "method": m, "params": p}
        for i, (m, p) in enumerate(calls)
    ]
    delay = 1.0
    order = list(range(len(RPCS)))
    random.shuffle(order)
    for attempt in range(max_tries):
        url = RPCS[order[attempt % len(RPCS)]]
        try:
            r = requests.post(url, json=payload, timeout=45)
            if r.status_code in (429, 502, 503, 504):
                raise RuntimeError(f"http {r.status_code}")
            j = r.json()
            if not isinstance(j, list):
                # single error object for whole batch
                raise RuntimeError(str(j)[:120])
            out = [None] * len(calls)
            ok = True
            for item in j:
                idx = item.get("id")
                if "result" in item and item["result"] is not None:
                    out[idx] = item["result"]
                else:
                    ok = False  # at least one sub-call failed (e.g. range cap)
            if ok:
                return out
            # partial failure -> retry whole batch on another endpoint
            raise RuntimeError("partial batch failure")
        except Exception:
            time.sleep(delay + random.random())
            delay = min(delay * 2, 20)
    return None


def get_logs_chunk(contract, direction, lo, hi):
    """One getLogs for a contract/direction/range, all wallets via OR-topic.
    direction 'in' = wallet is `to`; 'out' = wallet is `from`. Covers 721 + 1155."""
    # 721: topics [Transfer, from, to, tokenId]; 1155 single/batch: [sig, operator, from, to]
    if direction == "out":
        t721 = [T_ERC721, WTOPICS, None, None]
        t1155 = [[T_SINGLE, T_BATCH], None, WTOPICS, None]
    else:
        t721 = [T_ERC721, None, WTOPICS, None]
        t1155 = [[T_SINGLE, T_BATCH], None, None, WTOPICS]
    base = {"address": contract, "fromBlock": hex(lo), "toBlock": hex(hi)}
    calls = [
        ("eth_getLogs", [{**base, "topics": t721}]),
        ("eth_getLogs", [{**base, "topics": t1155}]),
    ]
    res = rpc_batch(calls)
    if res is None:
        return None
    logs = []
    for r in res:
        if r:
            logs.extend(r)
    return logs


def cache_path(col, direction, lo):
    return os.path.join(CACHE_DIR, f"{col}__{direction}__{lo}.json")


def head_block():
    r = rpc_batch([("eth_blockNumber", [])])
    return int(r[0], 16)


def block_ts(block):
    if block in _blk_ts:
        return _blk_ts[block]
    r = rpc_batch([("eth_getBlockByNumber", [hex(block), False])])
    ts = int(r[0]["timestamp"], 16) if r and r[0] else None
    _blk_ts[block] = ts
    return ts


def decode_721(lg):
    frm = "0x" + lg["topics"][1][-40:]
    to = "0x" + lg["topics"][2][-40:]
    token = str(int(lg["topics"][3], 16))
    return [(frm.lower(), to.lower(), token, 1)]


def decode_1155(lg):
    frm = "0x" + lg["topics"][2][-40:]
    to = "0x" + lg["topics"][3][-40:]
    data = lg["data"][2:]
    out = []
    if lg["topics"][0] == T_SINGLE:
        tid = str(int(data[0:64], 16))
        qty = int(data[64:128], 16)
        out.append((frm.lower(), to.lower(), tid, qty))
    else:  # batch: dynamic arrays of ids then values
        words = [data[i : i + 64] for i in range(0, len(data), 64)]
        # layout: off_ids, off_vals, len_ids, ids..., len_vals, vals...
        n = int(words[2], 16)
        ids = [int(words[3 + i], 16) for i in range(n)]
        voff = 3 + n
        nv = int(words[voff], 16)
        vals = [int(words[voff + 1 + i], 16) for i in range(nv)]
        for tid, qty in zip(ids, vals):
            out.append((frm.lower(), to.lower(), str(tid), qty))
    return out


def main():
    head = head_block()
    print(f"head block {head}")
    raw_legs = []  # (col, contract, standard, token, qty, frm, to, block, tx)
    for col, (contract, deploy) in DEPLOYS.items():
        n_chunks = (head - deploy) // CHUNK + 1
        print(f"\n{col}: blocks {deploy}..{head}  ({n_chunks} chunks/direction)")
        for direction in ("in", "out"):
            lo = deploy
            done = 0
            while lo <= head:
                hi = min(lo + CHUNK - 1, head)
                cp = cache_path(col, direction, lo)
                if os.path.exists(cp):
                    logs = json.load(open(cp))
                else:
                    logs = get_logs_chunk(contract, direction, lo, hi)
                    if logs is None:
                        print(f"  !! FAILED chunk {col} {direction} {lo}-{hi}; "
                              f"leaving uncached for retry on rerun")
                        lo = hi + 1
                        continue
                    json.dump(logs, open(cp, "w"))
                for lg in logs:
                    standard = "erc721" if lg["topics"][0] == T_ERC721 else "erc1155"
                    decoded = decode_721(lg) if standard == "erc721" else decode_1155(lg)
                    blk = int(lg["blockNumber"], 16)
                    tx = lg["transactionHash"]
                    for frm, to, token, qty in decoded:
                        raw_legs.append((col, contract, standard, token, qty,
                                         frm, to, blk, tx))
                done += 1
                lo = hi + 1
            print(f"  {direction}: {done} chunks scanned")

    # De-dup raw logs (the in/out scans overlap when both ends are ours -> internal
    # transfer appears in both). Key on (tx, contract, token, frm, to, block).
    seen = set()
    uniq = []
    for r in raw_legs:
        col, contract, standard, token, qty, frm, to, blk, tx = r
        k = (tx, contract, token, frm, to, blk)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    # Expand each raw transfer into per-wallet legs (a transfer between two of our
    # wallets yields one 'out' leg and one 'in' leg).
    blocks_needed = sorted({r[7] for r in uniq})
    print(f"\n{len(uniq)} unique transfers; fetching {len(blocks_needed)} block timestamps...")
    # batch timestamp fetches
    BATCH = 40
    for i in range(0, len(blocks_needed), BATCH):
        grp = blocks_needed[i : i + BATCH]
        res = rpc_batch([("eth_getBlockByNumber", [hex(b), False]) for b in grp])
        if res:
            for b, r in zip(grp, res):
                if r:
                    _blk_ts[b] = int(r["timestamp"], 16)

    legs = []
    for col, contract, standard, token, qty, frm, to, blk, tx in uniq:
        ts = _blk_ts.get(blk)
        if frm in WSET:
            legs.append({"wallet": frm, "dir": "out", "collection": col,
                         "contract": contract, "standard": standard, "token": token,
                         "qty": qty, "block": blk, "ts": ts, "tx": tx,
                         "counterparty": to})
        if to in WSET:
            legs.append({"wallet": to, "dir": "in", "collection": col,
                         "contract": contract, "standard": standard, "token": token,
                         "qty": qty, "block": blk, "ts": ts, "tx": tx,
                         "counterparty": frm})

    legs.sort(key=lambda x: (x["wallet"], x["collection"], x["block"]))
    with open(OUT, "w") as f:
        for leg in legs:
            f.write(json.dumps(leg) + "\n")
    print(f"\nwrote {len(legs)} legs -> {OUT}")


if __name__ == "__main__":
    main()
