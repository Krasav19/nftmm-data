# NFT Market Maker — final cross-venue P&L (90-day active loop)

**Window:** 2026-03-14 → 2026-06-12 (trailing 90d) · **Floors:** 2026-06-12T20:45:01Z · **Venues:** OpenSea + Blur on-chain, FIFO, one ledger.

**Net of:** OpenSea 1% fee on sells only · Blur 0% fee · royalty 0 · gas (Blur real from RPC, OpenSea flat 0.0015 ETH/leg). Orphan entries (buy before window) excluded as legacy (11 trips, -0.512 ETH). 257 OpenSea sales deduped against the authoritative Blur record.

| wallet | realized 90d (ETH) | trips | win rate | open-MTM 90d (ETH) | open lots |
|---|---|---|---|---|---|
| 0x0282 (trait bot) | **+1.213** | 105 | 76.2% | -0.573 | 11 |
| 0x400f (item bot) | **+3.429** | 38 | 78.9% | -12.334 | 18 |
| 0x8e8d (vault) | **+0.000** | 0 | 0.0% | +0.180 | 1 |
| **TOTAL** | **+4.642** | **143** | **76.9%** | **-12.726** | **30** |

**Net P&L of the active loop, last 90 days = +4.642 ETH realized + -12.726 ETH open-MTM = -8.084 ETH.**
