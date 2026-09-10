from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from mycelium_accel.acceleration import accelerate_external, accelerate_self


class AccelerationTests(unittest.TestCase):
    def test_accelerate_self(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        outcome = accelerate_self(project_root, apply=False)
        self.assertIn(outcome.best_variant, {"loop", "pythonic"})
        generated = project_root / "mycelium_accel" / "generated" / "active_variants.py"
        self.assertTrue(generated.exists())

    def test_accelerate_external(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        source = project_root / "examples" / "accelerate_target.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "accelerate_target.py"
            shutil.copy2(source, target)
            outcome = accelerate_external(target)
            content = target.read_text(encoding="utf-8")
            self.assertEqual(outcome.module_path, str(target))
            self.assertIn(outcome.best_variant, content)


if __name__ == "__main__":
    unittest.main()
