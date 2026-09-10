"""Example contract for `python -m mycelium_accel accelerate --target examples/accelerate_target.py`.

The accelerator will benchmark the listed variants, verify they return exactly the
same outputs on BENCHMARK_SPEC['cases'], and rewrite ACTIVE_VARIANT in this file.
"""

ACTIVE_VARIANT = "baseline"


def baseline(values: list[int]) -> int:
    total = 0
    for value in values:
        total += value * value
    return total


def candidate_loop(values: list[int]) -> int:
    total = 0
    for value in values:
        total += value * value
    return total


def candidate_sum(values: list[int]) -> int:
    return sum(value * value for value in values)


BENCHMARK_SPEC = {
    "baseline": "baseline",
    "variants": ["baseline", "candidate_loop", "candidate_sum"],
    "repeats": 600,
    "cases": [
        {"args": [[1, 2, 3, 4, 5]]},
        {"args": [[10, 20, 30, 40, 50, 60]]},
        {"args": [[-7, -3, 0, 3, 7, 11, 13]]},
        {"args": [list(range(200))]},
    ],
}
