#!/usr/bin/env python3
"""history.py — collection-level event history for top collections from profile.json.

For each top collection (max 15, ranked by total events in profile.json):
  GET /events/collection/{slug} with event_type order + sale, walking the time
  axis in windows with 1h overlap (after/before unix ts) because the cursor
  pagination is known to skip events. Keep only events whose maker/buyer/seller
  is one of our 3 addresses.

Output: data/events_<slug>.json with fields:
  order_hash, event_type, event_timestamp, maker, price_eth, criteria,
  expiration_date, taker  (+ a few useful extras: order_type, seller, buyer,
  collection, marketplace)
"""
import json
import os
import time

from osea import ADDRESSES, ADDR_SET, DATA, get, eth_value

MAX_COLLECTIONS = 10
LOOKBACK = 3 * 24 * 3600        # only the last 3 days of collection history
WINDOW = 24 * 3600             # 1-day windows
OVERLAP = 3600                  # 1 hour overlap (known cursor gaps)
LIMIT = 50
PACE = 0.5                     # portal key has higher limits; pace down to 0.5s


def proto_to_marketplace(addr):
    if not addr:
        return None
    a = addr.lower()
    known = {
        "0x0000000000000068f116a894984e2db1123eb395": "seaport-1.6",
        "0x00000000000000adc04c56bf30ac9d3c0aaf14dc": "seaport-1.5",
        "0x00000000006c3852cbef3e08e8df289169ede581": "seaport-1.1",
        "0x0000000000000000000000000000000000000000": "none",
    }
    return known.get(a, addr)


def criteria_of(e):
    """Build a compact criteria descriptor: collection / trait / item."""
    if e.get("criteria"):
        c = e["criteria"]
        coll = (c.get("collection") or {}).get("slug")
        contract = (c.get("contract") or {}).get("address")
        trait = c.get("trait")
        enc = c.get("encoded_token_ids")
        if trait:
            return {"type": "trait", "collection": coll, "trait": trait}
        if enc and enc != "*":
            return {"type": "item", "collection": coll, "contract": contract, "token_ids": enc}
        return {"type": "collection", "collection": coll, "contract": contract}
    # sale / item order: derive item from nft/asset
    node = e.get("nft") or e.get("asset")
    if node:
        return {"type": "item", "collection": node.get("collection"),
                "contract": node.get("contract"), "token_ids": node.get("identifier")}
    return None


def involves_us(e):
    for k in ("maker", "taker", "buyer", "seller"):
        v = e.get(k)
        if v and v.lower() in ADDR_SET:
            return True
    return False


def slim(e):
    node = e.get("nft") or e.get("asset") or {}
    return {
        "order_hash": e.get("order_hash"),
        "event_type": e.get("event_type"),
        "order_type": e.get("order_type"),
        "event_timestamp": e.get("event_timestamp"),
        "maker": e.get("maker"),
        "taker": e.get("taker"),
        "seller": e.get("seller"),
        "buyer": e.get("buyer"),
        "price_eth": eth_value(e.get("payment")),
        "payment_symbol": (e.get("payment") or {}).get("symbol"),
        "criteria": criteria_of(e),
        "expiration_date": e.get("expiration_date"),
        "start_date": e.get("start_date"),
        "collection": node.get("collection"),
        "marketplace": proto_to_marketplace(e.get("protocol_address")),
    }


def jsonl_path(slug):
    return os.path.join(DATA, f"events_hist_{slug}.jsonl")


def progress_path(slug):
    return os.path.join(DATA, f"events_hist_{slug}.progress.json")


def event_key(e):
    return (e.get("order_hash"), e.get("event_type"),
            e.get("event_timestamp"), e.get("maker"), e.get("buyer"))


def load_resume(slug):
    """Rebuild dedupe set from existing JSONL and read last completed window."""
    seen = set()
    n = 0
    jp = jsonl_path(slug)
    if os.path.exists(jp):
        with open(jp) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                seen.add(event_key(e))
                n += 1
    resume_win = None
    pp = progress_path(slug)
    if os.path.exists(pp):
        try:
            resume_win = json.load(open(pp)).get("next_win_start")
        except (json.JSONDecodeError, OSError):
            resume_win = None
    return seen, n, resume_win


def fetch_window(slug, after, before, seen, out_fh):
    """Paginate one window, appending kept (slim) events to out_fh as JSONL.

    Returns number of new events written this window.
    """
    # The REQUEST enum has no "order" — that's a response-only type. Request the
    # order subtypes (listing/offer/collection_offer/trait_offer) + sale; they
    # come back with event_type == "order". (Verified against openapi.json.)
    params = [("event_type", "listing"), ("event_type", "offer"),
              ("event_type", "collection_offer"), ("event_type", "trait_offer"),
              ("event_type", "sale"),
              ("after", after), ("before", before), ("limit", LIMIT)]
    cursor = None
    pages = 0
    written = 0
    while True:
        q = list(params)
        if cursor:
            q.append(("next.value", cursor))
        page = get(f"/events/collection/{slug}", params=q, pace=PACE)
        if isinstance(page, dict) and page.get("_error"):
            print(f"    ! {slug} window err {page['_error']}: {page.get('_body','')[:100]}",
                  flush=True)
            break
        batch = page.get("asset_events", [])
        for e in batch:
            if not involves_us(e):
                continue
            k = event_key(e)
            if k in seen:
                continue
            seen.add(k)
            out_fh.write(json.dumps(slim(e)) + "\n")
            written += 1
        out_fh.flush()
        cursor = page.get("next")
        pages += 1
        if pages % 10 == 0:
            print(f"    {slug} ...win page {pages}, kept {written} so far", flush=True)
        if not cursor:
            break
    return written


