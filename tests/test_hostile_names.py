"""Q2.4 — hostile names (unicode, spaces, quotes, HTML) stay correct.

JSON roundtrips, CSV parses, and the HTML report escapes (no stored XSS via
a crafted variant name). Env values never touch a shell (subprocess argv).
"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent))
from test_targets import _make_python_project  # noqa: E402

from mycelium_accel.accelerate_generic import accelerate_target  # noqa: E402

EVIL = '<img src=x onerror=alert(1)>'
NAMES = ['fast "quoted"', 'slów ünïcode', EVIL, 'pipe|name']


class HostileNameTests(unittest.TestCase):
    def test_accelerate_and_exports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dir com espaço"
            root.mkdir()
            _make_python_project(root)
            manifest = json.loads((root / "mycelium.target.json").read_text())
            manifest["variants"] = [
                {"name": name, "mode": "env", "env": {"BENCH_MODE": "fast"}}
                for name in NAMES
            ]
            (root / "mycelium.target.json").write_text(json.dumps(manifest), encoding="utf-8")
            out = accelerate_target(root, seeds=[101, 103, 107], apply=False)
            self.assertIsNotNone(out.sweep_path)
            exp = root / ".mycelium_benchmarks"
            by_ext = {}
            for path in exp.iterdir():
                by_ext.setdefault(path.suffix, path)

            sweep = json.loads(by_ext[".json"].read_text(encoding="utf-8"))
            got = [s["candidate"] for s in sweep["summaries"]]
            self.assertEqual(got, ["baseline", *NAMES])

            with by_ext[".csv"].open(encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
            self.assertGreater(len(rows), 4)  # header + runs
            names_in_csv = {row[0] for row in rows[1:]}
            self.assertTrue(set(NAMES) <= names_in_csv)

            html = by_ext[".html"].read_text(encoding="utf-8")
            self.assertNotIn(EVIL, html)  # escaped, not stored XSS
            self.assertIn("img", html)  # ...but still legible-ish

            md = by_ext[".md"].read_text(encoding="utf-8")
            self.assertIn("slów ünïcode", md)

    def test_shell_metachars_and_controls_roundtrip(self) -> None:
        # C4: names a shell would interpret ($ ; \ newline tab) stay inert
        # labels — JSON/CSV roundtrip them, exports never crash on them.
        extra = ["dollar$BENCH", "semi;colon", "back\\slash", "line\nbreak",
                 "tab\tname", "snowman☃", 'quote"q']
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dir com espaço"
            root.mkdir()
            _make_python_project(root)
            manifest = json.loads((root / "mycelium.target.json").read_text())
            manifest["variants"] = [
                {"name": name, "mode": "env", "env": {"BENCH_MODE": "fast"}}
                for name in extra
            ]
            (root / "mycelium.target.json").write_text(json.dumps(manifest), encoding="utf-8")
            out = accelerate_target(root, seeds=[101, 103, 107], apply=False)
            self.assertIsNotNone(out.sweep_path)
            exp = root / ".mycelium_benchmarks"
            by_ext = {}
            for path in exp.iterdir():
                by_ext.setdefault(path.suffix, path)
            self.assertEqual(set(by_ext), {".json", ".csv", ".md", ".html"})
            sweep = json.loads(by_ext[".json"].read_text(encoding="utf-8"))
            self.assertEqual([s["candidate"] for s in sweep["summaries"]],
                             ["baseline", *extra])
            with by_ext[".csv"].open(encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertTrue(set(extra) <= {row[0] for row in rows[1:]})


if __name__ == "__main__":
    unittest.main()
