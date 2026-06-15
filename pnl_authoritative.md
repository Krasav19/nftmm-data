# Authoritative P&L — reconciled Transfer ledger (one pass, final)

Built on `transfer_ledger_enriched.jsonl` (net in−out == on-chain `balanceOf`, diff=0; active core 97.7% priced). FIFO buy→sell per token, cross-venue, single ledger. **90d window 2026-03-17 → 2026-06-15** (the active loop) shown beside all-time. Floors @ 2026-06-15T16:45:01Z.

**Net of:** OpenSea 1% fee on sells only · Blur 0% · royalty 0 · gas (Blur real from receipt, OpenSea flat 0.0015/leg). Feed prices are gross (fee applied); on-chain trace/receipt prices are already net of fee. MTM only on tokens **held now** (reconciled `balanceOf` set). Orphan sells (entry before our data) excluded.

| wallet | realized 90d | 90d trips | 90d win | open-MTM (held now) | realized all-time | all-time trips |
|---|---|---|---|---|---|---|
| 0x0282 (trait bot) | **+1.119** | 115 | 75.7% | -0.059 (3.31→3.25) | +3.163 | 421 |
| 0x400f (item bot) | **-6.923** | 83 | 74.7% | +0.320 (4.37→4.69) | -3.099 | 307 |
| 0x8e8d (vault) | **+0.000** | 0 | 0.0% | — | -28.149 | 301 |
| **TOTAL** | **-5.803** | **198** | **75.3%** | **+0.261 (7.68→7.94)** | **-28.084** | **1029** |

*open-MTM column = (cost basis → floor value); the signed number is unrealized at floor on currently-held tokens.*

## Bottom line (kept separate, not summed)

- **Net realized P&L, 90d active loop = -5.803 ETH** across 198 priced round-trips, 75.3% win.
- **Current open-MTM (held now, at floor) = +0.261 ETH** unrealized, on 7.68 ETH cost basis (7.94 ETH at floor).
- These are **not added** into a single figure: one is realized cash, the other is an unrealized mark on open inventory that moves with the floor.

## Limits of certainty (what the P&L does NOT capture)

- **Unpriced out-legs: 137 lots on 751.03 ETH cost basis.** These tokens left our wallets with **no recoverable exit price** (OTC / escrow / delegate / settlement in another tx). They are **not** valued at floor and **not** in realized above — their exit P&L is **unknown** (not zero, not floor). This is real economic activity we cannot see; treat realized as a figure over the *priced* exits only.
- **Burns: 40 lots on 14.55 ETH basis** — sent to 0x0, disposal with no proceeds (not a floor sale).
- **Migrations: 10 lots on 96.21 ETH basis** — tokens swapped out in a tx where we also received an NFT (the 2023 DeGods/MAYC contract migrations). These are **not sales**; the incidental ETH in those txs is not an exit price, so they are excluded from realized rather than booked as ~0 ETH dumps.
- **Mints** entered FIFO at cost basis 0 (receipt showed no mint price).
