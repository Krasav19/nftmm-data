#!/usr/bin/env python3
"""blur_backfill.py — on-chain backfill of missing acquisition prices.

The Blur API is not yet granted, so we reconstruct the entry leg on-chain.

Mechanism (verified): OpenSea's events API reports Blur / non-OpenSea fills only
as a price-less `transfer`, not a priced `sale`. So the 132 "sells without known
entry" in export/pnl actually DO have an inbound transfer in our own dataset —
we just lacked the price. For each such token we:
  1. find the inbound transfer (to one of our wallets) in data/events_*.jsonl,
  2. fetch that transaction receipt via a public Ethereum RPC,
  3. sum ETH + WETH + BETH (Blur Pool) paid BY our wallet in that tx = entry price,
  4. flag whether a Blur contract / Blur-Pool settlement was involved.

This closes the Blur entry leg for the unmatched sells without needing the Blur
API. Remaining gaps are logged explicitly.

Outputs:
  analysis/blur/blur_entries.json      recovered entries per token
  analysis/blur/blur_backfill.log      run log (also logs/blur_backfill.log)
"""
import glob
import json
import os
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "analysis", "blur")
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)

RPCS = ["https://ethereum-rpc.publicnode.com", "https://rpc.mevblocker.io"]
WALLETS = {
    "0x028296d8bf1995549d5b9446622cf565bbd0a26e",
    "0x400f2bd92098c386cea677d6e7f832eb25c6e3cf",
    "0x8e8d6246c45d0e7f68172e85573546d90fc2e062",
}
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
BLUR_POOL = "0x0000000000a39bb272e79075ade125fd351887ac"
ETH_TOKENS = {WETH, BLUR_POOL}
# known Blur execution / exchange contracts (lower-case). Used only to LABEL the
# venue; price recovery does not depend on this list being exhaustive.
BLUR_CONTRACTS = {
    "0x000000000000ad05ccc4f10045630fb830b95127": "BlurExchange",
    "0xb2ecfe4e4d61f8790bbb9de2d1259b9e2410cea5": "BlurExchangeV2",
    "0x39da41747a83aee658334415666f3ef92dd0d541": "Blend",
    "0x983e96c26782a8db500a6fb8ab47a52e1b44862d": "BlurExchangeProxy",
    BLUR_POOL: "BlurPool",
}

_logf = open(os.path.join(HERE, "logs", "blur_backfill.log"), "w")
_rpc_i = 0


def log(*a):
    m = " ".join(str(x) for x in a)
    print(m, flush=True)
    _logf.write(m + "\n")
    _logf.flush()


def rpc(method, params):
    global _rpc_i
    for attempt in range(6):
        url = RPCS[_rpc_i % len(RPCS)]
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method,
                                         "params": params}, timeout=25)
            j = r.json()
            if "result" in j:
                return j["result"]
            if j.get("error", {}).get("code") == 429 or "limit" in str(j.get("error", "")).lower():
                _rpc_i += 1
                time.sleep(1.5)
                continue
            return None
        except Exception:
            _rpc_i += 1
            time.sleep(1.0)
    return None


def build_token_index():
    """collection -> contract, and (collection,token) -> {inbound:[transfers], sells:[...]}"""
    coll2contract = {}
    tok = {}
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
            coll, ident = n.get("collection"), n.get("identifier")
            if coll and n.get("contract"):
                coll2contract.setdefault(coll, n["contract"])
            if not coll or ident is None:
                continue
            key = (coll, str(ident))
            d = tok.setdefault(key, {"inbound": [], "sells": []})
            et = e.get("event_type")
            if et == "transfer" and (e.get("to_address") or "").lower() in WALLETS:
                d["inbound"].append({"tx": e.get("transaction"), "ts": e.get("event_timestamp"),
                                     "to": (e.get("to_address") or "").lower(),
                                     "from": (e.get("from_address") or "").lower()})
            if et == "sale" and (e.get("seller") or "").lower() in WALLETS:
                d["sells"].append({"ts": e.get("event_timestamp"),
                                   "seller": (e.get("seller") or "").lower()})
    return coll2contract, tok


