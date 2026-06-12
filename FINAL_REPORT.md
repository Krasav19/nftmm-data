# NFT Market Maker — final report

**Operator:** GimmeGimmeG / NFT Butler, running three Ethereum wallets.
**Data:** OpenSea API v2 (Ethereum mainnet). Full sale/transfer history; offers
limited to a 3-day pull; **153 order-book snapshots** every 15 min
(2026-06-10 20:30Z → 2026-06-12 10:15Z) for delta analysis.

> **Scope & limits (read first).** Everything here is the **OpenSea side only**.
> The operator also trades on **Blur**, which is invisible to this data — in the
> live 90-day window **2.5% of sells have no visible buy** (Blur entries), and the
> historical share is much larger. P&L is **gross** of gas/fees. A **legacy bag of
> −466 ETH unrealized** (mostly 2023 DeGods/BAYC) sits outside the active loop and
> is treated as context, not the operating business. Treat all economics as
> OpenSea-attributable lower bounds, not a closed cross-venue ledger.

Backing detail: `export/REPORT_v2.md` (active-loop), `export/pnl.md`,
`export/mtm.md`, `export/trait_analysis.md`, `analysis/delta/DELTA_REPORT.md`.

---

## 1. Collections

41 collections touched lifetime; the **live loop has narrowed to 3 core names**
(≈90% of 90-day round-trips):

| collection | 90d trips | 90d P&L (ETH) | role now |
|---|---|---|---|
| lilpudgys | 82 | +1.92 | active (trait + item bids) |
| clonex | 66 | +1.04 | active (trait bids + the only listings) |
| pudgypenguins | 32 | +5.33 | active (item-bid ladders) |
| azuki / bayc / doodles | 2–9 | small + | occasional |

**Dead/legacy (0 trades in 90d):** mutant-ape, sappy-seals, bitmappunks,
the-dooplicator, moonbirds, y00ts, persona, normies — once-active books now frozen.

## 2. Marketplaces

**OpenSea / Seaport** for bids/listings (protocol `0x0000…eb395` = Seaport 1.6).
**Blur is the second venue** — and its trade leg has now been **closed on-chain**
(`blur_backfill.py`, Blur API still pending). Of the 132 OpenSea-exit-only sells,
**44 entries were recovered via the inbound-transfer transaction** (36 explicitly
**BlurExchangeV2 + Blur Pool / BETH**, 8 via a Blur router with BETH/WETH flow),
confirming Blur Exchange v2 + Blend-era settlement. Residual unattributed:
**15 non-dust sells / 91 ETH** (inbound transfer with 0 on-chain payment — cross-
wallet/claims/pre-window) plus 73 bitmappunks dust. So the venue set is **OpenSea +
Blur**, and the cross-venue blind spot is now ~91 ETH (mostly legacy degods), down
from the earlier 384 ETH.

## 3. Bid frequency, cancellations, lifetime, sizing

From the 3-day offer pull + 153 snapshots (`DELTA_REPORT.md`):

- **Frequency:** two always-on bots. **0x0282 trait bot** — 45,632 trait offers in
  3 days, **median 1 s** between offers (p90 11 s). **0x400f item bot** — 76,744
  per-token offers, **median 2 s** (p90 6 s).
- **Lifetime / cancellation (real, measured):** trait bids are pure churn —
  **97.5% vanish within one 15-min snapshot** (TTL 10–30 min, sub-sampled),
  **57% replaced** by a fresh same-trait bid at a new price, **43% expired**, ~0%
  filled on-grid. Item bids are stickier — **median ~45 min alive**, p75 135 min,
  only 24.6% seen once. So the trait bot re-quotes far more aggressively than the
  item bot.
- **Sizing:** trait bot bids **at/just-below floor on common traits, up to ~1.75×
  floor on rare ones** (e.g. LilPudgys Body:Kimono Ice/Gold). Item bot bids
  **below floor** across **1,226 unique pudgy tokens (4.21–5.42 ETH)**, with **228
  tokens laddered at several prices at once** — accumulation, not top-of-book.

