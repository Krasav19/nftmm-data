#!/usr/bin/env python3
"""Final cross-venue P&L — one pass, 90-day active loop.

Single script. Rebuilds one cross-venue ledger from raw sources, runs FIFO
buy->sell per token across both venues, and reports the last-90-day active loop
split into REALIZED (closed pairs, both legs in window) and OPEN-MTM (lots bought
in window, marked to current floor). Orphan entries (buy before the window) are
excluded as legacy.

Sources
  analysis/blur/trades_full.jsonl   Blur on-chain trades (authoritative; tx hash,
                                    price already aggregates ETH+WETH+BETH legs).
  export/events_hist_*.json         OpenSea sales (ETH/WETH legs; price_eth).
  snapshots/snap_*.json             current collection floors for MTM.

Dedup
  326-ish Blur settlements also surface in the OpenSea sale feed. Blur on-chain is
  authoritative: any OpenSea sale matching a Blur trade on (wallet, contract,
  token) within 24h is dropped so nothing is double-counted.

Fees / gas (model, per operator spec)
  OpenSea: 1% fee on the SELL side ONLY (selling our NFT). No fee on buys. Royalty 0.
  Blur:    0% fee everywhere. Royalty 0.
  Gas:     Blur  -> real, from RPC receipt by tx hash (split across NFTs in the tx);
           OpenSea -> flat 0.0015 ETH per leg (buy and sell).
  All P&L below is NET of these.

Window: trailing 90 days from today (UTC midnight).

Outputs: pnl_final.md (the table) and pnl_final.json (machine).
"""
import json
import glob
import time
import datetime as dt
from collections import defaultdict, OrderedDict

ROOT = __file__.rsplit("/", 1)[0]
BLUR = f"{ROOT}/analysis/blur/trades_full.jsonl"
GAS_CACHE = f"{ROOT}/analysis/blur/gas_cache.json"
OUT_MD = f"{ROOT}/pnl_final.md"
OUT_JSON = f"{ROOT}/pnl_final.json"
RPCS = ["https://ethereum-rpc.publicnode.com", "https://rpc.mevblocker.io"]

WALLETS = OrderedDict(
    [
        ("0x028296d8bf1995549d5b9446622cf565bbd0a26e", "0x0282 (trait bot)"),
        ("0x400f2bd92098c386cea677d6e7f832eb25c6e3cf", "0x400f (item bot)"),
        ("0x8e8d6246c45d0e7f68172e85573546d90fc2e062", "0x8e8d (vault)"),
    ]
)

OS_FEE_SELL = 0.01      # 1% on OpenSea sells only
OS_GAS_LEG = 0.0015     # flat ETH per OpenSea leg (buy or sell)
DEDUP_WINDOW = 86400    # 24h to match a Blur trade against an OpenSea sale


# ---------------------------------------------------------------- gas (Blur) ---
def load_gas_cache():
    try:
        return json.load(open(GAS_CACHE))
    except FileNotFoundError:
        return {}


def rpc(method, params):
    import requests

    for url in RPCS:
        try:
            r = requests.post(
                url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                timeout=25,
            )
            j = r.json()
            if "result" in j and j["result"] is not None:
                return j["result"]
        except Exception:
            continue
    return None


def blur_gas_eth(tx, cache):
    """Real gas (ETH) for a Blur settlement tx, cached on disk."""
    if tx in cache:
        return cache[tx]
    rc = rpc("eth_getTransactionReceipt", [tx])
    if not rc:
        cache[tx] = None
        return None
    gas = int(rc["gasUsed"], 16) * int(rc["effectiveGasPrice"], 16) / 1e18
    cache[tx] = gas
    return gas


# ------------------------------------------------------------ build ledger ---
def load_blur():
    rows = []
    with open(BLUR) as f:
        for line in f:
            b = json.loads(line)
            rows.append(
                {
                    "wallet": b["wallet"].lower(),
                    "contract": b["contract"].lower(),
                    "token": str(b["token"]),
                    "collection": b["collection"],
                    "ts": b["ts"],
                    "side": "buy" if b["direction"] == "buy" else "sell",
                    "price": b["price_eth"],   # already ETH+WETH+BETH
                    "venue": "blur",
                    "tx": b["tx"],
                }
            )
    return rows