def recover_price(tx, wallet):
    """Sum ETH+WETH+BETH paid by `wallet` in tx; return (price_eth, venue, detail)."""
    txd = rpc("eth_getTransactionByHash", [tx])
    rcpt = rpc("eth_getTransactionReceipt", [tx])
    if not txd or not rcpt:
        return None, None, "rpc_fail"
    paid = 0.0
    # native ETH sent by the wallet as tx.from
    if (txd.get("from") or "").lower() == wallet and txd.get("value"):
        paid += int(txd["value"], 16) / 1e18
    venues = set()
    for lg in rcpt.get("logs", []):
        a = lg["address"].lower()
        if a in BLUR_CONTRACTS:
            venues.add(BLUR_CONTRACTS[a])
        if a in ETH_TOKENS and lg["topics"] and lg["topics"][0] == TRANSFER and len(lg["topics"]) >= 3:
            frm = "0x" + lg["topics"][1][-40:]
            if frm.lower() == wallet:
                try:
                    paid += int(lg["data"], 16) / 1e18
                except (ValueError, TypeError):
                    pass
    # contract the tx was sent to (router) — label heuristically
    to_c = (txd.get("to") or "").lower()
    venue = "+".join(sorted(venues)) if venues else ("blur-router?" if paid and to_c not in ETH_TOKENS else "unknown")
    return round(paid, 6), venue, to_c


def main():
    log("=== blur_backfill: on-chain entry recovery ===")
    bn = rpc("eth_blockNumber", [])
    log(f"RPC ok, head block {int(bn, 16) if bn else '?'}")

    raw = json.load(open("/tmp/pnl_raw.json")) if os.path.exists("/tmp/pnl_raw.json") \
        else json.load(open(os.path.join(HERE, "export", "pnl.json")))
    # the unmatched sells live in pnl_raw (raw) or we derive from export
    sne = raw.get("sells_no_entry") if isinstance(raw, dict) and "sells_no_entry" in raw else None
    if sne is None:
        # fall back: rebuild from pnl.json structure is not granular; require pnl_raw
        log("ERROR: need /tmp/pnl_raw.json with sells_no_entry; rerun the P&L matcher first.")
        return
    log(f"unmatched sells to backfill: {len(sne)}")

    coll2contract, tok = build_token_index()
    recovered, still_missing = [], []
    cache = {}
    for i, s in enumerate(sne):
        coll, ident = s["collection"], str(s["token"])
        key = (coll, ident)
        d = tok.get(key, {})
        inbound = d.get("inbound", [])
        sell_ts = s.get("sell_ts")
        # pick the latest inbound transfer strictly before the sell
        cand = [t for t in inbound if t.get("tx") and (sell_ts is None or (t["ts"] or 0) <= sell_ts)]
        cand.sort(key=lambda t: t["ts"] or 0)
        if not cand:
            still_missing.append({**key_to_d(key), "sell_eth": s.get("sell"),
                                  "reason": "no inbound transfer in dataset"})
            continue
        entry = cand[-1]
        ck = (entry["tx"], entry["to"])
        if ck in cache:
            price, venue, router = cache[ck]
        else:
            price, venue, router = recover_price(entry["tx"], entry["to"])
            cache[ck] = (price, venue, router)
            time.sleep(0.15)
        rec = {"collection": coll, "token": ident, "buyer_wallet": entry["to"],
               "entry_tx": entry["tx"], "entry_ts": entry["ts"], "entry_eth": price,
               "venue": venue, "sell_eth": s.get("sell"), "sell_ts": sell_ts}
        if price and price > 0:
            rec["roundtrip_pnl"] = round((s.get("sell") or 0) - price, 6)
            recovered.append(rec)
        else:
            rec["reason"] = "price not recoverable from tx (0 ETH/WETH/BETH paid)"
            still_missing.append(rec)
        if (i + 1) % 20 == 0:
            log(f"  ...{i+1}/{len(sne)} processed, recovered {len(recovered)}")

    out = {
        "method": "inbound-transfer tx receipt; sum ETH+WETH+BETH paid by wallet",
        "unmatched_sells": len(sne),
        "entries_recovered": len(recovered),
        "still_missing": len(still_missing),
        "recovered": recovered,
        "missing": still_missing,
    }
    json.dump(out, open(os.path.join(OUT, "blur_entries.json"), "w"), indent=1)
    log(f"recovered {len(recovered)} entries; still missing {len(still_missing)}")
    # venue breakdown
    from collections import Counter
    vc = Counter(r["venue"] for r in recovered)
    log(f"venue breakdown: {dict(vc)}")
    tot_pnl = sum(r["roundtrip_pnl"] for r in recovered)
    log(f"recovered round-trip P&L (gross): {tot_pnl:+.3f} ETH")
    log("=== done ===")


def key_to_d(key):
    return {"collection": key[0], "token": key[1]}


if __name__ == "__main__":
    main()
