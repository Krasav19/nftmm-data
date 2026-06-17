# Operator software reconstruction — analytical specification

**What this is.** A consolidated, data-backed specification of the *operator's*
trading software (the bot run by **GimmeGimmeG / NFT Butler**), as reconstructed from
on-chain and OpenSea data across this project. It describes **observed functionality**,
not an implementation we run. Every claim is tagged: unmarked = confirmed by data;
**[hypothesis]** = consistent with data but not proven; **[not observable]** = beyond
what the available data can show.

**Sources synthesised:** `export/REPORT_v2.md`, `FINAL_REPORT.md`,
`analysis/delta/DELTA_REPORT.md`, `export/trait_analysis.json`,
`analysis/delta/item_ttl_tiers.json`, `analysis/blur/BLUR_ANALYSIS.md`,
`pnl_authoritative.md/json`, `transfer_ledger_enriched.jsonl`, the 572 order-book
snapshots, and `analysis/cluster_linkage.json`. No new data runs; synthesis only.

---

## 1. Wallets and roles

Three trading wallets plus an operator-controlled funding/treasury cluster:

| address | role | confirmed by |
|---|---|---|
| `0x028296…a26e` (**0x0282**) | **Trait-bid bot** — CloneX + LilPudgys. Posts collection-criteria *trait* offers; the only wallet that also lists. Leans **taker** on Blur (75/46). | delta snapshots, trait_analysis, BLUR_ANALYSIS |
| `0x400f2b…e3cf` (**0x400f**) | **Item/trait-bid bot** — PudgyPenguins + LilPudgys. Per-token + trait offers with a coupled price×TTL scheme. Leans **maker** on Blur (151/61) — a passive LP. | item_ttl_tiers, delta, BLUR_ANALYSIS |
| `0x8e8d62…e062` (**0x8e8d**) | **Vault / two-sided** — barely uses OpenSea (never lists), but **110 Blur trades / 724 ETH**; on-chain currently **empty**. Not idle — a Blur-primary book. | BLUR_ANALYSIS, transfer_ledger, reconcile |
| **Funding cluster — 11 addresses** | Inventory parking + ETH funding. Incl. `0x66e1f614` (EOA), `0xa171759d` (**EIP-7702 smart account**), `0x6453ef85`, +8. | cluster_linkage, transfer_ledger |

**Cluster linkage is confirmed by ETH flow, not inferred:** each of the 11 addresses
has **thousands of bidirectional native-ETH transfers (~6.5k–7.4k ETH each way)** with
the three trading wallets. All **137 "unpriced" NFT exits (751 ETH cost basis)** went
to this cluster — 73 as wallet-initiated `transferFrom` pushes, 64 via a bulk-transfer
helper — with **0 ETH received** for the NFTs. So the cluster is where the operation
**parks inventory**, not where it sells. (cluster_linkage.json, pnl_authoritative §"751 ETH resolved")

---

## 2. Engines and strategy type

**Strategy: bid-side trait market-making, two-sided (bid in → list/Blur out).**

- **Trait bids, not item ladders, not collection-wide bids** (for 0x0282). The
  operator posts **collection-criteria offers scoped to a specific trait**
  (`criteria_traits`), anchored to **trait-floor**, not collection floor. Confirmed
  directly: in snapshots, **all** of 0x0282's CloneX/LilPudgys offers (and even its
  doodles offers) carry a single `trait` criterion with an `encoded_token_ids` set.
- **0x400f runs both** per-token item ladders (PudgyPenguins, 228 tokens multi-priced)
  **and** trait offers — with the two-axis price×TTL scheme of §4.
- **Two-sided loop:** entry via **resting bid**, exit via **listing or Blur**, not by
  market-taking. The bid side dominates massively — **~63k bids in-window vs 11
  listings** (delta §4).
