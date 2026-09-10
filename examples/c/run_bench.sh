#!/usr/bin/env sh
# usage: ./run_bench.sh [O2|O3|O3native|O2unroll]  (default O2 = baseline)
exec ./bench_${1:-O2}
