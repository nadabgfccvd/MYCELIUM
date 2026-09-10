"""C2: SyGuS adapter — vendored .sl samples (offline-safe)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mycelium_accel.sygus_adapter import (
    extract_task,
    parse_sexp,
    score_callable,
    split_pairs,
)

VALID_SL = """(set-logic LIA)
(synth-fun f ((x Int)) Int ())
(declare-var x Int)
(constraint (= (f 0) 0))
(constraint (= (f 1) 10))
(constraint (= (f 2) 20))
(constraint (= (f 3) 30))
(constraint (= (f 4) 40))
(constraint (= (f 5) 50))
(check-synth)
"""

MULTIARG_SL = "(set-logic LIA)\n(synth-fun f ((x Int) (y Int)) Int ())\n(check-synth)\n"

NEG_SL = """(set-logic LIA)
(synth-fun g ((n Int)) Int ())
(declare-var n Int)
(constraint (= (g 0) 0))
(constraint (= (g 1) 1))
(constraint (= (g (- 2)) (- 4)))
(constraint (= (g 3) 9))
(constraint (= (g 4) 16))
(check-synth)
"""


def _write(tmp: str, name: str, content: str) -> str:
    path = Path(tmp) / name
    path.write_text(content, encoding="utf-8")
    return str(path)


class SyGuSAdapterTests(unittest.TestCase):
    def test_parse_sexp_balanced(self) -> None:
        forms = parse_sexp("(a (b 1) (c))")
        self.assertEqual(forms, [[["a", ["b", "1"], ["c"]]][0]])
        with self.assertRaises(ValueError):
            parse_sexp("(a (b)")

    def test_valid_task_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = extract_task(_write(tmp, "v.sl", VALID_SL), min_examples=5)
        self.assertTrue(task.valid)
        self.assertEqual(task.logic, "LIA")
        self.assertEqual(task.examples[:2], [(0, 0), (1, 10)])
        self.assertEqual(len(task.examples), 6)

    def test_multitask_excluded_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = extract_task(_write(tmp, "m.sl", MULTIARG_SL), min_examples=5)
        self.assertFalse(task.valid)
        self.assertIn("arity", task.excluded_reason)

    def test_negative_encoding_and_split_and_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = extract_task(_write(tmp, "n.sl", NEG_SL), min_examples=5)
        self.assertTrue(task.valid)
        self.assertIn((-2, -4), task.examples)
        train, test = split_pairs(task.examples, 101)
        self.assertTrue(train and test)
        self.assertEqual(len(train) + len(test), len(task.examples))
        self.assertEqual(score_callable(lambda x: x * x, [(3, 9), (4, 16)])["exact"], 1.0)
        self.assertEqual(score_callable(lambda x: 0, [(3, 9)])["exact"], 0.0)


if __name__ == "__main__":
    unittest.main()
