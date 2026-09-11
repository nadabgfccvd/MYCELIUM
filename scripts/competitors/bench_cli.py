#!/usr/bin/env python3
"""Uniform driver for the S2 Cycle-9 sieve comparison.

Times every implementation over the SAME sizes in the SAME way (one warmup,
best-of-P9_REPS in-process passes per size, total wall seconds) and emits a
checksum so a wrong implementation can never silently "win". Run with the
module name as the only argument; compiled extensions (.so from mypyc/Cython)
must be importable from the current directory.

    python bench_cli.py cpython|mycelium|mypyc|mypyc_fast|cython|cython_fast

Prints one JSON object: {"seconds", "best_per_n", "count_1m", "sum_1m", ...}.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import time

MODULES = {
    "cpython": "kernel",          # classic nested loop (also used under -O)
    "mycelium": "kernel_mycelium",  # safe pure-Python bulk-slice variant
    "mypyc": "kernel_mypyc",      # classic loop, mypyc (typed Python list)
    "mypyc_fast": "kernel_mypyc_fast",  # bytearray marking loop, mypyc
    "cython": "kernel_cy",        # classic loop, Cython (Python list)
    "cython_fast": "kernel_cy_fast",  # bytearray, bounds checks off
}
SIZES = [200_000, 500_000, 1_000_000]


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in MODULES:
        print(f"usage: bench_cli.py {{{'|'.join(MODULES)}}}", file=sys.stderr)
        return 2
    impl = argv[1]
    mod = importlib.import_module(MODULES[impl])
    reps = int(os.environ.get("P9_REPS", "5"))

    reference = mod.primes_below(SIZES[-1])
    count_1m, sum_1m = len(reference), sum(reference)
    mod.primes_below(50_000)  # warmup

    best_per_n: dict[int, float] = {}
    for n in SIZES:
        best = float("inf")
        last_len = 0
        for _ in range(reps):
            t0 = time.perf_counter()
            out = mod.primes_below(n)
            dt = time.perf_counter() - t0
            best = min(best, dt)
            last_len = len(out)
        best_per_n[n] = best
        # cross-size sanity against the well-known prime counts
        expected = {200_000: 17_984, 500_000: 41_538, 1_000_000: 78_498}[n]
        if last_len != expected:
            print(f"WRONG RESULT for {impl} n={n}: {last_len} != {expected}",
                  file=sys.stderr)
            return 1

    print(json.dumps({
        "impl": impl,
        "seconds": sum(best_per_n.values()),
        "best_per_n": {str(k): v for k, v in best_per_n.items()},
        "count_1m": count_1m,
        "sum_1m": sum_1m,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
