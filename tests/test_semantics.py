from __future__ import annotations

import unittest

from mycelium_accel.counterexamples import Counterexample, CounterexampleBank, harvest_counterexamples
from mycelium_accel.dsl import Node, compile_program
from mycelium_accel.semantics import SemanticBank, safe_signature, signature_distance

LIMITS = dict(max_nodes=63, max_abs_value=100_000, max_steps=256)
PROBES = (-5, -2, 0, 1, 3, 7, 11)


def _tree(kind="add", left=None, right=None):
    return Node(kind, children=[left or Node("input"), right if right is not None else Node("const", value=1)])


class SignatureTests(unittest.TestCase):
    def test_equivalent_trees_share_signature(self) -> None:
        a = Node("add", children=[Node("input"), Node("const", value=0)])
        b = Node("input")
        sig_a = safe_signature(a, {}, PROBES, **LIMITS)
        sig_b = safe_signature(b, {}, PROBES, **LIMITS)
        self.assertEqual(sig_a, sig_b)
        self.assertEqual(signature_distance(sig_a, sig_b), 0.0)

    def test_different_trees_differ(self) -> None:
        a = Node("input")
        b = Node("square", children=[Node("input")])
        sig_a = safe_signature(a, {}, PROBES, **LIMITS)
        sig_b = safe_signature(b, {}, PROBES, **LIMITS)
        self.assertGreater(signature_distance(sig_a, sig_b), 0.4)

    def test_unrunnable_returns_none(self) -> None:
        huge = Node("macro", value="missing")
        self.assertIsNone(safe_signature(huge, {}, PROBES, **LIMITS))


class BankTests(unittest.TestCase):
    def test_register_and_nearest(self) -> None:
        bank = SemanticBank(probes=PROBES)
        base = Node("add", children=[Node("input"), Node("const", value=1)])
        near = Node("add", children=[Node("input"), Node("const", value=2)])
        far = Node("mul", children=[Node("input"), Node("input")])
        bank.register(base, {}, 1, **LIMITS)
        bank.register(near, {}, 1, **LIMITS)
        bank.register(far, {}, 1, **LIMITS)
        query = safe_signature(near, {}, PROBES, **LIMITS)
        neighbors = bank.nearest(query, exclude_render=near.render(), k=2)
        self.assertTrue(neighbors)
        self.assertEqual(neighbors[0][1].render, base.render())

    def test_record_outcome_updates_success(self) -> None:
        bank = SemanticBank(probes=PROBES)
        tree = _tree()
        bank.register(tree, {}, 1, **LIMITS)
        bank.record_outcome(tree.render(), improved=True, round_index=2)
        entry = bank.entries[tree.render()]
        self.assertEqual(entry.success_count, 1)
        self.assertEqual(entry.fitness_estimate, 1.0)


class CounterexampleTests(unittest.TestCase):
    def test_harvest_finds_failing_cases(self) -> None:
        good = Node("add", children=[Node("input"), Node("const", value=1)])
        executor = compile_program(good, {}, **LIMITS)
        pairs = [(x, x + 1) for x in range(-4, 4)]
        pairs[3] = (pairs[3][0], pairs[3][1] + 5)  # corrupt one expectation
        found = harvest_counterexamples(executor, pairs, source_seed=101, round_index=3)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].residual, 5)

    def test_bank_capacity_and_priorities(self) -> None:
        bank = CounterexampleBank(capacity=4)
        for index in range(10):
            bank.add(Counterexample(x=index, expected=100, predicted=90, source_seed=101, added_round=index))
        self.assertEqual(bank.size(), 4)
        # freshest with highest residuals survive
        self.assertEqual(sorted(item.x for item in bank.items.values()), [6, 7, 8, 9])

    def test_training_pairs(self) -> None:
        bank = CounterexampleBank(capacity=8)
        bank.add(Counterexample(x=1, expected=5, predicted=2, source_seed=1, added_round=1))
        pairs = bank.blame_pairs(4)
        self.assertEqual(pairs, [(1, 5)])

    def test_persistence_roundtrip(self) -> None:
        import tempfile
        from pathlib import Path

        bank = CounterexampleBank(capacity=8)
        bank.add(Counterexample(x=7, expected=9, predicted=1, source_seed=101, added_round=2))
        with tempfile.TemporaryDirectory() as temp:
            path = bank.persist(Path(temp) / "ce.json")
            reloaded = CounterexampleBank.load(path)
        self.assertEqual(reloaded.size(), 1)
        self.assertEqual(reloaded.items[7].expected, 9)


if __name__ == "__main__":
    unittest.main()
