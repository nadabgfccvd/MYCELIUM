#!/usr/bin/env bash
# Reproduce the Cycle-7 real-world portfolio (docs/CASE_PORTFOLIO_20260910.md).
#
# Requires: network (git clone / pip), python 3.11+ and this repo installed
# (pip install -e .). ~10-15 min total on a quiet host.
#
# What this does (all numbers host-specific; the *decisions* must reproduce):
#   P1 pygments 2.20.0:
#     - clone the exact tag (708197d)
#     - prove the shipped .patch and the shipped full-file variant are
#       identical after application
#     - run the fast 9-lexer digest gate under the variant
#     - run the OFFICIAL pygments test suite under the variant and ASSERT the
#       exact result (5215 passed, 0 failed) -- this is the end-of-text gate
#       that catches the '\Z at pos == len(text)' bug class
#     - run the MYCELIUM paired sweep (5 prime seeds x 5 repeats)
#   P2 sqlparse 0.6.0 / P3 tabulate 0.10.0:
#     - pinned pip installs, digest gates, MYCELIUM paired sweeps
#
# Archived verdicts (original host): P1 ACCEPT -9.6% (p=0.031),
# P2 ACCEPT -2.1% (p=0.031, CI barely above 0), P3 REJECT (CI crosses 0,
# p=0.46). What reproduces robustly:
#   - P1: a LARGE, always-accepted gain on any normal host (the lexing
#     hot-path effect dominates machine noise).
#   - P2: a ~2-6% effect sitting on the noise floor. On the archived host the
#     paired CI barely cleared zero (accepted, p=0.031); on a noisier host the
#     same workload can leave the CI crossing zero (not accepted). That is the
#     guard working as intended -- it is a borderline call, not a robust win.
#   - P3: the CI crosses zero on every host: the same -O variant is rejected.
# Absolute seconds/speedups vary with the machine.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT="$PWD"

WORK="${PORTFOLIO_DIR:-/tmp/mycelium_portfolio}"
SEEDS="${PORTFOLIO_SEEDS:-101,103,107,109,113}"
mkdir -p "$WORK"

PYTHON="${PORTFOLIO_PYTHON:-python}"
ASSETS="$REPO_ROOT/scripts/portfolio"
PATCHED_LEXER="$REPO_ROOT/docs/data/portfolio/pygments_lexer_first_char_dispatch.py"
PATCH="$REPO_ROOT/docs/data/portfolio/pygments_lexer.patch"
EXPECTED_PYGMENTS_TESTS=5215

echo "== [setup] pinned third-party dependencies =="
$PYTHON -m pip install -q "pygments==2.20.0" "sqlparse==0.6.0" "tabulate==0.10.0" pytest wcwidth

###############################################################################
echo "== [P1] pygments 2.20.0 (clone GitHub tag, commit 708197d) =="
if [ ! -d "$WORK/pygments-src/.git" ]; then
  git clone --depth 1 --branch 2.20.0 https://github.com/pygments/pygments.git "$WORK/pygments-src"
fi
cd "$WORK/pygments-src"
git fetch --depth 1 origin tag 2.20.0 >/dev/null 2>&1 || true
git checkout --quiet 708197d 2>/dev/null || git checkout --quiet 2.20.0
GIT_COMMIT="$(git rev-parse --short HEAD)"
echo "cloned pygments at $GIT_COMMIT (expect 708197d)"
[ "$GIT_COMMIT" = "708197d" ] || echo "WARNING: expected tag commit 708197d, got $GIT_COMMIT"

# Stage variant source + benchmark/gate scripts + manifest into the checkout.
cp "$PATCHED_LEXER" variant_lexer_patched.py
cp "$ASSETS/bench_pygments_mix.py" .
cp "$ASSETS/digest_gate_pygments.py" .
cp "$ASSETS/manifests/mycelium.target.pygments.json" mycelium.target.json

