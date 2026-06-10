#!/usr/bin/env python3
"""snapshot.py — lightweight point-in-time order-book snapshot for top collections.

Quota-efficient design (does NOT scan all 76k+ offers):
  - OUR active orders: /offers/collection/{slug}/all?maker=<addr> and
    /listings/collection/{slug}/all?maker=<addr> for each of the 3 addresses
    (server-side maker filter -> only our orders, a handful of pages each).
  - TOP-20 OTHER bids: /offers/collection/{slug}?limit=20 — this endpoint
    returns collection offers already sorted by price descending; one page is
    the current top of book. We drop any that are ours.
  - FLOOR: /collections/{slug}/stats.

~8 requests per collection -> well under 3 minutes for 15 collections.

Output: snapshots/snap_<UTC_ISO>.json
"""
import datetime
import json
import os

from osea import ADDRESSES, ADDR_SET, SNAPS, DATA, get, eth_value

TOP_N_OTHER_BIDS = 20
SNAP_PACE = 1.0   # snapshot is small; run a touch faster than the crawlers


def price_eth(order):
    """ETH price from an offers/listings order dict (price.current, then seaport)."""
    pr = order.get("price") or {}
    cur = pr.get("current") or {}
    if cur.get("value"):
        try:
            return int(cur["value"]) / 10 ** int(cur.get("decimals", 18)), cur.get("currency")
        except (TypeError, ValueError):
            pass
    params = (order.get("protocol_data") or {}).get("parameters") or {}
    off = params.get("offer") or []
    if off:
        try:
            return int(off[0]["startAmount"]) / 10 ** 18, "WETH"
        except (TypeError, ValueError, KeyError):
            pass
    return 0.0, None


def maker_of(order):
    return ((order.get("protocol_data") or {}).get("parameters") or {}).get("offerer", "").lower()


def record(order, kind):
    p, cur = price_eth(order)
    params = (order.get("protocol_data") or {}).get("parameters") or {}
    crit = order.get("criteria") or {}
    return {
        "kind": kind,
        "order_hash": order.get("order_hash"),
        "maker": params.get("offerer"),
        "price_eth": round(p, 6),
        "currency": cur,
        "start_time": params.get("startTime"),
        "expiration": params.get("endTime"),
        "protocol_address": order.get("protocol_address"),
        "criteria_collection": (crit.get("collection") or {}).get("slug"),
        "criteria_trait": crit.get("trait"),
        "order_created_at": order.get("order_created_at"),
    }


def our_orders(slug, endpoint, items_key, kind):
    """Fetch only our orders via the server-side maker filter, per address."""
    out = []
    for addr in ADDRESSES:
        cursor = None
        while True:
            params = [("maker", addr), ("limit", 100)]
            if cursor:
                params.append(("next.value", cursor))
            page = get(f"/{endpoint}/collection/{slug}/all", params=params, pace=SNAP_PACE)
            if isinstance(page, dict) and page.get("_error"):
                break
            for o in page.get(items_key, []):
                out.append(record(o, kind))
            cursor = page.get("next")
            if not cursor:
                break
    return out


def top_other_bids(slug):
    """Top-N collection bids by price (one page, sorted desc), minus ours."""
    page = get(f"/offers/collection/{slug}", params=[("limit", TOP_N_OTHER_BIDS + 10)],
               pace=SNAP_PACE)
    if isinstance(page, dict) and page.get("_error"):
        return []
    recs = []
    for o in page.get("offers", []):
        if maker_of(o) in ADDR_SET:
            continue
        recs.append(record(o, "offer"))
    recs.sort(key=lambda r: r["price_eth"], reverse=True)
    return recs[:TOP_N_OTHER_BIDS]


def snap_collection(slug):
    print(f"[snapshot] {slug}", flush=True)
    stats = get(f"/collections/{slug}/stats", pace=SNAP_PACE)
    floor = None
    if isinstance(stats, dict) and not stats.get("_error"):
        floor = (stats.get("total") or {}).get("floor_price")

    our_off = our_orders(slug, "offers", "offers", "offer")
    our_lst = our_orders(slug, "listings", "listings", "listing")
    others = top_other_bids(slug)

    return {
        "slug": slug,
        "floor_price_eth": floor,
        "counts": {
            "our_offers": len(our_off),
            "our_listings": len(our_lst),
            "top_other_bids": len(others),
        },
        "our_offers": our_off,
        "our_listings": our_lst,
        "top20_other_bids": others,
        "top_other_bid_eth": others[0]["price_eth"] if others else None,
    }


def main():
    os.makedirs(SNAPS, exist_ok=True)
    profile = json.load(open(os.path.join(DATA, "profile.json")))
    top = profile.get("top_collections", [])[:15]
    now = datetime.datetime.now(datetime.timezone.utc)
    iso = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    snap = {"snapshot_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "collections": {}}
    for slug in top:
        try:
            snap["collections"][slug] = snap_collection(slug)
        except Exception as e:
            print(f"   ! {slug} failed: {e}", flush=True)
            snap["collections"][slug] = {"error": str(e)}
    path = os.path.join(SNAPS, f"snap_{iso}.json")
    with open(path, "w") as f:
        json.dump(snap, f, indent=1)
    print(f"[snapshot] wrote {path}", flush=True)


if __name__ == "__main__":
    main()
