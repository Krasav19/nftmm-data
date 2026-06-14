#!/usr/bin/env python3
"""Price-enrich the authoritative Transfer ledger and classify every leg.

The ledger (transfer_ledger.jsonl) is the source of legs. Marketplace feeds and
tx receipts are used ONLY to attach a price and a class to each leg:

  - internal : counterparty is one of our own three wallets -> NOT a trade.
  - mint/claim : from == 0x0 (or to == 0x0 burn), or zero on-chain value -> cost
                 basis 0 (acquisition without market price), tracked separately.
  - sale : a price is found from Blur trades (trades_full.jsonl), OpenSea events
           (events_hist_*.json), or the tx's on-chain ETH/WETH/BETH value moved
           to/from our wallet in the same tx -> eligible for P&L.
  - unpriced : a real external transfer with no recoverable price (OTC, unindexed
               venue) -> kept in ledger, flagged, NOT counted in P&L.

Outputs:
  transfer_ledger_enriched.jsonl  every leg + {class, price_eth, price_src}
  (price-coverage stats printed; consumed by ledger_reconciliation.md)
"""
import json, os, glob
from collections import defaultdict
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER = f"{ROOT}/transfer_ledger.jsonl"
OUT = f"{ROOT}/transfer_ledger_enriched.jsonl"
RECEIPT_CACHE = f"{ROOT}/analysis/receipt_value_cache.json"

WSET = {"0x028296d8bf1995549d5b9446622cf565bbd0a26e",
        "0x400f2bd92098c386cea677d6e7f832eb25c6e3cf",
        "0x8e8d6246c45d0e7f68172e85573546d90fc2e062"}
ZERO = "0x0000000000000000000000000000000000000000"

WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
BETH = "0x0000000000a39bb272e79075ade125fd351887ac"  # Blur Pool (BETH)
T_ERC20 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"  # Transfer(addr,addr,uint256)

RPCS = ["https://ethereum-rpc.publicnode.com", "https://rpc.mevblocker.io",
        "https://eth.llamarpc.com", "https://eth.drpc.org"]
_i = 0


def rpc(method, params):
    global _i
    for _ in range(len(RPCS) * 3):
        url = RPCS[_i % len(RPCS)]; _i += 1
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1,
                              "method": method, "params": params}, timeout=30)
            if r.status_code != 200:
                continue
            j = r.json()
            if "result" in j:
                return j["result"]
        except Exception:
            continue
    return None


def load_market_prices():
    """(wallet, contract, token, side) -> price_eth, keyed loosely for matching."""
    px = {}
    # Blur on-chain (authoritative price incl ETH+WETH+BETH)
    for b in (json.loads(l) for l in open(f"{ROOT}/analysis/blur/trades_full.jsonl")):
        side = "in" if b["direction"] == "buy" else "out"
        px[(b["wallet"].lower(), b["contract"].lower(), str(b["token"]), side)] = (
            b["price_eth"], "blur")
        # also key by tx for direct lookup
        px[("tx", b["tx"].lower(), str(b["token"]))] = (b["price_eth"], "blur")
    # OpenSea events
    for f in glob.glob(f"{ROOT}/export/events_hist_*.json"):
        for e in json.load(open(f)):
            if e.get("event_type") != "sale" or not e.get("price_eth"):
                continue
            crit = e.get("criteria") or {}
            con = (crit.get("contract") or "").lower()
            tok = str(crit.get("token_ids") or "")
            if not con or not tok or "," in tok:
                continue
            s = (e.get("seller") or "").lower(); bu = (e.get("buyer") or "").lower()
            if s in WSET:
                px.setdefault((s, con, tok, "out"), (e["price_eth"], "opensea"))
            if bu in WSET:
                px.setdefault((bu, con, tok, "in"), (e["price_eth"], "opensea"))
    return px


def load_receipt_cache():
    try:
        return json.load(open(RECEIPT_CACHE))
    except FileNotFoundError:
        return {}


