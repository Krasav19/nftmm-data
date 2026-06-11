# Mark-to-market of open inventory (at floor)

**Method:** MTM at collection floor (conservative, ignores trait premium). Floors from latest snapshot or /stats.
As of **2026-06-11**. **174 open lots** (all priced).

| metric | ETH |
|---|---|
| total entry cost | 755.6968 |
| total floor value (now) | 289.6389 |
| **unrealized P&L (at floor)** | **-466.0579** |

> **Floor verification (2026-06-11):** floors were cross-checked against live bottom
> listings — all real and current:
> - **degods-eth 0.17** ETH — confirmed (bottom listings 0.1700/0.1769); same contract
>   `0x8821bee2…cd280` in our sales, stats, and bids → **no slug/migration mismatch**.
>   The lone "5.8 ETH bid" is a single stale outlier; the real bid stack is
>   **0.14–0.16 ETH**, i.e. at floor. DeGods genuinely collapsed ~10 → 0.17 ETH;
>   the −262 ETH unrealized here is **real**, not an artifact.
> - bayc 8.96 (bottom listing 9.00), mayc 1.35 (1.37), doodles 0.50 (0.50) — all match.
>
> Floor MTM still ignores trait premium, so rare-trait lots may be marked slightly low,
> but the collection floors themselves are accurate.

## Unrealized P&L by collection (worst first)

| collection | lots | floor | entry cost | floor value | unrealized |
|---|---|---|---|---|---|
| degods-eth | 59 | 0.17 | 273.074 | 10.03 | -263.044 |
| pudgypenguins | 19 | 4.42495 | 163.002 | 84.0741 | -78.9279 |
| doodles-official | 12 | 0.4985 | 52.9446 | 5.982 | -46.9626 |
| boredapeyachtclub | 19 | 8.96 | 211.078 | 170.24 | -40.838 |
| mutant-ape-yacht-club | 3 | 1.3547 | 20.54 | 4.0641 | -16.4759 |
| lilpudgys | 16 | 0.474 | 14.2251 | 7.584 | -6.6411 |
| sappy-seals | 9 | 0.085 | 4.694 | 0.765 | -3.929 |
| y00ts-eth | 5 | 0.01 | 3.6169 | 0.05 | -3.5669 |
| azuki | 1 | 0.799 | 3.43 | 0.799 | -2.631 |
| persona | 12 | 0.02 | 2.31 | 0.24 | -2.07 |
| otherside-koda | 2 | 0.75 | 2.2 | 1.5 | -0.7 |
| the-dooplicator | 1 | 0.00798 | 0.31 | 0.008 | -0.302 |
| nftbutler | 1 | 0.63999 | 0.899 | 0.64 | -0.259 |
| zogz-editions-by-matt-furie | 2 | 0.00022 | 0.0051 | 0.0004 | -0.0046 |
| silks-genesis-avatars | 1 | 0.00066 | 0.0021 | 0.0007 | -0.0014 |
| clonex | 11 | 0.2888 | 3.105 | 3.1768 | 0.0718 |
| good-vibes-club | 1 | 0.4848 | 0.261 | 0.4848 | 0.2238 |

## Top-10 worst lots (drawdown at floor)

| collection:token | entry | floor | unrealized ETH | % |
|---|---|---|---|---|
| degods-eth:289 | 10.0503 | 0.17 | -9.8803 | -98.3% |
| degods-eth:8940 | 10.0 | 0.17 | -9.83 | -98.3% |
| degods-eth:152 | 10.0 | 0.17 | -9.83 | -98.3% |
| degods-eth:6353 | 9.869 | 0.17 | -9.699 | -98.3% |
| degods-eth:3973 | 9.85 | 0.17 | -9.68 | -98.3% |
| degods-eth:6404 | 9.17 | 0.17 | -9.0 | -98.1% |
| degods-eth:7819 | 8.9 | 0.17 | -8.73 | -98.1% |
| degods-eth:5005 | 8.81 | 0.17 | -8.64 | -98.1% |
| degods-eth:2043 | 8.73 | 0.17 | -8.56 | -98.1% |
| degods-eth:333 | 8.60499 | 0.17 | -8.43499 | -98.0% |

## Age distribution of open lots

| age bucket | lots | entry ETH |
|---|---|---|
| <30d | 16 | 9.7894 |
| 30-90d | 0 | 0 |
| 90-365d | 39 | 300.7967 |
| >365d | 119 | 445.1107 |
| unknown | 0 | 0 |

## Lots overlapping a Blur sell (likely already closed, not truly frozen)

**3 of 174 lots** share a token_id with a no-known-entry sell.

| collection:token | entry | blur sell(s) |
|---|---|---|
| degods-eth:9535 | 4.42 | 9.238@2023-06-15 |
| degods-eth:7060 | 8.16 | 8.58@2023-07-07 |
| pudgypenguins:7751 | 9.17 | 10.22@2025-03-24; 10.25@2025-03-27 |
