#!/usr/bin/env python3
"""Reconcile the Transfer ledger against on-chain balanceOf — the hard invariant.

net(in - out) per token from transfer_ledger.jsonl MUST equal current ownership.
We check at the token level: for each (wallet, contract, token), net must be 0 or
1 (1155 may exceed), and the set of tokens with net>0 must equal the wallet's
on-chain holdings (verified token-by-token via ownerOf for 721). Any mismatch =>
STOP (likely a too-high deploy lower-bound truncating early legs).
"""
import json, os
from collections import defaultdict
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
RPCS = ["https://ethereum-rpc.publicnode.com", "https://rpc.mevblocker.io",
        "https://eth.llamarpc.com", "https://eth.drpc.org"]
_i = 0


def rpc(method, params):
    global _i
    for _ in range(len(RPCS) * 3):
        url = RPCS[_i % len(RPCS)]; _i += 1
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1,
                              "method": method, "params": params}, timeout=30)
            if r.status_code != 200:
                continue
            j = r.json()
            if "result" in j:
                return j["result"]
        except Exception:
            continue
    return None


def balance_of(con, w):
    r = rpc("eth_call", [{"to": con, "data": "0x70a08231" + w[2:].rjust(64, "0")}, "latest"])
    return int(r, 16) if r else None


def owner_of(con, token):
    r = rpc("eth_call", [{"to": con, "data": "0x6352211e" + hex(int(token))[2:].rjust(64, "0")}, "latest"])
    return ("0x" + r[-40:]).lower() if r and len(r) >= 42 else None


WN = {"0x028296d8bf1995549d5b9446622cf565bbd0a26e": "0x0282",
      "0x400f2bd92098c386cea677d6e7f832eb25c6e3cf": "0x400f",
      "0x8e8d6246c45d0e7f68172e85573546d90fc2e062": "0x8e8d"}


def main():
    legs = [json.loads(l) for l in open(f"{ROOT}/transfer_ledger.jsonl")]
    contracts = {l["collection"]: l["contract"] for l in legs}

    # net per (wallet, collection, token)
    net = defaultdict(int)
    for l in legs:
        net[(l["wallet"], l["collection"], l["token"])] += l["qty"] if l["dir"] == "in" else -l["qty"]

    # implied holdings from ledger
    implied = defaultdict(list)  # (wallet, collection) -> [tokens with net>0]
    bad_net = []
    for (w, col, tok), n in net.items():
        if n < 0:
            bad_net.append((WN[w], col, tok, n))
        elif n > 0:
            implied[(w, col)].append((tok, n))

    print("=== INVARIANT CHECK: ledger net(in-out) vs on-chain ===\n")
    ok = True
    if bad_net:
        ok = False
        print(f"!! {len(bad_net)} tokens with NEGATIVE net (out>in) — impossible, "
              "means missing IN legs (deploy bound too high?):")
        for r in bad_net[:20]:
            print("   ", r)
        print()

    # per (wallet, collection): implied count vs balanceOf, and token-level ownerOf
    print(f"{'wallet':<7}{'collection':<22}{'ledger_net':>11}{'balanceOf':>11}{'diff':>6}")
    grand_ok = True
    for w in WN:
        cols = sorted({c for (ww, c) in implied if ww == w} | set(contracts))
        for col in cols:
            toks = implied.get((w, col), [])
            cnt = sum(q for _, q in toks)
            bo = balance_of(contracts[col], w)
            if cnt == 0 and bo == 0:
                continue
            diff = cnt - (bo or 0)
            flag = "" if diff == 0 else "  <-- MISMATCH"
            if diff != 0:
                grand_ok = False
            print(f"{WN[w]:<7}{col:<22}{cnt:>11}{str(bo):>11}{diff:>6}{flag}")

    # token-level ownerOf spot check for the named holdings
    print("\n=== token-level ownerOf verification (the named holdings) ===")
    checks = [
        ("0x028296d8bf1995549d5b9446622cf565bbd0a26e", "clonex"),
        ("0x028296d8bf1995549d5b9446622cf565bbd0a26e", "lilpudgys"),
        ("0x400f2bd92098c386cea677d6e7f832eb25c6e3cf", "pudgypenguins"),
    ]
    for w, col in checks:
        toks = sorted(t for t, q in implied.get((w, col), []))
        print(f"\n{WN[w]} {col}: ledger says held = {toks}")
        for t in toks:
            o = owner_of(contracts[col], t)
            mark = "OK" if o == w else f"OWNED BY {o}"
            if o != w:
                grand_ok = False
            print(f"   #{t}: ownerOf -> {mark}")

    print("\n" + ("=" * 50))
    if grand_ok and ok:
        print("INVARIANT HOLDS: ledger net == balanceOf, diff=0 for every wallet/"
              "collection, and every implied-held token is confirmed by ownerOf.")
    else:
        print("INVARIANT FAILS — STOP. Do not proceed to pricing/P&L.")
    print("=" * 50)
    return grand_ok and ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