def load_opensea(blur_rows):
    # index Blur trades for dedup: (wallet, contract, token) -> [(ts, side), ...]
    # Dedup is SAME-SIDE only: a Blur settlement also surfaces in the OpenSea feed
    # on the same side (double-count) -> drop the OpenSea copy. An opposite-side
    # Blur trade on the same token within 24h is a legitimately different leg of a
    # round-trip (e.g. buy on OpenSea, sell on Blur) and must be KEPT.
    bidx = defaultdict(list)
    for b in blur_rows:
        bidx[(b["wallet"], b["contract"], b["token"])].append((b["ts"], b["side"]))

    rows = []
    dropped = 0
    for path in glob.glob(f"{ROOT}/export/events_hist_*.json"):
        for e in json.load(open(path)):
            if e.get("event_type") != "sale":
                continue
            crit = e.get("criteria") or {}
            contract = (crit.get("contract") or "").lower()
            token = str(crit.get("token_ids") or "")
            if not contract or not token or "," in token:
                continue  # skip bundle/criteria sales we can't attribute to one token
            seller = (e.get("seller") or "").lower()
            buyer = (e.get("buyer") or "").lower()
            if seller in WALLETS:
                wallet, side = seller, "sell"
            elif buyer in WALLETS:
                wallet, side = buyer, "buy"
            else:
                continue
            ts = e["event_timestamp"]
            price = e.get("price_eth")
            if not price:
                continue
            # dedup against Blur authoritative record (SAME SIDE only)
            k = (wallet, contract, token)
            if k in bidx and any(
                bs == side and abs(ts - bt) < DEDUP_WINDOW for bt, bs in bidx[k]
            ):
                dropped += 1
                continue
            rows.append(
                {
                    "wallet": wallet,
                    "contract": contract,
                    "token": token,
                    "collection": e.get("collection") or crit.get("collection"),
                    "ts": ts,
                    "side": side,
                    "price": price,
                    "venue": "opensea",
                    "tx": None,
                }
            )
    return rows, dropped


# ------------------------------------------------------------------- costs ---
def buy_cost(leg, cache):
    """Cash out the door to acquire: price + gas. No buy-side fee either venue."""
    if leg["venue"] == "blur":
        g = blur_gas_eth(leg["tx"], cache)
        gas = g if g is not None else 0.0
    else:
        gas = OS_GAS_LEG
    return leg["price"] + gas


def sell_proceeds(leg, cache):
    """Cash received on sale: price - fee - gas. 1% OS fee on sells only; Blur 0%."""
    if leg["venue"] == "blur":
        g = blur_gas_eth(leg["tx"], cache)
        gas = g if g is not None else 0.0
        fee = 0.0
    else:
        gas = OS_GAS_LEG
        fee = leg["price"] * OS_FEE_SELL
    return leg["price"] - fee - gas