- **Accumulation tilt** [hypothesis]: 0x0282 leans taker on Blur and sources
  directional inventory; the realized-P&L work reads it as a cost-centre feeding the
  book rather than a self-funding scalper (pnl/BLUR_ANALYSIS) — directionally
  supported, not proven.

---

## 3. Pricing scheme (trait multipliers)

The bot prices each bid as a **multiple of that trait's floor**: common traits just
under floor, rares at a premium. From `trait_analysis.json` (operator's live trait
bids vs collection floor):

**LilPudgys** (floor ≈ 0.474), premium distribution of 152 trait bids:
`95–100%: 132 · 100–110%: 13 · 130–175%: 7 · (none <95% or >175%)`.

| trait | operator bid | × floor |
|---|---|---|
| Body=Kimono Ice | 0.828 | **175%** |
| Body=Kimono Gold | 0.797 | 168% |
| Head=Wizard Hat | 0.496 | 104% |
| Body=Pudgy Boy White / Purple | 0.490 | 103% |
| Head=Flower Crown | 0.474 | 100% |
| Head=Biker Helmet / Top Hat Gold | 0.471 / 0.462 | 99% / 98% |

**CloneX** (floor ≈ 0.289), 253 trait bids: `95–100%: 240 · 100–110%: 11 · 130–175%: 2`.

| trait | operator bid | × floor |
|---|---|---|
| DNA=Angel | 0.317 | **110%** |
| DNA=Demon | 0.293 | 100% |
| Mouth=ARMRD Mutant / Hair=Witch | 0.279 | 97% |
| Eyewear=RD LAZER / Back=Energy Wings | 0.286 / 0.285 | 99% / 98% |

**Read:** the overwhelming mass (132/152 LilPudgys, 240/253 CloneX) bids at **95–100%
of trait-floor** — i.e. at/just-below the trait's own floor — with a thin rare tail to
**1.75×**. The bot pays trait premium only where the trait commands one.

---

## 4. Timings

**Trait bot (0x0282) — high-churn cancel-and-replace:**
- **45,632 trait offers in 3 days**, **median 1 s** between offers (p90 11 s) — an
  always-on poster. A full trait sweep posts in seconds.
- **Bid TTL 10–30 min** (stated) ; observed: **97.5% of trait bids vanish within one
  15-min snapshot** — **57.6% replaced** same-trait at a new price, **42.4% expired**,
  **~0% filled on-grid**. Pure re-quote churn.
- **[not observable]** the exact internal cancel/replace *trigger* (timer vs
  floor-tick vs book-event) — 15-min snapshot cadence is coarser than the 1 s posting,
  so only the lower bound is seen.

**Item bot (0x400f) — coupled price × TTL tiers:**
- **76,744 per-token offers in 3 days**, **median 2 s** spacing (p90 6 s).
- **Discrete declared-TTL tiers (60/120/150/180/240/360/480 min)**, with TTL scaling
  **monotonically with bid depth vs floor** (item_ttl_tiers.json, n=39,194 closed orders):

  | TTL (min) | median offset vs floor | n |
  |---|---|---|
  | 60 | −1.9% | 7,080 |
  | 120 | −1.1% | 3,410 |
  | 150 | −0.4% | 4,010 |
  | 180 | +1.0% | 4,202 |
  | 240 | +5.0% | 12,109 |
  | 360 | +14.7% | 7,588 |
  | 480 | +15.7% | 795 |

  Cheap near-/sub-floor bids get **short TTL** (re-quoted fast as floor drifts);
  aggressive above-floor bids get **long TTL** (left standing to catch a motivated
  seller). A deliberate **two-axis quoting scheme**, not a flat ladder. (CONFIRMED in source.)

**Floor re-anchor (both):**
- Reprice when the floor moves **≥1%** since the level's anchor, on a **~30-min min
  interval**.
