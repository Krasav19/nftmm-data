# Authoritative P&L — reconciled Transfer ledger (one pass, final)

Built on `transfer_ledger_enriched.jsonl` (net in−out == on-chain `balanceOf`, diff=0; active core 97.7% priced). FIFO buy→sell per token, cross-venue, single ledger. **90d window 2026-03-17 → 2026-06-15** (the active loop) shown beside all-time. Floors @ 2026-06-15T20:45:01Z.

**Net of:** OpenSea 1% fee on sells only · Blur 0% · royalty 0 · gas (Blur real from receipt, OpenSea flat 0.0015/leg). Feed prices are gross (fee applied); on-chain trace/receipt prices are already net of fee. MTM only on tokens **held now** (reconciled `balanceOf` set). Orphan sells (entry before our data) excluded.

| wallet | realized 90d | 90d trips | 90d win | open-MTM (held now) | realized all-time | all-time trips |
|---|---|---|---|---|---|---|
| 0x0282 (trait bot) | **+1.119** | 115 | 75.7% | -0.092 (3.31→3.21) | +3.163 | 421 |
| 0x400f (item bot) | **-6.923** | 83 | 74.7% | +0.320 (4.37→4.69) | -3.099 | 307 |
| 0x8e8d (vault) | **+0.000** | 0 | 0.0% | — | -28.149 | 301 |
| **TOTAL** | **-5.803** | **198** | **75.3%** | **+0.228 (7.68→7.90)** | **-28.084** | **1029** |

*open-MTM column = (cost basis → floor value); the signed number is unrealized at floor on currently-held tokens.*

## Bottom line (kept separate, not summed)

- **Net realized P&L, 90d active loop = -5.803 ETH** across 198 priced round-trips, 75.3% win.
- **Current open-MTM (held now, at floor) = +0.228 ETH** unrealized, on 7.68 ETH cost basis (7.90 ETH at floor).
- These are **not added** into a single figure: one is realized cash, the other is an unrealized mark on open inventory that moves with the floor.

## The 751 ETH "unpriced exits" — resolved

The earlier report flagged **137 lots / 751 ETH** of cost basis as exits with unknown P&L — the boundary between "operator is deeply underwater" and "unknown". Tracing every one of those txs (full trace + all ETH/WETH/BETH flows, destination-address analysis) resolves it:

- **137 lots / 751.0 ETH → operator's own treasury cluster (INTERNAL, not sales).** All 137 went to just 11 addresses, every one of which has **thousands of bidirectional native-ETH transfers (~6.5k+ ETH each way) with our three wallets** — a funding/treasury cluster, not arm's-length buyers. **0 ETH was received for any of these NFTs**; 73 were plain `transferFrom` pushes we initiated, 64 went via a bulk-transfer helper to the same cluster (notably `0xa171759d`, an EIP-7702 smart account). These are **inventory relocations within the operation, not losses**.
- **Net effect on P&L: none to realized.** These legs never booked a sale, so realized (−5.80 90d / −28.08 all-time) is **unchanged**. What changes is the *interpretation*: the 751 ETH overhang is **not** a hidden loss — it is the operator's own inventory, moved to sibling wallets. Only **1** of the 137 lots (0.5 ETH lilpudgys) falls in the 90d window.
- **So the answer to "underwater or unknown?": neither becomes a bigger loss.** The unpriced exits are internal moves; the operator is **not** more underwater than the priced realized shows. The honest realized remains −5.80 ETH (90d) over visible market exits, with the big 751-ETH question mark removed.
- *Confidence:* linkage is strong by ETH-flow volume; the uniformity of the per-address totals may partly reflect shared MEV/builder bundles, but the direction is unambiguous — these are not external sale proceeds (0 ETH received).

## Remaining limits of certainty

- **Non-linked unpriced out-legs: 0 lots on 0.00 ETH basis** — exits to addresses NOT in the linked cluster with no recoverable price. Exit P&L unknown (not floored).
- **Burns: 40 lots on 14.55 ETH basis** — sent to 0x0, disposal with no proceeds (not a floor sale).
- **Migrations: 10 lots on 96.21 ETH basis** — tokens swapped out in a tx where we also received an NFT (the 2023 DeGods/MAYC contract migrations). These are **not sales**; the incidental ETH in those txs is not an exit price, so they are excluded from realized rather than booked as ~0 ETH dumps.
- **Cluster-moved inventory (751 ETH basis)** still exists in the operator's sibling wallets; it is outside our three tracked wallets, so it is neither realized nor in the open-MTM above — it simply left this ledger's scope intact (not destroyed value).
- **Mints** entered FIFO at cost basis 0 (receipt showed no mint price).
