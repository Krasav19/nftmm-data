# Trait-offer analysis

Source: corrected `profile.json` + 3 snapshots (snap_2026-06-11T10-30-01Z.json, snap_2026-06-11T10-35-22Z.json, snap_2026-06-11T10-45-01Z.json).

After fixing trait-criteria extraction (`criteria.traits` list + Seaport `itemType 4` merkle root), the bidders classify as: **0x0282 = trait-offer bot**, **0x400f = item-offer bot**.


## Top-15 trait bids — lilpudgys  (floor median 0.474 ETH, 51 distinct traits)

| trait | #bids | min | median | max | % floor (min–max) |
|---|---|---|---|---|---|
| Body=Kimono Ice | 3 | 0.828 | 0.828 | 0.828 | 174.7–174.7% |
| Body=Kimono Gold | 3 | 0.797 | 0.797 | 0.797 | 168.1–168.1% |
| Head=Wizard Hat | 3 | 0.494 | 0.496 | 0.496 | 104.2–104.6% |
| Body=Pudgy Boy White | 3 | 0.49 | 0.49 | 0.49 | 103.4–103.4% |
| Body=Pudgy Boy Purple | 3 | 0.49 | 0.49 | 0.49 | 103.4–103.4% |
| Head=Flower Crown | 3 | 0.472 | 0.474 | 0.474 | 99.6–100.0% |
| Head=Biker Helmet | 3 | 0.471 | 0.471 | 0.471 | 99.4–99.4% |
| Head=Top Hat Gold | 3 | 0.462 | 0.462 | 0.464 | 97.5–97.9% |
| Head=Leaf Crown | 3 | 0.46 | 0.461 | 0.461 | 97.0–97.3% |
| Right Flipper=Plushie Gold | 3 | 0.46 | 0.461 | 0.461 | 97.0–97.3% |
| Left Flipper=Surfboard Yellow | 3 | 0.46 | 0.461 | 0.461 | 97.0–97.3% |
| Body=Gold Chain | 3 | 0.46 | 0.461 | 0.461 | 97.0–97.3% |
| Right Flipper=Plushie Ice | 3 | 0.46 | 0.461 | 0.461 | 97.0–97.3% |
| Head=Grizzly Bear Hat | 3 | 0.46 | 0.461 | 0.461 | 97.0–97.3% |
| Body=Tube Dino Green | 3 | 0.46 | 0.461 | 0.461 | 97.0–97.3% |

## Top-15 trait bids — clonex  (floor median 0.2888 ETH, 67 distinct traits)

| trait | #bids | min | median | max | % floor (min–max) |
|---|---|---|---|---|---|
| Mouth=ARMRD Mutant | 7 | 0.279 | 0.279 | 0.279 | 96.6–96.6% |
| Hair=Witch | 6 | 0.279 | 0.279 | 0.279 | 96.6–96.6% |
| Mouth=INFCTD | 4 | 0.279 | 0.279 | 0.279 | 96.6–96.6% |
| DNA=Angel | 3 | 0.317 | 0.317 | 0.317 | 109.8–109.8% |
| DNA=Demon | 3 | 0.289 | 0.293 | 0.293 | 100.1–101.5% |
| Hair=MEDUZA | 3 | 0.28 | 0.288 | 0.29 | 97.0–100.4% |
| Eyewear=RD LAZER | 3 | 0.286 | 0.286 | 0.288 | 99.0–99.7% |
| Back=Energy Wings | 3 | 0.284 | 0.285 | 0.285 | 98.3–98.7% |
| Clothing=DOODLE HOODIE | 3 | 0.283 | 0.285 | 0.285 | 98.0–98.7% |
| Clothing=PLASMA HOODIE | 3 | 0.28 | 0.281 | 0.281 | 97.0–97.3% |
| Clothing=CHRMO HOODIE | 3 | 0.28 | 0.281 | 0.281 | 97.0–97.3% |
| Back=DEMONZ | 3 | 0.28 | 0.281 | 0.281 | 97.0–97.3% |
| Hair=DRIP | 3 | 0.279 | 0.279 | 0.279 | 96.6–96.6% |
| Eyewear=BLU LAZER | 3 | 0.279 | 0.279 | 0.279 | 96.6–96.6% |
| Hair=GHOST PIRATE | 3 | 0.279 | 0.279 | 0.279 | 96.6–96.6% |

## Premium distribution — all trait bids vs floor

| bucket (% of floor) | #bids |
|---|---|
| <95% | 0 |
| 95-100% | 380 |
| 100-110% | 20 |
| 110-130% | 0 |
| 130-175% | 6 |
| >175% | 0 |

By collection:

| collection | 95-100% | 100-110% | 110-130% | 130-175% |
|---|---|---|---|---|
| lilpudgys | 132 | 13 | 0 | 7 |
| clonex | 240 | 11 | 0 | 2 |
| doodles-official | 140 | 6 | 0 | 2 |
| azuki | 140 | 6 | 0 | 2 |

## 0x400f item bids on pudgypenguins — token coverage

- **1755** active item bids covering **1226** unique token IDs.
- Price range **4.21–5.42 ETH** (median 4.67).
- **228** tokens are quoted at *multiple* prices (stacked/laddered bids on the same NFT); up to **12** bids on a single token.
- Example: token `7790` bid at [5.12, 5.13, 5.22, 5.31, 5.42] ETH simultaneously.

Interpretation: 0x400f targets **specific desirable pudgy token IDs** (1,226 of 8,888), not the collection floor — it ladders several bids per token to win at the lowest clearing price. 0x0282 instead bids by **trait** across lilpudgys/clonex, paying up to **1.75× floor** for rare traits (e.g. lilpudgys Body:Kimono Ice/Gold).

