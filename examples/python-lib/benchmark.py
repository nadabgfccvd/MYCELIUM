"""Workload: dedupe 1.5k seeded ints (heavy duplicates). Prints {"seconds": t}."""
import json
import os
import random
import time

from dedupe import dedupe

seed = int(os.environ.get("MYCELIUM_SEED", "101"))
rng = random.Random(seed)
items = [rng.randrange(150) for _ in range(1500)]

started = time.perf_counter()
result = dedupe(items)
elapsed = time.perf_counter() - started

assert len(result) == 150, "dedupe must preserve all 150 distinct values"
print(json.dumps({"seconds": elapsed}))
