#!/usr/bin/env python3
"""P3 benchmark workload: tabulate under PYTHONOPTIMIZE=1 (Cycle 7 portfolio).

The archived run found ~0 effect (CI crosses zero, p=0.46) and the guard
REJECTED the same env variant that was accepted on sqlparse -- the honest
negative the harness exists to produce. This script reproduces the
methodology; host-specific numbers vary.
Prints ``{"seconds": <float>}``.
"""
from __future__ import annotations

import json
import os
import random
import time

# NOTE: tabulate is imported lazily inside main(), inside the timed region
# (the archived metric ~= whole-command wall time, import included).

seed = int(os.environ.get("MYCELIUM_SEED", "101"))
rng = random.Random(seed)

_TABLEFMTS = ["grid", "fancy_grid", "pipe", "orgtbl", "rst", "mediawiki",
              "latex", "tsv"]


# Sized for ~1 s per pass (archived run magnitude); override per host.
_TABLES = int(os.environ.get("PORTFOLIO_TAB_TABLES", "150"))
_FLOAT_TABLES = int(os.environ.get("PORTFOLIO_TAB_FLOATS", "50"))


def workload(tabulate) -> int:
    checksum = 0
    for _ in range(_TABLES):
        cols = rng.randrange(3, 7)
        rows = rng.randrange(20, 60)
        headers = [f"col_{rng.randrange(999)}" for _ in range(cols)]
        table = [
            [rng.randrange(100_000) for _ in range(cols)] for _ in range(rows)
        ]
        table[0] = [f"str {rng.randrange(9999)}"] + table[0][1:]
        for fmt in _TABLEFMTS:
            out = tabulate(table, headers=headers, tablefmt=fmt)
            checksum += len(out)

    for _ in range(_FLOAT_TABLES):
        table = [
            [rng.random() * 1000 for _ in range(8)] for _ in range(40)
        ]
        checksum += len(tabulate(table, floatfmt=".4f", tablefmt="grid"))
    return checksum


def main() -> None:
    # Timer includes import (see bench_sqlparse.py rationale).
    start = time.perf_counter()
    from tabulate import tabulate  # noqa: PLC0415

    checksum = workload(tabulate)
    elapsed = time.perf_counter() - start
    print(json.dumps({"seconds": elapsed, "checksum": checksum}))


if __name__ == "__main__":
    main()
