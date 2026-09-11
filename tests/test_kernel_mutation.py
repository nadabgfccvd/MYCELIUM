"""Ciclo 8 (C) — mutation battery for the compiled scoring kernel.

`_compile_score_kernel` is a 3.8x codegen fast path whose safety rests on
tests/test_dsl_codegen.py (differential vs the interpreter). This battery
proves that armor actually bites: each surgical mutation of the EMITTER
(the part that builds the straight-line source) must change the kernel's
output on a fixed program battery — i.e. the differential would go red.

Method: load a textually mutated copy of dsl.py as a fresh module (the
interpreter half is byte-identical in every mutation — only emitter lines
change), compile kernels with both modules, compare against the ORIGINAL
interpreter on programs/pairs chosen to hit the mutated arm (including the
no-clamp-after-MAX/MIN quirk and limit handling).
"""
from __future__ import annotations

import random
import sys
import types
import unittest
from pathlib import Path

from mycelium_accel import dsl as real_dsl
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
    OP_SUB,
)

ROOT = Path(__file__).resolve().parents[1]
DSL_SRC = (ROOT / "mycelium_accel" / "dsl.py").read_text(encoding="utf-8")

_LIMITS = (None, 1, 3)


def _load_mutated(mutation: tuple[str, str], name: str) -> dict:
    """Load dsl.py with one textual mutation applied to the emitter."""
    old, new = mutation
    assert old in DSL_SRC, f"mutation anchor not found: {old[:60]!r}"
    src = DSL_SRC.replace(old, new, 1)
    src = src.replace("from .model import", "from mycelium_accel.model import")
    src = src.replace("from .audit import", "from mycelium_accel.audit import")
    module = types.ModuleType(name)
    sys.modules[name] = module  # dataclasses resolve __module__ via sys.modules
    exec(compile(src, f"<mutated:{name}>", "exec"), module.__dict__)
    return module.__dict__


def _battery() -> list[tuple[tuple[tuple[int, int], ...], list[tuple[int, int]], int]]:
    """(instructions, pairs, max_abs) hitting every opcode + clamp quirks."""
    rng = random.Random(20260910)
    programs: list[tuple[tuple[tuple[int, int], ...], list[tuple[int, int]], int]] = [
        (((OP_INPUT, 0), (OP_CONST, 5), (OP_ADD, 0)), [(3, 8), (-3, 2), (999, 3), (-999, 5)], 10),
        (((OP_INPUT, 0), (OP_NEG, 0), (OP_ABS, 0)), [(-7, 7), (4, 4)], 100),
        (((OP_INPUT, 0), (OP_INC, 0), (OP_DEC, 0)), [(5, 5), (0, 0)], 100),
        (((OP_INPUT, 0), (OP_SQUARE, 0)), [(12, 4), (3, 9)], 15),
        (((OP_INPUT, 0), (OP_CONST, 7), (OP_MUL, 0)), [(6, 2), (2, 4)], 20),
        (((OP_INPUT, 0), (OP_CONST, 3), (OP_SUB, 0)), [(9, 6), (1, 2)], 50),
        (((OP_INPUT, 0), (OP_CONST, 4), (OP_MAX, 0), (OP_CONST, 3), (OP_MUL, 0)), [(2, 12), (5, 15)], 12),
        (((OP_INPUT, 0), (OP_CONST, -4), (OP_MIN, 0), (OP_CONST, 6), (OP_ADD, 0)), [(9, 2), (-1, 2)], 8),
        (((OP_INPUT, 0), (OP_CONST, 97), (OP_MOD, 0)), [(100, 3), (97, 0), (291, 0)], 500),
        (
            ((OP_INPUT, 0), (OP_CONST, 3), (OP_ADD, 0), (OP_CONST, 2), (OP_MUL, 0), (OP_CONST, 10), (OP_MOD, 0)),
            [(7, 5), (12, 4), (100, 3)],
            1000,
        ),
        # MAX/MIN results that EXCEED max_abs: pins the no-clamp-after quirk
        (((OP_CONST, 100), (OP_INPUT, 0), (OP_MAX, 0)), [(1, 100), (50, 100)], 10),
        (((OP_CONST, -100), (OP_INPUT, 0), (OP_MIN, 0)), [(1, -100), (50, -100)], 10),
    ]
    for _ in range(12):
        tree = real_dsl.random_tree(rng, max_depth=rng.randint(2, 5), constant_scale=50)
        try:
            exe = real_dsl.compile_program(tree, None, max_nodes=64, max_abs_value=1000, max_steps=512)
        except (ValueError, RuntimeError):
            continue
        pairs = [(rng.randint(-500, 500), rng.randint(-50, 50)) for _ in range(12)]
        programs.append((exe.instructions, pairs, 1000))
    return programs


