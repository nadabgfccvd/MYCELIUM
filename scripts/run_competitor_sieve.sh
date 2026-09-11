#!/usr/bin/env bash
# S2 Cycle-9 competitor benchmark on a NEW kernel (prime sieve).
#
# Compares, on the identical workload:
#   cpython      classic nested-loop sieve (reference, portable CPython)
#   cpython -O   same code under PYTHONOPTIMIZE=1
#   mycelium     safe pure-Python bulk-slice variant (also the MYCELIUM
#                manifest patch; correctness-gated, reversible, portable)
#   mypyc        classic loop AOT-compiled with mypyc (typed Python list)
#   mypyc_fast   bytearray marking loop AOT-compiled with mypyc
#   cython       classic loop compiled by Cython (Python list)
#   cython_fast  bytearray compiled by Cython, bounds checks disabled
#
# Needs gcc; installs Cython into the active environment if missing. Outputs
# one JSON per implementation into docs/data/competitors/sieve_<impl>.json and
# runs the actual MYCELIUM paired decision on the bulk-slice patch. Absolute
# seconds are host-specific; conclusions (algorithm > runtime here) reproduce.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT="$PWD"
COMP="$REPO_ROOT/scripts/competitors"
OUT="$REPO_ROOT/docs/data/competitors"
WORK="${P9_DIR:-/tmp/mycelium_p9}"
REPS="${P9_REPS:-7}"
SEEDS="${P9_SEEDS:-101,103,107,109,113}"
mkdir -p "$WORK" "$OUT"
export P9_REPS="$REPS"

echo "== [setup] toolchain (Cython + mypyc ship via dev deps; gcc required) =="
python -c "import Cython" 2>/dev/null || python -m pip install -q "Cython==3.1.3"
command -v gcc >/dev/null || { echo "gcc is required to compile competitors" >&2; exit 1; }

# Build the competitors in an isolated work dir (the repo stays source-only).
rm -rf "$WORK" && mkdir -p "$WORK"
cp "$COMP"/kernel*.py "$COMP"/kernel_cy.pyx "$COMP"/kernel_cy_fast.pyx \
   "$COMP"/bench_cli.py "$COMP"/digest_gate_sieve.py "$WORK"/
( cd "$WORK" && cp "$COMP/setup_cython.py" . \
  && python setup_cython.py >/dev/null \
  && python -m mypyc kernel_mypyc.py kernel_mypyc_fast.py >/dev/null 2>&1 )

echo "== correctness gate (classic kernel vs independent oracle) =="
( cd "$WORK" && python digest_gate_sieve.py )

echo "== timing each approach (best-of-$REPS, in-process) =="
for impl in cpython mycelium mypyc mypyc_fast cython cython_fast; do
  ( cd "$WORK" && python bench_cli.py "$impl" ) | tee "$OUT/sieve_${impl}.json" >/dev/null
done
( cd "$WORK" && PYTHONOPTIMIZE=1 python bench_cli.py cpython ) \
  | python -c "import sys,json; d=json.load(sys.stdin); d['impl']='cpython -O'; print(json.dumps(d))" \
  | tee "$OUT/sieve_cpython_O.json" >/dev/null
python - "$OUT" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
rows = []
for p in sorted(out.glob("sieve_*.json")):
    d = json.loads(p.read_text())
    rows.append((d["impl"], d["seconds"], d["count_1m"], d["sum_1m"]))
base = dict((r[0], r) for r in rows)["cpython"][1]
print(f"{'approach':14s} {'total_s':>10s} {'speedup':>8s}  checksum")
for impl, secs, count, total in rows:
    print(f"{impl:14s} {secs:10.5f} {base/secs:7.2f}x  ({count}, {total})")
PY

echo "== MYCELIUM paired decision (bulk-slice patch), correctness-gated =="
TARGET="$WORK/mycelium_target"
rm -rf "$TARGET" && mkdir -p "$TARGET"
cp "$COMP/kernel.py" "$COMP/kernel_mycelium.py" "$COMP/bench_cli.py" \
   "$COMP/digest_gate_sieve.py" "$TARGET/"
cp "$COMP/manifests/mycelium.target.sieve.json" "$TARGET/mycelium.target.json"
mycelium-accel accelerate --target "$TARGET" --seeds "$SEEDS" --no-apply \
  | tee "$OUT/sieve_mycelium_decision.json"

echo "== DONE. JSON artifacts in $OUT; see docs/BENCHMARK_COMPETITORS_S2_20260910.md =="