def collect_collection(slug):
    """Walk 2y in 7-day windows (1h overlap), appending to JSONL incrementally.

    Resumable: skips windows already completed per the progress file.
    """
    now = int(time.time())
    start = now - LOOKBACK
    seen, existing_n, resume_win = load_resume(slug)
    win_start = resume_win if resume_win is not None else start
    if resume_win is not None:
        print(f"  {slug}: resuming from window {win_start} "
              f"({existing_n} events already on disk)", flush=True)
    total_new = 0
    with open(jsonl_path(slug), "a") as fh:
        while win_start < now:
            win_end = min(win_start + WINDOW, now)
            w = fetch_window(slug, win_start, win_end, seen, fh)
            total_new += w
            next_start = win_end - OVERLAP   # 1h overlap
            # persist progress after each completed window
            with open(progress_path(slug), "w") as pf:
                json.dump({"next_win_start": next_start,
                           "last_win": [win_start, win_end],
                           "events_on_disk": existing_n + total_new}, pf)
            print(f"  {slug}: window {win_start}->{win_end} +{w} "
                  f"(total kept {existing_n + total_new})", flush=True)
            win_start = next_start
    return existing_n + total_new


def read_kept(slug):
    """Load all kept events from JSONL (sorted by ts) for summarising."""
    evs = []
    jp = jsonl_path(slug)
    if os.path.exists(jp):
        with open(jp) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        evs.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    evs.sort(key=lambda x: x.get("event_timestamp") or 0)
    return evs


def build_from_discover(top):
    """Build per-collection event files by filtering the discover JSONL.

    discover.py already captured EVERY event touching our 3 addresses, per
    address, with full fields. Filtering that to a collection is hole-free and
    needs zero extra API calls — unlike re-paginating the whole collection book
    via /events/collection (millions of foreign events to wade through). This is
    the authoritative source for "our events in collection X".
    """
    import glob
    by_coll = {s: [] for s in top}
    topset = set(top)
    for jf in glob.glob(os.path.join(DATA, "events_0x*.jsonl")):
        with open(jf) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                node = e.get("nft") or e.get("asset") or {}
                slug = node.get("collection")
                if slug in topset and involves_us(e):
                    by_coll[slug].append(slim(e))

    summary = {}
    for slug in top:
        evs = by_coll[slug]
        # dedupe (same event can appear in two addresses' files)
        seen = set()
        uniq = []
        for e in evs:
            k = (e.get("order_hash"), e.get("event_type"),
                 e.get("event_timestamp"), e.get("maker"), e.get("buyer"))
            if k in seen:
                continue
            seen.add(k)
            uniq.append(e)
        uniq.sort(key=lambda x: x.get("event_timestamp") or 0)
        path = os.path.join(DATA, f"events_hist_{slug}.json")
        with open(path, "w") as f:
            json.dump(uniq, f, indent=1)
        by_type = {}
        for e in uniq:
            k = (e["event_type"] if e["event_type"] != "order"
                 else f"order:{e.get('order_type')}")
            by_type[k] = by_type.get(k, 0) + 1
        summary[slug] = {"kept_events": len(uniq), "by_type": by_type,
                         "source": "discover"}
        print(f"  {slug}: kept {len(uniq)} -> {path}  {by_type}", flush=True)
    return summary


def main():
    import sys
    os.makedirs(DATA, exist_ok=True)
    profile = json.load(open(os.path.join(DATA, "profile.json")))
    top = profile.get("top_collections", [])[:MAX_COLLECTIONS]
    mode = "crawl" if "--crawl" in sys.argv else "discover"
    print(f"[history] {len(top)} collections ({mode} mode): {top}", flush=True)

    if mode == "discover":
        summary = build_from_discover(top)
    else:
        summary = {}
        for slug in top:
            print(f"[history] {slug}", flush=True)
            collect_collection(slug)
            events = read_kept(slug)
            path = os.path.join(DATA, f"events_hist_{slug}.json")
            with open(path, "w") as f:
                json.dump(events, f, indent=1)
            by_type = {}
            for e in events:
                k = (e["event_type"] if e["event_type"] != "order"
                     else f"order:{e.get('order_type')}")
                by_type[k] = by_type.get(k, 0) + 1
            summary[slug] = {"kept_events": len(events), "by_type": by_type,
                             "source": "crawl"}
            print(f"  {slug}: kept {len(events)} -> {path}  {by_type}", flush=True)

    with open(os.path.join(DATA, "history_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print("[history] done", flush=True)


if __name__ == "__main__":
    main()
