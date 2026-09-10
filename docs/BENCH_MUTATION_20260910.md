# bench.py mutation round (reconnaissance, post-1.4.0)

Date: 2026-09-10. A mutmut round over `mycelium_accel/bench.py` (446 lines)
finished at 562 mutants = 331 killed + 6 no-tests + 225 survived, i.e. 59.5%
kills excl. no-tests — BELOW the 80% gate, so this stays reconnaissance:
no CI entry, no gate pressure. The 6 no-tests are mutants covered only by
the two files excluded from the selection (test_pipeline_stateful,
test_decide_determinism: slow / subprocess-blind).

Selection (bench config, since restored to stats in pyproject.toml):
test_adaptive_repeats, test_failfast, test_flaky_history, test_regression,
test_sweep_cache, test_targets, test_report_html, test_scale, test_racing,
test_racing_recall, test_numeric_edges, test_io_failures,
test_hostile_names, test_candidate_screening.

## Triage outcome

All 225 survivors were triaged from mutmut diffs. Result: 188 killed by the
new battery below, 37 accepted as equivalent-or-policy. Projected rate with
the battery: (331+188)/556 = 93.3% excl. no-tests. The battery's kills were
verified by 20 fault-injection simulations (one per mutant family, 20/20
red→green), M1-style — no full rerun was spent.

Survivors by function: _run_once 54, sweep 35, export_markdown 28,
benchmark_candidate 18, export_csv 17, parse_metrics 14, _median 12,
_stddev 8, summarize_runs 7, export_json 6, export_html 6, adaptive_stop 4,
_per_seed_values 4, __init__ 3, is_flaky 3, _mean 3, _seed_means 2, _stem 1;
to_dict/from_dict 0 (well covered).

## Battery: tests/test_bench_mutation.py (44 tests, 0.27 s)

Stubbed targets only (scripted runner, no subprocesses): pure-helper pins
(_mean/_median/_stddev incl. M3 overflow, _seed_means/_per_seed_values,
adaptive_stop, is_flaky, summarize_runs incl. empty/mixed, parse_metrics
incl. regex battery + stdout/stderr spanning pattern, _stem); export goldens
(JSON sort+indent, CSV header bytes, Markdown full-text x2 directions with a
None-corrected row, HTML default+threaded verdict); executor battery
(_run_once 4 returns + variant branch by mode + env/seed/command threading,
candidate warmup count/seed/variant + repeats floor + adaptive default,
sweep payload/baseline/direction/confidence/2-shared-seeds/empty/KI paths);
nested export_dir creation.

## Accepted survivors (37)

Full registry in the battery module docstring. Families: exception message
text (9, M1 policy — type only is pinned); INF/NAN spelling (5); codec case
(3); newline/encoding defaults, POSIX-equivalent (8); runner seed=None
default (1); unused seed_index parameter (2); discarded warmup fields (3);
falsy warmup=None on the measured call (1); unreachable shared-seed gate
(1, futility break makes continue-vs-break dead); direction scale (2,
compare normalizes sign); adaptive </<= at exactly 1% (1, bit-exact 0.01
ratio unconstructible — M1 float-dust principle); CV == 0.15 (1,
measure-zero tolerance point).

## Findings (no prod change)

seed_index (_run_once) is dead weight: all four returns pass the seed kwarg
to BenchmarkRun; the positional index is never read. Left as-is (public-ish
signature, harmless); the battery pins run.seed == seed kwarg.