- On a clean sample (floor moves ≥1% *in collections the operator was actively
  quoting*): **64.3% repriced in the same direction** (9 of 14; the unfiltered figure
  was ~25%, diluted by non-quoted collections), at **median lag ~60 min** (4 snaps,
  p25 15m / p75 75m). A **lazy floor-anchored re-base**, slower than the quote-refresh
  cadence.

---

## 5. Listing side (exit)

Listing is a **minor, secondary activity** — **11 unique operator listings in-window**
(0x0282: 7 CloneX, 0x400f: 4 PudgyPenguins; vault 0x8e8d never lists) vs ~63k bids.

- **Ratchet-up only:** of the re-prices observed, **5 of 5 were up**, median step
  **+1.81%**; **0 down-cuts**. Plus **4 withdrawals**.
- So the listing side **only raises asks or pulls them, never cuts** — exits run
  predominantly through **accepting bids / Blur**, not standing OpenSea asks.
- **[not observable in detail]** the full listing-reprice cadence — only 11 listings
  in-window, too few to characterise timing precisely (see §9).

---

## 6. Venues

- **OpenSea / Seaport** (protocol `0x0000…eb395`, Seaport 1.6) — bids and listings,
  on-chain settlement.
- **Blur Exchange** — on-chain BETH (Blur Pool) settlement; **443 real Blur NFT trades**
  reconstructed across the three wallets, with **36 confirmed Blur-Exchange settlements**
  decoded. Big-ticket directional trades (degods/BAYC) ran largely through Blur, which
  is why they were invisible in OpenSea-only data.
- **Maker/taker (Blur):** 0x0282 **taker** (75/46), 0x400f **maker** (151/61), 0x8e8d
  balanced (57/53).
- **[not observable]** *how* Blur bids are placed. Blur maker orders are off-chain
  signed orders served via Blur's bid oracle/infra; they only hit chain on execution.
  We see settled trades, prices, sides, venues — but the **bid-placement mechanism on
  Blur is unknown** and left unknown.

---

## 7. Bot architecture (reconstruction)

A data-flow reconstruction consistent with all of the above (component wiring is
**[hypothesis]**; the per-stage behaviours are confirmed):

```
            ┌──────────────────────────────────────────────────────────┐
            │  FLOOR / TRAIT-FLOOR MONITOR  (poll OpenSea per collection │
            │  & per trait; detect ≥1% moves)                           │
            └───────────────┬──────────────────────────────────────────┘
                            │ trait-floor, collection floor
                            ▼
            ┌──────────────────────────────────────────────────────────┐
            │  TRAIT BOOK BUILDER  (per trait: bid = ×floor multiplier,  │
            │  §3; assign TTL tier coupled to depth, §4)                │
            └───────────────┬──────────────────────────────────────────┘
                            │ desired bids
                            ▼
            ┌──────────────────────────────────────────────────────────┐
            │  POSTER / CANCEL-REPLACE LOOP  (1–2 s cadence; expire by   │
            │  TTL → re-quote; re-anchor on floor move ≥1%, ~1 h lag)    │
            └───────────────┬──────────────────────────────────────────┘
                            │ resting bids on OpenSea (+ Blur maker, [not observable])
                            ▼
            ┌──────────────────────────────────────────────────────────┐
            │  FILL → INVENTORY  (a seller accepts a bid → token in)     │
            └───────────────┬──────────────────────────────────────────┘
                            │ acquired NFT
                            ▼
            ┌──────────────────────────────────────────────────────────┐
            │  EXIT  (list ratchet-up on OpenSea, §5, OR sell on Blur)   │
            └───────────────┬──────────────────────────────────────────┘
                            │ proceeds / unsold inventory
                            ▼
            ┌──────────────────────────────────────────────────────────┐
            │  PARK → FUNDING CLUSTER  (transferFrom / bulk-transfer to  │
            │  the 11-address cluster; §1 — internal, 0 ETH)            │
            └──────────────────────────────────────────────────────────┘
```