# --------------------------------------------------------------------- main ---
def main():
    cache = load_gas_cache()
    blur = load_blur()
    osea, dropped = load_opensea(blur)
    ledger = blur + osea
    ledger.sort(key=lambda r: r["ts"])

    today = dt.datetime.now(dt.timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    cut = int((today - dt.timedelta(days=90)).timestamp())

    # FIFO per (wallet, contract, token), both venues in one queue.
    by_token = defaultdict(list)
    for r in ledger:
        by_token[(r["wallet"], r["contract"], r["token"])].append(r)

    closed = []      # matched buy->sell pairs (net pnl, with both legs' ts)
    open_lots = []   # unmatched buys (still held)
    for key, legs in by_token.items():
        legs.sort(key=lambda r: r["ts"])
        fifo = []  # queue of open buy legs
        for leg in legs:
            if leg["side"] == "buy":
                fifo.append(leg)
            else:  # sell -> match oldest buy
                if not fifo:
                    continue  # orphan sell (no known entry) — excluded
                b = fifo.pop(0)
                cost = buy_cost(b, cache)
                proceeds = sell_proceeds(leg, cache)
                closed.append(
                    {
                        "wallet": b["wallet"],
                        "collection": b["collection"] or leg["collection"],
                        "token": b["token"],
                        "buy_ts": b["ts"],
                        "sell_ts": leg["ts"],
                        "buy_venue": b["venue"],
                        "sell_venue": leg["venue"],
                        "cost": cost,
                        "proceeds": proceeds,
                        "pnl": proceeds - cost,
                    }
                )
        for b in fifo:
            open_lots.append(
                {
                    "wallet": b["wallet"],
                    "collection": b["collection"],
                    "token": b["token"],
                    "buy_ts": b["ts"],
                    "venue": b["venue"],
                    "cost": buy_cost(b, cache),
                    "tx": b["tx"],
                }
            )

    json.dump(cache, open(GAS_CACHE, "w"))

    # ---- 90d window classification ----
    realized = [c for c in closed if c["buy_ts"] >= cut and c["sell_ts"] >= cut]
    orphan_entry = [c for c in closed if c["sell_ts"] >= cut and c["buy_ts"] < cut]

    # current floors for MTM
    snaps = sorted(glob.glob(f"{ROOT}/snapshots/snap_*.json"))
    snap = json.load(open(snaps[-1]))
    floors = {k: v.get("floor_price_eth") for k, v in snap["collections"].items()}
    snap_utc = snap["snapshot_utc"]

    open_90 = []
    for o in open_lots:
        if o["buy_ts"] < cut:
            continue  # legacy inventory
        f = floors.get(o["collection"])
        mv = f if f is not None else 0.0
        open_90.append({**o, "floor": f, "mtm": mv, "unrealized": mv - o["cost"]})

    # ---- aggregates ----
    def r_agg(rows):
        n = len(rows)
        pnl = sum(r["pnl"] for r in rows)
        wins = sum(1 for r in rows if r["pnl"] > 0)
        return {"trips": n, "pnl": pnl, "win": (100 * wins / n) if n else 0.0}

    def o_agg(rows):
        return {
            "lots": len(rows),
            "cost": sum(r["cost"] for r in rows),
            "mtm": sum(r["mtm"] for r in rows),
            "unrealized": sum(r["unrealized"] for r in rows),
        }

    per = OrderedDict()
    for w, name in WALLETS.items():
        per[w] = {
            "name": name,
            "realized": r_agg([c for c in realized if c["wallet"] == w]),
            "open": o_agg([o for o in open_90 if o["wallet"] == w]),
        }
    tot_r = r_agg(realized)
    tot_o = o_agg(open_90)
    tot_oe = r_agg(orphan_entry)

    result = {
        "method": "cross-venue FIFO (OpenSea + Blur on-chain, deduped by "
        "wallet/contract/token within 24h; Blur authoritative). 90d trailing "
        "window. Fees: OpenSea 1% on sells only, Blur 0%, royalty 0. Gas: Blur "
        "real (RPC receipt), OpenSea flat 0.0015 ETH/leg. All P&L net.",
        "window_start": dt.datetime.fromtimestamp(cut, dt.timezone.utc).date().isoformat(),
        "as_of": today.date().isoformat(),
        "floor_source": snap_utc,
        "opensea_sales_deduped_against_blur": dropped,
        "ledger_legs": len(ledger),
        "by_wallet": {
            w: {"name": v["name"], "realized": v["realized"], "open": v["open"]}
            for w, v in per.items()
        },
        "total": {
            "realized": tot_r,
            "open": tot_o,
            "orphan_entry_excluded": tot_oe,
            "active_loop_net": tot_r["pnl"] + tot_o["unrealized"],
        },
    }
    json.dump(result, open(OUT_JSON, "w"), indent=1)

    # ---- markdown table ----
    def f3(x):
        return f"{x:+.3f}"

    L = []
    L.append("# NFT Market Maker — final cross-venue P&L (90-day active loop)\n")
    L.append(
        f"**Window:** {result['window_start']} → {result['as_of']} (trailing 90d) · "
        f"**Floors:** {snap_utc} · "
        f"**Venues:** OpenSea + Blur on-chain, FIFO, one ledger.\n"
    )
    L.append(
        "**Net of:** OpenSea 1% fee on sells only · Blur 0% fee · royalty 0 · "
        "gas (Blur real from RPC, OpenSea flat 0.0015 ETH/leg). "
        f"Orphan entries (buy before window) excluded as legacy "
        f"({tot_oe['trips']} trips, {f3(tot_oe['pnl'])} ETH). "
        f"{result['opensea_sales_deduped_against_blur']} OpenSea sales deduped "
        "against the authoritative Blur record.\n")
    L.append(
        "| wallet | realized 90d (ETH) | trips | win rate | open-MTM 90d (ETH) | open lots |"
    )
    L.append("|---|---|---|---|---|---|")
    for w, v in per.items():
        r, o = v["realized"], v["open"]
        L.append(
            f"| {v['name']} | **{f3(r['pnl'])}** | {r['trips']} | {r['win']:.1f}% | "
            f"{f3(o['unrealized'])} | {o['lots']} |"
        )
    L.append(
        f"| **TOTAL** | **{f3(tot_r['pnl'])}** | **{tot_r['trips']}** | "
        f"**{tot_r['win']:.1f}%** | **{f3(tot_o['unrealized'])}** | **{tot_o['lots']}** |"
    )
    L.append("")
    net = tot_r["pnl"] + tot_o["unrealized"]
    L.append(
        f"**Net P&L of the active loop, last 90 days = "
        f"{f3(tot_r['pnl'])} ETH realized + {f3(tot_o['unrealized'])} ETH open-MTM "
        f"= {net:+.3f} ETH.**"
    )
    L.append("")
    open(OUT_MD, "w").write("\n".join(L))

    print("\n".join(L))
    print(f"\nWrote {OUT_MD} and {OUT_JSON}")


if __name__ == "__main__":
    main()
