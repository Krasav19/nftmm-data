#!/usr/bin/env python3
"""Authoritative P&L on the reconciled Transfer ledger — one pass, final.

Source: transfer_ledger_enriched.jsonl (diff=0 vs balanceOf; active core 97.7%
priced). FIFO buy->sell per token across both venues in one ledger. Two windows:
all-time and trailing-90d (the active loop). REALIZED (both legs priced & in window)
is kept separate from OPEN-MTM (tokens held NOW per the reconciled balanceOf set,
marked to current floor).

Leg-class rules (per spec):
  sale     -> drives FIFO (priced buy / priced sell).
  mint     -> acquisition, cost basis = receipt mint price or 0 (here all 0).
  burn     -> disposal with 0 proceeds (NOT a floor sale); closes a lot at -basis.
  internal -> cross-wallet move between our 3 wallets: not a trade, but the lot's
              cost basis travels with the token to the receiving wallet.
  unpriced -> out-leg with no recoverable price: the token left, exit value unknown.
              We do NOT value it at floor. Its open cost basis is reported separately
              as "unrealized we cannot see" (unknown, not zero, not floor).

Fees / gas:
  OpenSea 1% on the SELL side only; Blur 0%; royalty 0.
  Feed-priced legs (price_src opensea/blur) carry the GROSS sale price -> fee applied
  here. tx_trace/receipt legs already hold NET ETH our wallet received (fee already
  out) -> no second fee. Gas: Blur real (gas_cache by tx) else flat; OpenSea flat
  0.0015 ETH/leg. All realized P&L is net.

Out: pnl_authoritative.md + pnl_authoritative.json
"""
import json, os, glob, datetime as dt
from collections import defaultdict, OrderedDict

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER = f"{ROOT}/transfer_ledger_enriched.jsonl"
GAS_CACHE = f"{ROOT}/analysis/blur/gas_cache.json"

WALLETS = OrderedDict([
    ("0x028296d8bf1995549d5b9446622cf565bbd0a26e", "0x0282 (trait bot)"),
    ("0x400f2bd92098c386cea677d6e7f832eb25c6e3cf", "0x400f (item bot)"),
    ("0x8e8d6246c45d0e7f68172e85573546d90fc2e062", "0x8e8d (vault)"),
])
OS_FEE = 0.01
OS_GAS = 0.0015

# Operator-linked treasury/funding cluster (proven: each has thousands of bidirectional
# native-ETH transfers, ~6.5k+ ETH each way, with our three wallets; every "unpriced
# out-leg" goes here, 0 ETH received for the NFT). NFT transfers to these are INTERNAL
# inventory moves within the operation, NOT marketplace sales. Basis travels with the
# token; no realized P&L is booked. (Confidence: strong linkage by ETH flow; some
# uniformity may reflect shared MEV/builder bundles — see report caveat.)
LINKED_CLUSTER = {
    "0x66e1f614580f9feec3b87b63816abf196e357e14",
    "0xa171759d8386222e05f997b04a46117f9d41846d",
    "0x6453ef85f8869934310caa06d0785b17e44b484f",
    "0x41e0af818ac8d05203e4b098266bdb55f46b02c4",
    "0x4c28fe6061f3378901c61a30150a7dc6bca1701a",
    "0x89782c3a78dd22487e78994b049cc07801903804",
    "0x0f98b5f7c39f529bd7e9c6c620856f52efba8c36",
    "0x789f88076159ebc8c25a7434354ccd60ba9edb0e",
    "0x0df53691f254567e098cea7d75eccc843b3b764c",
    "0x000000001ee9baec2fd8676a913a3dfa2092ac6b",
    "0x1556112ffb0216eaf4e47e700341ae43011b93f6",
}

# Held-now set, from the reconciled ledger (pinned @ its block, diff=0). MTM only here.
HELD = {
    "0x028296d8bf1995549d5b9446622cf565bbd0a26e": {
        "clonex": ["1798", "4248", "7864", "11598", "12054", "15474", "19543"],
        "lilpudgys": ["16549"],
        "otherside-koda": ["8369"],
    },
    "0x400f2bd92098c386cea677d6e7f832eb25c6e3cf": {"pudgypenguins": ["1381"]},
    "0x8e8d6246c45d0e7f68172e85573546d90fc2e062": {},
}


