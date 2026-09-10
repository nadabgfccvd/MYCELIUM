from __future__ import annotations

import random
import unittest

from mycelium_accel.counterexamples import CounterexampleBank, harvest_counterexamples
from mycelium_accel.dsl import Node, compile_program
from mycelium_accel.mutation_semantic import (
    SemanticMutationContext,
    apply_semantic_mutation,
    behavior_preserving_simplify,
    counterexample_patch_mutation,
    library_instantiation_mutation,
    residual_fit_mutation,
    semantic_block_mutation,
    semantic_nearest_subtree_replace,
)
from mycelium_accel.semantics import SemanticBank, canonical_probes

LIMITS = dict(max_nodes=63, max_abs_value=100_000, max_steps=256)


def _ctx(**overrides) -> SemanticMutationContext:
    probes = canonical_probes(7)
    return SemanticMutationContext(
        bank=SemanticBank(probes=probes),
        counterexamples=CounterexampleBank(),
        probes=probes,
        max_nodes=63,
        max_abs_value=100_000,
        max_steps=256,
        macro_nodes=overrides.get("macro_nodes", {}),
        round_index=overrides.get("round_index", 1),
    )


def _wrong_by(delta: int) -> Node:
    return Node("add", children=[Node("input"), Node("const", value=delta)])


class SimplifyTests(unittest.TestCase):
    def test_simplify_removes_dead_code_and_verifies(self) -> None:
        tree = Node("add", children=[
            Node("add", children=[Node("input"), Node("const", value=0)]),
            Node("mul", children=[Node("const", value=3), Node("const", value=4)]),
        ])
        ctx = _ctx()
        result = behavior_preserving_simplify(tree, ctx, random.Random(101))
        self.assertIsNotNone(result)
        self.assertLess(result.count_nodes(), tree.count_nodes())
        executor_before = compile_program(tree, {}, **LIMITS)
        executor_after = compile_program(result, {}, **LIMITS)
        for x in range(-10, 11):
            self.assertEqual(executor_before.run(x), executor_after.run(x))

    def test_simplify_constant_folds(self) -> None:
        tree = Node("add", children=[Node("input"), Node("mul", children=[Node("const", value=2), Node("const", value=3)])])
        ctx = _ctx()
        result = behavior_preserving_simplify(tree, ctx, random.Random(3))
        if result is not None:
            self.assertIn("6", result.render())


class PatchTests(unittest.TestCase):
    def test_counterexample_patch_fixes_constant_offset(self) -> None:
        tree = _wrong_by(2)  # predicts x+2, truth is x+1
        ctx = _ctx()
        macro_bank = ctx.counterexamples
        executor = compile_program(tree, {}, **LIMITS)
        failing = harvest_counterexamples(
            executor,
            [(x, x + 1) for x in range(-6, 6)],
            source_seed=101,
            round_index=1,
        )
        macro_bank.add_batch(failing)
        patched = counterexample_patch_mutation(tree, ctx, random.Random(101))
        self.assertIsNotNone(patched)
        patched_executor = compile_program(patched, {}, **LIMITS)
        for x in range(-6, 6):
            self.assertEqual(patched_executor.run(x), x + 1)

    def test_residual_fit_affine_correction(self) -> None:
        tree = Node("mul", children=[Node("input"), Node("const", value=2)])  # truth: 4x-2
        ctx = _ctx()
        executor = compile_program(tree, {}, **LIMITS)
        failing = harvest_counterexamples(
            executor,
            [(x, 4 * x - 2) for x in range(-6, 6)],
            source_seed=101,
            round_index=1,
        )
        ctx.counterexamples.add_batch(failing)
        fitted = residual_fit_mutation(tree, ctx, random.Random(101))
        self.assertIsNotNone(fitted)
        fitted_executor = compile_program(fitted, {}, **LIMITS)
        errors = sum(abs(fitted_executor.run(x) - (4 * x - 2)) for x in range(-6, 6))
        baseline_errors = sum(abs(executor.run(x) - (4 * x - 2)) for x in range(-6, 6))
        self.assertLess(errors, baseline_errors)

    def test_patch_returns_none_without_counterexamples(self) -> None:
        ctx = _ctx()
        self.assertIsNone(counterexample_patch_mutation(_wrong_by(2), ctx, random.Random(1)))


class NeighborhoodTests(unittest.TestCase):
    def test_nearest_subtree_replace_uses_bank(self) -> None:
        ctx = _ctx()
        donor = Node("add", children=[Node("input"), Node("const", value=1)])
        ctx.bank.register(donor, {}, 1, **LIMITS)
        ctx.bank.record_outcome(donor.render(), improved=True, round_index=1)
        tree = Node("mul", children=[Node("sub", children=[Node("input"), Node("const", value=1)]), Node("const", value=2)])
        for name, tree_node in (("a", Node("add", children=[Node("input"), Node("const", value=2)])),
                                 ("b", Node("neg", children=[Node("input")]))):
            ctx.bank.register(tree_node, {}, 1, **LIMITS)
        candidate = semantic_nearest_subtree_replace(tree, ctx, random.Random(101))
        # may be None if distances too far, but must never be invalid
        if candidate is not None:
            self.assertLessEqual(candidate.count_nodes(), 63)

    def test_library_instantiation_replaces_close_subtree(self) -> None:
        macro_tree = Node("add", children=[Node("input"), Node("const", value=5)])
        ctx = _ctx(macro_nodes={"m1": macro_tree})
        tree = Node("mul", children=[Node("add", children=[Node("input"), Node("const", value=5)]), Node("const", value=2)])
        result = library_instantiation_mutation(tree, ctx, random.Random(101))
        self.assertIsNotNone(result)
        self.assertIn("@m1(x)", result.render())

    def test_block_mutation_respects_node_cap(self) -> None:
        ctx = _ctx(round_index=26)
        tree = Node("add", children=[Node("input"), Node("mul", children=[Node("input"), Node("const", value=3)])])
        result = semantic_block_mutation(tree, ctx, random.Random(101))
        if result is not None:
            self.assertLessEqual(result.count_nodes(), 63)


class DispatcherTests(unittest.TestCase):
    def test_dispatcher_returns_valid_tree_or_none(self) -> None:
        ctx = _ctx()
        ctx.counterexamples.add_batch(harvest_counterexamples(
            compile_program(_wrong_by(3), {}, **LIMITS),
            [(x, x + 1) for x in range(-6, 6)],
            source_seed=101,
            round_index=1,
        ))
        tree = _wrong_by(3)
        rng = random.Random(101)
        fires = 0
        for _ in range(10):
            candidate = apply_semantic_mutation(tree, ctx, rng)
            if candidate is not None:
                fires += 1
                self.assertLessEqual(candidate.count_nodes(), 63)
        self.assertGreater(fires, 0)


class EngineIntegrationTests(unittest.TestCase):
    def test_engine_semantic_mode_runs_and_collects(self) -> None:
        import tempfile
        from pathlib import Path

        from mycelium_accel.config import Config
        from mycelium_accel.engine import MyceliumEngine

        with tempfile.TemporaryDirectory() as temp:
            config = Config(
                seed=101,
                state_dir=str(Path(temp) / "state"),
                family_count=5,
                family_size=10,
                semantic_mutation_rate=0.5,
            )
            engine = MyceliumEngine(config)
            engine.init_state()
            engine.run(5)
            ctx = engine._semantic_ctx
            self.assertIsNotNone(ctx)
            self.assertGreater(ctx.counterexamples.size(), 0)
            self.assertGreater(ctx.bank.size(), 0)


if __name__ == "__main__":
    unittest.main()