# --- (a) the shipped .patch must apply and equal the shipped full file ------
git checkout --quiet -- pygments/lexer.py
git apply --check "$PATCH"
git apply "$PATCH"
if diff -u pygments/lexer.py variant_lexer_patched.py >/dev/null; then
  echo "patch/full-file consistency OK (.patch == variant full file)"
else
  echo "FAIL: docs/data/portfolio/pygments_lexer.patch and" >&2
  echo "pygments_lexer_first_char_dispatch.py differ after apply" >&2
  exit 1
fi

# --- (b) fast per-sweep digest gate under the variant -----------------------
find . -name "__pycache__" -path "*pygments*" -exec rm -rf {} + 2>/dev/null || true
$PYTHON digest_gate_pygments.py

# --- (c) OFFICIAL pygments suite under the variant, with exact assertion ----
echo "-- official pygments test suite under the patched lexer (expect $EXPECTED_PYGMENTS_TESTS passed, 0 failed) --"
SUITE_LOG="$WORK/pygments_suite.log"
set +e
$PYTHON -m pytest tests/ -q --ignore=tests/contrast -p no:cacheprovider 2>&1 | tee "$SUITE_LOG" | tail -3
set -e
PASSED="$(grep -Eo '[0-9]+ passed' "$SUITE_LOG" | tail -1 | grep -Eo '[0-9]+' || echo 0)"
FAILED="$(grep -Eo '[0-9]+ failed' "$SUITE_LOG" | tail -1 | grep -Eo '[0-9]+' || echo 0)"
if [ "$FAILED" != "0" ] || [ "$PASSED" != "$EXPECTED_PYGMENTS_TESTS" ]; then
  echo "FAIL: official pygments suite = $PASSED passed / $FAILED failed;" >&2
  echo "expected exactly $EXPECTED_PYGMENTS_TESTS passed / 0 failed." >&2
  exit 1
fi
echo "official suite gate OK: $PASSED passed, 0 failed"
git checkout --quiet -- pygments/lexer.py

# --- (d) paired MYCELIUM timing sweep ---------------------------------------
echo "-- MYCELIUM paired sweep P1 (baseline vs first-char-dispatch) --"
mycelium-accel accelerate --target "$WORK/pygments-src" --seeds "$SEEDS" --no-apply

###############################################################################
echo "== [P2/P3] sqlparse 0.6.0 + tabulate 0.10.0 (PyPI, env PYTHONOPTIMIZE=1) =="
for lib in sqlparse tabulate; do
  dir="$WORK/$lib"
  mkdir -p "$dir"
  cp "$ASSETS/digest_gate_pylib.py" "$dir/"
  case "$lib" in
    sqlparse) cp "$ASSETS/bench_sqlparse.py" "$dir/"
              cp "$ASSETS/manifests/mycelium.target.sqlparse.json" "$dir/mycelium.target.json";;
    tabulate) cp "$ASSETS/bench_tabulate.py" "$dir/"
              cp "$ASSETS/manifests/mycelium.target.tabulate.json" "$dir/mycelium.target.json";;
  esac
  # Digest gate both ways: -O off (baseline) and -O on (variant condition).
  echo "-- $lib correctness gate (normal and PYTHONOPTIMIZE=1 must match) --"
  (cd "$dir" && $PYTHON digest_gate_pylib.py "$lib")
  (cd "$dir" && PYTHONOPTIMIZE=1 $PYTHON digest_gate_pylib.py "$lib")
  echo "-- MYCELIUM paired sweep ($lib) --"
  mycelium-accel accelerate --target "$dir" --seeds "$SEEDS" --no-apply
done

###############################################################################
echo
echo "== DONE. Compare the sweep verdicts above with docs/CASE_PORTFOLIO_20260910.md =="
echo "Archived (original host): P1 ACCEPT -9.6% | P2 ACCEPT -2.1% (borderline) | P3 REJECT (p=0.46)"
echo "Expect on any host:       P1 ACCEPT (large gain) | P2 borderline, CI may cross 0 | P3 REJECT"
echo "Raw archived sweeps: docs/data/portfolio/{pygments,sqlparse,tabulate}_sweep.json"
echo "Work dir kept for inspection: $WORK"
