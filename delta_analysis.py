#!/usr/bin/env python3
"""delta_analysis.py — delta analysis of operator offer/listing snapshots.

Tracks each order by order_hash across adjacent 15-min snapshots to measure:
  1. real bid lifetime + disappearance reason (replaced / expired / filled)
  2. top-bid retention per criterion (ignoring >2x-floor stale outliers)
  3. operator reaction lag to floor moves
  4. listing-side behaviour (re-prices, withdrawals)

Valid window: snapshots from 2026-06-10T20:30Z onward (earlier ones had broken
trait criteria). Note: the raw trait `criteria` object only exists from
2026-06-11T10:30Z; before that we infer trait-vs-item from the maker
(0x0282 = trait bot, 0x400f = item bot), which the operator context confirms.

Run: python -u delta_analysis.py   (logs to logs/delta_analysis.log)
Outputs: analysis/delta/*.json + analysis/delta/DELTA_REPORT.md
"""
import glob
import json
import os
import statistics
import sys
from collections import defaultdict, Counter
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SNAPS = os.path.join(HERE, "snapshots")
OUT = os.path.join(HERE, "analysis", "delta")
LOGP = os.path.join(HERE, "logs", "delta_analysis.log")
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.dirname(LOGP), exist_ok=True)

VALID_FROM = "2026-06-10T20-30"          # inclusive cutoff (filename compare)
NEWFMT_FROM = "2026-06-11T10-30"         # raw criteria present from here
TRAIT_BOT = "0x028296d8bf1995549d5b9446622cf565bbd0a26e"
ITEM_BOT = "0x400f2bd92098c386cea677d6e7f832eb25c6e3cf"
VAULT = "0x8e8d6246c45d0e7f68172e85573546d90fc2e062"
OPERATOR = {TRAIT_BOT, ITEM_BOT, VAULT}
STALE_FLOOR_MULT = 2.0                   # ignore bids/listings > 2x floor as stale

_logf = open(LOGP, "w")


def log(*a):
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    _logf.write(msg + "\n")
    _logf.flush()


def snap_ts(path):
    s = path.split("snap_")[1].replace(".json", "")
    return datetime.strptime(s, "%Y-%m-%dT%H-%M-%SZ")


def load_valid():
    fs = sorted(glob.glob(os.path.join(SNAPS, "snap_*.json")))
    fs = [f for f in fs if f.split("snap_")[1] >= VALID_FROM]
    return fs


def bot_kind(maker):
    m = (maker or "").lower()
    if m == TRAIT_BOT:
        return "trait"
    if m == ITEM_BOT:
        return "item"
    return "other"


def criterion_key(o):
    """Stable key for 'the thing being bid on', for replacement matching.

    trait bot -> (collection, trait-tuple); item bot -> (collection, token_id).
    Falls back gracefully on old-format snapshots.
    """
    coll = o.get("criteria_collection")
    crit = o.get("criteria") if isinstance(o.get("criteria"), dict) else None
    if crit:
        coll = (crit.get("collection") or {}).get("slug") or coll
    # trait
    traits = None
    if crit and crit.get("traits"):
        traits = tuple(sorted((t.get("type"), t.get("value")) for t in crit["traits"]))
    elif o.get("criteria_traits"):
        traits = tuple(sorted((t.get("type"), t.get("value")) for t in o["criteria_traits"]))
    if traits:
        return ("trait", coll, traits)
    # item token
    asset = o.get("asset") or {}
    tid = asset.get("identifier")
    if tid:
        return ("item", coll, str(tid))
    # old-format item offer: no token id available -> key by collection+price-bucketless hash
    return ("unknown", coll, o.get("order_hash"))