The confirmed pieces: floor monitoring, trait-floor anchoring, ×floor pricing,
TTL-tiered cancel-replace at 1–2 s, ~1 h floor re-anchor, ratchet-up listing exits,
and inventory parking to the cluster. The **arrows between them are the [hypothesis]** —
we observe each stage's outputs, not the code that connects them.

---

## 8. Economics and limits

From `pnl_authoritative` (reconciled ledger, diff=0 to balanceOf; active core 97.7%
priced; FIFO cross-venue; OpenSea 1% sell fee, Blur 0%, real gas):

| scope | realized | trips | win | note |
|---|---|---|---|---|
| **90-day active loop** | **−5.80 ETH** | 198 | 75.3% | item bot 0x400f −6.92 (rare-pengu losses), trait bot 0x0282 **+1.12**, vault flat |
| all-time | −28.08 ETH | 1,029 | — | legacy degods/BAYC carried the loss |
| open-MTM (held now) | **+0.23 ETH** | — | — | near-flat, 7.7 ETH basis at floor |

**Confirmed boundary facts:**
- Realized over **visible market exits** is ~**zero to small-negative** in the 90-day
  window. High win-rate (75%), small per-trip, a few large rare-pengu losers.
- The **751 ETH of NFT exits to the cluster are NOT a loss** — they are internal
  transfers (0 ETH received), inventory relocated within the operation, excluded from
  realized. (Plus 96 ETH degods/MAYC migrations and 15 ETH burns, also not sales.)
- The **OpenSea trait-bid fill flow is thin**: on the most-traded selective traits,
  market bid-accepts run **<1/day**; only near-universal "traits" (= collection-wide)
  reach ≥3/day, and those clear at ~95% of *collection* floor (≈0 trait edge).

**The honest limit — where the profit, if any, lives — is not localised in the
observable OpenSea data.** Candidate explanations, all **[hypothesis, not proven]**:
1. **Blur leg** — large directional volume settles on Blur via off-chain maker infra
   we can't see (§6); profit could be captured there.
2. **Timing/latency edge** — the 1–2 s cancel-replace loop may capture fills our
   15-min snapshots can't resolve.
3. **Inventory/treasury** — value may accrue as inventory held in the cluster
   (751 ETH basis parked), realised outside the windows/wallets we track.

None of these is demonstrated; they mark where to look, not conclusions.

---

## 9. Not yet fully studied (to complete the software picture)

| gap | what's missing | data needed |
|---|---|---|
| **CloneX trait set & multipliers** | CloneX is characterised more weakly than Pudgy/LilPudgys — only a top-8 trait table, no full per-trait fill/edge map. | Full CloneX trait→token map + a live trait-offer/listing pull per CloneX trait (as done for LilPudgys), over a multi-day window. |
| **0x0282 cancel-replace trigger** | We see 1 s posting + 97.5% turnover, but not *what* fires the replace (fixed timer? floor tick? competing-bid event?). | Sub-minute order-book capture (poll ≪ TTL, e.g. 5–15 s) keyed by `order_hash`, to time replacements against floor/competitor changes. |
| **Listing-reprice pattern** | Only 11 listings in-window → ratchet-up direction known, but not cadence, step distribution, or withdrawal triggers. | A longer listing-side capture (weeks) or a wallet with more listing activity; per-listing `order_hash` tracking across snapshots. |
| **Blur bid placement** | [not observable on-chain] — off-chain signed maker orders. | Blur API/oracle access (off-chain order feed) — outside chain data entirely. |
| **Cluster internal economics** | 751 ETH parked; whether/where it's later realised is untracked (cluster wallets aren't in our 3-wallet P&L scope). | Extend the transfer-ledger + pricing to the 11 cluster addresses; reconcile their balances and exits. |

---

*Synthesis of existing project findings only — no new analysis runs. All figures
trace to the cited artifacts. Confirmed vs [hypothesis] vs [not observable] tags are
applied throughout per the evidence available.*