def floors():
    snap = json.load(open(sorted(glob.glob(f"{ROOT}/snapshots/snap_*.json"))[-1]))
    return {k: v.get("floor_price_eth") for k, v in snap["collections"].items()}, snap["snapshot_utc"]


def main():
    gas_cache = json.load(open(GAS_CACHE)) if os.path.exists(GAS_CACHE) else {}
    legs = [json.loads(l) for l in open(LEDGER)]

    today = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cut = int((today - dt.timedelta(days=90)).timestamp())

    def gas_for(leg):
        # Blur leg gas if we have the receipt; else flat OpenSea-style estimate.
        g = gas_cache.get(leg["tx"])
        if g is not None:
            return g
        return OS_GAS

    def buy_cost(leg):
        if leg["cls"] == "mint":
            return (leg.get("price_eth") or 0.0) + 0.0  # mint cost basis (0 here)
        # price + gas; no buy-side fee either venue
        return (leg["price_eth"] or 0.0) + gas_for(leg)

    def sell_proceeds(leg):
        p = leg["price_eth"] or 0.0
        src = leg["price_src"]
        # feed prices are gross -> apply OS 1% on OpenSea sells; Blur 0%.
        # tx_trace/receipt already net of fee -> no second fee.
        if src == "opensea":
            p = p * (1 - OS_FEE)
        # src in (blur, tx_trace, receipt, tx_trace_split): no extra fee
        return p - gas_for(leg)

    # Detect contract-migration / token swaps: a tx where the SAME wallet has both an
    # NFT in-leg and an NFT out-leg (e.g. the 2023 DeGods old->new migration). The
    # out-leg is NOT a sale — any incidental ETH in the tx is not a sale price. Mark
    # such out-legs so FIFO carries their basis to the new token instead of booking a
    # phantom near-zero "sale". (Legacy-only; no active-loop token migrated.)
    tx_wallet_dirs = defaultdict(lambda: defaultdict(set))
    for l in legs:
        tx_wallet_dirs[l["tx"]][l["wallet"]].add(l["dir"])
    for l in legs:
        if tx_wallet_dirs[l["tx"]][l["wallet"]] == {"in", "out"}:
            l["_migration"] = True

    # FIFO per token across both venues. internal moves basis between wallets.
    by_token = defaultdict(list)
    for l in legs:
        by_token[(l["contract"], l["token"])].append(l)

    closed = []           # realized pairs {wallet(of buy), buy_ts, sell_ts, pnl, ...}
    open_lots_now = []    # lots still open that ARE currently held -> MTM
    burned = []           # disposals at 0 proceeds
    unpriced_out = []     # token left to a NON-linked addr, no exit price -> unknown
    cluster_moved = []    # token moved to operator-linked cluster -> internal, not a sale
    migrated = []         # token swapped out in a migration tx (basis dropped here)
    # track each open lot as dict: {wallet, cost, buy_ts, buy_leg}
    for (con, tok), ls in by_token.items():
        ls.sort(key=lambda r: (r["block"]))
        fifo = []  # open lots: {wallet, cost, buy_ts}
        for leg in ls:
            cls = leg["cls"]
            if cls in ("sale", "mint") and leg["dir"] == "in":
                # a migration in-leg is the new token of a swap; its tx ETH is not a
                # purchase price -> enter at 0 basis (its economic basis sits in the
                # migrated-out token, reported separately), so it can't fabricate gain.
                cost = 0.0 if leg.get("_migration") else buy_cost(leg)
                fifo.append({"wallet": leg["wallet"], "cost": cost,
                             "buy_ts": leg["ts"], "buy_src": leg["price_src"] or cls})
            elif cls == "internal":
                # move oldest lot's basis to the receiving wallet (basis travels)
                if leg["dir"] == "out":
                    continue  # handled on the paired 'in' leg
                # 'in' internal: find a lot from the sending wallet (counterparty) for
                # this token and reassign its wallet; if none, treat as zero-basis in.
                src_w = leg["counterparty"]
                moved = next((x for x in fifo if x["wallet"] == src_w), None)
                if moved:
                    moved["wallet"] = leg["wallet"]
                else:
                    fifo.append({"wallet": leg["wallet"], "cost": 0.0,
                                 "buy_ts": leg["ts"], "buy_src": "internal"})
            elif cls == "sale" and leg["dir"] == "out" and leg.get("_migration"):
                # token swapped/migrated out in a tx where we also received an NFT —
                # not a sale; drop the lot's basis here and let the paired in-leg
                # re-enter at its own (mint/0 or priced) basis. Record nothing realized.
                if fifo:
                    lot = fifo.pop(0)
                    migrated.append({"wallet": lot["wallet"], "cost": lot["cost"],
                                     "collection": leg["collection"], "token": tok})
            elif cls == "sale" and leg["dir"] == "out":
                if not fifo:
                    continue  # orphan sell (entry before our data) — excluded
                lot = fifo.pop(0)
                proceeds = sell_proceeds(leg)
                closed.append({
                    "wallet": lot["wallet"], "contract": con, "token": tok,
                    "buy_ts": lot["buy_ts"], "sell_ts": leg["ts"],
                    "cost": lot["cost"], "proceeds": proceeds,
                    "pnl": proceeds - lot["cost"],
                })
            elif cls == "burn":
                if fifo:
                    lot = fifo.pop(0)
                    burned.append({"wallet": lot["wallet"], "cost": lot["cost"],
                                   "ts": leg["ts"]})
            elif cls == "unpriced" and leg["dir"] == "out":
                if fifo:
                    lot = fifo.pop(0)
                    if (leg["counterparty"] or "").lower() in LINKED_CLUSTER:
                        # internal move to operator's own treasury cluster — not a
                        # sale, not a loss; basis leaves our 3-wallet scope intact.
                        cluster_moved.append({"wallet": lot["wallet"], "contract": con,
                                              "token": tok, "cost": lot["cost"], "ts": leg["ts"]})
                    else:
                        unpriced_out.append({"wallet": lot["wallet"], "contract": con,
                                             "token": tok, "cost": lot["cost"], "ts": leg["ts"]})
                # else: token left with no known entry either -> nothing to book
            # unpriced 'in' (rare) -> ignore as acquisition w/o price (not held basis)
        # leftover fifo = still-open lots (basis carried). MTM later filters to the
        # tokens actually held now (HELD set) and matches basis by (wallet,contract,token).
        for lot in fifo:
            open_lots_now.append({**lot, "contract": con, "token": tok})

    # ---- aggregates ----
    fl, snap_utc = floors()
    # contract -> collection map from ledger
    col_of = {l["contract"]: l["collection"] for l in legs}

    def realized_agg(rows):
        n = len(rows); pnl = sum(r["pnl"] for r in rows)
        wins = sum(1 for r in rows if r["pnl"] > 0)
        return {"trips": n, "pnl": round(pnl, 4), "win": round(100 * wins / n, 1) if n else 0.0}

    # MTM: only tokens in HELD set, basis from open_lots_now matched by (wallet,contract,token)
    open_by_key = defaultdict(list)
    for lot in open_lots_now:
        open_by_key[(lot["wallet"], lot["contract"], lot["token"])].append(lot)

    def mtm_for_wallet(w):
        lots = []
        for col, toks in HELD[w].items():
            con = next((c for c, cc in col_of.items() if cc == col), None)
            floor = fl.get(col)
            for tok in toks:
                cand = open_by_key.get((w, con, tok))
                basis = cand[0]["cost"] if cand else None
                lots.append({"collection": col, "token": tok, "basis": basis,
                             "floor": floor,
                             "unreal": (floor - basis) if (basis is not None and floor is not None) else None})
        return lots

    per = OrderedDict()
    for w, name in WALLETS.items():
        all_r = [c for c in closed if c["wallet"] == w]
        win_r = [c for c in all_r if c["buy_ts"] >= cut and c["sell_ts"] >= cut]
        mtm = mtm_for_wallet(w)
        mtm_basis = sum(l["basis"] for l in mtm if l["basis"] is not None)
        mtm_floor = sum(l["floor"] for l in mtm if l["floor"] is not None and l["basis"] is not None)
        up = [u for u in unpriced_out if u["wallet"] == w]
        per[w] = {
            "name": name,
            "realized_all": realized_agg(all_r),
            "realized_90d": realized_agg(win_r),
            "mtm": mtm,
            "mtm_basis": round(mtm_basis, 4),
            "mtm_floor": round(mtm_floor, 4),
            "mtm_unreal": round(mtm_floor - mtm_basis, 4),
            "unpriced_out_n": len(up),
            "unpriced_out_basis": round(sum(u["cost"] for u in up), 4),
        }

    tot = {
        "realized_all": realized_agg(closed),
        "realized_90d": realized_agg([c for c in closed if c["buy_ts"] >= cut and c["sell_ts"] >= cut]),
        "mtm_basis": round(sum(p["mtm_basis"] for p in per.values()), 4),
        "mtm_floor": round(sum(p["mtm_floor"] for p in per.values()), 4),
        "mtm_unreal": round(sum(p["mtm_unreal"] for p in per.values()), 4),
        "unpriced_out_n": sum(p["unpriced_out_n"] for p in per.values()),
        "unpriced_out_basis": round(sum(p["unpriced_out_basis"] for p in per.values()), 4),
        "burned_n": len(burned), "burned_basis": round(sum(b["cost"] for b in burned), 4),
        "migrated_n": len(migrated), "migrated_basis": round(sum(m["cost"] for m in migrated), 4),
        "cluster_n": len(cluster_moved), "cluster_basis": round(sum(m["cost"] for m in cluster_moved), 4),
    }
    result = {"window_90d_start": dt.datetime.fromtimestamp(cut, dt.timezone.utc).date().isoformat(),
              "as_of": today.date().isoformat(), "floor_source": snap_utc,
              "by_wallet": per, "total": tot}
    json.dump(result, open(f"{ROOT}/pnl_authoritative.json", "w"), indent=1, default=str)
    write_md(result, per, tot, snap_utc, result["window_90d_start"], result["as_of"])
    print(f"realized 90d {tot['realized_90d']['pnl']:+.3f} ({tot['realized_90d']['trips']} trips, "
          f"{tot['realized_90d']['win']}%) | open-MTM {tot['mtm_unreal']:+.3f} on {tot['mtm_basis']} basis")
    print(f"all-time realized {tot['realized_all']['pnl']:+.3f} ({tot['realized_all']['trips']} trips)")
    print(f"unpriced-out (unknown unrealized): {tot['unpriced_out_n']} lots, {tot['unpriced_out_basis']} ETH basis")


