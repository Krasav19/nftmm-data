#!/usr/bin/env python3
"""blur_full.py — full on-chain Blur trade history for the 3 operator wallets.

Read-only, public RPC. Blur settles in BETH (Blur Pool, an ETH-pegged ERC-20), so
every Blur trade leaves a BETH Transfer touching the wallet:
  - BETH paid by wallet  (from=wallet) -> a BUY  (wallet acquired an NFT)
  - BETH received by wallet (to=wallet) -> a SELL (wallet sold an NFT)
We scan BETH Transfer logs (indexed from/to => cheap) across the wallet's whole
active range, then enrich each settlement tx with the NFT(s) moved, the total
ETH+WETH+BETH the wallet paid/received, and the maker/taker side.

maker/taker: the tx sender (tx.from) is the TAKER (executed/took an order). If our
wallet == tx.from we took someone's standing order; otherwise our order was taken
(we were the maker / resting side).

Note: Blur routes through several router/delegate contracts, so we do NOT key on a
single proxy address — the BETH+NFT pairing is the reliable settlement signal.

Outputs:
  analysis/blur/trades_full.jsonl   one row per (wallet, settlement, token)
  analysis/blur/trades_full_summary.json
"""
import json
import os
import time
from collections import defaultdict

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "analysis", "blur")
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)

RPCS = ["https://ethereum-rpc.publicnode.com", "https://rpc.mevblocker.io"]
WALLETS = [
    "0x028296d8bf1995549d5b9446622cf565bbd0a26e",
    "0x400f2bd92098c386cea677d6e7f832eb25c6e3cf",
    "0x8e8d6246c45d0e7f68172e85573546d90fc2e062",
]
WSET = {w.lower() for w in WALLETS}
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
BETH = "0x0000000000a39bb272e79075ade125fd351887ac"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
ETH20 = {BETH, WETH}
CHUNK = 49000
# Blur contract labels (for venue confirmation only; not used for detection)
BLUR_LABELS = {
    "0xb2ecfe4e4d61f8790bbb9de2d1259b9e2410cea5": "BlurExchangeV2",
    "0x000000000000ad05ccc4f10045630fb830b95127": "BlurExchange",
    "0x39da41747a83aee658334415666f3ef92dd0d541": "Blend",
    BETH: "BlurPool",
}
# contract -> collection slug (built from our dataset)
CONTRACT2SLUG = {}

_logf = open(os.path.join(HERE, "logs", "blur_full.log"), "w")
_ri = 0


def log(*a):
    m = " ".join(str(x) for x in a)
    print(m, flush=True)
    _logf.write(m + "\n")
    _logf.flush()


def rpc(method, params):
    global _ri
    for _ in range(8):
        url = RPCS[_ri % len(RPCS)]
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method,
                                         "params": params}, timeout=30)
            j = r.json()
            if "result" in j:
                return j["result"]
            _ri += 1
            time.sleep(1.0)
        except Exception:
            _ri += 1
            time.sleep(1.0)
    return None


def taddr(a):
    return "0x" + a[2:].lower().rjust(64, "0")


def load_contract_map():
    import glob
    mn = mx = None
    for jf in glob.glob(os.path.join(HERE, "data", "events_0x*.jsonl")):
        for line in open(jf):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            n = e.get("nft") or e.get("asset") or {}
            if n.get("contract") and n.get("collection"):
                CONTRACT2SLUG[n["contract"].lower()] = n["collection"]
            ts = e.get("event_timestamp")
            if ts:
                mn = ts if mn is None else min(mn, ts)
                mx = ts if mx is None else max(mx, ts)
    return mn, mx


def block_for_ts(ts, head, head_ts):
    return max(0, head - int((head_ts - ts) / 12.05))


def scan_beth(wallet, lo, hi):
    """Return settlement txs touching wallet via BETH, with direction."""
    txs = {}  # txhash -> {"dir_hint": set(), "beth_out":.., "beth_in":..}
    b = lo
    while b <= hi:
        top = min(b + CHUNK, hi)
        for direction, topics in (("out", [TRANSFER, taddr(wallet)]),
                                   ("in", [TRANSFER, None, taddr(wallet)])):
            logs = rpc("eth_getLogs", [{"fromBlock": hex(b), "toBlock": hex(top),
                                        "address": BETH, "topics": topics}])
            if logs is None:
                time.sleep(1)
                continue
            for lg in logs:
                h = lg["transactionHash"]
                d = txs.setdefault(h, {"block": int(lg["blockNumber"], 16),
                                       "beth_out": 0.0, "beth_in": 0.0})
                val = int(lg["data"], 16) / 1e18
                if direction == "out":
                    d["beth_out"] += val
                else:
                    d["beth_in"] += val
        b = top + 1
    return txs


