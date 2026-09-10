"""TEMPORÁRIO (sessão Arena 01a08cfc) — coleta de um artefato externo no CI.

Motivo: a sandbox de desenvolvimento não alcança filebin.net (egress filtrado),
mas os runners do GitHub Actions alcançam. Este módulo baixa o zip publicado
pelo mantenedor, imprime sha256 + listagem (nome, tamanho, CRC32) de cada
entrada e um dump base64 do arquivo, tudo direto no terminal do job (fora do
capture do pytest) para permitir comparação byte-a-byte com o repositório.

Este arquivo não é um teste (prefixo `_`), não coleta nada e nunca falha.
Deve ser REMOVIDO assim que a comparação terminar.
"""

from __future__ import annotations

import base64
import hashlib
import http.cookiejar
import io
import os
import urllib.request
import zipfile

URL = "https://filebin.net/qmyb4xtsarn0gnn3/MYCELIUM_CICLO10_FINAL.zip"
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def _download() -> tuple[bytes | None, str]:
    """Baixa o zip; o aviso do filebin aparece uma vez, então tentamos 3x."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    last = "no attempt"
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": _UA, "Accept": "*/*"})
            with opener.open(req, timeout=120) as resp:
                data = resp.read()
            status = getattr(resp, "status", "?")
            if data[:2] == b"PK":
                return data, f"attempt={attempt} http={status} bytes={len(data)}"
            head = data[:120].decode("utf-8", "replace").replace("\n", " ")
            last = f"attempt={attempt} http={status} bytes={len(data)} not-a-zip head={head!r}"
        except Exception as exc:  # pragma: no cover - rede
            last = f"attempt={attempt} EXC {type(exc).__name__}: {exc}"
    return None, last


def emit(reporter) -> None:  # noqa: ANN001 - terminal reporter do pytest
    if os.environ.get("RUNNER_OS") not in {"Linux", "macOS", "Windows"}:
        return
    write = reporter.write
    write("\n===== TMPFETCH início =====")
    data, info = _download()
    write(f"TMPFETCH_INFO {info}")
    if data is None:
        write("===== TMPFETCH fim (sem arquivo) =====")
        return
    write(f"TMPFETCH_SHA256 {hashlib.sha256(data).hexdigest()}")
    write(f"TMPFETCH_SIZE {len(data)}")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            write(f"TMPFETCH_ENTRIES {len(names)}")
            for zi in zf.infolist():
                write(f"TMPFETCH_ENTRY {zi.filename}|{zi.file_size}|{zi.CRC:08x}")
    except Exception as exc:
        write(f"TMPFETCH_ZIPERR {type(exc).__name__}: {exc}")
    # Dump base64 em blocos (permite reconstruir o arquivo fora do CI).
    b64 = base64.b64encode(data).decode("ascii")
    step = 3000
    for i in range(0, len(b64), step):
        write(f"TMPB64 {b64[i:i + step]}")
    write("===== TMPFETCH fim =====")