## 4. Strategy classification

**Bid-side trait/item market making with an accumulation tilt.** It blankets a few
collections with thousands of short-TTL offers, buys at-or-below floor, and re-sells
modestly higher hours later (median hold 10–77 h in the active window). It is **not**
a top-of-book liquidity race: on pudgy/clonex/lilpudgys it is essentially **never the
collection-wide top bid (0%)** — it sits below whales/collection offers by design;
it only leads the realistic stack on thin books (azuki 69%, doodles 61%).

## 5. Listing behaviour

Listing is **secondary** (11 unique operator listings vs ~63k bids in-window, mostly
clonex via 0x0282; vault 0x8e8d never lists). When it lists it **only ratchets price
up (+1.8% median, 0 down-cuts)** and occasionally withdraws. Exits are predominantly
via **accepting bids / Blur**, not standing OpenSea asks.

## 6. Floor reaction & risk management

- **Reaction lag (clean sample):** of 36 floor moves ≥1%, **22 were in collections
  the operator wasn't quoting** and are excluded. On the **14 episodes where it held
  an active bid, it repriced in the same direction ~64%** of the time, **lag ~1 h
  (median 4 snapshots)** — it re-bases bids on a slower cadence than its 10–30 min
  quote refresh, i.e. a floor-anchored target updated lazily rather than tick-chasing.
  (The unfiltered 25% figure was diluted by collections it doesn't trade.)
- **Risk posture:** active book is **small and near-flat** — 16 fresh (<90 d) lots,
  9.8 ETH at entry, **+0.08 ETH unrealized**. Short holds, sub-floor entries, and
  trait premiums only on rares are all conservative. **The risk that did blow up was
  legacy directional holding**, not the MM loop (see §9).

## 7. Bot architecture (reconstructed, with real timings)

- **Two independent quoting engines**, one per wallet, each Seaport-based:
  - *Trait engine (0x0282):* enumerates traits per collection (CloneX, LilPudgys),
    posts one collection-criteria offer per trait, **short TTL**, **replace cycle
    fast** (57.6% of bids replaced same-trait at a new price; 1 s inter-offer
    spacing → a full trait sweep posts in seconds). 97.6% of trait bids turn over
    inside one 15-min snapshot.
  - *Item engine (0x400f):* enumerates desirable token IDs on PudgyPenguins/
    LilPudgys, posts **laddered per-token bids** (228 tokens multi-priced), 2 s
    spacing — and runs a **coupled price×TTL scheme** (below):
- **TTL tiers (measured, new).** The item bot uses **discrete TTL tiers
  (60/120/150/180/240/360/480 min)**, and TTL scales **monotonically with how far
  above floor the bid sits**:

  | TTL | median offset vs floor |
  |---|---|
  | 60 min | −1.9% (below floor) |
  | 150 min | −0.4% |
  | 240 min | +5.0% |
  | 360–480 min | +14.7% / +15.7% |

  So cheap near-floor bids get **short TTL** (re-quoted fast as the floor drifts),
  while aggressive above-floor bids on prized tokens get **long TTL** (left standing
  to catch a motivated seller). This is a deliberate **two-axis quoting design**, not
  a flat ladder — the snaps-alive distribution is multi-modal with peaks at exactly
  these tiers.
- **Refresh, not chase:** bids re-post on a fixed short timer (replace/expire
  dominate; ~0 in-grid fills), while *price* re-basing to floor is lazier. When the
  operator is actually quoting a collection, it repriced after **~64% of ≥1% floor
  moves at ~1 h lag** (median 4 snaps) — reactive, but slower than its quote-refresh
  cadence. Classic "cancel-and-replace on a timer, re-anchor on floor drift" loop.

## 8. Wallet roles

| wallet | role |
|---|---|
| `0x028296…a26e` | **trait-offer bot** — 45.6k trait bids, CloneX/LilPudgys; the only lister |
| `0x400f2b…e3cf` | **item-offer bot** — 76.7k per-token ladder bids, Pudgy/LilPudgys |
| `0x8e8d62…e062` | **vault / two-sided trader, idle since 2026-04-27** — flat net inventory, **no NFT transfers shared with the bidder bots**, never lists; a separate book, not the bots' custody |

## 9. P&L

**Realized (FIFO, OpenSea, gross):**

| window | round-trips | realized P&L | win rate |
|---|---|---|---|
| 90 d (active) | 198 | **+8.93 ETH** | 67% → rising to 80–94% by month |
| all history (OpenSea) | 874 | **+21.22 ETH** | 67.3% |
| **+ Blur entries backfilled** | **918** | **+22.43 ETH** | — |

By bot: **0x400f +19.5 ETH (71.8% win)** is the engine; 0x8e8d +3.5; **0x0282 −1.8**
(wins often, tiny margins). Top trade +3.0 ETH (pudgy 7105 8.48→11.48); worst −2.31
(degods 1580).

**Hypothesis — 0x0282 (trait bot) is not a standalone profit centre.** On the
OpenSea-visible data it is **−1.8 ETH realized with ~0% on-grid fills** despite
45.6k trait bids — i.e. its economics don't close on OpenSea. Two readings, both
consistent with the data:
1. **Blur-closed economics** — the trait bot's fills/exits happen on Blur (invisible
   here), so its true P&L is unmeasured rather than negative. The 2.5% live / large
   historical Blur blind spot sits exactly where its missing fills would be.
