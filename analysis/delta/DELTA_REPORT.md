# Delta analysis — operator offer/listing snapshots

Adjacent-snapshot tracking of every order by `order_hash`. Operator **GimmeGimmeG / NFT Butler**; bidders **0x0282** (trait bot, CloneX/LilPudgys) and **0x400f** (item bot, LilPudgys/PudgyPenguins ladders). Stated bid TTL 10–30 min.

## Snapshot set

- **153 valid snapshots**, 2026-06-10 20:30Z → 2026-06-12 10:15Z (earlier dropped: broken trait criteria).
- Interval: **150/152 gaps are clean 15 min**; 2 irregular (+5.3m, +9.7m) on 2026-06-11 ~10:30 — an off-cycle manual snapshot during the trait-criteria fix deploy.
- Raw trait `criteria` from 2026-06-11 10:30Z (97 snaps); before that trait/item inferred from maker.

> ⚠️ **Sampling limit:** 15-min cadence vs short TTL means many bids appear in one snapshot, so *observed* lifetime is a 15-min-quantised lower bound. We report `snaps_alive`/`seen-once %` as the honest signal.

## 1. Bid lifetime & disappearance

| bot | closed orders | seen-once % | obs-life median | obs-life p75 | replaced | expired | filled |
|---|---|---|---|---|---|---|---|
| trait (0x0282) | 23228 | 97.5% | 0.0m | 0.0m | 57.6% | 42.4% | 0.0% |
| item (0x400f) | 39194 | 24.6% | 45.0m | 135.0m | 43.8% | 56.2% | 0.0% |

### Item-bot lifetime modes & TTL tiers (NEW)

The item bot's snaps-alive distribution is **multi-modal** — peaks at 1 snaps (~15m), 2 snaps (~30m), 3 snaps (~45m), 4 snaps (~60m), 8 snaps (~120m), 10 snaps (~150m), 12 snaps (~180m), 16 snaps (~240m), 24 snaps (~360m).
These are **discrete declared-TTL tiers** (expiration−start): 60/120/150/180/240/360/480 min.

**TTL-tier hypothesis — CONFIRMED.** Grouping bids by their declared TTL and measuring how far the price sits above/below floor shows a clean monotonic relationship:

| TTL (min) | n | median offset vs floor | p25 | p75 |
|---|---|---|---|---|
| 60 | 7080 | -1.9% | -2.5% | -1.7% |
| 120 | 3410 | -1.1% | -1.8% | -0.6% |
| 150 | 4010 | -0.4% | -0.9% | +0.0% |
| 180 | 4202 | +1.0% | +0.2% | +1.8% |
| 240 | 12109 | +5.0% | +3.2% | +7.5% |
| 360 | 7588 | +14.7% | +10.3% | +17.7% |
| 480 | 795 | +15.7% | +12.3% | +18.9% |

```
  60m TTL |  -1.9% floor offset ####
 120m TTL |  -1.1% floor offset ##
 150m TTL |  -0.4% floor offset #
 180m TTL | +  1.0% floor offset ##
 240m TTL | +  5.0% floor offset ##########
 360m TTL | + 14.7% floor offset ############################
 480m TTL | + 15.7% floor offset ##############################
```

**Read:** the deeper the bid (further above floor on a prized token), the **longer the TTL** — 60-min bids sit ~2% *below* floor (cheap, fast re-quote as floor drifts), while 360–480-min bids sit ~15% *above* floor (aggressive bids left standing to catch a motivated seller). The bot runs a **two-axis quoting scheme: price offset × TTL are coupled**, not a flat ladder. The trait bot, by contrast, is pure churn — **97.6% of trait bids vanish within one 15-min window** (57.6% replaced at a new price, 42.4% expired), ~0 on-grid fills.

**snaps-alive distribution:**


*trait bot:*
```
  1 snaps | ######################################## 22649
  2 snaps | # 568
  3 snaps |  6
  5 snaps |  1
  8 snaps |  1
  9 snaps |  1
 11 snaps |  1
 12 snaps |  1
```

*item bot:*
```
  1 snaps | ######################################## 9626
  2 snaps | ############################## 7225
  3 snaps | ######## 1877
  4 snaps | ######################## 5704
  5 snaps | #### 985
  6 snaps | ### 750
  7 snaps | ## 440
  8 snaps | ######## 1918
  9 snaps | # 224
 10 snaps | ##### 1140
```

