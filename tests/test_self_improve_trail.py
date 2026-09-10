"""C7 — self-improve screen trail: every candidate's verdict is explainable."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent))
from test_self_improve import make_snapshot  # noqa: E402

from mycelium_accel.config import Config  # noqa: E402
from mycelium_accel.self_improve import (  # noqa: E402
    GuardConfig,
    SelfImprover,
    SelfImproveCycleResult,
)


def _improver(root: Path) -> SelfImprover:
    state = root / "state"
    config = Config(seed=101, state_dir=str(state), family_count=5, family_size=10)
    guard = GuardConfig(seeds=[101], benchmark_rounds=2, require_tests=False,
                        use_paired_stats=False)
    return SelfImprover(root, config, guard)


class SearchTrailTests(unittest.TestCase):
    def test_trail_records_accept_and_reject(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            improver = _improver(root)
            baseline = make_snapshot()
            faster = make_snapshot(rounds_per_second_mean=99.0)  # +10% accepted
            slower = make_snapshot(rounds_per_second_mean=80.0)  # rejected
            slower.profile["family_count"] = 9  # visible diff
            with patch.object(SelfImprover, "_benchmark_candidates_parallel",
                              return_value=[faster, slower]):
                best = improver._search_best_candidate(baseline)
            self.assertIs(best, faster)
            trail = improver._last_search_trail
            self.assertEqual(len(trail), 2)
            self.assertEqual(
                sorted(trail[0]),
                sorted(["variant", "profile_diff", "rounds_per_second_mean",
                        "accepted", "reasons"]))
            self.assertTrue(trail[0]["accepted"])
            self.assertFalse(trail[1]["accepted"])
            self.assertEqual(trail[1]["profile_diff"], {"family_count": 9})
            self.assertEqual(trail[0]["profile_diff"], {})
            self.assertTrue(all(t["reasons"] for t in trail))

    def test_trail_reset_between_searches(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            improver = _improver(Path(temp))
            baseline = make_snapshot()
            with patch.object(SelfImprover, "_benchmark_candidates_parallel",
                              return_value=[make_snapshot()]):
                improver._search_best_candidate(baseline)
                self.assertEqual(len(improver._last_search_trail), 1)
                improver._search_best_candidate(baseline)
                self.assertEqual(len(improver._last_search_trail), 1)


class CycleResultTrailTests(unittest.TestCase):
    def test_screen_trail_defaults_empty(self) -> None:
        result = SelfImproveCycleResult(
            cycle_index=1, rounds_executed=5, applied=False,
            baseline=make_snapshot(), candidate=None,
            guard=__import__("mycelium_accel.self_improve",
                             fromlist=["GuardDecision"]).GuardDecision(False, ["x"]))
        self.assertEqual(result.screen_trail, [])
        self.assertIn("screen_trail", result.to_dict())

    def test_mocked_search_leaves_empty_trail(self) -> None:
        # Mocks bypass _search_best_candidate; cycles must not attach stale trails.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            improver = _improver(root)
            improver._last_search_trail = [{"stale": True}]  # type: ignore[list-item]
            with patch.object(SelfImprover, "_search_best_candidate",
                              return_value=None), \
                 patch.object(SelfImprover, "_benchmark_current_selection",
                              return_value=make_snapshot()), \
                 patch("mycelium_accel.self_improve.MyceliumEngine") as engine_cls:
                engine_cls.return_value.run.return_value.rounds_executed = 3
                result = improver._run_single_cycle(1, 1)
            self.assertEqual(result.screen_trail, [])
            self.assertFalse(result.applied)


if __name__ == "__main__":
    unittest.main()
