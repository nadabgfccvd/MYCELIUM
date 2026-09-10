"""C4 — every bench export + doctor --fix is atomic (tmp+rename, no halves).

Pins: CSV bytes bit-identical to the csv module's own output (incl. CRLF),
and fault-injection proof that a failed write leaves no partial file, no
tmp residue, and (on rewrite) the previous bytes intact.
"""
from __future__ import annotations

import csv
import errno
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent))
from test_targets import _make_python_project  # noqa: E402

from mycelium_accel.bench import (  # noqa: E402
    BenchmarkExecutor,
    BenchmarkRun,
    BenchmarkSweep,
    summarize_runs,
)
from mycelium_accel.doctor import fix_manifest  # noqa: E402
from mycelium_accel.targets import load_target  # noqa: E402


def _tiny_sweep() -> BenchmarkSweep:
    base = [
        BenchmarkRun("baseline", 101, "seconds", 1.5, 0.01, True),
        BenchmarkRun("baseline", 103, "seconds", 2.0, 0.02, True),
    ]
    fast = [
        BenchmarkRun("fast", 101, "seconds", 1.0, 0.01, True),
        BenchmarkRun("fast", 103, "seconds", 1.25, 0.02, True),
    ]
    return BenchmarkSweep(
        target="t", metric="seconds", lower_is_better=True,
        summaries=[summarize_runs("baseline", base), summarize_runs("fast", fast)],
        comparisons=[], started_at=1720000000.0,
    )


def _executor(root: Path) -> BenchmarkExecutor:
    _make_python_project(root)
    return BenchmarkExecutor(load_target(root, None))


def _no_space(src: str, dst: str) -> None:
    raise OSError(errno.ENOSPC, "No space left on device")


class CsvGoldenTests(unittest.TestCase):
    def test_csv_bytes_match_csv_module_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = _executor(Path(temp)).export_csv(_tiny_sweep())
            raw = path.read_bytes()
        buf = io.StringIO(newline="")
        writer = csv.writer(buf)
        writer.writerow(["candidate", "seed", "metric", "value", "seconds", "ok"])
        for cand, seed, val, sec in [
            ("baseline", 101, 1.5, 0.01), ("baseline", 103, 2.0, 0.02),
            ("fast", 101, 1.0, 0.01), ("fast", 103, 1.25, 0.02),
        ]:
            writer.writerow([cand, seed, "seconds", val, sec, True])
        self.assertEqual(raw, buf.getvalue().encode("utf-8"))
        self.assertIn(b"\r\n", raw)  # csv dialect preserved, every platform


class ExportAtomicityTests(unittest.TestCase):
    METHODS = ("export_json", "export_csv", "export_markdown", "export_html")

    def test_failed_export_leaves_nothing(self) -> None:
        for method in self.METHODS:
            with self.subTest(export=method), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                executor = _executor(root)
                with mock.patch("mycelium_accel.sweep_cache._replace",
                                side_effect=_no_space):
                    with self.assertRaises(OSError):
                        getattr(executor, method)(_tiny_sweep())
                export_dir = root / ".mycelium_benchmarks"
                finals = [p for p in export_dir.iterdir()
                          if not p.name.startswith(".")]
                self.assertEqual(finals, [])
                self.assertEqual(list(export_dir.glob("*.tmp")), [])

    def test_failed_rewrite_keeps_previous_bytes(self) -> None:
        for method in self.METHODS:
            with self.subTest(export=method), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                executor = _executor(root)
                sweep = _tiny_sweep()
                first = getattr(executor, method)(sweep)
                before = first.read_bytes()
                with mock.patch("mycelium_accel.sweep_cache._replace",
                                side_effect=_no_space):
                    with self.assertRaises(OSError):
                        getattr(executor, method)(sweep)  # same stem → same path
                self.assertEqual(first.read_bytes(), before)
                self.assertEqual(list(first.parent.glob("*.tmp")), [])

    def test_healthy_exports_still_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            executor = _executor(Path(temp))
            sweep = _tiny_sweep()
            as_json = json.loads(executor.export_json(sweep).read_bytes())
            self.assertEqual(as_json["metric"], "seconds")
            self.assertEqual(len(as_json["summaries"]), 2)
            md = executor.export_markdown(sweep).read_text(encoding="utf-8")
            self.assertIn("baseline", md)
            html = executor.export_html(sweep).read_text(encoding="utf-8")
            self.assertIn("<html", html)


class FixManifestAtomicityTests(unittest.TestCase):
    def test_failed_fix_keeps_original_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            manifest_path = root / "mycelium.target.json"
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            raw.pop("manifest_version", None)  # something to fix
            manifest_path.write_text(json.dumps(raw), encoding="utf-8")
            before = manifest_path.read_bytes()
            with mock.patch("mycelium_accel.sweep_cache._replace",
                            side_effect=_no_space):
                with self.assertRaises(OSError):
                    fix_manifest(root)
            self.assertEqual(manifest_path.read_bytes(), before)
            self.assertEqual(list(root.glob("*.tmp")), [])

    def test_healthy_fix_still_stamps(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            manifest_path = root / "mycelium.target.json"
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            raw.pop("manifest_version", None)
            manifest_path.write_text(json.dumps(raw), encoding="utf-8")
            done = fix_manifest(root)
            self.assertTrue(any("manifest_version" in item for item in done))
            stamped = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(stamped["manifest_version"], "1.0")


if __name__ == "__main__":
    unittest.main()
