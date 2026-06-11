#!/usr/bin/env python3
"""discover.py — per-address event collection for the 3 operator addresses.

Depth strategy (per user spec):
  - order events (offers + listings): only the last 60 days  (after = now-60d)
  - sale + transfer events: full available history (there are few of them)

Implementation: two paginated passes per address (different `after` bounds),
both appending to the SAME file data/events_{addr}.jsonl. event_type=listing/
offer/* come back as event_type=="order".

Incremental JSONL write (one event per line, flushed each page) + resume from
last saved cursor per pass. Pacing 1.1s, timeout=30 (both enforced in osea.get).
Progress logged to stdout with the current event date so you can see how far
back the pull has reached.

Outputs:
  data/events_{addr}.jsonl              raw events (append, resumable)
  data/events_{addr}.progress.json      {pass: {cursor, done, total}}
  data/raw_events_{addr_short}.json     full .json copy (compat)
  data/profile.json                     aggregated profile
"""
import datetime
import json
import os
import statistics
from collections import defaultdict

from osea import ADDRESSES, DATA, get, eth_value

ORDERS_WINDOW_DAYS = 3
ORDERS_WINDOW = ORDERS_WINDOW_DAYS * 86400

# two passes: name -> (event_type list, use time window?)
# NOTE: the API may ignore `after`, so the orders pass ALSO enforces a
# client-side cutoff: it stops as soon as an event older than the cutoff is
# returned, and never writes events older than the cutoff.
PASSES = {
    "orders_7d": (["listing", "offer", "collection_offer", "trait_offer"], True),
    "sale_transfer_full": (["sale", "transfer"], False),
}


def short(addr):
    return addr[:6] + addr[-4:]


def iso(ts):
    if not ts:
        return None
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_progress(addr):
    p = os.path.join(DATA, f"events_{addr}.progress.json")
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_progress(addr, prog):
    p = os.path.join(DATA, f"events_{addr}.progress.json")
    with open(p, "w") as f:
        json.dump(prog, f)


def run_pass(addr, pass_name, event_types, use_window, fh, prog):
    now = int(__import__("time").time())
    cutoff = now - ORDERS_WINDOW if use_window else None   # client-side floor
    params = [("chain", "ethereum"), ("limit", 50)]
    for et in event_types:
        params.append(("event_type", et))
    if use_window:
        params.append(("after", cutoff))                   # hint; not trusted

    st = prog.get(pass_name, {})
    if st.get("done"):
        print(f"  {short(addr)} [{pass_name}]: already complete ({st.get('total',0)})",
              flush=True)
        return st.get("total", 0)
    cursor = st.get("cursor")
    total = st.get("total", 0)
    if cursor:
        print(f"  {short(addr)} [{pass_name}]: resuming from saved cursor", flush=True)

    pages = 0
    while True:
        q = list(params)
        if cursor:
            q.append(("next.value", cursor))
        page = get(f"/events/accounts/{addr}", params=q)
        if isinstance(page, dict) and page.get("_error"):
            print(f"  ! {short(addr)} [{pass_name}] err {page['_error']}: "
                  f"{page.get('_body','')[:120]}", flush=True)
            break
        batch = page.get("asset_events", [])
        last_ts = None
        wrote = 0
        hit_cutoff = False
        for e in batch:
            ts = e.get("event_timestamp")
            # client-side cutoff: stop the windowed pass once we pass the floor.
            if cutoff is not None and ts is not None and ts < cutoff:
                hit_cutoff = True
                break
            fh.write(json.dumps(e) + "\n")
            wrote += 1
            last_ts = ts or last_ts
        fh.flush()
        total += wrote
        pages += 1
        cursor = page.get("next")
        done = (not cursor) or hit_cutoff
        prog[pass_name] = {"cursor": cursor, "done": done, "total": total}
        save_progress(addr, prog)
        tag = " CUTOFF-REACHED" if hit_cutoff else ""
        print(f"  {short(addr)} [{pass_name}] page {pages}: +{wrote} "
              f"(total {total}) at {iso(last_ts)} next={'Y' if cursor else 'N'}{tag}",
              flush=True)
        if done:
            break
    return total


def collect_address(addr):
    jl = os.path.join(DATA, f"events_{addr}.jsonl")
    prog = load_progress(addr)
    grand = 0
    with open(jl, "a") as fh:
        for pass_name, (event_types, use_window) in PASSES.items():
            grand += run_pass(addr, pass_name, event_types, use_window, fh, prog)
    print(f"  {short(addr)}: DONE total {grand} events", flush=True)
    return grand


def read_events(addr):
    out = []
    jl = os.path.join(DATA, f"events_{addr}.jsonl")
    if os.path.exists(jl):
        with open(jl) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return out


def event_collection(e):
    node = e.get("nft") or e.get("asset") or {}
    return node.get("collection"), node.get("contract")


def bid_price(e):
    """ETH price for an offer-type order event."""
    return eth_value(e.get("payment"))


def offer_subtype(e):
    """Classify an order event as trait / collection / item offer, or listing.

    The trait criterion is in criteria.traits (a LIST), not criteria.trait.
    A trait offer therefore has a non-empty traits/numeric_traits list.
    """
    ot = e.get("order_type", "")
    if ot == "listing":
        return "listing"
    crit = e.get("criteria") or {}
    if crit.get("traits") or crit.get("numeric_traits"):
        return "trait_offer"
    enc = crit.get("encoded_token_ids")
    # collection-wide offer: criteria has a collection but no trait
    if crit.get("collection") and (not enc or enc == "*"):
        return "collection_offer"
    if crit.get("collection") and enc:
        return "collection_offer"
    if ot == "collection_offer":
        return "collection_offer"
    if ot == "trait_offer":
        return "trait_offer"
    return "item_offer"


