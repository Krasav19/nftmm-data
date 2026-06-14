#!/usr/bin/env python3
"""Fill the logcache for ONE collection (both directions), resumably.
Parallel-safe: each worker writes only its own (collection, dir, chunk) files.
Usage: python3 fill_cache.py <collection>
"""
import sys, os, json
import build_ledger as B

col = sys.argv[1]
contract, deploy = B.DEPLOYS[col]
head = B.head_block()
done = skipped = failed = 0
for direction in ("in", "out"):
    lo = deploy
    while lo <= head:
        hi = min(lo + B.CHUNK - 1, head)
        cp = B.cache_path(col, direction, lo)
        if os.path.exists(cp):
            skipped += 1
            lo = hi + 1
            continue
        logs = B.get_logs_chunk(contract, direction, lo, hi)
        if logs is None:
            failed += 1
        else:
            json.dump(logs, open(cp, "w"))
            done += 1
        lo = hi + 1
print(f"{col}: done={done} skipped={skipped} failed={failed}")