def main():
    fs = load_valid()
    times = [snap_ts(f) for f in fs]
    log("=== delta_analysis: snapshot validation ===")
    log(f"valid snapshots (>= {VALID_FROM}Z): {len(fs)}")
    log(f"date range: {times[0]}Z .. {times[-1]}Z")
    gaps = [(times[i + 1] - times[i]).total_seconds() / 60 for i in range(len(times) - 1)]
    gc = Counter(round(g) for g in gaps)
    log(f"interval distribution (minutes): {dict(sorted(gc.items()))}")
    irr = [(times[i].isoformat(), round(gaps[i], 1)) for i in range(len(gaps)) if not (13 <= gaps[i] <= 17)]
    log(f"irregular intervals (not ~15m): {len(irr)}")
    for t, g in irr:
        log(f"   irregular: {t}Z -> +{g} min")
    newfmt = [f for f in fs if f.split("snap_")[1] >= NEWFMT_FROM]
    log(f"snapshots with raw trait criteria (>= {NEWFMT_FROM}Z): {len(newfmt)} "
        f"(before that, trait/item inferred from maker)")
    log("")

    # ---- load all snapshots into memory (offers + listings per collection) ----
    snaps = []
    for f, t in zip(fs, times):
        s = json.load(open(f))
        snaps.append({"t": t, "file": os.path.basename(f), "coll": s["collections"]})

    lifetimes(snaps)
    top_bid_retention(snaps)
    floor_reaction(snaps)
    listing_side(snaps)
    log("=== delta_analysis complete ===")


# ----------------------------------------------------------------------------
# 1. BID LIFETIMES + disappearance classification
# ----------------------------------------------------------------------------
def load_sales_index():
    """order_hash and (collection,token,ts) index of sales from history files."""
    by_hash = {}
    by_tok = defaultdict(list)
    for jf in glob.glob(os.path.join(HERE, "data", "events_hist_*.json")):
        try:
            evs = json.load(open(jf))
        except (json.JSONDecodeError, OSError):
            continue
        for e in evs:
            if e.get("event_type") != "sale":
                continue
            ts = e.get("event_timestamp")
            oh = e.get("order_hash")
            if oh:
                by_hash[oh] = ts
            coll = e.get("collection")
            crit = e.get("criteria") or {}
            tid = (crit.get("token_ids") if isinstance(crit, dict) else None)
            by_tok[(coll, str(tid))].append(ts)
    return by_hash, by_tok


def lifetimes(snaps):
    log("=== 1. BID LIFETIMES & disappearance ===")
    sales_hash, _ = load_sales_index()
    # first/last seen per order_hash
    first_seen, last_seen, meta = {}, {}, {}
    seen_idx = defaultdict(list)
    for i, sn in enumerate(snaps):
        for slug, d in sn["coll"].items():
            if not isinstance(d, dict):
                continue
            for o in d.get("our_offers", []):
                oh = o.get("order_hash")
                if not oh:
                    continue
                if oh not in first_seen:
                    first_seen[oh] = i
                    meta[oh] = {"maker": o.get("maker"), "slug": slug,
                                "price": o.get("price_eth"), "crit": criterion_key(o),
                                "expiration": o.get("expiration"), "start": o.get("start_time")}
                last_seen[oh] = i
                seen_idx[oh].append(i)

    # criterion -> ordered list of (snap_idx, order_hash, price, maker) for replacement detection
    crit_timeline = defaultdict(list)
    for oh, m in meta.items():
        crit_timeline[(m["maker"], m["crit"])].append(oh)

    # classify each order_hash that DISAPPEARED before the last snapshot
    last_i = len(snaps) - 1
    results = []  # per-order lifecycle records
    for oh, fi in first_seen.items():
        li = last_seen[oh]
        m = meta[oh]
        # lifetime in minutes between first and last sighting (+ assume it lived until next snap)
        t0 = snaps[fi]["t"]
        t1 = snaps[li]["t"]
        life_min = (t1 - t0).total_seconds() / 60
        still_live = (li == last_i)
        reason = None
        if not still_live:
            # next snapshot after li
            nxt = li + 1
            # (c) filled? sale of same order_hash, or sale on same criterion within +/-15min of disappearance
            disappear_t = snaps[nxt]["t"]
            filled = oh in sales_hash
            # (a) replaced? same (maker,criterion) has another order_hash present at snap nxt
            replaced = False
            for oh2 in crit_timeline[(m["maker"], m["crit"])]:
                if oh2 == oh:
                    continue
                if nxt in seen_idx.get(oh2, []) and first_seen[oh2] >= li:
                    replaced = True
                    break
            if filled:
                reason = "filled"
            elif replaced:
                reason = "replaced"
            else:
                reason = "expired"
        results.append({"order_hash": oh, "maker": m["maker"], "kind": bot_kind(m["maker"]),
                        "slug": m["slug"], "life_min": round(life_min, 1),
                        "snaps_alive": len(seen_idx[oh]), "still_live": still_live,
                        "reason": reason})

    # aggregate by kind
    # NOTE on lifetime: snapshots are 15 min apart, so observed life = (last-first
    # sighting) is a LOWER BOUND quantised to 15 min. A bid seen in exactly one
    # snapshot has observed life 0 but truly lived somewhere in (0, 30] min. With a
    # 10-30 min TTL most bids are seen 1-2 times, so we report the snaps-alive
    # distribution alongside the (floored) minute figures and flag the limit.
    out = {"by_kind": {}, "_sampling_note":
           "15-min sampling floors observed lifetime; true TTL (10-30m) is mostly "
           "sub-sampling, so 'snaps_alive' is the more honest signal than life_min."}
    for kind in ("trait", "item"):
        recs = [r for r in results if r["kind"] == kind and not r["still_live"]]
        if not recs:
            continue
        lives = sorted(r["life_min"] for r in recs)
        snaps_alive = sorted(r["snaps_alive"] for r in recs)
        reasons = Counter(r["reason"] for r in recs)
        tot = len(recs)
        out["by_kind"][kind] = {
            "closed_orders": tot,
            "life_min_observed_lowerbound": {
                "median": round(statistics.median(lives), 1),
                "p25": round(_pct(lives, .25), 1),
                "p75": round(_pct(lives, .75), 1),
                "min": lives[0], "max": lives[-1],
            },
            "snaps_alive": {
                "median": statistics.median(snaps_alive),
                "p75": _pct(snaps_alive, .75), "max": snaps_alive[-1],
                "seen_once_pct": round(sum(1 for s in snaps_alive if s == 1) / tot * 100, 1),
            },
            "reason_share": {k: round(reasons[k] / tot * 100, 1) for k in ("replaced", "expired", "filled")},
            "reason_count": dict(reasons),
            "histogram_snaps_alive": dict(Counter(snaps_alive)),
        }
        b = out["by_kind"][kind]
        log(f"  [{kind}] closed={tot} obs-life median={b['life_min_observed_lowerbound']['median']}m "
            f"(p75={b['life_min_observed_lowerbound']['p75']}m); seen-once={b['snaps_alive']['seen_once_pct']}% "
            f"reasons={b['reason_share']}")
    out["total_unique_orders"] = len(first_seen)
    out["still_live_at_end"] = sum(1 for r in results if r["still_live"])
    json.dump(out, open(os.path.join(OUT, "lifetimes.json"), "w"), indent=1)
    json.dump(results, open(os.path.join(OUT, "lifetimes_raw.json"), "w"))
    log(f"  total unique orders tracked: {out['total_unique_orders']}")
    log("")
    return out


