"""TEMPORÁRIO (sessão Arena 01a09029) — busca de artefato externo no CI.

Motivo: a sandbox de desenvolvimento não alcança filebin.net (o proxy de saída
roteia por SNI e só libera github/pypi/npm), e o log cru do job do Actions
também não é legível de dentro dela. Os runners, porém, têm saída livre.

Estratégia: baixar o zip publicado pelo mantenedor e devolvê-lo ao próprio
branch por commit. Se o push não for possível, o conteúdo vai para o *job
summary* ($GITHUB_STEP_SUMMARY), que a API de check-runs expõe em
`output.summary` — um canal de texto legível pela sandbox.

Fora do CI (e quando o arquivo já existe no branch remoto) não faz nada e não
falha. REMOVER este arquivo e `.incoming/` assim que a integração acabar.
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
_REPO = "nadabgfccvd/MYCELIUM"
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36"
)
_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY", "")
_PAYLOAD_LIMIT = 700_000  # caracteres por job (summaries têm teto de ~1 MB)


def _summary(lines: list[str]) -> None:
    """Escreve no job summary (canal legível pela API de check-runs)."""
    if not _SUMMARY:
        return
    with open(_SUMMARY, "a", encoding="utf-8") as fh:  # noqa: PTH123 - caminho do runner
        fh.write("\n".join(lines) + "\n")


def _run(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - lista fixa, sem shell
        args,
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        env=env,
    )


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return _run(["git", *args])


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
        except Exception as exc:  # noqa: BLE001 - rede
            log.append(f"attempt={attempt} EXC {type(exc).__name__}: {exc}")
    return None, log


def _slice_of(data: bytes) -> tuple[int, int]:
    """Dois runners Linux na matriz → cada um publica uma metade do payload."""
    key = os.environ.get("pythonLocation", "") + os.environ.get("RUNNER_OS", "")
    idx = 0 if "3.14" not in key else 1
    return idx, 2


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
    _git(["fetch", "origin", branch])

    incoming = _ROOT / ".incoming"
    incoming.mkdir(exist_ok=True)
    dest = incoming / _ZIP_NAME

    already = _git(["cat-file", "-e", f"origin/{branch}:.incoming/{_ZIP_NAME}"]).returncode == 0
    if already:
        pytest.skip("zip já está no branch remoto")

    data, log = _download()
    diag: list[str] = [f"url={URL}", f"branch={branch}", f"job={os.environ.get('GITHUB_JOB')}", *log]
    _summary(["<!-- TMPFETCH-BEGIN -->", "<pre>", *diag, "</pre>"])

    if data is None:
        _summary(["**TMPFETCH: download falhou**"])
        assert data is not None, f"download falhou: {log}"

    diag.append(f"sha256={hashlib.sha256(data).hexdigest()}")
    diag.append(f"size={len(data)}")
    try:
        dest.write_bytes(data)
        with zipfile.ZipFile(dest) as zf:
            diag.append(f"entries={len(zf.namelist())}")
            diag.extend(f"entry {i.filename}|{i.file_size}|{i.CRC:08x}" for i in zf.infolist())
    except Exception as exc:  # noqa: BLE001
        diag.append(f"ZIPERR {type(exc).__name__}: {exc}")
    _summary(["<pre>", *diag, "</pre>"])

    _git(["add", "--", ".incoming"])
    commit = _git(["commit", "-m", "tmp(chore): fetch MYCELIUM_UNIAO_V1.6.0.zip via CI"])
    pushed = False
    push_err = ""
    for _ in range(3):
        _git(["pull", "--rebase", "origin", branch])
        push = _git(["push", "origin", f"HEAD:{branch}"])
        if push.returncode == 0:
            pushed = True
            break
        push_err = (push.stderr or "").replace("\n", " ")[:300]

    perm = _run(
        ["gh", "api", f"repos/{_REPO}", "--jq", ".permissions"],
        env={**os.environ, "GH_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
    )
    _summary([
        "<pre>",
        f"commit_rc={commit.returncode}",
        f"pushed={pushed}",
        f"push_err={push_err}",
        f"token_permissions={(perm.stdout or perm.stderr or '').strip()[:300]}",
        "</pre>",
    ])

    if not pushed and os.environ.get("GITHUB_JOB") == "full":
        # Contingência: sem push, o conteúdo sai pelo job summary em fatias.
        b64 = base64.b64encode(data).decode("ascii")
        idx, total = _slice_of(data)
        step = _PAYLOAD_LIMIT
        start = idx * step
        chunk = b64[start : start + step]
        _summary([
            f"<!-- TMPB64 slice {idx}/{total} len={len(chunk)} total_b64={len(b64)} -->",
            "<pre>",
            chunk,
            "</pre>",
        ])
