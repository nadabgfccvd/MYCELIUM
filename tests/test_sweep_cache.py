"""V4.1: content-addressed sweep cache — hits reuse, any change misses.

Kill gate: a hit whose verdict differs from fresh measurement removes the
feature. Deterministic fixture makes hits bit-identical, not just verdict-equal.
"""
from __future__ import annotations

import json
import tempfile
import pytest
import unittest
from pathlib import Path

from mycelium_accel.accelerate_generic import accelerate_target
from mycelium_accel.sweep_cache import cache_key, lookup, store

BENCH = (
    "import json, os\n"
    "fast = os.environ.get('MODE') == 'fast'\n"
    "print(json.dumps({'seconds': 0.01 if fast else 0.05}))\n"
)
MANIFEST = {
    "benchmark_command": "python bench.py", "metrics_parser": "json_stdout",
    "manifest_version": "1.0", "repeats": 2, "warmup": 0,
    "variants": [{"name": "fast", "mode": "env", "env": {"MODE": "fast"}}],
}
SEEDS = [101, 103, 107, 109, 113, 127, 131]


def make_target(root: Path) -> None:
    (root / "bench.py").write_text(BENCH, encoding="utf-8")
    (root / "mycelium.target.json").write_text(json.dumps(MANIFEST), encoding="utf-8")


class CacheKeyTests(unittest.TestCase):
    def test_stable_and_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_target(root)
            key1 = cache_key(root, MANIFEST, SEEDS)
            key2 = cache_key(root, MANIFEST, SEEDS)
            self.assertEqual(key1, key2)
            (root / "bench.py").write_text(BENCH + "# touch\n", encoding="utf-8")
            self.assertNotEqual(cache_key(root, MANIFEST, SEEDS), key1)

    def test_state_dirs_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_target(root)
            key1 = cache_key(root, MANIFEST, SEEDS)
            bench_dir = root / ".mycelium_benchmarks"
            bench_dir.mkdir()
            (bench_dir / "sweep-1.json").write_text("{}", encoding="utf-8")
            self.assertEqual(cache_key(root, MANIFEST, SEEDS), key1)

    def test_version_mismatch_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            store(cache_dir, "k", {"sweep": {}})
            payload = json.loads((cache_dir / "k.json").read_text(encoding="utf-8"))
            payload["mycelium_version"] = "0.0.0-ancient"
            (cache_dir / "k.json").write_text(json.dumps(payload), encoding="utf-8")
            self.assertIsNone(lookup(cache_dir, "k"))


@pytest.mark.slow
class CacheEndToEndTests(unittest.TestCase):
    def test_cache_lifecycle_miss_hit_invalidate(self) -> None:
        # W1.2 fusion of miss/hit + code-change-miss: every assertion kept.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_target(root)
            fresh = accelerate_target(root, seeds=SEEDS, apply=False, cache=True)
            self.assertFalse(fresh.cached)
            hit = accelerate_target(root, seeds=SEEDS, apply=False, cache=True)
            self.assertTrue(hit.cached)
            # THE kill gate: identical verdict AND identical measurements
            self.assertEqual(hit.best_candidate, fresh.best_candidate)
            fresh_runs = json.loads(Path(fresh.sweep_path).read_text(encoding="utf-8"))["summaries"]
            hit_runs = json.loads(Path(hit.sweep_path).read_text(encoding="utf-8"))["summaries"]
            self.assertEqual(
                [[r["value"] for r in s["runs"]] for s in hit_runs],
                [[r["value"] for r in s["runs"]] for s in fresh_runs])
            self.assertTrue(any("cache hit" in r for r in hit.decision_reasons))
            (root / "bench.py").write_text(BENCH + "# v2\n", encoding="utf-8")
            second = accelerate_target(root, seeds=SEEDS, apply=False, cache=True)
            self.assertFalse(second.cached)

    def test_rapid_runs_do_not_clobber_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_target(root)
            first = accelerate_target(root, seeds=[101, 103], apply=False)
            second = accelerate_target(root, seeds=[101, 103], apply=False)
            self.assertNotEqual(first.sweep_path, second.sweep_path)
            self.assertTrue(Path(first.sweep_path).is_file())
            self.assertTrue(Path(second.sweep_path).is_file())

    def test_shared_cache_dir_hits_across_copies(self) -> None:
        # W2.4: same content in two dirs + shared --cache-dir => second hits.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for name in ("a", "b"):
                root = tmp_path / name
                root.mkdir()
                make_target(root)
            shared = tmp_path / "shared"
            first = accelerate_target(tmp_path / "a", seeds=SEEDS, apply=False,
                                      cache=True, cache_dir=shared)
            self.assertFalse(first.cached)
            second = accelerate_target(tmp_path / "b", seeds=SEEDS, apply=False,
                                       cache=True, cache_dir=shared)
            self.assertTrue(second.cached)
            self.assertEqual(second.best_candidate, first.best_candidate)

    def test_cache_with_apply_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_target(root)
            with self.assertRaises(ValueError) as ctx:
                accelerate_target(root, seeds=SEEDS, apply=True, cache=True)
            self.assertIn("--no-apply", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
