# Ledger reconciliation — authoritative ERC-721/1155 Transfer ledger

**Built from raw on-chain `Transfer` events** (not marketplace feeds). For each of
the three wallets we pulled every ERC-721 `Transfer` and ERC-1155
`TransferSingle`/`TransferBatch` log where the wallet is `from` or `to`, across the
full history of all 16 collections with any activity, via RPC (publicnode 50k-block
chunks, OR-topic on the three wallets, RPC failover + backoff, resumable per-chunk
cache). Marketplace feeds (OpenSea/Blur) are used ONLY to attach a price; they are
not the source of legs.

**Ledger:** `transfer_ledger.jsonl` (2492 legs) ·
**Enriched:** `transfer_ledger_enriched.jsonl` (+ class & price) ·
**Reconciled @ block 25317458.**

## 1. Invariant: ledger net(in − out) == on-chain `balanceOf` — **HOLDS (diff=0)**

Verified programmatically (`reconcile.py`): for every (wallet, collection) the net
of in minus out legs equals current `balanceOf`, and every token the ledger says is
held was confirmed token-by-token via `ownerOf`.

| wallet | ledger net == balanceOf | held tokens (ownerOf-confirmed) |
|---|---|---|
| 0x0282 (trait bot) | ✅ 7 CloneX, 1 LilPudgys, 1 Koda | CloneX #1798/4248/7864/11598/12054/15474/19543 · LilPudgys #16549 · Koda #8369 |
| 0x400f (item bot) | ✅ 1 PudgyPenguins | Pudgy #1381 |
| 0x8e8d (vault) | ✅ 0 | — (empty) |

*Note on live chain:* the chain keeps advancing, so reconciliation **pins all
on-chain reads to the ledger's last block** (25317458) — otherwise a sale landing
after the build creates a false mismatch. That is exactly what happened: 0x0282 sold
LilPudgys #8513 (to a marketplace contract) just after an earlier build, momentarily
showing net 2 vs balanceOf 1; the refreshed, pinned reconciliation captures the
disposal and ties out to diff=0. (Earlier mid-build moves — 0x0282 buying Koda #8369
and LilPudgys #8513, 0x400f selling one of two pengus — were likewise captured.) This
is the proof the marketplace-only data lacked: **every movement ties out to chain
state**, where the sale feeds covered only ~26% of legs.

## 2. Price-enrichment coverage — 80.2% → **93.1%** after router-price recovery

Each external (tradeable) leg gets a price from, in priority: Blur on-chain trade →
OpenSea sale event → on-chain value the wallet net-received/paid in the same tx.

**The on-chain step was upgraded** (`enrich_router_prices.py`). The original receipt
pass only credited ETH when `tx.to`/`tx.from` was our wallet — but in Seaport/Blur
sales the **buyer** sends the tx (`tx.to` = router) and the ETH reaches us as an
*internal* transfer invisible to receipt logs. The recovery pass reads
`trace_transaction` (internal ETH) + WETH/BETH, directionally (proceeds for OUT/sell,
paid for IN/buy), **regardless of tx initiator**. It prices ONLY legs that were
`unpriced` (no double-count), uses the **actual ETH our wallet received** (net of
marketplace fee — e.g. Pudgy #7610 = 7.583 vs 7.66 gross), never substitutes floor,
and splits multi-NFT batch txs equally per token (flagged `tx_trace_split`).

**Overall external-leg price coverage: 2186/2349 = 93.1%** (was 80.2%; 26% on
feeds alone). **301 legs recovered** on-chain — no new marketplace feed needed.
Price sources: OpenSea 1096, Blur 477, receipt 312, **tx_trace 236, tx_trace_split 65**.

| wallet | sale | unpriced | mint | burn | internal | price coverage (external) |
|---|---|---|---|---|---|---|
| 0x0282 (trait bot) | 829 | 35 | 100 | 27 | 2 | 829/864 = **96%** |
| 0x400f (item bot) | 709 | 82 | 0 | 14 | 0 | 709/791 = **90%** |
| 0x8e8d (vault) | 648 | 46 | 0 | 0 | 0 | 648/694 = **93%** |

### Active loop is now closed on exits

| scope | coverage | note |
|---|---|---|
| **active core (clonex+lilpudgys+pudgy)** | **1477/1511 = 97.7%** | exits recovered |
| clonex | 451/453 = **100%** | |
| lilpudgys | 476/487 = **98%** | |
| pudgypenguins | 550/571 = **96%** | |
| legacy (all other) | 709/838 = 84.6% | |

All 237 active-core unpriced legs were OUT-legs (exits); **176 carried recoverable
on-chain proceeds and are now priced**, lifting pudgy 64%→96% and clonex to 100%.

## 3. Leg classification (the full 2492-leg ledger)

| class | legs | meaning | in P&L? |
|---|---|---|---|
| **sale** | 2186 | price found (feed or on-chain trace/receipt) | **yes** |
| **unpriced** | 163 | real external transfer, no money leg to/from us — genuine OTC / delegation / escrow / settlement-in-another-tx | no (flagged, kept in ledger) |
| **mint** | 100 | acquired from 0x0 (mint/claim) | cost-basis 0, tracked separately |
| **burn** | 41 | sent to 0x0 | tracked separately |
| **internal** | 2 | counterparty is one of our own 3 wallets | **no — not a trade** |

**Remaining unpriced is the honest floor:** 34 active + 129 legacy. Every one of the
34 active legs was verified to have **zero** ETH/WETH/BETH flow to our wallet in its
tx (no recoverable price missed) — they are transfers to escrow/delegate contracts or
OTC moves, not sales, so they stay unpriced rather than get a fabricated floor.

## 4. Verdict

- **Invariant satisfied (re-checked post-patch)** — pricing changed no quantities;
  net movements still reconcile to `balanceOf`/`ownerOf` for every wallet, every held
  token, diff=0 (pinned @ ledger block to avoid live-chain drift).
- **Price coverage 93.1%**, active core **97.7%** (clonex 100%, lilpudgys 98%, pudgy
  96%) — the active loop is now **closed on exits**. 80% was an enricher limitation,
  not a data ceiling; the fix was on-chain `trace_transaction`, no new feed.
- **P&L is NOT computed here** (per instruction). The ledger now meets both
  preconditions (reconciled + active-loop priced); P&L is the next step, using only
  `sale` legs, `mint`/`burn` as zero-cost basis, and excluding `internal` and the
  remaining `unpriced`.

---
*Artifacts: `transfer_ledger.jsonl`, `transfer_ledger_enriched.jsonl`,
`reconcile.py`, `build_ledger.py`, `enrich_ledger.py`, `enrich_router_prices.py`.
Reconciled @ block 25317458.*