def enrich(txhash, wallet):
    """Decode a settlement tx: NFTs moved, total value paid/received by wallet, side."""
    txd = rpc("eth_getTransactionByHash", [txhash])
    rc = rpc("eth_getTransactionReceipt", [txhash])
    if not txd or not rc:
        return None
    sender = (txd.get("from") or "").lower()
    is_taker = sender == wallet
    paid = 0.0
    recv = 0.0
    if sender == wallet and txd.get("value"):
        paid += int(txd["value"], 16) / 1e18
    venues = set()
    nfts_in, nfts_out = [], []
    for lg in rc.get("logs", []):
        a = lg["address"].lower()
        if a in BLUR_LABELS:
            venues.add(BLUR_LABELS[a])
        t0 = lg["topics"][0]
        if t0 != TRANSFER:
            continue
        if a in ETH20 and len(lg["topics"]) >= 3:
            frm = "0x" + lg["topics"][1][-40:]
            to = "0x" + lg["topics"][2][-40:]
            try:
                val = int(lg["data"], 16) / 1e18
            except (ValueError, TypeError):
                continue
            if frm.lower() == wallet:
                paid += val
            elif to.lower() == wallet:
                recv += val
        elif len(lg["topics"]) == 4:  # ERC721 Transfer (3 indexed topics)
            frm = "0x" + lg["topics"][1][-40:]
            to = "0x" + lg["topics"][2][-40:]
            tid = int(lg["topics"][3], 16)
            rec = {"contract": a, "slug": CONTRACT2SLUG.get(a), "token": str(tid)}
            if to.lower() == wallet:
                nfts_in.append(rec)
            elif frm.lower() == wallet:
                nfts_out.append(rec)
    return {"sender": sender, "is_taker": is_taker, "paid_eth": round(paid, 6),
            "recv_eth": round(recv, 6), "nfts_in": nfts_in, "nfts_out": nfts_out,
            "venues": sorted(venues), "block_ts": None}


def main():
    log("=== blur_full: full on-chain Blur trade history ===")
    mn, mx = load_contract_map()
    head = int(rpc("eth_blockNumber", []), 16)
    head_ts = int(rpc("eth_getBlockByNumber", [hex(head), False])["timestamp"], 16)
    lo = block_for_ts(mn, head, head_ts)
    log(f"head block {head}; scanning blocks {lo}..{head} (~{(head-lo)//CHUNK+1} chunks/dir/wallet)")
    log(f"contract->slug map: {len(CONTRACT2SLUG)} collections")

    all_rows = []
    summary = {}
    blk_ts_cache = {}

    def blk_ts(b):
        if b not in blk_ts_cache:
            r = rpc("eth_getBlockByNumber", [hex(b), False])
            blk_ts_cache[b] = int(r["timestamp"], 16) if r else None
        return blk_ts_cache[b]

    for w in WALLETS:
        wl = w.lower()
        log(f"\n[{w[:10]}] scanning BETH settlements ...")
        txs = scan_beth(wl, lo, head)
        log(f"  {len(txs)} BETH-settlement txs found; enriching ...")
        buys = sells = 0
        taker = maker = 0
        vol_buy = vol_sell = 0.0
        colls = defaultdict(int)
        for i, (h, meta) in enumerate(sorted(txs.items(), key=lambda x: x[1]["block"])):
            en = enrich(h, wl)
            if not en:
                continue
            ts = blk_ts(meta["block"])
            # direction from NFT flow (authoritative), BETH as tiebreak
            if en["nfts_in"] and not en["nfts_out"]:
                direction = "buy"
            elif en["nfts_out"] and not en["nfts_in"]:
                direction = "sell"
            elif meta["beth_out"] > meta["beth_in"]:
                direction = "buy"
            else:
                direction = "sell"
            nfts = en["nfts_in"] if direction == "buy" else en["nfts_out"]
            price = en["paid_eth"] if direction == "buy" else en["recv_eth"]
            for nft in (nfts or [{"contract": None, "slug": None, "token": None}]):
                row = {"wallet": wl, "tx": h, "block": meta["block"], "ts": ts,
                       "direction": direction,
                       "side": "taker" if en["is_taker"] else "maker",
                       "price_eth": round(price / max(len(nfts), 1), 6) if nfts else price,
                       "collection": nft["slug"], "contract": nft["contract"],
                       "token": nft["token"], "venues": en["venues"]}
                all_rows.append(row)
                if nft["slug"]:
                    colls[nft["slug"]] += 1
            if direction == "buy":
                buys += 1
                vol_buy += price
            else:
                sells += 1
                vol_sell += price
            if en["is_taker"]:
                taker += 1
            else:
                maker += 1
            if (i + 1) % 50 == 0:
                log(f"    ...{i+1}/{len(txs)} enriched")
            time.sleep(0.05)
        summary[w] = {"settlements": len(txs), "buys": buys, "sells": sells,
                      "taker_side": taker, "maker_side": maker,
                      "buy_volume_eth": round(vol_buy, 3), "sell_volume_eth": round(vol_sell, 3),
                      "top_collections": dict(sorted(colls.items(), key=lambda x: -x[1])[:10])}
        log(f"  [{w[:10]}] buys {buys} sells {sells}; taker {taker} maker {maker}; "
            f"vol buy {vol_buy:.1f} / sell {vol_sell:.1f} ETH; colls {dict(list(summary[w]['top_collections'].items())[:5])}")

    with open(os.path.join(OUT, "trades_full.jsonl"), "w") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")
    json.dump({"wallets": summary, "total_rows": len(all_rows),
               "method": "BETH Transfer scan + tx enrichment; taker = tx.from == wallet"},
              open(os.path.join(OUT, "trades_full_summary.json"), "w"), indent=1)
    log(f"\nwrote {len(all_rows)} trade rows to trades_full.jsonl")
    log("=== done ===")


if __name__ == "__main__":
    main()
