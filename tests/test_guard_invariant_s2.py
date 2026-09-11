"""Sessão 2, Ciclo 2 — the acceptance guard can never lie (invariant tests).

The product's central promise is: ``decide_best_candidate`` only returns a
winner whose BCa CI lower bound is strictly positive AND whose multiplicity-
corrected sign-flip p-value clears alpha. These tests pin that contract across
many randomized sweeps and a handful of deterministic adversarial shapes, so a
future refactor (sorting/index alignment/correction wiring) cannot make the
guard accept a regression or an identical-to-baseline variant.
"""
from __future__ import annotations

import random
import unittest

from mycelium_accel.accelerate_generic import decide_best_candidate
from mycelium_accel.bench import BenchmarkRun, BenchmarkSweep, summarize_runs
from mycelium_accel.stats import AcceptancePolicy

# 7 prime paired seeds: the one-sided sign-flip test enumerates exactly when
# 7 <= n <= 16, where its floor 1/2^n (= 1/128 ≈ 0.0078) can beat alpha 0.05.
# With fewer seeds even a deterministic speedup cannot reach significance
# (n=3 floor 1/8) — this is why the shipped default is seven seeds.
SEEDS = (101, 103, 107, 109, 113, 127, 131)


def _summary(name: str, values: dict[int, float]) -> object:
    runs = [BenchmarkRun(name, seed, "seconds", value, value, True)
            for seed, value in values.items()]
    return summarize_runs(name, runs)


def _sweep(candidates: dict[str, dict[int, float]], *, lower_is_better: bool = True) -> BenchmarkSweep:
    summaries = [_summary("baseline", candidates["baseline"])]
    summaries += [_summary(name, values) for name, values in candidates.items() if name != "baseline"]
    return BenchmarkSweep(
        target="synthetic", metric="seconds", lower_is_better=lower_is_better,
        summaries=summaries, comparisons=[],
    )


def _baseline(rng: random.Random) -> dict[int, float]:
    return {seed: 1.0 + rng.uniform(-0.03, 0.03) for seed in SEEDS}


def _scaled(base: dict[int, float], factor: float, jitter: float, rng: random.Random) -> dict[int, float]:
    return {seed: value * factor + rng.uniform(-jitter, jitter) for seed, value in base.items()}


def _winner_payload(comparisons: list[dict], name: str) -> dict:
    return next(c for c in comparisons if c["candidate"] == name)


class GuardInvariantTests(unittest.TestCase):
    def test_returned_winner_always_satisfies_contract(self) -> None:
        rng = random.Random(20260910)
        checked = 0
        for _ in range(120):
            base = _baseline(rng)
            candidates = {"baseline": base}
            # random pool of challengers with mixed effects
            for name, factor in (("c1", 0.70), ("c2", 0.85), ("c3", 1.25),
                                 ("c4", 1.0), ("c5", 0.97)):
                if rng.random() < 0.6:
                    candidates[name] = _scaled(base, factor, 0.004, rng)
            sweep = _sweep(candidates)
            winner, _reasons, comparisons = decide_best_candidate(sweep, "baseline")
            if winner is None:
                continue
            checked += 1
            self.assertIn(winner, candidates)
            payload = _winner_payload(comparisons, winner)
            self.assertGreater(
                payload["ci_low"], 0.0,
                f"accepted {winner} with non-positive ci_low: {payload['ci_low']}")
            corrected = payload["p_value_corrected"]
            p = corrected if corrected is not None else payload["p_value"]
            self.assertLessEqual(p, 0.05, f"accepted {winner} with p={p}")
        self.assertGreater(checked, 20, "random pool produced too few acceptances to validate")

    def test_deterministic_verdict_across_calls(self) -> None:
        rng = random.Random(7)
        base = _baseline(rng)
        sweep = _sweep({"baseline": base,
                        "fast": _scaled(base, 0.7, 0.002, rng),
                        "slow": _scaled(base, 1.3, 0.002, rng)})
        first = decide_best_candidate(sweep, "baseline")[0]
        second = decide_best_candidate(sweep, "baseline")[0]
        self.assertEqual(first, second)

    def test_strictly_worse_candidate_never_accepted(self) -> None:
        base = {s: 1.0 for s in SEEDS}
        # every seed is 30% SLOWER -> must fail the CI gate regardless of tightness
        sweep = _sweep({"baseline": base, "slower": _scaled(base, 1.3, 0.0, random.Random(1))})
        winner, reasons, _ = decide_best_candidate(sweep, "baseline")
        self.assertIsNone(winner)
        self.assertTrue(any("improvement not established" in r for r in reasons))

    def test_three_seeds_cannot_reach_significance_even_for_perfect_speedup(self) -> None:
        # n=3 one-sided sign-flip floor 1/8 = 0.125 > alpha: conservatism before
        # all else. Documents why the shipped default is seven seeds, not three.
        three = (101, 103, 107)
        base = {s: 1.0 for s in three}
        fast = {s: 0.5 for s in three}  # deterministic 50% faster at every seed
        summaries = [_summary("baseline", base), _summary("fast", fast)]
        sweep = BenchmarkSweep(target="t", metric="seconds", lower_is_better=True,
                               summaries=summaries, comparisons=[])
        winner, _reasons, _ = decide_best_candidate(sweep, "baseline")
        self.assertIsNone(winner)
        # ... but the same perfect speedup at seven seeds IS accepted
        base7 = {s: 1.0 for s in SEEDS}
        fast7 = {s: 0.5 for s in SEEDS}
        sweep7 = _sweep({"baseline": base7, "fast": fast7})
        self.assertEqual(decide_best_candidate(sweep7, "baseline")[0], "fast")

    def test_identical_values_never_accepted(self) -> None:
        base = {s: 0.5 + s * 1e-6 for s in SEEDS}
        sweep = _sweep({"baseline": base, "same": dict(base)})
        winner, _reasons, _ = decide_best_candidate(sweep, "baseline")
        self.assertIsNone(winner)  # deltas all zero -> CI touches 0, p not significant

    def test_acceptance_respects_higher_is_better_direction(self) -> None:
        # throughput metric (higher better): a candidate LOWER on every seed loses
        base = {s: 100.0 for s in SEEDS}
        slower = {s: 70.0 for s in SEEDS}  # lower throughput
        sweep = _sweep({"baseline": base, "slower": slower}, lower_is_better=False)
        self.assertIsNone(decide_best_candidate(sweep, "baseline")[0])
        faster = {s: 130.0 for s in SEEDS}  # higher throughput -> accepted
        sweep2 = _sweep({"baseline": base, "faster": faster}, lower_is_better=False)
        winner, _reasons, comparisons = decide_best_candidate(sweep2, "baseline")
        self.assertEqual(winner, "faster")
        self.assertGreater(_winner_payload(comparisons, "faster")["ci_low"], 0.0)

    def test_stricter_alpha_rejects_more(self) -> None:
        rng = random.Random(11)
        accepted_relaxed = accepted_strict = 0
        for _ in range(30):
            base = _baseline(rng)
            # small, borderline speedup (~3%) that may or may not clear the gate
            cand = _scaled(base, 0.97, 0.01, rng)
            sweep = _sweep({"baseline": base, "border": cand})
            if decide_best_candidate(sweep, "baseline",
                                     policy=AcceptancePolicy(alpha=0.50))[0] is not None:
                accepted_relaxed += 1
            if decide_best_candidate(sweep, "baseline",
                                     policy=AcceptancePolicy(alpha=0.001))[0] is not None:
                accepted_strict += 1
        self.assertGreaterEqual(accepted_relaxed, accepted_strict)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
