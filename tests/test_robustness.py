"""Fase 3.5: malformed inputs — friendly ValueError, never a crash.

Covers the manifest loader and the SyGuS S-expression parser with garbage:
unbalanced parens, empty files, binary junk, wrong JSON shapes.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mycelium_accel.sygus_adapter import extract_task, parse_sexp
from mycelium_accel.targets.base import TargetManifest


class RobustnessTests(unittest.TestCase):
    def test_manifest_garbage_is_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cases = {
                "empty.sl": "",
                "list.json": "[1, 2, 3]",
                "scalar.json": "42",
                "broken.json": '{"benchmark_command": ',
                "binary.json": b"\xff\xfe\x00bad",
            }
            for name, content in cases.items():
                path = Path(tmp) / "mycelium.target.json"
                if isinstance(content, bytes):
                    path.write_bytes(content)
                else:
                    path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError, msg=name):
                    TargetManifest.load(path)

    def test_sexp_garbage_never_crashes(self) -> None:
        for text in ["", "(", ")", "((a)", "(a))((b)", "\x00\x01\x02", "(define-fun f () Int (+ 1 2)"]:
            try:
                result = parse_sexp(text)
            except ValueError:
                continue
            self.assertIsInstance(result, list)

    def test_extract_task_garbage_is_excluded_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.sl"
            path.write_bytes(b"\x89PNG\r\n\x1a\nnot-an-sl-file(((((")
            task = extract_task(path)
            self.assertFalse(task.valid)
            self.assertTrue(task.excluded_reason)


if __name__ == "__main__":
    unittest.main()
