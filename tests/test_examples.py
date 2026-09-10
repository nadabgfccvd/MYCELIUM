"""H1.1: example targets stay realistic AND green (win path + honest-loss path)."""

from __future__ import annotations

import shutil

import pytest

pytestmark = pytest.mark.slow
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEEDS = "101,103,107,109,113,127,131"


def accelerate(example: str) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "mycelium_accel",
            "accelerate",
            "--target",
            str(ROOT / "examples" / example),
            "--no-apply",
            "--seeds",
            SEEDS,
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Traceback" not in proc.stderr
    return json.loads(proc.stdout)


class ExampleTests(unittest.TestCase):
    def test_python_lib_variant_wins(self) -> None:
        outcome = accelerate("python-lib")
        self.assertEqual(outcome["best_candidate"], "set-fastpath")

    @pytest.mark.skipif(
        shutil.which("sh") is None,
        reason="shell example needs sh (absent on Windows runners)",
    )
    def test_shell_text_variant_loses_honestly(self) -> None:
        outcome = accelerate("shell-text")
        self.assertIsNone(outcome["best_candidate"])
        self.assertTrue(outcome["comparisons"])


if __name__ == "__main__":
    unittest.main()