# ----------------------------------------------------------------------------
# 2. TOP-BID RETENTION
# ----------------------------------------------------------------------------
def top_bid_retention(snaps):
    log("=== 2. TOP-BID RETENTION ===")
    # per (collection): for each snapshot, is operator's best realistic bid the top of book?
    # top of book = max over (our_offers + top20_other_bids) with price <= 2x floor
    per_coll = defaultdict(lambda: {"snaps": 0, "op_top": 0, "gaps_pct": []})
    per_kind = defaultdict(lambda: {"snaps": 0, "op_top": 0})
    for sn in snaps:
        for slug, d in sn["coll"].items():
            if not isinstance(d, dict):
                continue
            floor = d.get("floor_price_eth")
            cap = floor * STALE_FLOOR_MULT if floor else None
            ours = [o.get("price_eth") for o in d.get("our_offers", [])
                    if o.get("price_eth") and (cap is None or o["price_eth"] <= cap)]
            others = [b.get("price_eth") for b in d.get("top20_other_bids", [])
                      if b.get("price_eth") and (cap is None or b["price_eth"] <= cap)]
            if not ours:
                continue
            op_best = max(ours)
            other_best = max(others) if others else 0
            pc = per_coll[slug]
            pc["snaps"] += 1
            if op_best >= other_best:
                pc["op_top"] += 1
            elif floor:
                pc["gaps_pct"].append(round((other_best - op_best) / floor * 100, 2))
            # kind attribution: which bot holds our best?
            best_maker = None
            for o in d.get("our_offers", []):
                if o.get("price_eth") == op_best:
                    best_maker = o.get("maker")
                    break
            k = bot_kind(best_maker)
            if k in ("trait", "item"):
                per_kind[k]["snaps"] += 1
                if op_best >= other_best:
                    per_kind[k]["op_top"] += 1

    out = {"_definition":
           "'top' = operator's best realistic bid (<=2x floor) >= best competing "
           "collection-wide bid (<=2x floor). For the trait bot this compares a "
           "trait-specific bid to collection-wide demand, so 'not top' often just "
           "means a competitor posted a higher collection-wide offer, not that the "
           "operator was out-bid on its actual trait. Most meaningful for the item "
           "bot on pudgypenguins.",
           "by_collection": {}, "by_kind": {}}
    for slug, v in sorted(per_coll.items(), key=lambda x: -x[1]["snaps"]):
        if not v["snaps"]:
            continue
        gaps = sorted(v["gaps_pct"])
        out["by_collection"][slug] = {
            "snaps_with_our_bid": v["snaps"],
            "pct_we_are_top": round(v["op_top"] / v["snaps"] * 100, 1),
            "median_gap_below_top_pct_floor": round(statistics.median(gaps), 2) if gaps else None,
            "p90_gap_below_top_pct_floor": round(_pct(gaps, .9), 2) if gaps else None,
        }
        log(f"  [{slug}] top in {out['by_collection'][slug]['pct_we_are_top']}% of "
            f"{v['snaps']} snaps; median gap when not top "
            f"{out['by_collection'][slug]['median_gap_below_top_pct_floor']}% of floor")
    for k, v in per_kind.items():
        if v["snaps"]:
            out["by_kind"][k] = {"snaps": v["snaps"], "pct_top": round(v["op_top"] / v["snaps"] * 100, 1)}
    json.dump(out, open(os.path.join(OUT, "top_bid_retention.json"), "w"), indent=1)
    log("")
    return out


