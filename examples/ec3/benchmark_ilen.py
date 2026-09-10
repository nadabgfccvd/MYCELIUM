"""EC3 benchmark: ilen() over a seeded mix of sized (70%) and iterator (30%) inputs.

Honest mix on purpose: a benchmark with only lists would overstate the len()
fast path; real call sites pass both. Prints one JSON line for json_stdout.
"""
import json
import os
import random
import time

from more_itertools.more import ilen

seed = int(os.environ.get("MYCELIUM_SEED", "101"))
rng = random.Random(seed)

cases = []
for _ in range(60):
    n = rng.choice([1000, 5000, 20000])
    data = list(range(n))
    cases.append(data if rng.random() < 0.7 else iter(data))

start = time.perf_counter()
total = sum(ilen(c) for c in cases)
elapsed = time.perf_counter() - start
print(json.dumps({"seconds": elapsed, "checksum": total}))
