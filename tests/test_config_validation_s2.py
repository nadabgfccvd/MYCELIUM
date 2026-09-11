"""Sessão 2, Ciclo 2 — Config validation contract (freeze every guard rail).

``Config.__post_init__`` is a long declarative validation chain whose *raise*
branches were almost entirely untested (config.py ~73%). This locks the
contract: a single invalid field must raise ``ValueError``, while the defaults
and every documented boundary stay valid. It guards against an accidental
relaxation of an engine invariant silently shipping.
"""
from __future__ import annotations

import dataclasses
import unittest

from mycelium_accel.config import Config


def _valid_config() -> Config:
    # Prime seed + documented defaults are valid.
    return Config(seed=101)


class ConfigValidTests(unittest.TestCase):
    def test_defaults_construct(self) -> None:
        cfg = _valid_config()
        self.assertEqual(cfg.seed, 101)
        self.assertEqual(cfg.persistence_backend, "json")

    def test_boundary_values_are_accepted(self) -> None:
        cfg = _valid_config()
        # valid extremes that previously sat next to a raised branch
        dataclasses.replace(cfg, persistence_backend="pickle")
        dataclasses.replace(cfg, full_rescore_random_k=0)
        dataclasses.replace(cfg, ecology_reseed_rounds=0)
        dataclasses.replace(cfg, compositional_challenge_rate=0.0)
        dataclasses.replace(cfg, compositional_challenge_rate=1.0)
        dataclasses.replace(cfg, gene_splice_rate=0.0)
        dataclasses.replace(cfg, shrink_mutation_rate=1.0)
        dataclasses.replace(cfg, semantic_mutation_rate=1.0)
        dataclasses.replace(cfg, novelty_weight=0.0)
        dataclasses.replace(cfg, macro_transfer_threshold=0.0)

    def test_roundtrip_dict_drops_unknown_keys(self) -> None:
        cfg = _valid_config()
        payload = dict(cfg.to_dict())
        payload["not_a_field"] = 123
        again = Config.from_dict(payload)
        self.assertEqual(again.family_count, cfg.family_count)


class ConfigInvalidMatrixTests(unittest.TestCase):
    """One invalid field at a time -> ValueError naming the field's intent."""

    INVALID: tuple[tuple[str, object], ...] = (
        ("seed", 100),  # composite, not prime
        ("tournament_size", 1),
        ("tournament_size", 2),  # even
        ("family_count", 4),
        ("family_size", 9),
        ("survivors_per_extinction", 6),
        ("state_save_every", 0),
        ("probe_challenges", 0),
        ("probe_train_cases", 0),
        ("probe_train_cases", 99),  # > train_cases (default 8)
        ("probe_test_cases", 0),
        ("probe_test_cases", 99),  # > test_cases (default 16)
        ("full_rescore_top_k", 0),
        ("full_rescore_top_k", 999),  # > family_size
        ("full_rescore_random_k", -1),
        ("full_rescore_random_k", 999),
        ("persistence_backend", "yaml"),
        ("novelty_weight", -0.01),
        ("macro_potential_weight", -1.0),
        ("transfer_weight", -1.0),
        ("macro_support_threshold", 0),
        ("macro_transfer_threshold", -0.1),
        ("macro_retire_rounds", 0),
        ("compositional_challenge_rate", -0.1),
        ("compositional_challenge_rate", 1.1),
        ("niche_probe_count", 2),
        ("frontier_archive_limit", 1),  # < challenges_per_round (default 3)
        ("frontier_window", 2),
        ("gene_splice_rate", -0.1),
        ("gene_splice_rate", 1.1),
        ("shrink_mutation_rate", 2.0),
        ("semantic_mutation_rate", -0.5),
        ("semantic_probe_count", 2),
        ("counterexample_limit", 7),
        ("counterexample_harvest_top_k", 0),
        ("ecology_reseed_rounds", -1),
        ("ecology_patience", 1),
    )

    def test_each_invalid_field_raises(self) -> None:
        for field_name, bad_value in self.INVALID:
            with self.subTest(field=field_name, value=bad_value):
                with self.assertRaises(ValueError):
                    dataclasses.replace(_valid_config(), **{field_name: bad_value})

    def test_prime_seed_message(self) -> None:
        with self.assertRaisesRegex(ValueError, "[Pp]rime"):
            Config(seed=102)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
