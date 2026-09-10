"""C8 — UI server pure units: no socket, no subprocess, milliseconds.

The server module is importable (work lives under `__main__`), so its pure
helpers pin directly. Posix-gated like the smoke test (`resource` import).
"""
from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_server():
    spec = importlib.util.spec_from_file_location(
        "ui_server_under_test", ROOT / "scripts" / "mycelium_ui_server.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(os.name != "posix", "UI server requires Unix (resource module)")
class UiPureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.srv = _load_server()

    def test_mode_labels(self) -> None:
        self.assertEqual(self.srv.human_mode_label("run"), "Explorar")
        self.assertEqual(self.srv.human_mode_label("self-improve"), "Auto melhorar")
        self.assertEqual(self.srv.human_mode_label("focused"), "Calibrar a fundo")
        self.assertEqual(self.srv.human_mode_label(None), "Sem execução")
        self.assertEqual(self.srv.human_mode_label("weird"), "weird")

    def test_history_status_matrix(self) -> None:
        f = self.srv.human_history_status
        self.assertEqual(f(True, None, True, None)[0], "stopping")
        self.assertEqual(f(True, None, False, None)[0], "running")
        self.assertEqual(f(False, 0, True, 1.0)[0], "stopped_ok")
        self.assertEqual(f(False, 0, False, 1.0)[0], "success")
        self.assertEqual(f(False, 1, True, 1.0)[0], "stopped_error")
        self.assertEqual(f(False, 1, False, 1.0)[0], "failed")
        self.assertEqual(f(False, None, False, 1.0)[0], "interrupted")
        self.assertEqual(f(False, None, False, None)[0], "idle")
        for args in [(True, None, True, None), (False, 0, False, 1.0),
                     (False, 2, False, None), (False, None, False, None)]:
            code, label = f(*args)
            self.assertIsInstance(code, str)
            self.assertTrue(label)  # every code ships a human label

    def test_project_tree_caps_depth_and_sorts(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "b").mkdir()
            (root / "a").mkdir()
            (root / "a" / "deep").mkdir()
            (root / "a" / "deep" / "deeper").mkdir()
            (root / "a" / "deep" / "deeper" / "deepest").mkdir()
            tree = self.srv.build_project_tree(root, max_depth=3)
            self.assertLess(tree.index("a"), tree.index("b"))  # sorted
            self.assertNotIn("deepest", tree)  # depth cap honored

    def test_static_ui_has_no_external_refs(self) -> None:
        ui = ROOT / "mycelium_ui"
        for name in ("index.html", "app.js", "styles.css"):
            text = (ui / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                for banned in ("http://", "https://", "@import",
                               "src=\"http", "href=\"http"):
                    self.assertNotIn(banned, text)

    def test_no_reverse_dns_on_bind(self) -> None:
        # CI-5 regression pin at unit level: UIServer must not resolve names.
        import socket

        calls: list[str] = []
        real_getfqdn = socket.getfqdn
        socket.getfqdn = lambda *a, **k: calls.append("getfqdn") or "x"  # type: ignore[method-assign]
        try:
            server = self.srv.UIServer(("127.0.0.1", 0), self.srv.Handler)
            try:
                self.assertEqual(calls, [])
            finally:
                server.server_close()
        finally:
            socket.getfqdn = real_getfqdn


if __name__ == "__main__":
    unittest.main()