def main():
    os.makedirs(DATA, exist_ok=True)
    all_raw = {}
    for addr in ADDRESSES:
        print(f"[discover] {addr}", flush=True)
        collect_address(addr)
        evs = read_events(addr)
        all_raw[addr] = evs
        with open(os.path.join(DATA, f"raw_events_{short(addr)}.json"), "w") as f:
            json.dump(evs, f)

    build_profile(all_raw)


def build_profile(all_raw):
    profile = {"addresses": {}, "collections": {}}
    coll_meta = {}
    coll_agg = defaultdict(lambda: defaultdict(float))   # slug -> metric -> n
    coll_bid_prices = defaultdict(list)                  # slug -> [eth]
    offer_kind_total = defaultdict(int)                  # trait/collection/item/listing

    for addr in ADDRESSES:
        a = addr.lower()
        type_counts = defaultdict(int)
        buy_sell = {"buy": 0, "sell": 0, "buy_volume_eth": 0.0, "sell_volume_eth": 0.0}
        offer_kinds = defaultdict(int)
        ts_min = ts_max = None

        for e in all_raw[addr]:
            et = e.get("event_type", "unknown")
            type_counts[et] += 1
            slug, contract = event_collection(e)
            if slug:
                coll_meta.setdefault(slug, contract)
                coll_agg[slug][f"type_{et}"] += 1
            ts = e.get("event_timestamp")
            if ts:
                ts_min = ts if ts_min is None else min(ts_min, ts)
                ts_max = ts if ts_max is None else max(ts_max, ts)

            if et == "sale":
                val = eth_value(e.get("payment"))
                if (e.get("buyer") or "").lower() == a:
                    buy_sell["buy"] += 1
                    buy_sell["buy_volume_eth"] += val
                    if slug:
                        coll_agg[slug]["buy"] += 1
                        coll_agg[slug]["buy_volume_eth"] += val
                elif (e.get("seller") or "").lower() == a:
                    buy_sell["sell"] += 1
                    buy_sell["sell_volume_eth"] += val
                    if slug:
                        coll_agg[slug]["sell"] += 1
                        coll_agg[slug]["sell_volume_eth"] += val
            elif et == "order":
                kind = offer_subtype(e)
                offer_kinds[kind] += 1
                offer_kind_total[kind] += 1
                if slug:
                    coll_agg[slug]["orders"] += 1
                if kind != "listing":
                    p = bid_price(e)
                    if p > 0 and slug:
                        coll_bid_prices[slug].append(round(p, 6))

        profile["addresses"][addr] = {
            "short": short(addr),
            "total_events": len(all_raw[addr]),
            "events_by_type": dict(type_counts),
            "offer_kinds": dict(offer_kinds),
            "buy_sell": buy_sell,
            "activity_start_iso": iso(ts_min),
            "activity_end_iso": iso(ts_max),
            "activity_start_ts": ts_min,
            "activity_end_ts": ts_max,
        }

    # collections
    for slug, agg in coll_agg.items():
        d = {k: (int(v) if k.startswith("type_") or k in ("orders", "buy", "sell")
                 else round(v, 6)) for k, v in agg.items()}
        d["contract"] = coll_meta.get(slug)
        d["offers"] = int(agg.get("orders", 0))
        d["sales"] = int(agg.get("type_sale", 0))
        d["buy"] = int(agg.get("buy", 0))
        d["sell"] = int(agg.get("sell", 0))
        d["volume_eth"] = round(agg.get("buy_volume_eth", 0) + agg.get("sell_volume_eth", 0), 6)
        d["total_events"] = int(sum(v for k, v in agg.items() if k.startswith("type_")))
        profile["collections"][slug] = d

    ranked = sorted(profile["collections"],
                    key=lambda s: profile["collections"][s]["total_events"], reverse=True)
    profile["top_collections"] = ranked

    # offer-kind shares
    tot_orders = sum(offer_kind_total.values()) or 1
    profile["offer_kind_distribution"] = {
        k: {"count": v, "share": round(v / tot_orders, 4)}
        for k, v in sorted(offer_kind_total.items(), key=lambda x: -x[1])
    }

    # bid price distribution for top-5 collections
    bid_stats = {}
    for slug in ranked[:5]:
        prices = sorted(coll_bid_prices.get(slug, []))
        if not prices:
            bid_stats[slug] = {"n": 0}
            continue
        freq = defaultdict(int)
        for p in prices:
            freq[p] += 1
        bid_stats[slug] = {
            "n": len(prices),
            "min": prices[0],
            "max": prices[-1],
            "median": round(statistics.median(prices), 6),
            "unique_values": [{"price_eth": k, "count": freq[k]}
                              for k in sorted(freq)],
        }
    profile["top5_bid_price_distribution"] = bid_stats

    with open(os.path.join(DATA, "profile.json"), "w") as f:
        json.dump(profile, f, indent=1)
    print(f"[discover] profile.json written: {len(profile['collections'])} collections, "
          f"top={ranked[:5]}", flush=True)


if __name__ == "__main__":
    main()
