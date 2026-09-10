"""Deterministic access.log generator (20k lines, ~7% status 500)."""
import os
import random

seed = int(os.environ.get("MYCELIUM_SEED", "101"))
rng = random.Random(seed)
paths = ["/", "/index", "/api/items", "/api/users", "/static/app.js", "/login"]
with open("access.log", "w", encoding="utf-8") as handle:
    for i in range(20_000):
        status = 500 if rng.random() < 0.07 else rng.choice([200, 200, 200, 304, 404])
        handle.write(f'10.0.0.{i % 250} - - [09/Sep/2026] "GET {rng.choice(paths)}" {status} 1234\n')
print("wrote access.log")
