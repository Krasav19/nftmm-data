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

**OpenSea / Seaport only in this dataset** (protocol `0x0000…eb395` = Seaport 1.6,
plus older Seaport on historical fills). **Blur is used heavily but not captured** —
inferred from 132 lifetime sells (384 ETH) and 5 recent sells (22.5 ETH) that have
OpenSea exits but no OpenSea entry, plus Blur-Pool (ETH-pegged) payment tokens in
sales. Any cross-venue P&L statement is therefore incomplete.

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

- **Reaction lag:** of 36 floor moves ≥1%, the operator repriced in the same
  direction in only ~25%, and when it did the **lag was ~1 h (median 4 snapshots)** —
  it re-bases bids on a slower cadence than its 10–30 min quote refresh, i.e. a
  floor-anchored target that updates lazily rather than chasing every tick.
- **Risk posture:** active book is **small and near-flat** — 16 fresh (<90 d) lots,
  9.8 ETH at entry, **+0.08 ETH unrealized**. Short holds, sub-floor entries, and
  trait premiums only on rares are all conservative. **The risk that did blow up was
  legacy directional holding**, not the MM loop (see §9).

## 7. Bot architecture (reconstructed, with real timings)

- **Two independent quoting engines**, one per wallet, each Seaport-based:
  - *Trait engine (0x0282):* enumerates traits per collection (CloneX, LilPudgys),
    posts one collection-criteria offer per trait, **TTL ~10–30 min**, **replace
    cycle ≈ every 15 min or faster** (57% of bids replaced same-trait at a new
    price; 1 s inter-offer spacing → a full trait sweep posts in seconds).
  - *Item engine (0x400f):* enumerates desirable token IDs on PudgyPenguins/
    LilPudgys, posts **laddered per-token bids** (228 tokens multi-priced), longer
    TTL (median ~45 min alive), 2 s spacing.
- **Refresh, not chase:** bids are re-posted on a fixed short timer (replace/expire
  dominate; ~0 in-grid fills), while *price* re-basing to floor is lazier (~1 h lag).
  Classic "cancel-and-replace on a timer, re-anchor on floor drift" maker loop.
- **Order TTL window** observed 15 min–8 h (median 4 h on the standing book), with
  the high-churn layer turning over inside the 15-min sampling floor.

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
| all history | 874 | **+21.22 ETH** | 67.3% |

By bot: **0x400f +19.5 ETH (71.8% win)** is the engine; 0x8e8d +3.5; **0x0282 −1.8**
(wins often, tiny margins). Top trade +3.0 ETH (pudgy 7105 8.48→11.48); worst −2.31
(degods 1580).

**Unrealized (mark-to-floor, conservative):** open inventory **−466 ETH**, but this
is **legacy**: 119 of 174 lots are >1 year old, dominated by **DeGods −262 ETH**
(2023 buys ~10 ETH, floor verified 0.17, same contract — real, not an artifact) and
**BAYC −41 ETH**. The **active <90 d book is ~flat (+0.08 ETH)**.

**Excluded:** 132 lifetime sells / 384 ETH (90 d: 5 / 22.5 ETH) bought off-platform
(Blur) — entry unknown, kept out of P&L. These are the size of the blind spot.

---

### Bottom line
Through the operating lens, this is a **disciplined, profitable, bid-side trait/item
market-making loop on three collections** (+8.9 ETH/90 d on OpenSea alone, gross),
run by two high-frequency Seaport bots that cancel-and-replace on a short timer and
re-anchor to floor lazily (~1 h). The eye-catching **−466 ETH is legacy directional
risk** from an earlier era, not the current MM book. The one real unknown is **Blur**:
a ~2.5% live blind spot (larger historically) means the true cross-venue economics
cannot be closed from this data.
