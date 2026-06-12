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

**OpenSea / Seaport** for bids/listings (protocol `0x0000…eb395` = Seaport 1.6) and
**Blur** (BETH / Blur Pool settlement). The full Blur history is now reconstructed
on-chain (`blur_full.py`): **443 real Blur NFT trades** across the three wallets
(BETH-pool funding/Blend flows excluded; 326 settlements that also showed as OpenSea
"sales" deduped by tx hash). See `analysis/blur/BLUR_ANALYSIS.md`.

**Volume is split roughly evenly by venue:** each wallet trades ~720 ETH on Blur vs
~1.1–1.5k ETH on OpenSea. By *count* OpenSea dominates (the small bid orders), but the
**big-ticket directional trades (degods, BAYC) ran largely through Blur** — which is
exactly why the OpenSea-only P&L looked far rosier than reality.

**This revises the earlier "idle vault" finding:** wallet `0x8e8d` is **not idle** —
it does **110 Blur trades / 724 ETH** (it simply barely uses OpenSea). All three
wallets are active cross-venue. Residual blind spot after full backfill:
**109 orphan sells + 202 open lots** with no matched leg on either venue (pre-2023
history edges, cross-wallet moves, mints) — boundary effects, not a hidden venue.

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

**Realized (FIFO, gross). The full cross-venue figure (OpenSea + complete on-chain
Blur, deduped by tx) supersedes the OpenSea-only view:**

| scope | round-trips | realized P&L | win rate |
|---|---|---|---|
| OpenSea-only, all history | 874 | +21.22 ETH | 67.3% |
| **cross-venue, all history** | **924** | **−30.35 ETH** | 66.1% |
| **cross-venue, 90 d active** | **204** | **−2.22 ETH** | 81.4% |

The OpenSea-only +21 ETH was **misleadingly positive**: it omitted the high-priced
**degods/BAYC** buys that settled on **Blur** and pair into losing exits. With both
venues, realized is **−30.4 ETH gross** all-time. **By wallet (cross-venue):
0x400f (item bot) +9.5 ETH is the only profitable one**; 0x0282 (trait) −15.3 and
0x8e8d (vault) −24.5 carried the directional degods/bayc losses. ~22% of round-trips
are cross-venue (buy one venue, sell the other). The 90-day active loop is
**near break-even (−2.2 ETH, 81% win)** — many small wins, a few large degods losers.

**Resolved — 0x0282 (trait bot) economics do NOT close on Blur.** The earlier open
question ("its OpenSea −1.8 ETH must be rescued on Blur") is now answered by the full
on-chain Blur history: cross-venue, **0x0282 is −15.3 ETH**, not break-even. The Blur
leg made it *worse*, not better, because the trait bot's degods/clonex Blur buys pair
into losing exits. So the **accumulation-feeder** reading is the right one over the
hidden-profit one: 0x0282 sources rare-trait/directional inventory (it leans **taker
on Blur**, 75/46) that the operator then carries — and much of that inventory is the
underwater degods bag. It is a **cost centre feeding the book**, not a self-funding
scalper. (The first 44-pair backfill suggested ~break-even; the *complete* 443-trade
history corrects that to clearly negative.)

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
The **operating loop** — high-frequency bid-side trait/item making on three
collections via two Seaport bots (cancel-and-replace on a short timer, re-anchor to
floor ~1 h) — is **mechanically sound and near break-even in the 90-day window
(−2.2 ETH cross-venue, 81% win)**. But the **full cross-venue P&L is −30.4 ETH gross
all-time**, not the +21 ETH the OpenSea-only view implied: the complete on-chain Blur
history surfaces the high-priced **degods/BAYC** legs that the OpenSea-only data hid.
**Only the item bot (0x400f, +9.5 ETH) is profitable**; the trait bot and the
(previously "idle") vault — which is in fact a **724-ETH Blur trader** — carried the
directional losses, and the **−466 ETH unrealized legacy bag** compounds them. So the
honest picture: a competent small MM loop wrapped around a **loss-making directional
book**, the bulk of it stranded 2023 degods. **Hard limit:** bid *placement method*
(bot/manual/script) is not determinable on-chain and is left unknown.
