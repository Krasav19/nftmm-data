#!/usr/bin/env python3
"""90-day active-loop P&L rebuild (cross-venue, OpenSea + on-chain Blur).

Splits the cross-venue FIFO ledger (analysis/blur/xvenue_pnl.json) into the
three components the active-strategy read needs, strictly inside a 90-day window:

  1. REALIZED 90d  — fully closed buy->sell pairs where BOTH legs land inside
     the window. This is the true number of the active loop.
  2. OPEN/MTM 90d  — lots bought inside the window, not yet sold; marked to the
     current collection floor (latest snapshot) as unrealized.
  3. ORPHAN-ENTRY closed (excluded) — closed trips whose SELL is in-window but
     whose BUY predates the window. These are a legacy tail, not the active
     loop, and are reported separately so they can be removed from the headline.

Everything older than the window (all-time -30.4 ETH, 2023 degods/bayc, legacy
inventory) is out of focus by construction.

Outputs: export/pnl_90d.json  (machine), prints a summary table.
"""
import json
import datetime as dt
from collections import defaultdict

ROOT = __file__.rsplit("/", 1)[0]
XVENUE = f"{ROOT}/analysis/blur/xvenue_pnl.json"
OUT = f"{ROOT}/export/pnl_90d.json"

WALLET_NAME = {
    "0x028296d8bf1995549d5b9446622cf565bbd0a26e": "0x0282 (trait bot)",
    "0x400f2bd92098c386cea677d6e7f832eb25c6e3cf": "0x400f (item bot)",
    "0x8e8d6246c45d0e7f68172e85573546d90fc2e062": "0x8e8d (vault)",
}


def latest_snapshot_floors():
    import glob
    snaps = sorted(glob.glob(f"{ROOT}/snapshots/snap_*.json"))
    if not snaps:
        return {}, None
    s = json.load(open(snaps[-1]))
    floors = {k: v.get("floor_price_eth") for k, v in s["collections"].items()}
    return floors, s["snapshot_utc"]


def agg(rows):
    n = len(rows)
    pnl = sum(r["pnl"] for r in rows)
    wins = sum(1 for r in rows if r["pnl"] > 0)
    return {
        "trips": n,
        "pnl": round(pnl, 3),
        "win": round(100 * wins / n, 1) if n else 0.0,
    }


def main():
    d = json.load(open(XVENUE))
    closed, opens = d["closed"], d["open_lots"]
    floors, snap_utc = latest_snapshot_floors()

    # Window: trailing 90 days from "today" (UTC midnight).
    today = dt.datetime.now(dt.timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    cut = int((today - dt.timedelta(days=90)).timestamp())

    # 1. REALIZED 90d — both legs inside window.
    realized = [c for c in closed if c["buy_ts"] >= cut and c["sell_ts"] >= cut]
    # 3. ORPHAN-ENTRY closed — sell in-window, buy before window (legacy tail).
    orphan_entry = [
        c for c in closed if c["sell_ts"] >= cut and c["buy_ts"] < cut
    ]

    # 2. OPEN/MTM 90d — lots bought inside the window, still held.
    open_90 = [o for o in opens if o["buy_ts"] >= cut]
    open_rows = []
    for o in open_90:
        f = floors.get(o["collection"])
        cost = o["buy"]
        mv = f if f is not None else 0.0
        open_rows.append(
            {
                **o,
                "floor": f,
                "mtm_value": round(mv, 4),
                "unrealized": round(mv - cost, 4),
            }
        )

    def open_agg(rows):
        cost = sum(r["buy"] for r in rows)
        mv = sum(r["mtm_value"] for r in rows)
        return {
            "lots": len(rows),
            "cost_basis": round(cost, 3),
            "floor_value": round(mv, 3),
            "unrealized": round(mv - cost, 3),
        }

    by_wallet = {}
    for w in WALLET_NAME:
        by_wallet[w] = {
            "name": WALLET_NAME[w],
            "realized_90d": agg([c for c in realized if c["wallet"] == w]),
            "open_mtm_90d": open_agg([r for r in open_rows if r["wallet"] == w]),
        }

    out = {
        "method": "cross-venue FIFO (OpenSea + on-chain Blur, deduped by tx). "
        "90d trailing window; both legs in-window for realized; "
        "lots bought in-window marked to current floor for open/MTM.",
        "window_start": dt.datetime.fromtimestamp(cut, dt.timezone.utc).date().isoformat(),
        "as_of": today.date().isoformat(),
        "floor_source": snap_utc,
        "realized_90d_total": agg(realized),
        "open_mtm_90d_total": open_agg(open_rows),
        "orphan_entry_closed_excluded": agg(orphan_entry),
        "by_wallet": by_wallet,
        "open_lots_90d": open_rows,
    }
    json.dump(out, open(OUT, "w"), indent=1)

    # ---- pretty print ----
    r = out["realized_90d_total"]
    o = out["open_mtm_90d_total"]
    oe = out["orphan_entry_closed_excluded"]
    print(f"Window: {out['window_start']} -> {out['as_of']}  (floors @ {snap_utc})\n")
    print("=== REALIZED 90d (active loop, both legs in window) ===")
    print(f"  {r['trips']} trips | {r['pnl']:+.3f} ETH | {r['win']}% win\n")
    print("=== OPEN/MTM 90d (bought in window, unsold; floor-marked) ===")
    print(
        f"  {o['lots']} lots | cost {o['cost_basis']} | floor-val {o['floor_value']} "
        f"| {o['unrealized']:+.3f} ETH unrealized\n"
    )
    print("=== ORPHAN-ENTRY closed (EXCLUDED from headline: buy pre-window) ===")
    print(f"  {oe['trips']} trips | {oe['pnl']:+.3f} ETH | {oe['win']}% win")
    print(
        f"  (realized {r['trips']} + orphan {oe['trips']} = {r['trips']+oe['trips']} trips, "
        f"{r['pnl']+oe['pnl']:+.3f} ETH = the old contaminated '-2.2 / 204-trip' figure)\n"
    )
    print("--- per wallet ---")
    for w, v in by_wallet.items():
        rr, oo = v["realized_90d"], v["open_mtm_90d"]
        print(
            f"  {v['name']:<18} realized {rr['trips']:>3} trips {rr['pnl']:+.3f} ETH "
            f"{rr['win']:>5}% | open-MTM {oo['lots']} lots {oo['unrealized']:+.3f} ETH"
        )
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
