# Role analysis — `0x8e8d6246c45d0e7f68172e85573546d90fc2e062`

**Verdict: independent two-sided trader, now paused (idle since 2026-04-27).**
Not a custody/storage wallet for the two bidder bots, not currently active.

## Evidence

- **1,365 events total**, all `sale`/`transfer` — **zero offers/listings**. It does not quote the book like the two bidder bots; it trades outright.
- **Activity span:** 2025-05-27 → 2026-04-27, then stops.
  - last **buy**: 2026-03-11 14:01 UTC
  - last **sell**: 2026-04-27 08:15 UTC
  - last **transfer**: 2026-04-27 08:15 UTC
- **No NFT transfers to/from the two bidder wallets** (0x0282, 0x400f) — checked both directions, all collections: **none**. So it is not a vault that receives inventory from the bots.
- **Flat net inventory:** transfer inflow − outflow is ~0 for every major collection (pudgypenguins 122 in / 122 out, lilpudgys 79/79, boredapeyachtclub 45/45, clonex 49/49, sappy-seals 44/44, moonbirds 7/7 …). Everything it bought, it sold. Only ~6 dust NFTs from random airdrops/mints linger (pixanimal20000, dragonegg-3, gold-of-earth-nft, poiuycat, zogz-editions). It **clears to ~zero holdings** → behaves like a trader flattening its book, not a holder.
- **Lifetime volume:** ≈ **1,075 ETH bought / 841 ETH sold** — a net accumulator over its life that then liquidated down to flat.

## Monthly activity (sales)

| month | buys | sells | buy ETH | sell ETH |
|---|---|---|---|---|
| 2025-05 | 3 | 2 | 12.08 | 11.86 |
| 2025-06 | 14 | 8 | 101.92 | 47.72 |
| 2025-07 | 10 | 1 | 95.49 | 11.20 |
| 2025-08 | 10 | 5 | 64.52 | 34.07 |
| 2025-09 | 55 | 39 | 212.26 | 140.25 |
| 2025-10 | 89 | 95 | 227.72 | 234.55 |
| 2025-11 | 2 | 1 | 5.61 | 0.29 |
| 2025-12 | 66 | 59 | 198.31 | 181.42 |
| 2026-01 | 26 | 23 | 42.34 | 43.86 |
| 2026-02 | 47 | 49 | 77.88 | 92.21 |
| 2026-03 | 12 | 17 | 37.10 | 42.54 |
| 2026-04 | 0 | 4 | 0.00 | 1.21 |

Peak two-sided trading in 2025-09/10 and 2025-12; buys stop after March 2026 and only residual sells remain in April → a **wind-down**, consistent with a trader pausing or retiring this wallet rather than a storage role.
