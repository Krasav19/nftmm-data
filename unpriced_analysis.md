# Unpriced-leg analysis — are the gaps in the active loop or legacy?

464 of 2491 ledger legs are `unpriced` (no price from Blur/OpenSea feeds or the
receipt fallback). Before P&L, this resolves whether those gaps sit in the **active
core** (clonex/lilpudgys/pudgypenguins) or in **legacy**, and whether they are
**recoverable** with another data source.

## 1. By collection — active core vs legacy

| scope | collection | unpriced legs |
|---|---|---|
| **ACTIVE** | pudgypenguins | 216 |
| legacy | bitmappunks | 65 |
| legacy | degods-eth | 64 |
| legacy | boredapeyachtclub | 29 |
| legacy | doodles-official | 19 |
| **ACTIVE** | lilpudgys | 16 |
| legacy | persona | 13 |
| legacy | azuki | 9 |
| legacy | sappy-seals | 9 |
| **ACTIVE** | clonex | 5 |
| legacy | mutant-ape-yacht-club | 5 |
| legacy | y00ts-eth | 5 |
| legacy | otherside-koda | 5 |
| legacy | meebits | 2 |
| legacy | rektguy | 1 |
| legacy | the-dooplicator | 1 |
| | **active total** | **237** |
| | **legacy total** | **227** |

**Split is ~even: 237 active / 227 legacy.** The active count is almost all
pudgypenguins (216), with lilpudgys (16) and clonex (5).

## 2. By direction

| scope | in | out |
|---|---|---|
| active core | 0 | 237 |
| legacy | 24 | 203 |

**Active-core unpriced are 100% OUT-legs (dispositions)** — i.e. sales/exits whose
price we failed to attach. That is exactly the kind of gap that would bias P&L, so
it had to be chased down (below).

## 3. By reason — what these txs actually are (full tx inspection via RPC)

Every unpriced tx was fetched (`eth_getTransactionByHash` + receipt) and classified
by router (`tx.to` / log addresses) and money movement.

### Active core (237 legs / 235 txs)

| reason | txs | recoverable? |
|---|---|---|
| OpenSea (Seaport) sale, native ETH value present | 70 | **YES — value in tx** |
| Blur sale, native ETH value present | 58 | **YES — value in tx** |
| Blur sale, money-leg present but not to/from our wallet | 69 | partial (Blend/conduit routing) |
| no router, no money — pure transfer (OTC/wallet move) | 33 | no — genuinely priceless |
| OpenSea, money-leg not to our wallet | 5 | partial |

Net recoverability test (price = native `tx.value`, or our WETH/BETH leg):
**176 / 237 active legs (74%) are RECOVERABLE**, 61 are truly money-less transfers.
The cleanest ~128 (the native-ETH Seaport/Blur rows) give a per-leg sale price
directly; the ~48 "money-not-our-wallet" rows are recoverable in principle but need
care (some `tx.value` figures there are Blur Blend loan amounts, not the sale price)
— so treat 128 as the solid floor and 176 as the ceiling of active recovery.

### Legacy (227 legs)

**103 / 227 (45%) recoverable**, 124 truly money-less. Legacy unpriced are lower-value
(recoverable sum ≈ 68 ETH vs ≈ 887 ETH on the active side) and include 24 in-legs
(claims/airdrops).

## 4. Root cause — it is NOT a missing marketplace feed

The recoverable active legs do **not** route through LooksRare / X2Y2 / Sudoswap /
Magic Eden. They route through **OpenSea (Seaport) and Blur — venues we already
pull**. The price is missing only because:

- our **marketplace JSON feeds are incomplete** (these specific sales aren't in
  `events_hist_*.json` / `trades_full.jsonl`), AND
- the receipt fallback in `enrich_ledger.py` only credited ETH when `tx.to`/`tx.from`
  was our wallet. In these sales the **buyer sends the tx** (`tx.from` = buyer,
  `tx.to` = Seaport/Blur router) and the ETH reaches us *through the router* as an
  internal transfer — so `tx.value` holds the real price (e.g. clonex #6080 = 0.288,
  lilpudgys #9723 = 0.555, pudgy #7610 = 7.66, single NFT per tx, verified) but the
  enricher didn't read it.

**So the fix is not another feed — it is reading `tx.value` on router-routed sale
txs** (an enricher change), which recovers 176 active + 103 legacy = 279 legs on-chain
with no new external dependency.

## 5. Answer to the main question

- **How many active-core unpriced can be recovered, and with what feed?**
  **176 of 237 (74%)** — and the "feed" needed is **none**: it is on-chain
  `tx.value` on Seaport/Blur sale txs, which we can read with the RPC we already use.
  Adding LooksRare/X2Y2/etc. would recover **nothing** here — those venues aren't
  used.
- **Are the recoverable legs only legacy?** No — the opposite. The recoverable bucket
  is **larger and higher-value on the active side** (128–176 legs) than legacy
  (103 legs). These are real active-loop exits (notably 0x0282/0x400f trait & item
  pudgy sales) that P&L must not drop. (The raw recoverable-value sums — ≈887 ETH
  active vs ≈68 ETH legacy — are upper bounds; some active rows carry Blend loan
  amounts in `tx.value`, so the gap is directional, not exact.)
- **Verdict:** the 80% coverage is **not** the honest ceiling — it is an enricher
  limitation, not a data-availability one. Recovering `tx.value` on router-routed
  sales lifts active-core pricing from ~64% (pudgy) toward ~95%+ and is a prerequisite
  before P&L. The ~61 active + 124 legacy truly-money-less legs (pure transfers) are
  the real floor and stay `unpriced` by design.

---
*Method: full RPC inspection of all 464 unpriced txs (router id + WETH/BETH/native
value). Per-leg sale prices spot-verified single-NFT (no multi-item inflation).*
