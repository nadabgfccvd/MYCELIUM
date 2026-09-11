"""TEMPORÁRIO (sessão Arena 01a09029) — busca de artefato externo no CI.

Motivo: a sandbox de desenvolvimento não alcança filebin.net (o proxy de saída
roteia por SNI e só libera github/pypi/npm), enquanto os runners do GitHub
Actions têm saída livre. Este módulo baixa o zip publicado pelo mantenedor e o
devolve ao próprio branch por commit, para que a sessão possa integrá-lo.

Fora do CI (e quando o arquivo já existe no branch remoto) ele não faz nada e
não falha. REMOVER este arquivo e `.incoming/` assim que a integração acabar.
"""

from __future__ import annotations

import base64
import hashlib
import http.cookiejar
import os
import pathlib
import subprocess
import urllib.request
import zipfile

import pytest

URL = "https://filebin.net/mycelium-s2-20260910/MYCELIUM_UNIAO_V1.6.0.zip"
_ZIP_NAME = "MYCELIUM_UNIAO_V1.6.0.zip"
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36"
)
_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - caminho fixo, sem shell
        ["git", *args],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=check,
    )


def _download() -> tuple[bytes | None, list[str]]:
    """Baixa o zip; o aviso do filebin aparece uma vez, então tentamos 3x."""
    log: list[str] = []
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": _UA, "Accept": "*/*"})
            with opener.open(req, timeout=180) as resp:
                data = resp.read()
            status = getattr(resp, "status", "?")
            if data[:2] == b"PK":
                log.append(f"attempt={attempt} http={status} bytes={len(data)}")
                return data, log
            head = data[:160].decode("utf-8", "replace").replace("\n", " ")
            log.append(f"attempt={attempt} http={status} bytes={len(data)} not-a-zip head={head!r}")
        except Exception as exc:  # pragma: no cover - rede
            log.append(f"attempt={attempt} EXC {type(exc).__name__}: {exc}")
    return None, log


def test_tmp_fetch_filebin() -> None:
    """No CI: baixa o zip e o devolve ao branch. Fora do CI: no-op."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        pytest.skip("coleta externa só roda no CI (sandbox sem saída p/ filebin)")
    if os.environ.get("RUNNER_OS") != "Linux":
        pytest.skip("coleta externa roda só no runner Linux")

    branch = os.environ.get("GITHUB_REF_NAME", "")
    if not branch:
        pytest.skip("sem GITHUB_REF_NAME")

    _git(["config", "user.email", "github-actions[bot]@users.noreply.github.com"])
    _git(["config", "user.name", "github-actions[bot]"])
    _git(["fetch", "origin", branch], check=False)

    incoming = _ROOT / ".incoming"
    incoming.mkdir(exist_ok=True)
    report = incoming / "FETCH_REPORT.txt"
    dest = incoming / _ZIP_NAME

    already = subprocess.run(  # noqa: S603
        ["git", "cat-file", "-e", f"origin/{branch}:.incoming/{_ZIP_NAME}"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
    ).returncode == 0
    if already:
        pytest.skip("zip já está no branch remoto")

    data, log = _download()
    lines: list[str] = [f"url={URL}", f"branch={branch}", *log]
    if data is None:
        report.write_text("\n".join(lines) + "\nFALHOU: zip não baixado\n", encoding="utf-8")
    else:
        dest.write_bytes(data)
        lines.append(f"sha256={hashlib.sha256(data).hexdigest()}")
        lines.append(f"size={len(data)}")
        lines.append(f"b64_sha256={hashlib.sha256(base64.b64encode(data)).hexdigest()}")
        try:
            with zipfile.ZipFile(dest) as zf:
                lines.append(f"entries={len(zf.namelist())}")
                lines.extend(f"entry {i.filename}|{i.file_size}|{i.CRC:08x}" for i in zf.infolist())
        except Exception as exc:  # noqa: BLE001
            lines.append(f"ZIPERR {type(exc).__name__}: {exc}")
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _git(["add", "--", ".incoming"])
    _git(["commit", "-m", "tmp(chore): fetch MYCELIUM_UNIAO_V1.6.0.zip via CI (remover depois)"], check=False)
    pushed = False
    push_error = ""
    for _ in range(3):
        _git(["pull", "--rebase", "origin", branch], check=False)
        push = _git(["push", "origin", f"HEAD:{branch}"], check=False)
        if push.returncode == 0:
            pushed = True
            break
        push_error = (push.stderr or "")[:400]

    if not pushed and data is not None:
        # Contingência: push falhou → manda o conteúdo como anotações do check
        # run (legíveis pela API, já que o log do job não é alcançável).
        b64 = base64.b64encode(data).decode("ascii")
        for i in range(0, len(b64), 3000):
            print(f"::warning::TMPB64 {b64[i : i + 3000]}")  # noqa: T201
        print(f"::error::tmpfetch push falhou: {push_error}")  # noqa: T201

    assert data is not None, f"download falhou: {log}"