def _kernel_output(module: dict, instructions, pairs, max_abs: int, limit):
    depth = module["_max_stack_depth"](instructions)  # type: ignore[operator]
    kernel = module["_compile_score_kernel"](instructions, max_abs, depth)  # type: ignore[operator]
    return kernel(pairs, limit)


def _interpreter_output(instructions, pairs, max_abs: int, limit):
    depth = real_dsl._max_stack_depth(instructions)
    return real_dsl._score_pairs_program(instructions, max_abs, depth, pairs, limit)


MAX_ARM = '            body.append(f"        t{a} = t{a} if t{a} >= t{b} else t{b}")'
MIN_ARM = '            body.append(f"        t{a} = t{a} if t{a} <= t{b} else t{b}")'
MOD_ARM = '                    body.append(f"        t{a} = t{a} % (abs(t{b}) % 97 + 1)")'
MUL_ARM = '                    body.append(f"        t{a} = t{a} * t{b}")'
NEG_ARM = '                body.append(f"        t{q} = -t{q}")'
INC_ARM = '            elif opcode == OP_INC:\n                body.append(f"        t{q} = t{q} + 1")'
PREDICTED = '    predicted = f"t{p - 1}" if p > 0 else "0"'
LIMIT_CHECK = '        f"        if limit is not None and count >= limit:\\n"\n'
X_CLAMP_HI = '        f"        if x > {max_abs_value}:\\n"\n        f"            x = {max_abs_value}\\n"\n'
X_CLAMP_LO = '        f"        elif x < -{max_abs_value}:\\n"\n        f"            x = -{max_abs_value}\\n"\n'


class KernelMutationBattery(unittest.TestCase):
    """Each emitter mutation must be caught (kernel diverges from interpreter)."""

    MUTATIONS: list[tuple[str, str, str]] = [
        (
            "clamp-after-MAX (must NOT clamp)",
            MAX_ARM + "\n            p -= 1",
            MAX_ARM + "\n            p -= 1\n            _emit_clamp(p - 1, max_abs_value, body)",
        ),
        ("MAX becomes MIN", MAX_ARM, MIN_ARM),
        ("MOD modulus off-by-one", MOD_ARM, MOD_ARM.replace("% 97 + 1", "% 96 + 1")),
        ("MUL becomes ADD", MUL_ARM, MUL_ARM.replace("*", "+")),
        ("predicted reads wrong slot", PREDICTED, PREDICTED.replace("p - 1", "p - 2").replace("p > 0", "p > 1")),
        ("limit off-by-one", LIMIT_CHECK, LIMIT_CHECK.replace(">=", ">")),
        (
            "input entry lower-clamp inverts",
            X_CLAMP_LO,
            X_CLAMP_LO.replace("-{max_abs_value}", "+{max_abs_value}"),
        ),
        ("INC becomes DEC", INC_ARM, INC_ARM.replace("+ 1", "- 1")),
        ("NEG becomes ABS", NEG_ARM, NEG_ARM.replace("-t{q}", "abs(t{q})")),
    ]

    def test_every_mutation_is_caught(self) -> None:
        battery = _battery()
        for name, old, new in self.MUTATIONS:
            with self.subTest(mutation=name):
                module = _load_mutated((old, new), f"dsl_mut_{self._id_for(name)}")
                diverged = False
                for instructions, pairs, max_abs in battery:
                    for limit in _LIMITS:
                        expected = _interpreter_output(instructions, pairs, max_abs, limit)
                        got = _kernel_output(module, instructions, pairs, max_abs, limit)
                        if got != expected:
                            diverged = True
                            break
                    if diverged:
                        break
                self.assertTrue(
                    diverged,
                    f"mutation '{name}' SURVIVED — differential battery is too weak",
                )

    @staticmethod
    def _id_for(name: str) -> str:
        import re

        slug = re.sub(r"\W+", "_", name)[:30]
        return f"{slug}_{abs(hash(name)) % 100_000}"

    def test_unmutated_reload_is_equivalent(self) -> None:
        """Control: reloading dsl.py with a no-op edit must NOT diverge
        (guards the rig — a loader that always 'catches' mutants would make
        the battery above pass vacuously)."""
        module = _load_mutated(("import random", "import random  # no-op"), "dsl_control")
        for instructions, pairs, max_abs in _battery():
            for limit in _LIMITS:
                self.assertEqual(
                    _kernel_output(module, instructions, pairs, max_abs, limit),
                    _interpreter_output(instructions, pairs, max_abs, limit),
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
