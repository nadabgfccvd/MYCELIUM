#!/bin/sh
# COUNTER=grep (baseline): ONE grep pass. COUNTER=python (variant): 1 process, 10 passes.
# Single grep (not a 20-fork loop): on Windows each fork costs ~50ms under msys,
# which flipped the honest-negative verdict there; one fork wins ~3x everywhere.
if [ "${COUNTER:-grep}" = "python" ]; then
  python count_500.py > /dev/null
else
  grep -c '" 500 ' access.log > /dev/null
fi
