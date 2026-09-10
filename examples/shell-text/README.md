# Example: shell log pipeline — variant LOSES (honest negative)

Use case: "rewrite this grep loop in Python for maintainability — what does
it cost?" `env` mode switching `COUNTER=grep` (baseline, 20 forks) vs
`COUNTER=python` (one process, 20 passes).

```bash
mycelium-accel accelerate --target examples/shell-text --no-apply
```

Measured 2026-09-10 (7 seeds × 5 repeats, `time` parser, 20k-line log,
10 passes): baseline **29 ms**, variant **60 ms** — corrected p = 1.0,
variant rejected. The verdict path "measure, don't guess": intuition said
amortizing 10 forks might win; data said grep is 2× faster here (at larger
workloads the gap was 5.6× — spawn overhead dominates small runs, which is
itself an honest measurement). A negative verdict is a successful measurement.
