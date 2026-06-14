# Ledger reconciliation — authoritative ERC-721/1155 Transfer ledger

**Built from raw on-chain `Transfer` events** (not marketplace feeds). For each of
the three wallets we pulled every ERC-721 `Transfer` and ERC-1155
`TransferSingle`/`TransferBatch` log where the wallet is `from` or `to`, across the
full history of all 16 collections with any activity, via RPC (publicnode 50k-block
chunks, OR-topic on the three wallets, RPC failover + backoff, resumable per-chunk
cache). Marketplace feeds (OpenSea/Blur) are used ONLY to attach a price; they are
not the source of legs.

**Ledger:** `transfer_ledger.jsonl` (2491 legs) ·
**Enriched:** `transfer_ledger_enriched.jsonl` (+ class & price) ·
**Reconciled @ block 25317059.**

## 1. Invariant: ledger net(in − out) == on-chain `balanceOf` — **HOLDS (diff=0)**

Verified programmatically (`reconcile.py`): for every (wallet, collection) the net
of in minus out legs equals current `balanceOf`, and every token the ledger says is
held was confirmed token-by-token via `ownerOf`.

| wallet | ledger net == balanceOf | held tokens (ownerOf-confirmed) |
|---|---|---|
| 0x0282 (trait bot) | ✅ 7 CloneX, 2 LilPudgys, 1 Koda | CloneX #1798/4248/7864/11598/12054/15474/19543 · LilPudgys #16549/#8513 · Koda #8369 |
| 0x400f (item bot) | ✅ 1 PudgyPenguins | Pudgy #1381 |
| 0x8e8d (vault) | ✅ 0 | — (empty) |

*Note on live chain:* the chain advanced during the build. 0x0282 acquired Koda
#8369 and LilPudgys #8513, and 0x400f sold one of its two pengus, all mid-build —
each captured and re-reconciled to diff=0 at block 25317059. (The earlier audit's
"0x400f = 2 Pudgy" snapshot was true at its block; one was sold since.) This is the
proof the marketplace-only data lacked: **every movement now ties out to chain
state**, where the sale feeds covered only ~26% of legs.

## 2. Price-enrichment coverage

Each external (tradeable) leg gets a price from, in priority: Blur on-chain trade →
OpenSea sale event → on-chain ETH/WETH/BETH value moved to/from the wallet in the
same tx (`receipt`).

**Overall external-leg price coverage: 1884/2348 = 80.2%**
(was ~26% on marketplace feeds alone). Price sources: OpenSea 1095,
Blur 477, on-chain receipt 312.

| wallet | sale | unpriced | mint | burn | internal | price coverage (external) |
|---|---|---|---|---|---|---|
| 0x0282 (trait bot) | 699 | 164 | 100 | 27 | 2 | 699/863 = 81% |
| 0x400f (item bot) | 619 | 172 | 0 | 14 | 0 | 619/791 = 78% |
| 0x8e8d (vault) | 566 | 128 | 0 | 0 | 0 | 566/694 = 82% |

## 3. Leg classification (the full 2491-leg ledger)

| class | legs | meaning | in P&L? |
|---|---|---|---|
| **sale** | 1884 | price found (market or on-chain value) | **yes** |
| **unpriced** | 464 | real external transfer, no recoverable price (OTC / unindexed venue / transfer to contract) | no (flagged, kept in ledger) |
| **mint** | 100 | acquired from 0x0 (mint/claim) | cost-basis 0, tracked separately |
| **burn** | 41 | sent to 0x0 | tracked separately |
| **internal** | 2 | counterparty is one of our own 3 wallets | **no — not a trade** |

**Unpriced legs are 440/464 out-legs**, concentrated in
pudgypenguins/degods/bayc — i.e. dispositions via venues or transfer types not in
our price sources (e.g. transfers to staking/escrow contracts, OTC). The
**active-loop collections price near-completely** (CloneX 99%, LilPudgys 92–99%,
the-dooplicator 97%), so P&L on the active loop is well-supported; the unpriced tail
sits mostly in legacy directional names.

## 4. Verdict

- **Invariant satisfied** — the ledger is complete: net movements reconcile to
  `balanceOf` and `ownerOf` for every wallet, every held token, diff=0.
- **Price coverage 80%** — acceptable and 3× the prior 26%;
  the gap is legacy non-market dispositions, flagged not fabricated.
- **P&L is NOT computed here** (per instruction). The ledger now meets both
  preconditions (reconciled + priced); P&L can be built on it as the next step,
  using only `sale` legs, `mint`/`burn` as zero-cost basis, and excluding
  `internal` and `unpriced`.

---
*Artifacts: `transfer_ledger.jsonl`, `transfer_ledger_enriched.jsonl`,
`reconcile.py`, `build_ledger.py`, `enrich_ledger.py`. Reconciled @ block 25317059.*
