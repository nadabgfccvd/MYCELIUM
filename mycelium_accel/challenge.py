from __future__ import annotations

import random
from dataclasses import dataclass

from .dsl import BINARY_OPS, UNARY_OPS, Macro, Node, ProgramExecutor, compile_program, random_tree
from .prime import next_prime


@dataclass(slots=True)
class Challenge:
    seed: int
    difficulty: int
    train_pairs: list[tuple[int, int]]
    test_pairs: list[tuple[int, int]]
    oracle_repr: str
    oracle_kind: str = "standard"


class ChallengeFactory:
    def __init__(
        self,
        *,
        max_program_depth: int,
        max_program_nodes: int,
        max_abs_value: int,
        max_eval_steps: int,
        train_cases: int,
        test_cases: int,
    ) -> None:
        self.max_program_depth = max_program_depth
        self.max_program_nodes = max_program_nodes
        self.max_abs_value = max_abs_value
        self.max_eval_steps = max_eval_steps
        self.train_cases = train_cases
        self.test_cases = test_cases

    def build(
        self,
        base_seed: int,
        difficulty: int,
        macros: list[Macro] | dict[str, Node] | None = None,
        *,
        force_compositional: bool = False,
    ) -> Challenge:
        seed = next_prime(base_seed)
        rng = random.Random(seed)
        macro_nodes = self._normalize_macros(macros)
        oracle, oracle_kind = self._build_non_trivial_oracle(rng, difficulty, macro_nodes, force_compositional=force_compositional)
        executor = compile_program(
            oracle,
            macro_nodes,
            max_nodes=self.max_program_nodes,
            max_abs_value=self.max_abs_value,
            max_steps=self.max_eval_steps,
        )
        span = 12 + difficulty * 5

        train_inputs = self._sample_inputs(rng, self.train_cases, span)
        test_inputs = self._sample_inputs(rng, self.test_cases, span)
        train_pairs = [(x, executor.run(x)) for x in train_inputs]
        test_pairs = [(x, executor.run(x)) for x in test_inputs]
        return Challenge(
            seed=seed,
            difficulty=difficulty,
            train_pairs=train_pairs,
            test_pairs=test_pairs,
            oracle_repr=oracle.render(),
            oracle_kind=oracle_kind,
        )

    def _normalize_macros(self, macros: list[Macro] | dict[str, Node] | None) -> dict[str, Node]:
        if not macros:
            return {}
        if isinstance(macros, dict):
            return macros
        return {macro.name: macro.tree for macro in macros}

    def _build_non_trivial_oracle(
        self,
        rng: random.Random,
        difficulty: int,
        macro_nodes: dict[str, Node],
        *,
        force_compositional: bool,
    ) -> tuple[Node, str]:
        target_depth = min(self.max_program_depth, 2 + difficulty // 3)
        constant_scale = 3 + difficulty * 3
        macro_names = tuple(macro_nodes)
        fallback = Node("add", children=[Node("input"), Node("const", value=difficulty + 1)])

        for _ in range(80):
            use_compositional = force_compositional or (macro_names and difficulty >= 3 and rng.random() < 0.45)
            if use_compositional:
                oracle = self._build_compositional_oracle(rng, target_depth, constant_scale, macro_names)
                oracle_kind = "compositional"
            else:
                oracle = random_tree(
                    rng,
                    max_depth=target_depth,
                    constant_scale=constant_scale,
                    macro_names=macro_names,
                )
                oracle_kind = "standard"
            if oracle.count_nodes() > self.max_program_nodes:
                continue
            try:
                executor = compile_program(
                    oracle,
                    macro_nodes,
                    max_nodes=self.max_program_nodes,
                    max_abs_value=self.max_abs_value,
                    max_steps=self.max_eval_steps,
                )
            except Exception:
                continue
            if self._is_semantically_non_trivial(oracle, executor, rng, difficulty):
                return oracle, oracle_kind
        return fallback, "fallback"

    def _build_compositional_oracle(
        self,
        rng: random.Random,
        target_depth: int,
        constant_scale: int,
        macro_names: tuple[str, ...],
    ) -> Node:
        components: list[Node] = []
        component_count = 2 + int(target_depth >= 4 and rng.random() < 0.5)
        branch_depth = max(1, target_depth - 1)
        for _ in range(component_count):
            if macro_names and rng.random() < 0.55:
                components.append(Node("macro", value=rng.choice(macro_names)))
            else:
                components.append(
                    random_tree(
                        rng,
                        max_depth=branch_depth,
                        constant_scale=constant_scale,
                        macro_names=macro_names,
                    )
                )
        combined = components[0]
        for component in components[1:]:
            combined = Node(rng.choice(BINARY_OPS), children=[combined, component])
        if rng.random() < 0.65:
            combined = Node(rng.choice(UNARY_OPS), children=[combined])
        return combined

    def _sample_inputs(self, rng: random.Random, count: int, span: int) -> list[int]:
        population = range(-span, span + 1)
        if count <= len(population):
            return rng.sample(population, count)
        values = set(population)
        while len(values) < count:
            values.add(rng.randint(-span, span))
        return list(values)

    def _is_semantically_non_trivial(
        self,
        oracle: Node,
        executor: ProgramExecutor,
        rng: random.Random,
        difficulty: int,
    ) -> bool:
        lower = -20 - difficulty * 3
        upper = 20 + difficulty * 3
        sample_inputs = [rng.randint(lower, upper) for _ in range(20)]
        outputs = [executor.run(x) for x in sample_inputs]
        if len(set(outputs)) < min(6, max(3, difficulty + 1)):
            return False
        if outputs == sample_inputs:
            return False
        if all(output == outputs[0] for output in outputs):
            return False
        drift = sum(abs(out - inp) for inp, out in zip(sample_inputs, outputs))
        if drift < difficulty * 2:
            return False
        return oracle.complexity_score() >= difficulty + 3