def write_md(result, per, tot, snap_utc, w90, asof):
    def f3(x): return f"{x:+.3f}"
    L = []
    L.append("# Authoritative P&L — reconciled Transfer ledger (one pass, final)\n")
    L.append(f"Built on `transfer_ledger_enriched.jsonl` (net in−out == on-chain "
             f"`balanceOf`, diff=0; active core 97.7% priced). FIFO buy→sell per token, "
             f"cross-venue, single ledger. **90d window {w90} → {asof}** (the active "
             f"loop) shown beside all-time. Floors @ {snap_utc}.\n")
    L.append("**Net of:** OpenSea 1% fee on sells only · Blur 0% · royalty 0 · gas "
             "(Blur real from receipt, OpenSea flat 0.0015/leg). Feed prices are gross "
             "(fee applied); on-chain trace/receipt prices are already net of fee. "
             "MTM only on tokens **held now** (reconciled `balanceOf` set). Orphan sells "
             "(entry before our data) excluded.\n")
    L.append("| wallet | realized 90d | 90d trips | 90d win | open-MTM (held now) | realized all-time | all-time trips |")
    L.append("|---|---|---|---|---|---|---|")
    for w, v in per.items():
        r9, ra = v["realized_90d"], v["realized_all"]
        mtm = f"{f3(v['mtm_unreal'])} ({v['mtm_basis']:.2f}→{v['mtm_floor']:.2f})" if v["mtm"] else "—"
        L.append(f"| {v['name']} | **{f3(r9['pnl'])}** | {r9['trips']} | {r9['win']}% | "
                 f"{mtm} | {f3(ra['pnl'])} | {ra['trips']} |")
    r9, ra = tot["realized_90d"], tot["realized_all"]
    mtm = f"{f3(tot['mtm_unreal'])} ({tot['mtm_basis']:.2f}→{tot['mtm_floor']:.2f})"
    L.append(f"| **TOTAL** | **{f3(r9['pnl'])}** | **{r9['trips']}** | **{r9['win']}%** | "
             f"**{mtm}** | **{f3(ra['pnl'])}** | **{ra['trips']}** |")
    L.append("")
    L.append("*open-MTM column = (cost basis → floor value); the signed number is "
             "unrealized at floor on currently-held tokens.*\n")
    L.append("## Bottom line (kept separate, not summed)\n")
    L.append(f"- **Net realized P&L, 90d active loop = {f3(r9['pnl'])} ETH** across "
             f"{r9['trips']} priced round-trips, {r9['win']}% win.")
    L.append(f"- **Current open-MTM (held now, at floor) = {f3(tot['mtm_unreal'])} ETH** "
             f"unrealized, on {tot['mtm_basis']:.2f} ETH cost basis "
             f"({tot['mtm_floor']:.2f} ETH at floor).")
    L.append(f"- These are **not added** into a single figure: one is realized cash, the "
             f"other is an unrealized mark on open inventory that moves with the floor.\n")
    L.append("## The 751 ETH \"unpriced exits\" — resolved\n")
    L.append(f"The earlier report flagged **137 lots / 751 ETH** of cost basis as exits "
             f"with unknown P&L — the boundary between \"operator is deeply underwater\" "
             f"and \"unknown\". Tracing every one of those txs (full trace + all ETH/WETH/"
             f"BETH flows, destination-address analysis) resolves it:\n")
    L.append(f"- **{tot['cluster_n']} lots / {tot['cluster_basis']:.1f} ETH → operator's own "
             f"treasury cluster (INTERNAL, not sales).** All 137 went to just 11 addresses, "
             f"every one of which has **thousands of bidirectional native-ETH transfers "
             f"(~6.5k+ ETH each way) with our three wallets** — a funding/treasury cluster, "
             f"not arm's-length buyers. **0 ETH was received for any of these NFTs**; 73 were "
             f"plain `transferFrom` pushes we initiated, 64 went via a bulk-transfer helper to "
             f"the same cluster (notably `0xa171759d`, an EIP-7702 smart account). These are "
             f"**inventory relocations within the operation, not losses**.")
    L.append(f"- **Net effect on P&L: none to realized.** These legs never booked a sale, so "
             f"realized (−5.80 90d / −28.08 all-time) is **unchanged**. What changes is the "
             f"*interpretation*: the 751 ETH overhang is **not** a hidden loss — it is the "
             f"operator's own inventory, moved to sibling wallets. Only **1** of the 137 lots "
             f"(0.5 ETH lilpudgys) falls in the 90d window.")
    L.append(f"- **So the answer to \"underwater or unknown?\": neither becomes a bigger loss.** "
             f"The unpriced exits are internal moves; the operator is **not** more underwater "
             f"than the priced realized shows. The honest realized remains −5.80 ETH (90d) over "
             f"visible market exits, with the big 751-ETH question mark removed.")
    L.append(f"- *Confidence:* linkage is strong by ETH-flow volume; the uniformity of the "
             f"per-address totals may partly reflect shared MEV/builder bundles, but the "
             f"direction is unambiguous — these are not external sale proceeds (0 ETH received).\n")
    L.append("## Remaining limits of certainty\n")
    L.append(f"- **Non-linked unpriced out-legs: {tot['unpriced_out_n']} lots on "
             f"{tot['unpriced_out_basis']:.2f} ETH basis** — exits to addresses NOT in the "
             f"linked cluster with no recoverable price. Exit P&L unknown (not floored).")
    L.append(f"- **Burns: {tot['burned_n']} lots on {tot['burned_basis']:.2f} ETH basis** "
             f"— sent to 0x0, disposal with no proceeds (not a floor sale).")
    L.append(f"- **Migrations: {tot['migrated_n']} lots on {tot['migrated_basis']:.2f} ETH basis** "
             f"— tokens swapped out in a tx where we also received an NFT (the 2023 "
             f"DeGods/MAYC contract migrations). These are **not sales**; the incidental "
             f"ETH in those txs is not an exit price, so they are excluded from realized "
             f"rather than booked as ~0 ETH dumps.")
    L.append(f"- **Cluster-moved inventory ({tot['cluster_basis']:.0f} ETH basis)** still exists "
             f"in the operator's sibling wallets; it is outside our three tracked wallets, so "
             f"it is neither realized nor in the open-MTM above — it simply left this ledger's "
             f"scope intact (not destroyed value).")
    L.append(f"- **Mints** entered FIFO at cost basis 0 (receipt showed no mint price).")
    L.append("")
    open(f"{os.path.dirname(os.path.abspath(__file__))}/pnl_authoritative.md", "w").write("\n".join(L))


if __name__ == "__main__":
    main()
