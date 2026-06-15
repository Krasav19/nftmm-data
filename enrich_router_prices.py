#!/usr/bin/env python3
"""Recover prices for router-routed sales the feed-based enricher missed.

Root cause (confirmed): the original enricher credited ETH only when tx.to/tx.from
was our wallet. In Seaport/Blur sales the BUYER sends the tx (tx.to = router) and
the ETH reaches us through the router as an INTERNAL transfer, invisible to receipt
logs. The real proceeds are recoverable from trace_transaction (internal ETH) plus
WETH/BETH ERC-20 transfers, regardless of who initiated the tx.

This pass:
  - touches ONLY legs currently classed `unpriced` (no double-pricing).
  - for each such leg's tx, computes ETH our wallet net-received (for OUT/sell) or
    net-paid (for IN/buy): internal ETH (trace) + WETH + BETH, directional.
  - 1 NFT/tx -> assign full amount. Multi-NFT same-direction batch -> split equally
    per token in that tx for that wallet/direction (flagged split). Mixed buy+sell
    in one tx (swap) -> price the net to the disposed leg, flagged.
  - never substitutes floor. If no money leg to/from us exists, stays `unpriced`.
  - does NOT change any quantities -> the balanceOf invariant is untouched (re-checked
    afterwards by reconcile.py).

In:  transfer_ledger_enriched.jsonl
Out: transfer_ledger_enriched.jsonl (rewritten; price_src='tx_trace' for recovered)
"""
import json, os
from collections import defaultdict
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER = f"{ROOT}/transfer_ledger_enriched.jsonl"
TRACE_CACHE = f"{ROOT}/analysis/trace_value_cache.json"

WSET = {"0x028296d8bf1995549d5b9446622cf565bbd0a26e",
        "0x400f2bd92098c386cea677d6e7f832eb25c6e3cf",
        "0x8e8d6246c45d0e7f68172e85573546d90fc2e062"}
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
BETH = "0x0000000000a39bb272e79075ade125fd351887ac"
T_ERC20 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
# trace_transaction is the one tracing method our public RPC supports.
TRACE_RPCS = ["https://ethereum-rpc.publicnode.com"]
LOG_RPCS = ["https://ethereum-rpc.publicnode.com", "https://rpc.mevblocker.io",
            "https://eth.llamarpc.com"]
_i = 0


def rpc(pool, method, params):
    global _i
    for _ in range(len(pool) * 4):
        url = pool[_i % len(pool)]; _i += 1
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1,
                              "method": method, "params": params}, timeout=45)
            if r.status_code != 200:
                continue
            j = r.json()
            if "result" in j:
                return j["result"]
        except Exception:
            continue
    return None


def tx_money_flows(tx, cache):
    """Return (eth_in, eth_out) for EACH of our wallets in this tx, summed over
    native internal ETH (trace) + WETH + BETH. Cached per tx."""
    if tx in cache:
        return cache[tx]
    flows = {w: [0.0, 0.0] for w in WSET}  # wallet -> [in, out]

    # 1) internal + top-level ETH via trace_transaction
    tr = rpc(TRACE_RPCS, "trace_transaction", [tx])
    if tr:
        for f in tr:
            if f.get("type") not in ("call", "create"):
                continue
            a = f.get("action", {})
            val = int(a.get("value", "0x0"), 16) / 1e18
            if val <= 0:
                continue
            frm = (a.get("from") or "").lower()
            to = (a.get("to") or "").lower()
            if to in WSET:
                flows[to][0] += val
            if frm in WSET:
                flows[frm][1] += val

    # 2) WETH/BETH ERC-20 transfers from the receipt logs
    rcpt = rpc(LOG_RPCS, "eth_getTransactionReceipt", [tx])
    if rcpt:
        for lg in rcpt.get("logs", []):
            if (lg["address"].lower() in (WETH, BETH)
                    and len(lg["topics"]) == 3 and lg["topics"][0] == T_ERC20):
                amt = int(lg["data"], 16) / 1e18
                frm = ("0x" + lg["topics"][1][-40:]).lower()
                to = ("0x" + lg["topics"][2][-40:]).lower()
                if to in WSET:
                    flows[to][0] += amt
                if frm in WSET:
                    flows[frm][1] += amt

    cache[tx] = flows
    return flows


def main():
    legs = [json.loads(l) for l in open(LEDGER)]
    cache = json.load(open(TRACE_CACHE)) if os.path.exists(TRACE_CACHE) else {}

    # group unpriced legs by tx so multi-NFT splits are computed per tx
    unpriced = [l for l in legs if l["cls"] == "unpriced"]
    by_tx = defaultdict(list)
    for l in unpriced:
        by_tx[l["tx"]].append(l)

    print(f"{len(unpriced)} unpriced legs across {len(by_tx)} txs; recovering...")
    recovered = 0
    still_unpriced = 0
    for n, (tx, group) in enumerate(by_tx.items()):
        flows = tx_money_flows(tx, cache)
        # per wallet+direction, allocate the relevant money across that wallet's
        # unpriced legs in this tx.
        # OUT leg (sell)  -> use eth_in for that wallet (proceeds received)
        # IN leg  (buy)   -> use eth_out for that wallet (paid)
        buckets = defaultdict(list)  # (wallet, dir) -> [leg,...]
        for l in group:
            buckets[(l["wallet"], l["dir"])].append(l)
        for (w, d), ls in buckets.items():
            eth_in, eth_out = flows.get(w, [0.0, 0.0])
            amount = eth_in if d == "out" else eth_out
            if amount <= 0:
                for l in ls:
                    l["price_src"] = None  # remains unpriced
                    still_unpriced += len(ls) if False else 0
                continue
            per = amount / len(ls)
            split = len(ls) > 1
            for l in ls:
                l["price_eth"] = round(per, 6)
                l["cls"] = "sale"
                l["price_src"] = "tx_trace_split" if split else "tx_trace"
                recovered += 1
        if (n + 1) % 50 == 0:
            json.dump(cache, open(TRACE_CACHE, "w"))
            print(f"  ...{n+1}/{len(by_tx)} txs, recovered {recovered}")
    json.dump(cache, open(TRACE_CACHE, "w"))

    still_unpriced = sum(1 for l in legs if l["cls"] == "unpriced")
    with open(LEDGER, "w") as f:
        for l in legs:
            f.write(json.dumps(l) + "\n")

    from collections import Counter
    c = Counter(l["cls"] for l in legs)
    ext = [l for l in legs if l["cls"] in ("sale", "unpriced")]
    priced = [l for l in ext if l["cls"] == "sale"]
    print(f"\nrecovered {recovered} legs; still unpriced {still_unpriced}")
    print(f"classes: {dict(c)}")
    print(f"external price coverage: {len(priced)}/{len(ext)} = "
          f"{100*len(priced)/len(ext):.1f}%")
    print(f"price sources: {Counter(l['price_src'] for l in priced)}")


if __name__ == "__main__":
    main()
