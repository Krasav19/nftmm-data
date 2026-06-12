# Realized P&L — FIFO round-trip analysis

**Method:** FIFO buy->sell match by (address,collection,token); ETH/WETH/Blur-Pool treated 1:1 ETH; transfers ignored.
Data through **2026-06-09**. 2076 sale events → **874 closed round-trips**.

> ⚠️ **Gross P&L** (sell − buy). Does **not** deduct gas or marketplace/royalty fees, so true net is lower. Prices in ETH, WETH and Blur-Pool are treated 1:1 ETH; transfers (no price) are not trades.

## 1. By window (window = sale date)

| window | round-trips | realized P&L (ETH) | win rate | median/trip | mean/trip |
|---|---|---|---|---|---|
| 7d | 40 | 3.993 | 80.0% | 0.0205 | 0.09983 |
| 30d | 79 | 4.9677 | 82.3% | 0.022 | 0.06288 |
| 90d | 198 | 8.9269 | 83.8% | 0.02225 | 0.04509 |
| 365d | 741 | 16.8804 | 66.8% | 0.01 | 0.02278 |
| all | 874 | 21.2179 | 67.3% | 0.01105 | 0.02428 |

**Best / worst trade per window:**

| window | best (token / in→out / P&L) | worst |
|---|---|---|
| 7d | pudgypenguins:1453 4.28→7.0 (**+2.72**) | lilpudgys:530 1.11→0.99 (**-0.12**) |
| 30d | pudgypenguins:1453 4.28→7.0 (**+2.72**) | azuki:759 1.08→0.96 (**-0.12**) |
| 90d | pudgypenguins:1453 4.28→7.0 (**+2.72**) | boredapeyachtclub:6737 5.63→5.2 (**-0.43**) |
| 365d | pudgypenguins:1453 4.28→7.0 (**+2.72**) | pudgypenguins:1192 8.97→7.738 (**-1.232**) |
| all | pudgypenguins:7105 8.48→11.48 (**+3.0**) | degods-eth:1580 6.86→4.55 (**-2.31**) |

## 2. By collection (all history)

| collection | trips | realized P&L (ETH) | win rate | median hold (h) |
|---|---|---|---|---|
| pudgypenguins | 223 | 13.0613 | 66.8% | 16.06 |
| doodles-official | 27 | 4.123 | 85.2% | 7.48 |
| boredapeyachtclub | 18 | 3.565 | 83.3% | 1.91 |
| lilpudgys | 222 | 2.6256 | 70.7% | 7.4 |
| clonex | 216 | 1.0901 | 64.8% | 26.18 |
| azuki | 11 | 0.507 | 81.8% | 6.39 |
| the-dooplicator | 16 | 0.4221 | 75.0% | 52.14 |
| y00ts-eth | 1 | 0.38 | 100.0% | 14.72 |
| good-vibes-club | 2 | 0.147 | 100.0% | 67.59 |
| otherside-koda | 1 | 0.103 | 100.0% | 24.54 |
| moonbirds | 9 | 0.055 | 77.8% | 2.11 |
| persona | 2 | 0.0476 | 100.0% | 245.07 |
| gemesis | 1 | -0.0001 | 0.0% | 0.12 |
| mrfreeman | 1 | -0.0004 | 0.0% | 0.01 |
| bitmappunks | 12 | -0.0023 | 8.3% | 2356.72 |
| normies | 2 | -0.0253 | 50.0% | 168.17 |
| sappy-seals | 49 | -0.156 | 49.0% | 39.48 |
| degods-eth | 52 | -2.0542 | 75.0% | 16.63 |
| mutant-ape-yacht-club | 9 | -2.6705 | 55.6% | 6.9 |

## 3. By address

| address | trips | realized P&L (ETH) | win rate | median/trip |
|---|---|---|---|---|
| 0x028296d8bf1995549d5b9446622cf565bbd0a26e (0x0282a26e) | 309 | -1.8402 | 67.3% | 0.014 |
| 0x8e8d6246c45d0e7f68172e85573546d90fc2e062 (0x8e8de062) | 292 | 3.5429 | 63.0% | 0.008 |
| 0x400f2bd92098c386cea677d6e7f832eb25c6e3cf (0x400fe3cf) | 273 | 19.5152 | 71.8% | 0.0171 |

## 4. Unclosed inventory (bought, not yet sold)

**174 lots, 755.6968 ETH frozen at entry cost.**

| collection | lots | frozen ETH (entry) |
|---|---|---|
| degods-eth | 59 | 273.074 |
| boredapeyachtclub | 19 | 211.078 |
| pudgypenguins | 19 | 163.002 |
| doodles-official | 12 | 52.9446 |
| mutant-ape-yacht-club | 3 | 20.54 |
| lilpudgys | 16 | 14.2251 |
| sappy-seals | 9 | 4.694 |
| y00ts-eth | 5 | 3.6169 |
| azuki | 1 | 3.43 |
| clonex | 11 | 3.105 |
| persona | 12 | 2.31 |
| otherside-koda | 2 | 2.2 |
| nftbutler | 1 | 0.899 |
| the-dooplicator | 1 | 0.31 |
| good-vibes-club | 1 | 0.261 |
| zogz-editions-by-matt-furie | 2 | 0.0051 |
| silks-genesis-avatars | 1 | 0.0021 |

## 5. Sells without known entry (bought off-platform, e.g. Blur)

_NFT bought outside captured history (e.g. on Blur) — entry price unknown, EXCLUDED from P&L._

**132 sells, 383.6437 ETH sell volume — EXCLUDED from P&L above.**

| collection | sells | sell volume (ETH) |
|---|---|---|
| pudgypenguins | 23 | 178.771 |
| degods-eth | 23 | 155.015 |
| doodles-official | 6 | 23.16 |
| boredapeyachtclub | 1 | 11.2 |
| mutant-ape-yacht-club | 2 | 10.94 |
| lilpudgys | 3 | 4.148 |
| clonex | 1 | 0.33 |
| bitmappunks | 73 | 0.0797 |

---

## 6. Blur entry backfill (on-chain, Blur API pending)

The Blur API request is still pending, so the entry leg of the 132 unmatched sells was reconstructed **on-chain** via a public Ethereum RPC: OpenSea reports Blur/non-OS fills only as price-less `transfer`s, so for each token we pulled the inbound-transfer transaction and summed ETH+WETH+BETH (Blur Pool) paid by our wallet = the true entry price.

| metric | value |
|---|---|
| entries recovered | **44** of 132 |
| recovered sell volume | 292.41 ETH |
| recovered round-trip P&L (gross) | **+1.212 ETH** |
| venue: BlurExchangeV2 + BlurPool | 36 |
| venue: Blur router (BETH/WETH flow) | 8 |
| **combined realized (OpenSea + Blur)** | **918 trips, +22.4299 ETH** |

**Residual blind spot (now small):**
- 88 sells still unpriced, but **73 are dust** (mostly bitmappunks ~0.0001 ETH floor — mints/free transfers, not Blur buys).
- Only **15 non-dust sells / 91.15 ETH** remain unattributed: inbound transfer carried 0 on-chain ETH/WETH/BETH (cross-wallet moves, claims, or acquisitions before our event window).

**Read:** the Blur leg is **roughly break-even** (+1.21 ETH over 44 round-trips) — it does not hide large profits or losses (one −8.29 ETH degods outlier aside). The earlier "384 ETH of unattributable Blur sells" is now **closed to ~91 ETH of non-dust residual**, mostly long-held legacy degods, not the active loop.

