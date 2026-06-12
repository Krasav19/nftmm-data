# NFT Market Maker — final report

**Operator:** GimmeGimmeG / NFT Butler, running three Ethereum wallets.
**Data:** OpenSea API v2 (Ethereum mainnet). Full sale/transfer history; offers
limited to a 3-day pull; **153 order-book snapshots** every 15 min
(2026-06-10 20:30Z → 2026-06-12 10:15Z) for delta analysis.

> **Scope & focus (read first).** The headline of this report is the **active loop
> over the last 90 days** (window 2026-03-14 → 2026-06-12): **−1.89 ETH realized at
> 82.8% win, 192 cross-venue round-trips** (§9). **P&L is cross-venue** — OpenSea API
> v2 plus the full on-chain Blur history (`blur_full.py`), deduped by tx — and gross of
> gas/fees. Behavioural sections (§3–§7) are OpenSea-side observations (offers/snapshots
> live there). **Everything older than 90 days is legacy and out of focus:** the
> all-time −30.4 ETH cross-venue and the **−466 ETH unrealized bag** (mostly 2023
> DeGods/BAYC) sit *outside* the active loop and are kept only as a footnote, not the
> operating business.

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
- **Risk posture:** active book is **small and near-flat** — 18 fresh (<90 d) lots
  opened in-window, **24 ETH at entry, −1.06 ETH unrealized** at current floor
  (cross-venue; the earlier +0.08 ETH was OpenSea-only and pre-Blur). Short holds,
  sub-floor entries, and trait premiums only on rares are all conservative. **The risk
  that did blow up was legacy directional holding**, not the MM loop (see §9).

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

## 9. P&L — the active loop, strictly 90 days

**The headline number of this report is the realized P&L of the active loop over the
last 90 days** (window **2026-03-14 → 2026-06-12**), cross-venue (OpenSea + complete
on-chain Blur, deduped by tx), FIFO, gross of gas/fees. Everything older — the
all-time −30.4 ETH, the 2023 degods/BAYC legs, the −466 ETH legacy inventory — is a
legacy tail and is moved to the footnote below; it is **not** the operating business.

The 90d ledger is split into three components so the active number is isolated from
boundary effects (`pnl_90d.py` → `export/pnl_90d.json`):

| component | trips / lots | P&L (ETH) | win | counts as |
|---|---|---|---|---|
| **REALIZED 90d** (both legs in window) | **192 trips** | **−1.89** | **82.8%** | **the active loop** |
| OPEN / MTM 90d (bought in-window, unsold) | 18 lots | −1.06 unrealized | — | open risk |
| orphan-entry closed (buy *pre*-window) | 12 trips | −0.33 | 58.3% | excluded (legacy tail) |

**Clarifying the −2.2 ETH:** that earlier figure was realized-90d **with orphan-entry
contamination**. It summed the 192 clean trips (−1.886) with 12 closed trips whose
*buy was before the window* (−0.328) → 204 trips, −2.214 ≈ −2.215, win 81.4%. Those 12
are a legacy-tail entry, not the active loop. **Removing them, the clean realized 90d
of the active loop is −1.89 ETH at 82.8% win** (the win rate is *higher*, 82.8% vs the
mixed 81.4%, because the orphan-entry trips were mostly losers).

**Per wallet — 90d (the live ranking, which inverts the all-time one):**

| wallet | realized 90d | win | open-MTM 90d |
|---|---|---|---|
| **0x0282 (trait bot)** | **+2.23 ETH** (114 trips) | 86.0% | −0.56 (11 lots, cost 4.3) |
| 0x400f (item bot) | **−3.92 ETH** (77 trips) | 79.2% | −0.51 (7 lots, cost 19.7) |
| 0x8e8d (vault) | −0.19 ETH (1 trip) | 0% | none in 90d |

In the live window the **trait bot 0x0282 is the earner (+2.23 ETH, 86% win)** and the
**item bot 0x400f is the drag (−3.92 ETH)** — the *reverse* of the all-time ranking,
which is dominated by stale degods/bayc. The vault is effectively inactive in-window
(1 trip). So the active loop nets **−1.89 ETH realized + −1.06 ETH open** ≈ −2.95 ETH
mark-to-market on a 90-day book — one bot solidly profitable, one carrying recent
losses, on small size (24 ETH of in-window open cost basis).

**Open / MTM 90d detail:** the 18 lots opened in-window mark to **−1.06 ETH** against a
24 ETH cost basis (~96% of basis at floor). It is small and near-flat; the drag is two
above-floor lilpudgys lots (one per bot, ~0.9 ETH entry vs 0.47 floor). Short holds,
sub-floor entries, trait premiums only on rares — conservative, as before.

> **Legacy, out of focus (footnote — not the active strategy).**
> *All-time cross-venue realized* is **−30.35 ETH / 924 trips / 66.1% win** (by wallet:
> 0x0282 −15.3, 0x400f +9.5, 0x8e8d −24.5). The OpenSea-only view (+21.2 ETH / 874
> trips) was misleadingly positive — it omitted the high-priced degods/BAYC buys that
> settled on Blur and pair into losing exits. *Unrealized legacy inventory* marks to
> **−466 ETH** (174 lots, 119 of them >1 yr old; DeGods −262, BAYC −41). These
> all-time figures are dominated by 2023 directional positions that no longer trade in
> the window; they are recorded for completeness only. Note the all-time wallet
> ranking (0x400f the only profitable one; 0x0282/0x8e8d the losers) is a *legacy*
> ranking — in the live 90d loop it inverts (above).

---

### Bottom line
The **active loop** — high-frequency bid-side trait/item making on three collections
via two Seaport bots (cancel-and-replace on a short timer, re-anchor to floor ~1 h) —
is, **strictly over the last 90 days, −1.89 ETH realized at 82.8% win across 192
fully-closed cross-venue round-trips**, plus −1.06 ETH of open inventory at floor. It
is **mechanically sound and roughly break-even**: a high-volume, high-win-rate scalp
where the realized loss is a handful of large legs against many small wins. In the live
window the **trait bot 0x0282 is the earner (+2.23 ETH, 86%)** and the **item bot
0x400f is the recent drag (−3.92 ETH)** — the inverse of the all-time ranking. The
old "−2.2 ETH" headline was that same loop with 12 orphan-entry (legacy-tail) trips
mixed in; removing them gives the clean −1.89. **Everything older is out of focus:**
all-time cross-venue P&L is −30.4 ETH gross with a −466 ETH unrealized legacy degods/
BAYC bag, but that is stranded 2023 directional inventory, not the operating loop (see
§9 footnote). **Hard limit:** bid *placement method* (bot/manual/script) is not
determinable on-chain and is left unknown.
