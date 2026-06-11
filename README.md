# nftmm-data

Collected on-chain marketplace data for an **NFT market maker** — one operator
running three Ethereum addresses — for analysis. Sourced from the **OpenSea API v2**.

## Addresses (one operator)

| address | role |
|---|---|
| `0x028296d8bf1995549d5b9446622cf565bbd0a26e` | **trait-offer bot** (bids by rarity trait) |
| `0x400f2bd92098c386cea677d6e7f832eb25c6e3cf` | item-offer bot (per-token bidder) |
| `0x8e8d6246c45d0e7f68172e85573546d90fc2e062` | two-sided trader, idle since 2026-04-27 |

> **Trait-criteria correction (2026-06-11):** the first pass mislabeled
> `0x0282`'s 45k offers as collection-wide offers. They are in fact **trait
> offers** — the criterion lives in `criteria.traits` (a list) in the API
> wrapper and as a Seaport `consideration` item with `itemType 4` (a merkle
> root over the eligible token set). `snapshot.py` now stores the whole
> `criteria` object verbatim (plus the item-offer `asset` token id), and
> `discover.py` classifies trait vs collection vs item correctly. See
> `export/trait_analysis.md`.

## Collection window

- **Sales & transfers:** full available history (per address).
- **Offers & listings (`order` events):** **last 3 days only** — the bidder bots
  place thousands of offers per day, so deep offer history was intentionally bounded.
- Snapshot data: point-in-time, captured 2026-06-10.

## Contents

### `export/`
- `profile.json` — per-address aggregates, 41 collections, offer-kind shares, top-5 bid-price distributions.
- `bidder_stats.json` — per-bidder offer cadence, top-5 collection price clustering, hour-of-day histogram (UTC), inter-offer intervals (median/p10/p90).
- `events_hist_<slug>.json` — our events per top-10 collection (sale + order subtypes), one file each.
- `REPORT.md` — consolidated written report.
- `role_0x8e8d.md` — role analysis of the third address, with monthly buy/sell table.

### `snapshots/`
Three most recent 15-minute order-book snapshots: floor price, our active
offers/listings, and the top-20 competing bids per collection.

### Collection scripts (Python)
- `osea.py` — shared OpenSea API v2 client (auth via `OPENSEA_KEY` env, backoff, pagination).
- `discover.py` — per-address event collection → `profile.json`.
- `history.py` — per-collection event files for the top collections.
- `snapshot.py` — point-in-time order-book snapshot (run on a 15-min cron).

To run the scripts you need your own OpenSea API key in a local `.env`
(`OPENSEA_KEY=...`). **No key is included in this repo.**

## Source

All data is from `https://api.opensea.io/api/v2/` (Ethereum mainnet, OpenSea/Seaport).
