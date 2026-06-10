# NFT Market-Maker — data collection report

**Operator:** one entity running three Ethereum addresses
**Source:** OpenSea API v2 (`https://api.opensea.io/api/v2/`), spec pinned in `openapi.json`
**Data range:** 2023-05-04 → 2026-06-09 (sales/transfers full history; **offers/listings limited to the last 3 days** by design)
**Report generated:** 2026-06-10

## Addresses & roles

| address | short | role | events captured |
|---|---|---|---|
| `0x028296d8bf1995549d5b9446622cf565bbd0a26e` | 0x0282a26e | **collection-offer bot** (high-freq bidder) | 47,429 |
| `0x400f2bd92098c386cea677d6e7f832eb25c6e3cf` | 0x400fe3cf | **item-offer bot** (per-token bidder) | 78,247 |
| `0x8e8d6246c45d0e7f68172e85573546d90fc2e062` | 0x8e8de062 | **two-sided trader, now paused** (idle since 2026-04-27) | 1,365 |

See `role_0x8e8d.md` for the full role analysis of the third address.

## Events found per address

| address | order | sale | transfer | total | active range |
|---|---|---|---|---|---|
| 0x0282a26e | 45,656 | 773 | 1,000 | 47,429 | 2023-05-04 → 2026-06-09 |
| 0x400fe3cf | 76,761 | 668 | 818 | 78,247 | 2024-03-01 → 2026-06-09 |
| 0x8e8de062 | 0 | 637 | 728 | 1,365 | 2025-05-27 → 2026-04-27 |

> `order` events are offers/listings and were collected only for the **last 3 days** (the bidders place thousands per day). `sale`/`transfer` are full history.

## Order/offer kind distribution (all order events)

| kind | count | share |
|---|---|---|
| item_offer | 76,747 | 62.7% |
| collection_offer | 45,639 | 37.3% |
| listing | 31 | 0.0% |
| trait_offer | 0 | 0.0% |

The two bidders specialise: **0x0282 → collection offers** (45,637), **0x400f → item offers** (76,744). Listings are negligible — this operator is a **buy-side liquidity provider** (it bids the book), not a seller-side lister.

## Bidder cadence (from `bidder_stats.json`)

| bidder | orders | dominant kind | median gap between offers | p10 / p90 gap |
|---|---|---|---|---|
| 0x0282a26e | 45,656 | collection_offer | **1 s** | 0 s / 11 s |
| 0x400fe3cf | 76,761 | item_offer | **2 s** | 0 s / 6 s |

Both are automated high-frequency quoting bots (sub-second to a few seconds between offers).

## Collections with trades (top by total events)

| collection | events | offers | sales | buy | sell | volume ETH |
|---|---|---|---|---|---|---|
| pudgypenguins | 77,800 | 76,749 | 489 | 243 | 246 | 2,808.1 |
| lilpudgys | 952 | 13 | 463 | 238 | 225 | 303.6 |
| clonex | 906 | 11 | 445 | 228 | 217 | 129.7 |
| degods-eth | 488 | 0 | 186 | 111 | 75 | 1,071.9 |
| bitmappunks | 321 | 0 | 97 | 12 | 85 | 0.1 |
| sappy-seals | 223 | 0 | 107 | 58 | 49 | 37.9 |
| doodles-official | 172 | 0 | 72 | 39 | 33 | 242.7 |
| boredapeyachtclub | 154 | 0 | 56 | 37 | 19 | 495.3 |
| the-dooplicator | 67 | 0 | 33 | 17 | 16 | 6.5 |
| mutant-ape-yacht-club | 53 | 0 | 23 | 12 | 11 | 115.8 |

(41 collections total in `profile.json`; full top-20 there.)

## Marketplaces

All activity is on **OpenSea / Seaport** (Ethereum mainnet). Protocol contracts seen in the data: Seaport 1.6 (`0x0000…eb395`) plus older Seaport versions on historical fills. No non-OpenSea venues appear in the OpenSea-sourced events.

## Order events by type, top-10 collections (from `events_hist_*.json`)

| collection | sale | order:item_offer | order:collection_offer | order:listing |
|---|---|---|---|---|
| pudgypenguins | 487 | 76,744 | 0 | 5 |
| lilpudgys | 439 | 1 | 0 | 12 |
| clonex | 437 | 1 | 0 | 10 |
| degods-eth | 182 | 0 | 0 | 0 |
| sappy-seals | 99 | 0 | 0 | 0 |
| doodles-official | 71 | 0 | 0 | 0 |
| boredapeyachtclub | 56 | 0 | 0 | 0 |
| bitmappunks | 24 | 0 | 0 | 0 |
| the-dooplicator | 23 | 0 | 0 | 0 |
| mutant-ape-yacht-club | 23 | 0 | 0 | 0 |

> Note: the OpenSea events API exposes order subtypes as `event_type=order` with an `order_type` field; the request enum has no literal `order` (it is `listing`/`offer`/`collection_offer`/`trait_offer`/`sale`/`transfer`). `order_created` vs `order_cancelled` is not separable from this endpoint — it returns active/known orders, not a created/cancelled stream. Cancellations are therefore not represented; only placed orders (offers/listings) and fills (sales) are.

## Bid-price clustering (the MM's quoting levels)

- **pudgypenguins** (76,744 priced bids): min 3.44 / median **4.44** / max 5.53 ETH; tightly stacked around 4.2–4.5 (e.g. 4.40×3022, 4.25×1924, 4.21×1898). This is a laddered bid wall just under floor (floor ≈ 4.37–4.45 in snapshots).
- Other collections have far fewer standing priced bids in the 3-day window. Full per-collection price→frequency tables are in `bidder_stats.json`.

## Strategy read

Classic **bid-side market making**: two bots blanket the top collections with offers (one collection-wide, one per-item) priced a few percent under floor, get filled, and re-sell slightly higher hours later. The token cross-check (20/21 sample tokens found) shows the buy-low/sell-higher loop directly — e.g. `lilpudgys:10982` bought 0.430 → sold 0.4565; `boredapeyachtclub:9816` bought 8.44 → sold 8.69; `good-vibes-club:3299` bought 0.408 → sold 0.515. The third wallet (0x8e8d) ran a separate two-sided trading book and has gone idle.

## Live snapshots

`snapshot.py` runs every 15 min via cron, writing `snapshots/snap_<UTC_ISO>.json` (floor + our active offers/listings + top-20 competing bids per collection). Verified running at ~2 min/run with no rate-limiting on the portal key.

```
*/15 * * * * /home/jenya/nftmm/venv/bin/python /home/jenya/nftmm/snapshot.py >> /home/jenya/nftmm/snap.log 2>&1
```

## File index

- `profile.json` — per-address aggregates, 41 collections, offer-kind shares, top-5 bid distributions
- `events_hist_<slug>.json` — our events per top-10 collection (hole-free, from per-address capture)
- `bidder_stats.json` — per-bidder offer cadence, price clustering, hour-of-day histogram, inter-offer intervals
- `role_0x8e8d.md` — role analysis of the third address
- `snapshots/snap_*.json` — 15-min order-book snapshots
- `data/events_<address>.jsonl` — raw per-address event stream (resumable source of truth)
