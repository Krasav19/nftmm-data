# Blur on-chain analysis — full operator history

Read-only on-chain reconstruction (public RPC). Blur settles in **BETH** (Blur Pool, ETH-pegged), so every Blur NFT trade leaves a BETH transfer + an NFT transfer in the settlement tx. We scanned all BETH transfers touching the 3 wallets across their full history, then decoded each settlement: NFT(s), price (ETH+WETH+BETH), direction, side.

> **Method note / data hygiene:** of all BETH-touching txs, only those carrying an actual **NFT transfer are real trades (443)**; the rest (~1855) are BETH-pool funding / withdrawals / Blend flows, excluded. **326 Blur settlement txs also appear as OpenSea "sales"** in our earlier data — these are deduped by tx hash (Blur on-chain record authoritative) so nothing is double-counted.

## 1. Blur trade volume by wallet (real NFT trades)

| wallet | Blur trades | buys/sells | taker/maker | Blur vol (ETH) |
|---|---|---|---|---|
| 0x0282 (trait bot) | 121 | 71/50 | 75/46 | 718 |
| 0x400f (item bot) | 212 | 178/34 | 61/151 | 724 |
| 0x8e8d (vault) | 110 | 71/39 | 57/53 | 724 |

**Hypothesis check (vs the original OpenSea-only read):**
- *"0x400f is the main Blur actor"* — **partly true**: 0x400f has the most Blur trades (212) but all three wallets trade comparable Blur **volume (~720 ETH each)**.
- *"0x0282 almost empty on Blur"* — **FALSE**: 0x0282 has 121 Blur trades / 718 ETH, heavily **degods** — its OpenSea-invisible economics live here.
- *"0x8e8d (vault) is zero"* — **FALSE**: the vault does **110 Blur trades / 724 ETH**. It looked idle only because it barely uses OpenSea; on Blur it is fully active. This **revises the earlier "idle vault" conclusion** — it's a Blur-primary trader.

## 2. Blur vs OpenSea flow (same wallet)

| wallet | Blur trades / vol | OpenSea trades / vol | primary venue |
|---|---|---|---|
| 0x0282 (trait bot) | 121 / 718 ETH | 662 / 1130 ETH | OpenSea (count) |
| 0x400f (item bot) | 212 / 724 ETH | 501 / 1161 ETH | OpenSea (count) |
| 0x8e8d (vault) | 110 / 724 ETH | 575 / 1538 ETH | OpenSea (count) |

**Read:** by **trade count** OpenSea dominates (the bid bots post/fill far more small orders there), but by **ETH volume the two venues are comparable** — Blur carries ~720 ETH/wallet vs OpenSea ~1.1–1.5k. The big-ticket directional trades (degods, bayc) ran substantially through **Blur**, which is why they were invisible in the OpenSea-only P&L.

## 3. Maker vs taker on Blur

| wallet | taker (took resting order) | maker (own order hit) | lean |
|---|---|---|---|
| 0x0282 (trait bot) | 75 | 46 | **taker** |
| 0x400f (item bot) | 61 | 151 | **maker** |
| 0x8e8d (vault) | 57 | 53 | **taker** |

(Side = tx initiator: if our wallet sent the settlement tx it **took** a resting order; otherwise its own order was hit = **maker**.)

**Read:** **0x400f leans maker on Blur (151 maker / 61 taker)** — it rests bids and waits, consistent with its OpenSea bid-bot identity. **0x0282 leans taker (75/46)** and **0x8e8d is balanced (57/53)**. So the item bot is a passive liquidity provider on both venues; the trait bot and vault more often cross the spread to take.

## 4. Active-loop P&L — strictly 90 days (cross-venue FIFO)

**Focus = the last 90 days (window 2026-03-14 → 2026-06-12).** Everything older is legacy and is out of focus by construction (see footnote). The 90d ledger is split into three components so the active-strategy number is isolated from boundary effects (`pnl_90d.py` → `export/pnl_90d.json`):