# ----------------------------------------------------------------------------
# 3. FLOOR REACTION
# ----------------------------------------------------------------------------
def floor_reaction(snaps):
    log("=== 3. FLOOR REACTION ===")
    # per collection: floor series + operator best-bid series + item-ladder width series
    series = defaultdict(list)
    for i, sn in enumerate(snaps):
        for slug, d in sn["coll"].items():
            if not isinstance(d, dict):
                continue
            floor = d.get("floor_price_eth")
            ours = [o.get("price_eth") for o in d.get("our_offers", [])
                    if o.get("price_eth") and (not floor or o["price_eth"] <= floor * STALE_FLOOR_MULT)]
            best = max(ours) if ours else None
            width = (max(ours) - min(ours)) if len(ours) > 1 else None
            series[slug].append({"i": i, "t": sn["t"], "floor": floor, "best": best, "width": width})

    episodes = []
    for slug, ser in series.items():
        for j in range(1, len(ser)):
            f0, f1 = ser[j - 1]["floor"], ser[j]["floor"]
            if not f0 or not f1:
                continue
            chg = (f1 - f0) / f0
            if abs(chg) < 0.01:
                continue
            # find lag: snaps until operator best moves in same direction
            lag = None
            b_at = ser[j - 1]["best"]
            if b_at:
                for k in range(j, min(j + 12, len(ser))):
                    bk = ser[k]["best"]
                    if bk is None:
                        continue
                    if (chg > 0 and bk > b_at * 1.002) or (chg < 0 and bk < b_at * 0.998):
                        lag = k - (j - 1)
                        break
            w0 = ser[j - 1]["width"]
            w1 = ser[min(j + 3, len(ser) - 1)]["width"]
            episodes.append({"slug": slug, "t": ser[j]["t"].isoformat(),
                             "floor_from": f0, "floor_to": f1, "floor_chg_pct": round(chg * 100, 2),
                             "lag_snaps": lag, "lag_min": lag * 15 if lag else None,
                             "ladder_width_before": round(w0, 4) if w0 else None,
                             "ladder_width_after": round(w1, 4) if w1 else None})

    lags = [e["lag_snaps"] for e in episodes if e["lag_snaps"] is not None]
    out = {"episodes": len(episodes),
           "episodes_with_reprice": len(lags),
           "reprice_lag_snaps": {"median": statistics.median(lags) if lags else None,
                                 "p25": _pct(lags, .25) if lags else None,
                                 "p75": _pct(lags, .75) if lags else None} if lags else {},
           "detail": sorted(episodes, key=lambda e: -abs(e["floor_chg_pct"]))[:40]}
    json.dump(out, open(os.path.join(OUT, "floor_reaction.json"), "w"), indent=1)
    log(f"  floor-move episodes (>=1%): {out['episodes']}; with measurable reprice: {out['episodes_with_reprice']}")
    if lags:
        log(f"  reprice lag (snaps of 15m): median={out['reprice_lag_snaps']['median']} "
            f"p25={out['reprice_lag_snaps']['p25']} p75={out['reprice_lag_snaps']['p75']}")
    log("")
    return out


