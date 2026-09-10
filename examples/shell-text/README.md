# Example: shell log pipeline — variant LOSES (honest negative)

Use case: "rewrite this grep call in Python for maintainability — what does
it cost?" `env` mode switching `COUNTER=grep` (baseline, one fork) vs
`COUNTER=python` (one process, 10 passes).

```bash
mycelium-accel accelerate --target examples/shell-text --no-apply
```

Measured 2026-09-10 (7 seeds × 5 repeats, `time` parser, 20k-line log):
baseline **3 ms** (one grep), variant **55 ms** (one process, 10 passes) —
corrected p = 1.0, variant rejected. The verdict path "measure, don't
guess": intuition said one python process might beat fork+exec; data said
grep is ~18× faster here (a single pass over 20k lines costs ~3 ms; the
python counter re-reads the log 10 times). One fork also keeps the verdict
stable on Windows, where each msys fork costs ~50 ms. A negative verdict
is a successful measurement.