2. **Accumulation feeder** — it isn't meant to flip; it sources rare-trait inventory
   at/near floor into the operator's shared book, with monetisation realised
   elsewhere (item-bot resale, Blur, or longer-horizon holding). The 57.6% replace /
   42.4% expire churn with near-floor pricing fits "keep a standing rare-trait bid
   wall" more than "scalp a spread."

Either way, **0x0282's −1.8 ETH should not be read as a losing strategy**; it is the
OpenSea-only slice of a bot whose payoff is realised off this dataset. *Update from
the on-chain Blur backfill:* the recovered Blur round-trips are **roughly break-even
(+1.21 ETH over 44 trips)**, so the off-OpenSea leg neither rescues nor sinks the
economics materially — consistent with the accumulation-feeder reading over a
hidden-profit one.

**Unrealized (mark-to-floor, conservative):** open inventory **−466 ETH**, but this
is **legacy**: 119 of 174 lots are >1 year old, dominated by **DeGods −262 ETH**
(2023 buys ~10 ETH, floor verified 0.17, same contract — real, not an artifact) and
**BAYC −41 ETH**. The **active <90 d book is ~flat (+0.08 ETH)**.

**Blur backfill (on-chain):** of the 132 off-platform sells (384 ETH), **44 entries
recovered** → combined realized **+22.43 ETH** over 918 trips; the Blur leg is
**~break-even (+1.21 ETH)**. Residual blind spot shrinks to **15 non-dust sells /
91 ETH** (zero on-chain payment on the inbound — cross-wallet/claims/pre-window) plus
73 bitmappunks dust. See `export/pnl.md` §6.

---

### Bottom line
Through the operating lens, this is a **disciplined, profitable, bid-side trait/item
market-making loop on three collections** (+8.9 ETH/90 d on OpenSea alone, gross),
run by two high-frequency Seaport bots that cancel-and-replace on a short timer and
re-anchor to floor lazily (~1 h). The eye-catching **−466 ETH is legacy directional
risk** from an earlier era, not the current MM book. The **Blur leg is now closed
on-chain** (44/132 entries recovered, ~break-even +1.21 ETH; combined realized
+22.43 ETH) — leaving only a **~91 ETH non-dust residual**, mostly long-held legacy
degods. So the cross-venue economics are now largely reconstructed, not a black box:
a small, consistently profitable OpenSea MM loop with a break-even Blur leg, sitting
on stranded 2023 inventory.
