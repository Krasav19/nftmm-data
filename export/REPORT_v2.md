# NFT Market Maker — active-loop report (v2)

**Focus:** the *operating* market-making loop — a 90-day window (sales since **2026-03-11**), the 3-day offer book, and live snapshots. Legacy inventory (lots older than 90 days) is summarised in one paragraph at the end.

> **Scope caveat (applies throughout):** all figures are the **OpenSea side only**. This operator also trades on **Blur**, which is not visible here. Round-trips whose buy or sell happened on Blur are incomplete, so any statement about *total* economics is premature. Treat P&L as OpenSea-attributable, gross of gas/fees.

## 1. Active profile — 90 days, by month

| month | round-trips | realized P&L (ETH) | win rate | median/trip (ETH) | median hold (h) |
|---|---|---|---|---|---|
| 2026-03 | 37 | 0.197 | 64.9% | 0.0087 | 46.88 |
| 2026-04 | 62 | 3.0109 | 93.5% | 0.02535 | 77.3 |
| 2026-05 | 56 | 1.675 | 87.5% | 0.0225 | 10.82 |
| 2026-06 | 43 | 4.044 | 81.4% | 0.02 | 14.75 |
| **90d total** | **198** | **8.9269** | — | — | — |

Trend: activity is steady (~40–60 trips/mo) and **consistently profitable** — win rate stepped up from 65% (Mar) to 80–94% (Apr–Jun), with short holds (10–77h median). This is a live, working loop, not a wind-down.

## 2. Which collections work *now* (90d) vs what died

**Active (traded in last 90d):**

| collection | 90d trips | 90d P&L (ETH) | 90d win | all-time trips | all-time P&L |
|---|---|---|---|---|---|
| lilpudgys | 82 | 1.9167 | 89.0% | 222 | 2.6256 |
| clonex | 66 | 1.04 | 80.3% | 216 | 1.0901 |
| pudgypenguins | 32 | 5.328 | 81.2% | 223 | 13.0613 |
| azuki | 9 | 0.287 | 77.8% | 11 | 0.507 |
| boredapeyachtclub | 3 | 0.09 | 66.7% | 18 | 3.565 |
| doodles-official | 2 | 0.048 | 100.0% | 27 | 4.123 |
| degods-eth | 2 | 0.0072 | 50.0% | 52 | -2.0542 |
| otherside-koda | 1 | 0.103 | 100.0% | 1 | 0.103 |
| good-vibes-club | 1 | 0.107 | 100.0% | 2 | 0.147 |

**Dropped (no trades in 90d) — now legacy only:** sappy-seals (all-time -0.16 ETH, 49 trips), the-dooplicator (all-time +0.42 ETH, 16 trips), bitmappunks (all-time -0.00 ETH, 12 trips), mutant-ape-yacht-club (all-time -2.67 ETH, 9 trips), moonbirds (all-time +0.06 ETH, 9 trips), persona (all-time +0.05 ETH, 2 trips), normies (all-time -0.03 ETH, 2 trips), mrfreeman (all-time -0.00 ETH, 1 trips), y00ts-eth (all-time +0.38 ETH, 1 trips), gemesis (all-time -0.00 ETH, 1 trips).

The live loop has **narrowed to 3 core names** — lilpudgys, clonex, pudgypenguins (~90% of 90d trips) — plus occasional azuki/bayc/doodles. Once-meaningful books (mutant-ape, sappy-seals, bitmappunks, the-dooplicator, moonbirds) are **inactive**; their all-time P&L is now frozen history, not current activity.

## 3. Active quoting loop (3-day offers + snapshots)

Two automated bots quote continuously on OpenSea/Seaport:

- **0x0282 — trait-offer bot:** 45,632 trait bids in 3 days; **median 1 s** between offers (p90 11 s). Bids by rarity trait on lilpudgys & clonex.
- **0x400f — item-offer bot:** 76,744 per-token bids in 3 days; **median 2 s** (p90 6 s). Ladders multiple bids on specific pudgypenguins token IDs (1,226 unique tokens, 228 quoted at several prices at once).
- **Order TTL ≈ 4 h** (median 14,400 s; range 15 min–8 h) — quotes are short-lived and constantly refreshed.

**Trait bids vs floor** (premium buckets): 380 at 95–100%, 20 at 100–110%, 6 at 130–175% of floor. The bot sits **at/just-below floor on common traits** and pays a steep premium only on rare ones (e.g. lilpudgys Body:Kimono Ice/Gold ≈1.7× floor). See `export/trait_analysis.md`.

