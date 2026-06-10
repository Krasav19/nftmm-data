"""Shared OpenSea API v2 client helpers for the nftmm market-maker data collection.

Source of truth for endpoints/params: ~/nftmm/openapi.json
Confirmed via live probes:
  - GET /events/accounts/{address}  -> {asset_events:[...], next:<cursor str>}
  - GET /events/collection/{slug}   -> {asset_events:[...], next:<cursor str>}
  - event_type query enum: sale, transfer, mint, listing, offer, trait_offer, collection_offer
    (requesting listing/offer/* yields events whose event_type == "order" with an order_type subfield)
  - pagination param is "next.value" (value of prior response's `next`)
  - GET /offers/collection/{slug}/all   -> {offers:[...], next:<cursor>}
  - GET /listings/collection/{slug}/all -> {listings:[...], next:<cursor>}
  - GET /collections/{slug}/stats       -> {total:{...}, intervals:[...]}
"""
import os
import time
import requests
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
# override=True so the .env file is the source of truth even if a stale
# OPENSEA_KEY is already exported in the launching shell.
load_dotenv(os.path.join(HERE, ".env"), override=True)

API_KEY = os.environ["OPENSEA_KEY"]
BASE = "https://api.opensea.io/api/v2"
HEADERS = {"x-api-key": API_KEY, "accept": "application/json"}

ADDRESSES = [
    "0x028296d8bf1995549d5b9446622cf565bbd0a26e",
    "0x8e8d6246c45d0e7f68172e85573546d90fc2e062",
    "0x400f2bd92098c386cea677d6e7f832eb25c6e3cf",
]
ADDR_SET = {a.lower() for a in ADDRESSES}

DATA = os.path.join(HERE, "data")
SNAPS = os.path.join(HERE, "snapshots")

_session = requests.Session()
_session.headers.update(HEADERS)


# Base pacing between SUCCESSFUL requests. The key appears to have an hourly
# quota, so we keep this conservative (2s -> ~30 req/min) rather than racing
# the per-minute ceiling.
PACE = 2.0
MAX_WAIT = 300            # backoff ceiling (was 60)
JITTER = 0.20            # +/-20% jitter so we don't resync with the limit window

# state for diagnostics + hot key reload
_last_success = time.time()
_consec_429 = 0


def _jittered(wait):
    import random
    return wait * (1.0 + random.uniform(-JITTER, JITTER))


def _reload_key():
    """Re-read OPENSEA_KEY from .env and apply it to the session (hot reload)."""
    global API_KEY
    load_dotenv(os.path.join(HERE, ".env"), override=True)
    newk = os.environ.get("OPENSEA_KEY")
    if newk and newk != API_KEY:
        API_KEY = newk
        _session.headers["x-api-key"] = newk
        print(f"   >>> picked up NEW OPENSEA_KEY from .env "
              f"(...{newk[-6:]})", flush=True)
        return True
    return False


def get(path, params=None, max_wait=MAX_WAIT, timeout=30, pace=PACE):
    """GET with fixed pacing + jittered exponential backoff on 429/5xx.

    On 429/5xx the SAME request (same url+params, i.e. same cursor) is retried
    until it succeeds — the caller never advances the cursor past a failed page,
    so there are no gaps. Diagnostics: consecutive-429 count and seconds since
    the last successful page are logged. Every 5th consecutive 429 the .env is
    re-read so a freshly dropped-in OPENSEA_KEY is picked up on the fly.
    """
    global _last_success, _consec_429
    url = path if path.startswith("http") else f"{BASE}{path}"
    if pace:
        time.sleep(pace)
    wait = 1
    while True:
        try:
            r = _session.get(url, params=params, timeout=timeout)
        except requests.RequestException as e:
            print(f"   net error {e}; retry same request in {wait:.0f}s", flush=True)
            time.sleep(_jittered(wait))
            wait = min(wait * 2, max_wait)
            continue
        if r.status_code == 200:
            _last_success = time.time()
            _consec_429 = 0
            return r.json()
        if r.status_code == 429 or r.status_code >= 500:
            if r.status_code == 429:
                _consec_429 += 1
            idle = time.time() - _last_success
            sleep_for = _jittered(wait)
            print(f"   HTTP {r.status_code} on {url}; consec_429={_consec_429} "
                  f"idle={idle:.0f}s; retry SAME cursor in {sleep_for:.0f}s",
                  flush=True)
            # every 5th consecutive 429, try to pick up a fresh key from .env
            if r.status_code == 429 and _consec_429 % 5 == 0:
                if _reload_key():
                    wait = 1            # new key -> reset backoff, retry promptly
                    continue
            time.sleep(sleep_for)
            wait = min(wait * 2, max_wait)
            continue
        # 4xx other than 429: surface, caller decides
        return {"_error": r.status_code, "_body": r.text[:500], "_url": r.url}


def paginate(path, params, items_key, cursor_param="next.value",
             max_pages=100000, page_pause=0.2):
    """Yield each page dict, following the `next` cursor via cursor_param."""
    params = dict(params or {})
    pages = 0
    while True:
        page = get(path, params)
        if isinstance(page, dict) and page.get("_error"):
            yield page
            return
        yield page
        pages += 1
        nxt = page.get("next")
        if not nxt or pages >= max_pages:
            return
        # if the page returned no items and no advancement, stop to avoid loop
        params[cursor_param] = nxt
        if page_pause:
            time.sleep(page_pause)


def eth_value(payment):
    """Return float token amount (in whole units) from a payment dict, or 0.0."""
    if not payment:
        return 0.0
    try:
        q = int(payment.get("quantity", 0))
        dec = int(payment.get("decimals", 18))
        return q / (10 ** dec)
    except (TypeError, ValueError):
        return 0.0


def is_ours(addr):
    return bool(addr) and addr.lower() in ADDR_SET
