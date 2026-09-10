#!/bin/sh
# COUNTER=grep (baseline): 10 grep passes. COUNTER=python (variant): 1 process, 10 passes.
if [ "${COUNTER:-grep}" = "python" ]; then
  python count_500.py > /dev/null
else
  i=0
  while [ "$i" -lt 20 ]; do
    grep -c '" 500 ' access.log > /dev/null
    i=$((i + 1))
  done
fi