**Item bids (pudgy):** 1755 live bids over 1226 tokens, 4.21–5.42 ETH (median 4.67), 228 tokens laddered at multiple prices.

## 4. Blur blind-spot in the fresh window

Of **203 OpenSea sell legs in the last 90d**, **5** (2.5%) have **no visible buy** — the entry was on Blur. That's **22.498 ETH** of sells we can't pair.

So in the *current* loop the blind zone is small (2.5%); the large unattributable Blur flow is mostly **historical**. Still, even 2.5% means the live-loop P&L is a lower bound.

| collection | unpaired sells | volume ETH |
|---|---|---|
| pudgypenguins | 5 | 22.498 |

## 5. Fresh working inventory (<90d)

**16 lots, 9.7894 ETH at entry, +0.0788 ETH unrealized at floor** — essentially flat. This is the real active book: small, near floor, fast-turning.

| buy date | collection:token | addr | entry | floor | unrealized |
|---|---|---|---|---|---|
| 2026-06-04 | clonex:19543 | 0x0282a26e | 0.342 | 0.28879998 | -0.0532 |
| 2026-06-04 | clonex:4248 | 0x0282a26e | 0.342 | 0.28879998 | -0.0532 |
| 2026-06-04 | clonex:1798 | 0x0282a26e | 0.342 | 0.28879998 | -0.0532 |
| 2026-06-09 | clonex:11598 | 0x0282a26e | 0.301 | 0.28879998 | -0.0122 |
| 2026-06-09 | clonex:15474 | 0x0282a26e | 0.292 | 0.28879998 | -0.0032 |
| 2026-06-09 | clonex:7864 | 0x0282a26e | 0.288 | 0.28879998 | +0.0008 |
| 2026-06-08 | clonex:6080 | 0x0282a26e | 0.283 | 0.28879998 | +0.0058 |
| 2026-06-08 | clonex:7844 | 0x0282a26e | 0.282 | 0.28879998 | +0.0068 |
| 2026-06-09 | lilpudgys:2152 | 0x0282a26e | 0.4529 | 0.474 | +0.0211 |
| 2026-06-09 | lilpudgys:17575 | 0x400fe3cf | 0.4525 | 0.474 | +0.0215 |
| 2026-06-09 | lilpudgys:9723 | 0x0282a26e | 0.452 | 0.474 | +0.022 |
| 2026-06-07 | clonex:18878 | 0x0282a26e | 0.265 | 0.28879998 | +0.0238 |
| 2026-06-05 | lilpudgys:2924 | 0x400fe3cf | 0.45 | 0.474 | +0.024 |
| 2026-06-08 | lilpudgys:13844 | 0x0282a26e | 0.44 | 0.474 | +0.034 |
| 2026-06-09 | pudgypenguins:47 | 0x400fe3cf | 4.38 | 4.424955 | +0.044955 |
| 2026-06-08 | lilpudgys:18801 | 0x400fe3cf | 0.425 | 0.474 | +0.049 |

## Legacy inventory (older than 90 days) — context, not focus

Separately, **158 lots bought >90 days ago** carry **~-466.14 ETH** of unrealized loss at floor — overwhelmingly **degods-eth (~−262 ETH, 2023 buys ~10 ETH, floor 0.17)** and **bayc (~−41 ETH)**. Floors were verified against live listings (degods 0.17 confirmed, same contract — no migration artifact). This is stranded long-term bags from an earlier strategy, unrelated to the current quoting loop, and is **not marked to Blur or to bid** — so the headline number is a conservative worst case.

## 6. Data limitations (read before drawing conclusions)

- **OpenSea-only.** Blur (a primary venue for this operator) is invisible. ~2.5% of 90d sells and a large share of historical sells have no paired entry. Cross-venue net is unknown.
- **Gross P&L.** No gas, marketplace, or royalty fees deducted; net is lower.
- **Offer history = last 3 days only** (the bots place thousands/day). Sales/transfers are full history.
- **MTM at floor**, ignoring trait premium and using OpenSea floor; a worst-case mark, not fair value.
- **FIFO matching** by (address, collection, token): re-buys of the same token pair oldest-buy→sell; the leftover lot stays open (correct, but means 'open inventory' can include economically-closed positions — 3 such Blur overlaps found).
- **WETH / ETH / Blur-Pool treated 1:1**; non-ETH-denominated sales (rare) are excluded.

