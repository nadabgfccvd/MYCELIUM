"""Fase 1.4: UI server smoke — boots and answers HTTP 200 on /.

Skipped on non-posix platforms (the server imports `resource`, Unix-only);
that limitation is documented in docs/ARCHITECTURE.md instead of faked.

CI-5 (macOS runs were red on *timing*, never on behavior). Three hardenings:

* the OS picks the port (``MYCELIUM_UI_PORT=0``) and the test reads it back
  from the server's own banner — no "find a free port then hope nobody steals
  it" race, and no guesswork about which interface the child bound;
* boot + HTTP share one generous, CI-scaled deadline with a per-attempt socket
  timeout sized for a starved child (xdist + real sweeps saturate CI runners;
  the old 15 s/2 s pair was already tight on macOS);
* child stdout/stderr are drained in threads, so the pipes can never fill and
  wedge the child — and the server's own log lines ride into the failure
  message, so a future red CI run names the cause instead of the symptom.
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import threading
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Locally the server answers in well under a second; on a CI box running the
# whole suite under -n auto it can be starved for tens of seconds. Budget for
# the slowest host we measure, not the fastest we own.
BOOT_TIMEOUT = 120.0 if os.environ.get("CI") else 30.0
PROBE_TIMEOUT = 10.0  # per-attempt socket timeout (connect + read)
_BANNER = re.compile(r"listening on http://(?P<host>[^:\s]+):(?P<port>\d+)")


class _StreamTail:
    """Drain a child pipe in a thread, keeping its text for diagnostics."""

    def __init__(self, stream) -> None:  # noqa: ANN001 - TextIOWrapper
        self._stream = stream
        self._lines: list[str] = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._pump, daemon=True)

    def _pump(self) -> None:
        for line in iter(self._stream.readline, ""):
            with self._lock:
                self._lines.append(line)
        try:
            self._stream.close()
        except OSError:
            pass

    def start(self) -> None:
        self._thread.start()

    def lines(self) -> list[str]:
        with self._lock:
            return list(self._lines)

    def text(self, limit: int = 4000) -> str:
        with self._lock:
            return "".join(self._lines)[-limit:]

    def join(self, timeout: float = 5.0) -> None:
        self._thread.join(timeout=timeout)


@unittest.skipIf(os.name != "posix", "UI server requires Unix (resource module)")
class UiSmokeTests(unittest.TestCase):
    def test_server_boots_and_serves_index(self) -> None:
        env = dict(os.environ)
        env.update({
            "MYCELIUM_UI_HOST": "127.0.0.1",
            "MYCELIUM_UI_PORT": "0",  # 0 => the OS assigns; read it from the banner
            "PYTHONUNBUFFERED": "1",  # banner must reach us before we can poll
            "PYTHONUTF8": "1",  # the UI logs Portuguese text into a pipe
        })
        proc = subprocess.Popen(
            [sys.executable, "scripts/mycelium_ui_server.py"],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL,
        )
        out, err = _StreamTail(proc.stdout), _StreamTail(proc.stderr)
        out.start()
        err.start()
        try:
            deadline = time.monotonic() + BOOT_TIMEOUT
            port = self._await_banner(out, err, proc, deadline)
            self._await_port(port, err, proc, deadline)
            # Bypass proxy env vars: CI runners set http_proxy, which urllib
            # would otherwise apply even to loopback URLs.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            body = self._await_index(opener, port, err, proc, deadline)
            self.assertIn("MYCELIUM", body)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            out.join()
            err.join()

    # -- helpers ---------------------------------------------------------
    def _died(self, proc: subprocess.Popen[str]) -> bool:
        return proc.poll() is not None

    def _early_exit(self, err: _StreamTail, out: _StreamTail | None = None) -> None:
        detail = err.text(2000) + (out.text(1000) if out else "")
        self.fail(f"server exited early: {detail.strip()[-500:] or 'no output'}")

    def _await_banner(self, out: _StreamTail, err: _StreamTail,
                      proc: subprocess.Popen[str], deadline: float) -> int:
        while time.monotonic() < deadline:
            for line in out.lines():
                match = _BANNER.search(line)
                if match:
                    return int(match.group("port"))
            if self._died(proc):
                self._early_exit(err, out)
            time.sleep(0.05)
        self.fail(
            "server never announced its port: "
            f"stdout={out.text(500)!r} stderr={err.text(500)!r}")

    def _await_port(self, port: int, err: _StreamTail,
                    proc: subprocess.Popen[str], deadline: float) -> None:
        """Wait until the listening socket accepts — HTTP on a half-booted
        server shows up as a bare timeout, which tells us nothing."""
        last: Exception | None = None
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                    return
            except OSError as exc:
                last = exc
            if self._died(proc):
                self._early_exit(err)
            time.sleep(0.05)
        self.fail(f"port {port} never accepted connections: {last!r} "
                  f"stderr={err.text(500)!r}")

    def _await_index(self, opener: urllib.request.OpenerDirector, port: int,
                     err: _StreamTail, proc: subprocess.Popen[str],
                     deadline: float) -> str:
        last: Exception | None = None
        while time.monotonic() < deadline:
            if self._died(proc):
                self._early_exit(err)
            try:
                with opener.open(f"http://127.0.0.1:{port}/",
                                 timeout=PROBE_TIMEOUT) as resp:
                    self.assertEqual(resp.status, 200)
                    body = resp.read().decode("utf-8", errors="replace")
                    self.assertTrue(body, "server answered / with an empty body")
                    return body
            except Exception as exc:  # noqa: BLE001 - retry until deadline
                last = exc
                time.sleep(0.3)
        self.fail(f"server never answered: {last} stderr={err.text(500)!r}")


if __name__ == "__main__":
    unittest.main()
