#!/usr/bin/env bash
# Reproduce the S2 Cycle-7 real-world portfolio (docs/CASE_PORTFOLIO_S2_20260910.md).
#
# Requires: network (git clone / pip), python 3.11+ and this repo installed
# (pip install -e .). A few minutes on a quiet host; run baselines serially.
#
# NEW third-party projects (none repeat pygments/sqlparse/tabulate):
#   P4 Unidecode 1.3.8 (GitHub avian2/unidecode, tag unidecode-1.3.8):
#       a real SOURCE patch — errors='ignore' transliteration goes through a
#       one-shot C-level str.translate table; other error policies and
#       surrogates keep the original per-character loop.
#   P5 natsort 8.4.0  (PyPI, env PYTHONOPTIMIZE=1)
#   P6 Markdown 3.8   (PyPI, env PYTHONOPTIMIZE=1)
#
# Archived verdicts on the authoring host (2026-09-10, serial, 5 prime seeds):
#   P4 ACCEPT  CI [+0.0232, +0.0387]  p=0.031  (faster, statistically clear)
#   P5 REJECT  CI [-0.1373, -0.0137]  p=0.935  (-O does not help natsort)
#   P6 REJECT  CI [-0.1003, +0.0072]  p=0.882  (CI crosses zero)
# Absolute seconds vary with the machine; the ACCEPT (a large dense-text
# speedup) and the two null-effect REJECTs are what should reproduce.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT="$PWD"

WORK="${PORTFOLIO_S2_DIR:-/tmp/mycelium_p7}"
SEEDS="${PORTFOLIO_SEEDS:-101,103,107,109,113}"
PYTHON="${PORTFOLIO_PYTHON:-python}"
ASSETS="$REPO_ROOT/scripts/portfolio"
PATCHED_INIT="$REPO_ROOT/docs/data/portfolio/unidecode_init_translate_fastpath.py"
PATCH="$REPO_ROOT/docs/data/portfolio/unidecode_translate_fastpath.patch"
EXPECTED_UNIDECODE_COMMIT="a31eb5fb3a8a7fbb94b7379ec403539d8ec481b0"
EXPECTED_UNIDECODE_TESTS=62
mkdir -p "$WORK"

echo "== [setup] pinned third-party dependencies (P5/P6) =="
$PYTHON -m pip install -q "natsort==8.4.0" "Markdown==3.8"

###############################################################################
echo "== [P4] Unidecode 1.3.8 (clone GitHub tag unidecode-1.3.8) =="
if [ ! -d "$WORK/p4/.git" ]; then
  rm -rf "$WORK/p4"
  git clone --depth 1 --branch unidecode-1.3.8 \
    https://github.com/avian2/unidecode.git "$WORK/p4"
fi
cd "$WORK/p4"
GIT_COMMIT="$(git rev-parse HEAD)"
echo "cloned unidecode at $GIT_COMMIT"
[ "$GIT_COMMIT" = "$EXPECTED_UNIDECODE_COMMIT" ] || \
  echo "WARNING: expected $EXPECTED_UNIDECODE_COMMIT, got $GIT_COMMIT"

cp "$PATCHED_INIT" variant_init_patched.py
cp "$ASSETS/bench_unidecode.py" .
cp "$ASSETS/digest_gate_unidecode.py" .
cp "$ASSETS/manifests/mycelium.target.unidecode.json" mycelium.target.json

# (a) shipped .patch must apply and equal the shipped full patched file
git checkout --quiet -- unidecode/__init__.py
git apply --check "$PATCH"
git apply "$PATCH"
if diff -u unidecode/__init__.py variant_init_patched.py >/dev/null; then
  echo "patch/full-file consistency OK (.patch == shipped full file)"
else
  echo "FAIL: .patch and shipped full file differ after apply" >&2; exit 1
fi

# (b) digest gate under the patch (must match the pinned pristine digest)
$PYTHON digest_gate_unidecode.py

# (c) UPSTREAM suite under the patch: exactly 62 passed, 0 failed
echo "-- upstream unidecode tests under the patched __init__ (expect $EXPECTED_UNIDECODE_TESTS passed) --"
SUITE_LOG="$WORK/unidecode_suite.log"
set +e
PYTHONPATH=. $PYTHON -m pytest tests/ -q -p no:cacheprovider 2>&1 | tee "$SUITE_LOG" | tail -3
set -e
PASSED="$(grep -Eo '[0-9]+ passed' "$SUITE_LOG" | tail -1 | grep -Eo '[0-9]+' || echo 0)"
FAILED="$(grep -Eo '[0-9]+ failed' "$SUITE_LOG" | tail -1 | grep -Eo '[0-9]+' || echo 0)"
if [ "$FAILED" != "0" ] || [ "$PASSED" != "$EXPECTED_UNIDECODE_TESTS" ]; then
  echo "FAIL: upstream suite = $PASSED passed / $FAILED failed; expected $EXPECTED_UNIDECODE_TESTS/0" >&2
  exit 1
fi
echo "upstream suite gate OK: $PASSED passed, 0 failed"
git checkout --quiet -- unidecode/__init__.py

# (d) paired MYCELIUM timing sweep (patch applied+reverted around each run)
echo "-- MYCELIUM paired sweep P4 (baseline vs str-translate-fastpath) --"
mycelium-accel accelerate --target "$WORK/p4" --seeds "$SEEDS" --no-apply

###############################################################################
echo "== [P5]/[P6] natsort 8.4.0 + Markdown 3.8 (env PYTHONOPTIMIZE=1) =="
for lib in natsort markdown; do
  dir="$WORK/$lib"
  rm -rf "$dir"; mkdir -p "$dir"
  cp "$ASSETS/digest_gate_pylib_s2.py" "$dir/"
  case "$lib" in
    natsort) cp "$ASSETS/bench_natsort.py" "$dir/"
              cp "$ASSETS/manifests/mycelium.target.natsort.json" "$dir/mycelium.target.json";;
    markdown) cp "$ASSETS/bench_markdown.py" "$dir/"
              cp "$ASSETS/manifests/mycelium.target.markdown.json" "$dir/mycelium.target.json";;
  esac
  echo "-- $lib correctness gate (normal and PYTHONOPTIMIZE=1 must match) --"
  (cd "$dir" && $PYTHON digest_gate_pylib_s2.py "$lib")
  (cd "$dir" && PYTHONOPTIMIZE=1 $PYTHON digest_gate_pylib_s2.py "$lib")
  echo "-- MYCELIUM paired sweep ($lib) --"
  mycelium-accel accelerate --target "$dir" --seeds "$SEEDS" --no-apply
done

echo
echo "== DONE. Compare with docs/CASE_PORTFOLIO_S2_20260910.md =="
echo "Archived: P4 ACCEPT (+0.023..+0.039, p=0.031) | P5 REJECT (p=0.935) | P6 REJECT (p=0.882)"
echo "Raw archived sweeps: docs/data/portfolio/{unidecode,natsort,markdown}_sweep.json"