# ----------------------------------------------------------------------------
# 4. LISTING SIDE
# ----------------------------------------------------------------------------
def listing_side(snaps):
    log("=== 4. LISTING SIDE ===")
    total = sum(len(d.get("our_listings", [])) for sn in snaps for d in sn["coll"].values()
                if isinstance(d, dict))
    if total == 0:
        log("  NO operator listings in snapshots.")
        log("  Minimal fix: snapshot.py already fetches /listings/.../all?maker=<addr> per address;")
        log("  if listings are missing it's because the operator isn't listing on OpenSea (sells via")
        log("  accepting bids / Blur). No code change needed unless we also want non-/all best listings.")
        json.dump({"total_listings": 0, "note": "operator does not list on OpenSea in window"},
                  open(os.path.join(OUT, "listing_side.json"), "w"), indent=1)
        log("")
        return
    # track listings by order_hash; detect re-prices on same token by same maker
    first_seen, last_seen, meta, seen_idx = {}, {}, {}, defaultdict(list)
    tok_timeline = defaultdict(list)   # (maker, slug, token) -> [(i, price, hash)]
    last_i = len(snaps) - 1
    for i, sn in enumerate(snaps):
        for slug, d in sn["coll"].items():
            if not isinstance(d, dict):
                continue
            for l in d.get("our_listings", []):
                oh = l.get("order_hash")
                if not oh:
                    continue
                if oh not in first_seen:
                    first_seen[oh] = i
                    asset = l.get("asset") or {}
                    tok = asset.get("identifier") or l.get("criteria_collection")
                    meta[oh] = {"maker": l.get("maker"), "slug": slug, "price": l.get("price_eth"),
                                "token": tok}
                    tok_timeline[(l.get("maker"), slug, str(tok))].append((i, l.get("price_eth"), oh))
                last_seen[oh] = i
                seen_idx[oh].append(i)

    reprices = []
    for key, lst in tok_timeline.items():
        lst.sort()
        for a, b in zip(lst, lst[1:]):
            if a[1] and b[1] and a[2] != b[2]:
                step = (b[1] - a[1]) / a[1] * 100
                reprices.append({"maker": key[0], "slug": key[1], "token": key[2],
                                 "from": a[1], "to": b[1], "step_pct": round(step, 2),
                                 "dir": "up" if step > 0 else "down"})
    withdrawals = sum(1 for oh in first_seen if last_seen[oh] < last_i and oh not in
                      {x[2] for v in tok_timeline.values() for x in v[1:]})
    by_maker = Counter(meta[oh]["maker"] for oh in first_seen)
    by_slug = Counter(meta[oh]["slug"] for oh in first_seen)
    ups = sum(1 for r in reprices if r["dir"] == "up")
    out = {"total_listing_observations": total, "unique_listings": len(first_seen),
           "by_maker": dict(by_maker), "by_collection": dict(by_slug),
           "reprices": len(reprices), "reprice_up": ups, "reprice_down": len(reprices) - ups,
           "median_reprice_step_pct": round(statistics.median([abs(r["step_pct"]) for r in reprices]), 2)
           if reprices else None,
           "withdrawals_no_reprice": withdrawals,
           "reprice_detail": reprices[:40]}
    json.dump(out, open(os.path.join(OUT, "listing_side.json"), "w"), indent=1)
    log(f"  unique listings: {out['unique_listings']} (by maker {dict(by_maker)})")
    log(f"  by collection: {dict(by_slug)}")
    log(f"  reprices: {out['reprices']} (up {ups}/down {len(reprices)-ups}, "
        f"median step {out['median_reprice_step_pct']}%); withdrawals {withdrawals}")
    log("")
    return out


def _pct(d, q):
    if not d:
        return None
    d = sorted(d)
    k = (len(d) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(d) - 1)
    return d[lo] + (d[hi] - d[lo]) * (k - lo)


def _hist(vals, edges):
    h = {}
    for a, b in zip(edges, edges[1:]):
        h[f"{a}-{b}m"] = sum(1 for v in vals if a <= v < b)
    h[f">{edges[-1]}m"] = sum(1 for v in vals if v >= edges[-1])
    return h


if __name__ == "__main__":
    main()