def tx_value_for_wallet(tx, wallet, rc_cache):
    """ETH+WETH+BETH that NET moved to/from `wallet` in tx — used as a price when
    no marketplace record exists. Returns (eth_value, 'receipt') or (None, None)."""
    key = f"{tx}|{wallet}"
    if key in rc_cache:
        v = rc_cache[key]
        return (v, "receipt") if v else (None, None)
    rcpt = rpc("eth_getTransactionReceipt", [tx])
    txd = rpc("eth_getTransactionByHash", [tx])
    if not rcpt:
        rc_cache[key] = None
        return None, None
    wt = wallet[2:].lower().rjust(64, "0")
    eth_in = eth_out = 0.0
    # native ETH: value field, direction by from/to
    if txd:
        val = int(txd.get("value", "0x0"), 16) / 1e18
        if val:
            if (txd.get("to") or "").lower() == wallet:
                eth_in += val
            if (txd.get("from") or "").lower() == wallet:
                eth_out += val
    # WETH/BETH ERC-20 Transfer logs touching wallet
    for lg in rcpt.get("logs", []):
        if (lg["address"].lower() in (WETH, BETH)
                and len(lg["topics"]) == 3 and lg["topics"][0] == T_ERC20):
            amt = int(lg["data"], 16) / 1e18
            frm = lg["topics"][1][-64:]; to = lg["topics"][2][-64:]
            if to == wt:
                eth_in += amt
            if frm == wt:
                eth_out += amt
    # the price of the NFT leg ≈ the larger directional flow for the wallet
    v = round(max(eth_in, eth_out), 6)
    rc_cache[key] = v if v > 0 else None
    return (v, "receipt") if v > 0 else (None, None)


def main():
    legs = [json.loads(l) for l in open(LEDGER)]
    px = load_market_prices()
    rc_cache = load_receipt_cache()

    out = []
    # Only resolve receipts for legs not otherwise priced & not internal/mint, to
    # bound RPC. Internal = counterparty is ours; mint/burn = 0x0 endpoint.
    for leg in legs:
        w = leg["wallet"]; cp = (leg["counterparty"] or "").lower()
        con = leg["contract"]; tok = leg["token"]; side = leg["dir"]
        cls = None; price = None; src = None

        if cp in WSET:
            cls = "internal"
        elif (side == "in" and cp == ZERO):
            cls = "mint"
        elif (side == "out" and cp == ZERO):
            cls = "burn"
        else:
            # try marketplace price
            hit = px.get((w, con, tok, side))
            if not hit:
                hit = px.get(("tx", (leg["tx"] or "").lower(), tok))
            if hit:
                price, src = hit
                cls = "sale"
        out.append({**leg, "cls": cls, "price_eth": price, "price_src": src})

    # second pass: receipt fallback for still-unclassified external legs
    need = [o for o in out if o["cls"] is None]
    print(f"resolving on-chain receipt value for {len(need)} unpriced external legs...")
    for i, o in enumerate(need):
        v, s = tx_value_for_wallet(o["tx"], o["wallet"], rc_cache)
        if v:
            o["cls"] = "sale"; o["price_eth"] = v; o["price_src"] = s
        else:
            o["cls"] = "unpriced"
        if i % 100 == 0:
            json.dump(rc_cache, open(RECEIPT_CACHE, "w"))
    json.dump(rc_cache, open(RECEIPT_CACHE, "w"))

    with open(OUT, "w") as f:
        for o in out:
            f.write(json.dumps(o) + "\n")

    # ---- stats ----
    from collections import Counter
    c = Counter(o["cls"] for o in out)
    print("\nleg classes:", dict(c))
    ext = [o for o in out if o["cls"] in ("sale", "unpriced")]
    priced = [o for o in ext if o["cls"] == "sale"]
    print(f"external (tradeable) legs: {len(ext)}  priced: {len(priced)} "
          f"({100*len(priced)/len(ext):.1f}% coverage)")
    print(f"price sources: {Counter(o['price_src'] for o in priced)}")
    print(f"\nwrote {len(out)} enriched legs -> {OUT}")


if __name__ == "__main__":
    main()
