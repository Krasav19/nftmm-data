# Delta analysis — operator offer/listing snapshots

Adjacent-snapshot tracking of every order by `order_hash`. Operator **GimmeGimmeG / NFT Butler**; bidders **0x0282** (trait bot, CloneX/LilPudgys) and **0x400f** (item bot, LilPudgys/PudgyPenguins ladders). Stated bid TTL 10–30 min.

## Snapshot set

- **153 valid snapshots**, 2026-06-10 20:30Z → 2026-06-12 10:15Z (earlier dropped: broken trait criteria).
- Interval: **150/152 gaps are clean 15 min**; 2 irregular (+5.3m, +9.7m) on 2026-06-11 ~10:30 — an off-cycle manual snapshot during the trait-criteria fix deploy.
- Raw trait `criteria` present from 2026-06-11 10:30Z (97 snaps); before that trait/item is inferred from maker (context-confirmed: 0x0282=trait, 0x400f=item).

> ⚠️ **Sampling limit:** 15-min cadence vs 10–30 min TTL means most bids appear in only one snapshot, so *observed* lifetime is a 15-min-quantised lower bound. We therefore report `snaps_alive` and `seen-once %` as the honest lifetime signal.

## 1. Bid lifetime & disappearance

| bot | closed orders | seen-once % | obs-life median | obs-life p75 | replaced | expired | filled |
|---|---|---|---|---|---|---|---|
| trait (0x0282) | 22742 | 97.5% | 0.0m | 0.0m | 57.0% | 43.0% | 0.0% |
| item (0x400f) | 38377 | 24.6% | 45.0m | 135.0m | 43.7% | 56.3% | 0.0% |

**snaps-alive distribution** (how many consecutive 15-min snapshots a bid survived):


*trait bot:*
```
  1 snaps | ######################################## 22175
  2 snaps | # 556
  3 snaps |  6
  5 snaps |  1
  8 snaps |  1
  9 snaps |  1
 11 snaps |  1
 12 snaps |  1
```

*item bot:*
```
  1 snaps | ######################################## 9440
  2 snaps | ############################## 7088
  3 snaps | ######## 1865
  4 snaps | ######################## 5591
  5 snaps | #### 982
  6 snaps | ### 750
  7 snaps | ## 440
  8 snaps | ######## 1893
  9 snaps | # 224
 10 snaps | ##### 1132
```

**Read:** the trait bot is pure churn — **97.5% of trait bids vanish within one 15-min window**, 57% replaced by a fresh same-trait bid at a new price, 43% expire. The item bot is stickier: only 24.6% seen once, **median ~45 min alive**, p75 135 min — item ladders sit longer before being re-quoted. Neither shows OpenSea fills in-window (fills happen via bid-acceptance off the snapshot grid / on Blur).

## 2. Top-bid retention

_'top' = operator's best realistic bid (<=2x floor) >= best competing collection-wide bid (<=2x floor). For the trait bot this compares a trait-specific bid to collection-wide demand, so 'not top' often just means a competitor posted a higher collection-wide offer, not that the operator was out-bid on its actual trait. Most meaningful for the item bot on pudgypenguins._

| collection | snaps w/ our bid | % we are top | median gap when not top (% of floor) | p90 gap |
|---|---|---|---|---|
| pudgypenguins | 153 | 0.0% | 50.68 | 69.57 |
| clonex | 153 | 0.0% | 81.72 | 84.82 |
| lilpudgys | 150 | 0.0% | 9.38 | 19.96 |
| doodles-official | 150 | 61.3% | 86.86 | 88.87 |
| azuki | 147 | 68.7% | 88.75 | 91.11 |
| otherside-koda | 45 | 26.7% | 0.13 | 0.65 |

**Read:** on **pudgypenguins/clonex/lilpudgys the operator is essentially never the collection-wide top bid (0%)** — by design: the item bot bids *below floor* to accumulate cheap, and the trait bot bids on specific traits, so collection-wide whales sit above it. On thinner books (azuki 69%, doodles 61%) it does lead the realistic stack most of the time. This is an *accumulation* posture, not a top-of-book liquidity race.

## 3. Floor reaction

- Floor-move episodes ≥1% between snapshots: **36**; with a measurable operator reprice in the same direction: **9**.
- **Reprice lag: median 4 snaps ≈ 60 min** (p25 15m, p75 75m).

Top floor-move episodes:

| collection | time | floor Δ% | reprice lag | ladder width before→after |
|---|---|---|---|---|
| the-dooplicator | 06-12T09:30 | +18.38% | — | — |
| persona | 06-11T19:30 | +10.77% | — | — |
| persona | 06-11T21:00 | -9.72% | — | — |
| otherside-koda | 06-11T13:00 | +5.49% | 75m | — |
| sappy-seals | 06-11T19:30 | +5.48% | — | — |
| otherside-koda | 06-11T12:45 | -5.33% | — | — |
| moonbirds | 06-11T14:00 | +5.0% | — | — |
| moonbirds | 06-11T10:30 | +4.53% | — | — |
| moonbirds | 06-11T13:15 | -4.09% | — | — |
| degods-eth | 06-11T15:00 | +2.88% | — | — |

**Read:** the operator repriced after only ~25% of ≥1% floor moves, and when it did the **lag was ~1 hour (median 4 snaps)** — i.e. it does not chase every tick; it re-bases the ladder/trait bids on a slower cadence than its 10–30 min quote-refresh, consistent with a floor-anchored target that updates lazily.

## 4. Listing side

- **11 unique operator listings** in-window (by maker: {'0x028296d8bf1995549d5b9446622cf565bbd0a26e': 7, '0x400f2bd92098c386cea677d6e7f832eb25c6e3cf': 4}), collections {'clonex': 7, 'pudgypenguins': 4}. Vault 0x8e8d: **no listings** (idle).
- Re-prices: **5** (all **5 up** / 0 down, median step 1.81%); withdrawals (gone, no reprice): 4.

**Read:** listing is a **minor, secondary activity** (11 listings vs ~63k bids). When it does list (mostly clonex via 0x0282), it only **ratchets prices up** (+1.8% median) and occasionally pulls them — never cuts. The operator is overwhelmingly a **bid-side** actor; exits are via accepting bids / Blur, not via standing OpenSea asks.

### Files
`analysis/delta/{lifetimes,top_bid_retention,floor_reaction,listing_side}.json` + `lifetimes_raw.json`; log at `logs/delta_analysis.log`.