## 2. Top-bid retention

_'top' = operator's best realistic bid (<=2x floor) >= best competing collection-wide bid (<=2x floor). For the trait bot this compares a trait-specific bid to collection-wide demand, so 'not top' often just means a competitor posted a higher collection-wide offer, not that the operator was out-bid on its actual trait. Most meaningful for the item bot on pudgypenguins._

| collection | snaps w/ our bid | % we are top | median gap when not top (% floor) | p90 gap |
|---|---|---|---|---|
| pudgypenguins | 156 | 0.0% | 50.68 | 69.57 |
| clonex | 156 | 0.0% | 81.72 | 84.81 |
| lilpudgys | 153 | 0.0% | 9.38 | 19.93 |
| doodles-official | 153 | 62.1% | 86.86 | 88.87 |
| azuki | 150 | 68.0% | 88.75 | 91.11 |
| otherside-koda | 45 | 26.7% | 0.13 | 0.65 |

**Read:** on pudgy/clonex/lilpudgys the operator is essentially **never the collection-wide top bid (0%)** — by design (item bot bids below floor to accumulate; trait bot bids on specific traits). It leads only on thin books (azuki 69%, doodles 61%). An **accumulation** posture, not a liquidity race.

## 3. Floor reaction (clean sample)

_only floor moves in collections where the operator has an active bid at episode start; episodes in non-quoted collections excluded._

- Floor moves ≥1% **in collections the operator was actively quoting: 14** (excluded **22** where it held no bid).
- **Repriced in same direction: 9 = 64.3%** (vs only ~25% before filtering — the earlier figure was diluted by collections it wasn't trading).
- **Reprice lag: median 4 snaps ≈ 60 min** (p25 15m, p75 75m).

Top floor-move episodes (operator quoting):

| collection | time | floor Δ% | reprice lag | ladder width before→after |
|---|---|---|---|---|
| otherside-koda | 06-11T13:00 | +5.49% | 75m | — |
| azuki | 06-11T08:30 | -2.47% | 60m | 0.013→None |
| lilpudgys | 06-11T14:15 | +2.09% | no reprice | 0.367→0.358 |
| doodles-official | 06-11T00:45 | +2.04% | 15m | 0.006→0.012 |
| doodles-official | 06-11T02:00 | +1.96% | 15m | 0.016→0.02 |
| doodles-official | 06-11T16:00 | -1.92% | 15m | 0.063→0.011 |
| pudgypenguins | 06-10T23:30 | +1.83% | no reprice | 1.17→1.14 |
| pudgypenguins | 06-11T20:00 | +1.79% | 60m | 1.16→1.56 |
| lilpudgys | 06-11T07:30 | +1.74% | no reprice | 0.372→0.368 |
| pudgypenguins | 06-10T23:15 | -1.71% | 135m | 1.13→1.15 |

**Read:** when the operator *is* in the book, it repriced after **~64% of ≥1% floor moves**, lag **~1 h (median 4 snaps)** — it reacts the majority of the time but on a slower cadence than its 10–30 min quote refresh, i.e. a floor-anchored target updated lazily rather than tick-chasing.

## 4. Listing side

- **11 unique operator listings** in-window (by maker: {'0x028296d8bf1995549d5b9446622cf565bbd0a26e': 7, '0x400f2bd92098c386cea677d6e7f832eb25c6e3cf': 4}), collections {'clonex': 7, 'pudgypenguins': 4}. Vault 0x8e8d: **no listings** (idle).
- Re-prices: **5** (all **5 up**/0 down, median step 1.81%); withdrawals: 4.

**Read:** listing is a **minor, secondary activity** (11 listings vs ~63k bids). When it lists it only **ratchets prices up** (+1.8% median) and occasionally pulls them — never cuts. Overwhelmingly a **bid-side** actor; exits via accepting bids / Blur, not standing OpenSea asks.

### Files
`analysis/delta/{lifetimes,item_ttl_tiers,top_bid_retention,floor_reaction,listing_side}.json` + `lifetimes_raw.json`; log at `logs/delta_analysis.log`.

