"""Minimal python-manifest example: workload scales with EXAMPLE_MODE."""
import json
import os
import time

N = {"fast": 200_000, "slow": 2_000_000}.get(os.environ.get("EXAMPLE_MODE", ""), 500_000)
start = time.perf_counter()
acc = sum(i * i for i in range(N))
elapsed = time.perf_counter() - start
print(json.dumps({"seconds": elapsed, "acc": acc}))
