"""Ciclo 3 (V) — compiled scoring kernel ≡ interpreter, bit-for-bit.

`_compile_score_kernel` codegens a straight-line twin of
`_score_pairs_program`. Any divergence (clamp policy, MAX/MIN no-clamp quirk,
empty program, limit handling, float op order) flips these tests. Random
programs come from the production tree generator; targeted cases pin the
edge quirks individually so a failure names the bug.
"""
from __future__ import annotations

import random
import unittest

from mycelium_accel import dsl
from mycelium_accel.dsl import (
    OP_ABS,
    OP_ADD,
    OP_CONST,
    OP_DEC,
    OP_INC,
    OP_INPUT,
    OP_MAX,
    OP_MIN,
    OP_MOD,
    OP_MUL,
    OP_NEG,
    OP_SQUARE,
    ProgramExecutor,
    compile_program,
    random_tree,
    _compile_score_kernel,
    _score_pairs_program,
)


def _score_both(
    instructions: tuple[tuple[int, int], ...], pairs: list[tuple[int, int]], limit: int | None, max_abs: int = 10**6
) -> None:
    depth = dsl._max_stack_depth(instructions)
    exe = ProgramExecutor(
        instructions=instructions,
        max_abs_value=max_abs,
        max_stack_depth=depth,
        instruction_count=len(instructions),
    )
    reference = _score_pairs_program(instructions, max_abs, depth, pairs, limit)
    kernel = _compile_score_kernel(instructions, max_abs, depth)
    compiled = kernel(pairs, limit)
    assert reference == compiled, (instructions, limit, reference, compiled)
    # Executor methods route through the kernel too.
    if limit is None:
        assert exe.score_pairs(pairs) == reference
    else:
        assert exe.score_pairs_limit(pairs, limit) == reference


class DifferentialTests(unittest.TestCase):
    def test_random_programs_bit_identical(self) -> None:
        rng = random.Random(20260910)
        for _ in range(120):
            tree = random_tree(rng, max_depth=rng.randint(1, 5), constant_scale=100)
            try:
                exe = compile_program(
                    tree, None, max_nodes=64, max_abs_value=10**9, max_steps=512
                )
            except ValueError:
                continue  # generator may emit consts without value; skip
            pairs = [
                (rng.randint(-10**9, 10**9), rng.randint(-10**6, 10**6))
                for _ in range(rng.randint(1, 40))
            ]
            for limit in (None, 1, max(1, len(pairs) // 2), len(pairs)):
                with self.subTest(instr=exe.instructions, limit=limit):
                    _score_both(exe.instructions, pairs, limit)

    def test_targeted_quirks(self) -> None:
        cases = [
            # (instructions, pairs) — clamp boundaries and no-clamp arms
            (( (OP_INPUT, 0), (OP_CONST, 5), (OP_ADD, 0) ), [(3, 8), (-3, 2)]),  # add + clamp
            (( (OP_INPUT, 0), (OP_NEG, 0), ), [(7, -7)]),  # neg + clamp
            (( (OP_INPUT, 0), (OP_ABS, 0), ), [(-9, 9)]),
            (( (OP_INPUT, 0), (OP_SQUARE, 0), ), [(1000, 6)]),  # clamp after square
            (( (OP_INPUT, 0), (OP_CONST, 3), (OP_MAX, 0), ), [(2, 3), (-10, 3)]),  # MAX: no clamp
            (( (OP_INPUT, 0), (OP_CONST, -3, ), (OP_MIN, 0), ), [(2, -3), (99, -3)]),  # MIN: no clamp
            (( (OP_INPUT, 0), (OP_CONST, 97), (OP_MOD, 0), ), [(100, 3)]),
            (( (OP_INPUT, 0), (OP_INC, 0), (OP_DEC, 0), (OP_INC, 0), ), [(5, 6)]),
            ((), [(1, 0), (2, 0)]),  # empty program: interpreter reads stack[-1] == 0
            (( (OP_CONST, 10**17), (OP_INPUT, 0), (OP_MUL, 0), ), [(10**17, 0)]),  # huge-value clamp
        ]
        for instructions, pairs in cases:
            with self.subTest(instructions=instructions):
                for limit in (None, 1):
                    _score_both(tuple(instructions), list(pairs), limit)

    def test_max_min_result_can_exceed_max_abs_identically(self) -> None:
        # If MAX skipped the clamp in the interpreter, the kernel must too —
        # an over-clamping "optimization" would change scores.
        instructions = ((OP_INPUT, 0), (OP_CONST, 10), (OP_MAX, 0), (OP_CONST, 10), (OP_MUL, 0))
        pairs = [(5, 50)]
        _score_both(instructions, pairs, None, max_abs=7)

    def test_kernel_cache_reuses_and_bounded(self) -> None:
        dsl._KERNEL_CACHE.clear()
        instructions = ((OP_INPUT, 0), (OP_CONST, 1), (OP_ADD, 0))
        first = _compile_score_kernel(instructions, 100, 2)
        second = _compile_score_kernel(instructions, 100, 2)
        self.assertIs(first, second)
        for i in range(dsl._KERNEL_CACHE_LIMIT + 10):
            _compile_score_kernel(((OP_CONST, i), (OP_INPUT, 0), (OP_ADD, 0)), 100, 2)
        self.assertLessEqual(len(dsl._KERNEL_CACHE), dsl._KERNEL_CACHE_LIMIT)

    def test_zero_pairs_returns_zero_zero(self) -> None:
        for limit in (None, 5):
            _score_both(((OP_INPUT, 0),), [], limit)

    def test_underflowing_tuple_raises_valueerror(self) -> None:
        # Unary on an empty stack, binary with one item, and an unknown opcode
        # must be rejected explicitly instead of emitting "t-1 = ..." (which
        # would be a SyntaxError buried in exec) or silently miscompiling.
        underflowing = [
            ((OP_NEG, 0),),  # unary on empty stack
            ((OP_INPUT, 0), (OP_MAX, 0)),  # binary with a single item
            ((OP_CONST, 1), (OP_ADD, 0)),  # binary after one const
            ((OP_ABS, 0), (OP_INPUT, 0)),  # unary first, then input
            ((9999, 0),),  # unknown opcode
        ]
        for instructions in underflowing:
            with self.subTest(instructions=instructions):
                with self.assertRaises(ValueError):
                    _compile_score_kernel(tuple(instructions), 100, 8)
        # Empty program is still valid (quirk: reads stack[-1] == 0); it must
        # match the interpreter, as pinned by the differential cases above.
        _score_both((), [(1, 0), (2, 1)], None, max_abs=100)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
