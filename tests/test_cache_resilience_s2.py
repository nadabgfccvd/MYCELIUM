"""Sessão 2, Ciclo 2 — sweep cache resilience (corruption, retry, atomicity).

Covers the defensive branches of ``sweep_cache.py`` that a happy-path run never
touches: a corrupt/tampered cache must always degrade to a *miss* (never raise,
never be trusted), the key must ignore symlinks and bytecode, the Windows-style
replace retry must recover from transient PermissionError, and a failed atomic
write must not leave a temp file behind.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mycelium_accel import sweep_cache
from mycelium_accel.sweep_cache import cache_key, lookup, store


def _manifest() -> dict:
    return {"name": "x", "kind": "shell", "benchmark_command": "true"}


class CacheKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "bench.py").write_text("print('v1')")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _key(self) -> str:
        return cache_key(self.root, _manifest(), [101, 103, 107])

    def test_changes_in_content_seeds_and_settings_invalidate(self) -> None:
        k0 = self._key()
        (self.root / "bench.py").write_text("print('v2 changed')")
        self.assertNotEqual(k0, self._key())
        self.assertNotEqual(cache_key(self.root, _manifest(), [101, 103]), k0)
        self.assertNotEqual(cache_key(self.root, _manifest(), [101, 103, 107], race=True), k0)

    def test_symlinks_and_bytecode_are_ignored(self) -> None:
        k0 = self._key()
        # symlink TARGET lives OUTSIDE the hashed root (only the link is inside)
        outside = tempfile.mkdtemp()
        target = Path(outside) / "outside.py"
        target.write_text("A")
        link = self.root / "link.py"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unsupported here")
        # mutating the symlink's target must NOT change the key (links skipped)
        target.write_text("BBBBBB completely different bytes")
        self.assertEqual(k0, self._key())
        cache_dir = self.root / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "bench.cpython-313.pyc").write_bytes(b"\x00" * 999)
        self.assertEqual(k0, self._key())

    def test_hidden_state_dirs_ignored(self) -> None:
        k0 = self._key()
        state = self.root / ".mycelium_benchmarks"
        state.mkdir()
        (state / "sweep.json").write_text('{"junk": 9999}')
        self.assertEqual(k0, self._key())


class LookupResilienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.key = "a" * 64
        self.payload = {"sweep": {"target": "t", "summaries": []}}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _put(self, raw: str) -> None:
        (self.dir / f"{self.key}.json").write_text(raw, encoding="utf-8")

    def test_roundtrip(self) -> None:
        store(self.dir, self.key, self.payload)
        hit = lookup(self.dir, self.key)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["sweep"], self.payload["sweep"])

    def test_missing_is_none(self) -> None:
        self.assertIsNone(lookup(self.dir, "b" * 64))

    def test_corrupt_json_is_miss(self) -> None:
        self._put("{not valid json")
        self.assertIsNone(lookup(self.dir, self.key))

    def test_non_dict_is_miss(self) -> None:
        self._put(json.dumps([1, 2, 3]))
        self.assertIsNone(lookup(self.dir, self.key))

    def test_wrong_key_and_version_are_misses(self) -> None:
        store(self.dir, self.key, self.payload)
        path = self.dir / f"{self.key}.json"
        data = json.loads(path.read_text())
        data["key"] = "x" * 64
        path.write_text(json.dumps(data))
        self.assertIsNone(lookup(self.dir, self.key))
        data["key"] = self.key
        data["mycelium_version"] = "0.0.0-tampered"
        path.write_text(json.dumps(data))
        self.assertIsNone(lookup(self.dir, self.key))

    def test_missing_sweep_is_miss(self) -> None:
        # a well-formed, correctly-versioned envelope without a dict 'sweep'
        from mycelium_accel import __version__
        (self.dir / f"{self.key}.json").write_text(
            json.dumps({"key": self.key, "mycelium_version": __version__}))
        self.assertIsNone(lookup(self.dir, self.key))


class AtomicWriteTests(unittest.TestCase):
    def test_replace_retry_recovers_from_transient_permission_error(self) -> None:
        calls = {"n": 0}
        real_replace = sweep_cache.os.replace

        def flaky(src, dst):
            calls["n"] += 1
            if calls["n"] < 3:
                raise PermissionError("transient lock")
            return real_replace(src, dst)

        with tempfile.TemporaryDirectory() as temp:
            sweep_cache.os.replace = flaky
            try:
                target = Path(temp) / "out.txt"
                sweep_cache._atomic_write_text(target, "hello")
                self.assertEqual(target.read_text(), "hello")
            finally:
                sweep_cache.os.replace = real_replace
        self.assertEqual(calls["n"], 3)

    def test_failed_write_removes_tmp_and_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "out.txt"

            def boom(*_a, **_k):
                raise PermissionError("locked forever")

            real = sweep_cache.os.replace
            sweep_cache.os.replace = boom
            try:
                with self.assertRaises(PermissionError):
                    sweep_cache._atomic_write_text(target, "x")
            finally:
                sweep_cache.os.replace = real
            leftovers = [p for p in Path(temp).iterdir() if p.name.startswith(".out.txt.")]
            self.assertEqual(leftovers, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
