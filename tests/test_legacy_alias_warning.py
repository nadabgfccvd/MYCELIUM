"""Ciclo 5 (P) — legacy `mycelium` console alias deprecation warning.

The README has declared the alias deprecated "desde 1.0 — remoção prevista
na 2.0" since the rename, but it never warned. Contract: exactly one stderr
line when invoked as ``mycelium``; silence for ``mycelium-accel`` and
``python -m mycelium_accel``; never on stdout (scriptable output stays
parseable); exit code unaffected.
"""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch


from mycelium_accel.__main__ import _warn_legacy_alias


class LegacyAliasWarningTests(unittest.TestCase):
    def test_warning_when_invoked_as_mycelium(self) -> None:
        stderr = io.StringIO()
        with patch("sys.argv", ["mycelium", "--version"]), redirect_stderr(stderr):
            _warn_legacy_alias()
        self.assertIn("deprecated", stderr.getvalue())
        self.assertIn("mycelium-accel", stderr.getvalue())

    def test_silent_for_canonical_name(self) -> None:
        stderr = io.StringIO()
        with patch("sys.argv", ["mycelium-accel", "--version"]), redirect_stderr(stderr):
            _warn_legacy_alias()
        self.assertEqual(stderr.getvalue(), "")

    def test_silent_for_module_invocation_and_paths(self) -> None:
        for argv in (["__main__.py", "--version"], ["python", "-m", "mycelium_accel"], ["./bin/mycelium-accel"]):
            with self.subTest(argv=argv):
                stderr = io.StringIO()
                with patch("sys.argv", argv), redirect_stderr(stderr):
                    _warn_legacy_alias()
                self.assertEqual(stderr.getvalue(), "")

    def test_warning_does_not_pollute_stdout_or_exit_code(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["mycelium", "--version"]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                try:
                    from mycelium_accel.__main__ import main

                    main()
                except SystemExit as exc:
                    self.assertEqual(exc.code, 0)
        self.assertIn("deprecated", stderr.getvalue())
        self.assertNotIn("deprecated", stdout.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