| component | trips/lots | P&L (ETH) | win | note |
|---|---|---|---|---|
| **REALIZED 90d** (both legs in window) | 192 trips | **−1.886** | **82.8%** | the active loop |
| OPEN / MTM 90d (bought in-window, unsold) | 18 lots | **−1.063** unrealized | — | floor-marked, current snapshot |
| orphan-entry closed (buy *pre*-window) | 12 trips | −0.328 | 58.3% | **excluded** — legacy tail |

**The clean active-loop figure is −1.89 ETH realized at 82.8% win** (192 fully-closed pairs with both legs inside the window). The earlier "−2.2 ETH / 204 trips / 81.4%" was that same realized set **with 12 orphan-entry trips mixed in** (buy before the window, sell inside): 192 + 12 = 204 trips, −1.886 + −0.328 = −2.214 ≈ −2.215. Those 12 are a legacy tail, not the active loop, so they are removed from the headline.

**Per wallet — 90d:**

| wallet | realized 90d | win | open-MTM 90d |
|---|---|---|---|
| 0x0282 (trait bot) | **+2.229 ETH** (114 trips) | 86.0% | −0.557 (11 lots, cost 4.27) |
| 0x400f (item bot) | **−3.924 ETH** (77 trips) | 79.2% | −0.506 (7 lots, cost 19.69) |
| 0x8e8d (vault) | −0.192 ETH (1 trip) | 0% | none in 90d |

**Read (90d active loop):** in the live window the *trait bot* (0x0282) is the earner (**+2.23 ETH, 86% win**) while the *item bot* (0x400f) is the drag (**−3.92 ETH**) — the reverse of the all-time ranking, because all-time is dominated by legacy degods/bayc that no longer trade. The vault is essentially inactive in-window (1 trip). Open inventory opened in-window is small and slightly underwater (**−1.06 ETH** unrealized on 24 ETH cost, ~95% of basis, mostly one off-floor lilpudgys lot per bot). Net active-loop position = **−1.89 ETH realized + −1.06 ETH open**.

**Cross-venue round-trips (all-history context):** buy-Blur→sell-OpenSea **127**, buy-OpenSea→sell-Blur **79** (= 206 cross-venue, 22% of trips); OpenSea→OpenSea 684, Blur→Blur 34.

> **Legacy, out of focus (footnote).** All-history cross-venue realized is **−30.35 ETH / 924 trips / 66.1% win** — by wallet 0x0282 −15.3, 0x400f +9.5, 0x8e8d −24.5. That number is dominated by 2023 **degods/bayc** legs that settled on Blur and have not traded in the window; it is recorded for completeness but is **not** the active strategy and is excluded from the 90d read above.

## 5. Residual blind spot after full backfill

- **109 sells** still have no matched entry on either venue, and **202 open lots** have no exit yet. These are pre-history acquisitions (before 2023-05), cross-wallet moves, mints/airdrops, or the small set of non-ETH-denominated settlements. This is the floor of what on-chain + OpenSea data can explain.
- Down from the original 384-ETH OpenSea-only blind spot: the Blur leg is now reconstructed; what remains is mostly **boundary effects** (history edges) rather than a hidden venue.

## 6. Hard limitation (recorded, not inferred)

> **How bids were placed — bot vs manual vs script — is NOT determinable from on-chain data.** On-chain we see only settled trades and the BETH/NFT flows; Blur bids are off-chain signed orders that never hit the chain until execution. We can measure *timing, prices, sides, and venues*, but **the placement mechanism is unknown and is left as unknown** — not guessed. (The OpenSea-side delta analysis showed 1–2 s inter-offer spacing consistent with automation, but that is an OpenSea observation and is not extended to Blur here.)

### Files
`analysis/blur/trades_full.jsonl` (443 real trades), `beth_pool_moves.jsonl` (excluded pool ops), `xvenue_pnl.json` (cross-venue FIFO), `trades_full_summary.json`. Log: `logs/blur_full.log`.

