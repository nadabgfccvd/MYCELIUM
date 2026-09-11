"""Fase 1.4: UI server smoke — boots and answers HTTP 200 on /.

Skipped on non-posix platforms (the server imports `resource`, Unix-only);
that limitation is documented in docs/ARCHITECTURE.md instead of faked.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@unittest.skipIf(os.name != "posix", "UI server requires Unix (resource module)")
class UiSmokeTests(unittest.TestCase):
    def test_server_boots_and_serves_index(self) -> None:
        port = _free_port()
        env = dict(os.environ)
        env["MYCELIUM_UI_HOST"] = "127.0.0.1"
        env["MYCELIUM_UI_PORT"] = str(port)
        proc = subprocess.Popen(
            [sys.executable, "scripts/mycelium_ui_server.py"],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        try:
            deadline = time.time() + 15
            body = None
            last_error: Exception | None = None
            while time.time() < deadline:
                if proc.poll() is not None:
                    _, err = proc.communicate(timeout=5)
                    self.fail(f"server exited early: {err.decode()[-500:]}")
                try:
                    # Bypass proxy env vars: CI macOS runners may set http_proxy,
                    # which urllib would otherwise apply even to loopback URLs.
                    opener = urllib.request.build_opener(
                        urllib.request.ProxyHandler({}))
                    with opener.open(f"http://127.0.0.1:{port}/", timeout=2) as resp:
                        self.assertEqual(resp.status, 200)
                        body = resp.read().decode("utf-8", errors="replace")
                    break
                except Exception as exc:  # noqa: BLE001 - retry until deadline
                    last_error = exc
                    time.sleep(0.3)
            self.assertIsNotNone(body, f"server never answered: {last_error}")
            assert body is not None
            self.assertIn("MYCELIUM", body)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    unittest.main()
