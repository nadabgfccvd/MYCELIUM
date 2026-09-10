# Example: pure-Python lib (dedupe) — variant WINS

`patch` mode swapping an O(n²) list scan for an O(n) seen-set.

```bash
mycelium-accel accelerate --target examples/python-lib --no-apply
```

Measured 2026-09-10 (7 seeds × 5 repeats, `json_stdout`, 1.5k items):
**set-fastpath accepted** (CI lower bound > 0, corrected p = 0.0078 — the
minimum with 7 seeds). Baseline ~1.2 ms/op, variant ~0.1 ms/op — the verdict
path "apply the winner".
