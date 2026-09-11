#!/usr/bin/env python3
"""P5 benchmark workload: natsort 8.4.0 under PYTHONOPTIMIZE=1 (S2 Cycle 7).

Natural-sort a large, deterministic list generated from MYCELIUM_SEED (paired:
baseline and variant sort the same list per seed). Import is inside the timed
region so the -O effect on import/assert bytecode is included.

Prints ``{"seconds": <float>, "checksum": <int>}``.
"""
from __future__ import annotations

import json
import os
import random
import time

seed = int(os.environ.get("MYCELIUM_SEED", "101"))
rng = random.Random(seed)
count = int(os.environ.get("PORTFOLIO_NATSORT_COUNT", "120000"))


def corpus() -> list[str]:
    names = []
    for _ in range(count):
        kind = rng.randrange(4)
        n = rng.randrange(9_999_999)
        if kind == 0:
            names.append(f"file{n:07d}_v{rng.randrange(20)}.txt")
        elif kind == 1:
            names.append(f"{rng.choice(['img', 'doc', 'log'])}-{n}.{rng.randrange(99)}.dat")
        elif kind == 2:
            names.append(f"{rng.randrange(50)}.{n}.{rng.randrange(9)}-release")
        else:
            names.append(f"{rng.choice(['IMG', 'img', 'File', 'file'])}{n}.tmp")
    return names


def main() -> None:
    start = time.perf_counter()
    from natsort import natsorted, ns  # noqa: PLC0415

    data = corpus()
    ordered = natsorted(data, alg=ns.DEFAULT)
    elapsed = time.perf_counter() - start
    checksum = len(ordered) + sum(len(s) for s in ordered[:1000])
    print(json.dumps({"seconds": elapsed, "checksum": checksum}))


if __name__ == "__main__":
    main()
