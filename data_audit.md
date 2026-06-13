# Data completeness audit — trade-parse vs on-chain ground truth

**Question (this step, NOT P&L):** is the parsed trade data complete and accurate
enough to compute P&L on top of it? **Invariant tested:** for each wallet,
*current on-chain NFT balance == (all buys − all sells) in our parsed data*, per
collection. If it doesn't hold, the trade data is incomplete and any P&L built on
it is unreliable.

**Verdict: FAIL — comprehensively.** The invariant breaks for **31 of 31**
(wallet, collection) pairs that have any activity. Our parsed data implies a net
**+233 NFTs still held** across the three wallets; the **on-chain truth is 10**.
The data is not complete; **do not compute P&L on it yet.**

- **Ground truth:** `balanceOf(wallet)` per ERC-721 contract at **block 25309848**
  (today), cross-checked against full ERC-721 `Transfer`-event reconstruction for
  the three active collections. This is authoritative and source-independent.
- **Our data:** `analysis/blur/trades_full.jsonl` (Blur on-chain) +
  `export/events_hist_*.json` (OpenSea), netted buys−sells per token.

## On-chain ground truth (block 25309848)

| wallet | holdings (balanceOf) |
|---|---|
| 0x0282 (trait bot) | **7 CloneX** (#1798, 4248, 7864, 11598, 12054, 15474, 19543) + **1 LilPudgys** (#16549) |
| 0x400f (item bot) | **2 PudgyPenguins** (incl. #1381) |
| 0x8e8d (vault) | **0 — empty** (no NFTs in any traded collection) |

(The 0x400f reference — "1 Pudgy #1381 + 1 other in Blur UI" — is confirmed: both
held tokens are PudgyPenguins; #1381 is one of them.)

## Reconciliation: our net vs on-chain, per wallet/collection

### 0x0282 (trait bot)

| wallet | collection | our buys | our sells | our net | on-chain | diff | likely cause |
|---|---|---|---|---|---|---|---|
| 0x0282 (trait bot) | azuki | 0 | 2 | -2 | 0 | -2 | missing BUY-legs (orphan/legacy entry before parse) |
| 0x0282 (trait bot) | bitmappunks | 4 | 20 | -16 | 0 | -16 | missing BUY-legs (orphan/legacy entry before parse) |
| 0x0282 (trait bot) | clonex | 106 | 113 | -7 | 7 | -14 | missing BUY-legs (orphan/legacy entry before parse) |
| 0x0282 (trait bot) | degods-eth | 130 | 86 | +44 | 0 | +44 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x0282 (trait bot) | lilpudgys | 82 | 90 | -8 | 1 | -9 | missing BUY-legs (orphan/legacy entry before parse) |
| 0x0282 (trait bot) | meebits | 0 | 1 | -1 | 0 | -1 | missing BUY-legs (orphan/legacy entry before parse) |
| 0x0282 (trait bot) | mutant-ape-yacht-club | 10 | 9 | +1 | 0 | +1 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x0282 (trait bot) | pudgypenguins | 5 | 1 | +4 | 0 | +4 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x0282 (trait bot) | sappy-seals | 4 | 5 | -1 | 0 | -1 | missing BUY-legs (orphan/legacy entry before parse) |
| 0x0282 (trait bot) | y00ts-eth | 4 | 0 | +4 | 0 | +4 | missing SELL-legs (buys recorded, exits not parsed) |

### 0x400f (item bot)

| wallet | collection | our buys | our sells | our net | on-chain | diff | likely cause |
|---|---|---|---|---|---|---|---|
| 0x400f (item bot) | azuki | 2 | 0 | +2 | 0 | +2 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x400f (item bot) | boredapeyachtclub | 4 | 3 | +1 | 0 | +1 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x400f (item bot) | clonex | 70 | 81 | -11 | 0 | -11 | missing BUY-legs (orphan/legacy entry before parse) |
| 0x400f (item bot) | degods-eth | 65 | 17 | +48 | 0 | +48 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x400f (item bot) | doodles-official | 74 | 31 | +43 | 0 | +43 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x400f (item bot) | lilpudgys | 87 | 64 | +23 | 0 | +23 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x400f (item bot) | meebits | 0 | 1 | -1 | 0 | -1 | missing BUY-legs (orphan/legacy entry before parse) |
| 0x400f (item bot) | mutant-ape-yacht-club | 5 | 2 | +3 | 0 | +3 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x400f (item bot) | persona | 14 | 0 | +14 | 0 | +14 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x400f (item bot) | pudgypenguins | 50 | 12 | +38 | 2 | +36 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x400f (item bot) | rektguy | 0 | 1 | -1 | 0 | -1 | missing BUY-legs (orphan/legacy entry before parse) |
| 0x400f (item bot) | sappy-seals | 15 | 2 | +13 | 0 | +13 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x400f (item bot) | the-dooplicator | 13 | 18 | -5 | 0 | -5 | missing BUY-legs (orphan/legacy entry before parse) |

### 0x8e8d (vault)

| wallet | collection | our buys | our sells | our net | on-chain | diff | likely cause |
|---|---|---|---|---|---|---|---|
| 0x8e8d (vault) | boredapeyachtclub | 65 | 20 | +45 | 0 | +45 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x8e8d (vault) | clonex | 49 | 50 | -1 | 0 | -1 | missing BUY-legs (orphan/legacy entry before parse) |
| 0x8e8d (vault) | degods-eth | 2 | 0 | +2 | 0 | +2 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x8e8d (vault) | lilpudgys | 72 | 82 | -10 | 0 | -10 | missing BUY-legs (orphan/legacy entry before parse) |
| 0x8e8d (vault) | mutant-ape-yacht-club | 7 | 4 | +3 | 0 | +3 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x8e8d (vault) | otherside-koda | 2 | 0 | +2 | 0 | +2 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x8e8d (vault) | pudgypenguins | 29 | 17 | +12 | 0 | +12 | missing SELL-legs (buys recorded, exits not parsed) |
| 0x8e8d (vault) | sappy-seals | 42 | 47 | -5 | 0 | -5 | missing BUY-legs (orphan/legacy entry before parse) |

## Diagnosis — what is missing

The mismatch has two signatures, both present:

**A. Missing SELL-legs (dominant).** We record buys but not the matching exits, so
our net is far *higher* than reality — **287 tokens our data calls "still held"
against only ~10 truly held**. Worst net-diff rows (our_net − on-chain): 0x400f
degods +48, doodles +43, pudgy +36, lilpudgys +23; 0x8e8d bayc +45, pudgy +12.
**0x8e8d is on-chain empty (0 NFTs) yet our data implies it nets ~+48 still held.**
Every "open lot" in the prior P&L (notably 0x400f's "−12.7 ETH open PudgyPenguins
inventory") is **phantom** — those tokens were sold; we just never parsed the
disposal.

**B. Missing BUY-legs (legacy/orphan).** Some collections show our net *below*
on-chain or negative — we have sells with no recorded entry (148 tokens oversold).
E.g. 0x0282 bitmappunks −16, clonex −7, 0x8e8d lilpudgys −10. These are entries
made before the parse window / via unparsed paths.

**C. Identity drift even where counts nearly agree.** Counts balancing does not mean
the data is right. 0x0282 lilpudgys: our net "held" set = {2152, 9723, 10982,
13844} — **all four are ghosts**; the one token actually on-chain (#16549) is
**absent from our data entirely**. Netting hides compensating errors.

### Coverage measurement (active collections, full Transfer reconstruction)

| wallet · collection | on-chain IN / OUT | our buys / sells | buy capture | sell capture |
|---|---|---|---|---|
| 0x400f · pudgypenguins | 118 / 117 | 50 / 12 | **42%** | **10%** |
| 0x0282 · clonex | 108 / 101 | 106 / 113 | 98% | 112%* |
| 0x0282 · lilpudgys | 92 / 91 | 82 / 90 | 89% | 99% |

\*>100% = our sells exceed on-chain acquisitions for those tokens → double-counts
and/or sells of tokens whose buy we missed.

**The clearest gap — 0x400f PudgyPenguins (the active-loop core):** on-chain shows
**235 transfer legs (118 in, 117 out)**; our data has **62 legs, all Blur, zero
OpenSea → ~26% leg coverage**. ~173 acquisitions/disposals are completely
unparsed.

## What is under-parsed (the concrete gaps — diagnosis only, NOT patched)

1. **OpenSea history is truncated / mis-keyed for the high-volume item bot.**
   0x400f has **0** PudgyPenguins rows in `events_hist_pudgypenguins.json`, yet
   on-chain it churned 118 pengus. The OpenSea pull is missing this wallet's
   pudgy trades (and the OpenSea sale feed ends **2026-06-09**, ~3 days stale vs
   the Blur feed at 2026-06-12).
2. **Sell/transfer-out legs systematically dropped.** Across all wallets we keep
   far more buys than sells; 287 "ghost" holdings vs 10 real. Disposals via
   marketplaces or transfer types we don't decode (e.g. non-ETH settlements,
   bundle sales, transfers to other addresses/contracts) are not captured.
3. **No transfer-level ledger at all.** Both sources are *marketplace-sale*
   feeds. Plain ERC-721 `Transfer`s — mints, claims, cross-wallet moves,
   transfers to/from the vault, OTC — are invisible. The audit's ground truth
   needed raw `Transfer` logs precisely because the sale feeds miss them.
4. **Blur feed itself is incomplete on disposals.** Even on Blur-only pudgy,
   we have 50 buys but only 12 sells while on-chain in≈out — Blur exit legs are
   under-captured, not just OpenSea ones.

## Conclusion

The parsed trade data is **incomplete in both directions** (missing exits
dominate, missing entries present) and **wrong at the token-ID level even where
aggregate counts nearly match**. The invariant fails for every active pair. The
previously reported P&L — especially open mark-to-market inventory — rests on
phantom holdings and is **not trustworthy**.

**P&L should be recomputed only after** the trade ledger reconciles to on-chain
`balanceOf` per wallet/collection (target: diff = 0 for all rows), which requires
rebuilding from **raw ERC-721 `Transfer` events** (the authoritative leg source)
rather than marketplace-sale feeds, plus re-pulling the OpenSea history for the
item bot and the missing Blur disposal legs.

---
*Ground truth: on-chain `balanceOf` + `Transfer` reconstruction @ block 25309848.
Artifacts: `analysis/onchain_balances.json`, `analysis/onchain_transfers_sample.json`.*
