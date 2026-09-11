from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, UTC
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mycelium_accel.runtime_profile import load_default_profile
from mycelium_accel.state import load_state

UI_ROOT = PROJECT_ROOT / "mycelium_ui"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765

HELP_TEXT = """/help
Mostra esta ajuda em linguagem simples.

/status
Mostra o estado atual do MYCELIUM Auto-evolve: se está rodando, há quanto tempo, quantos rounds já fez e quais foram as últimas métricas.

/run 100
Roda 100 rounds normais de evolução. Use quando você só quer que o sistema evolua sem tentar se recalibrar.

/self-improve 25
Roda auto melhoria por 25 minutos. O sistema testa candidatos e só aplica os que passarem no guarda anti-regressão.

/focused 8
Roda a calibração focada dos mecanismos novos por 8 horas. Esse modo tenta melhorar os componentes ligados a macro staging, fronteira, diversidade e recombinação.

/stop
Pede para a rodada atual parar com segurança. O progresso salvo continua em disco.

/report
Mostra onde está o último relatório automático da rodada.

/ram 2048
Define o orçamento de memória em MB para a próxima execução iniciada pela interface. Exemplo: /ram 2048.

O que significa cada modo:
- Run: evolução normal, mais simples e direta.
- Auto melhoria: evolução + autotuning com trava de segurança.
- Calibração focada: autotuning mirando os mecanismos novos do projeto.

Modo segundo plano:
Se você ficar 5 minutos sem interagir com o terminal da interface, ela entra em modo segundo plano. Isso reduz o peso da própria interface. Quando você clicar de volta, o progresso reaparece e continua de onde parou.

RAM:
Mais RAM pode ajudar o processo a manter mais estado e reduzir pressão de memória, especialmente em auto melhoria com múltiplos workers. Não garante milagre, mas pode ajudar a estabilidade e o desempenho.
"""


def human_mode_label(mode: str | None) -> str:
    if mode == "run":
        return "Explorar"
    if mode == "self-improve":
        return "Auto melhorar"
    if mode == "focused":
        return "Calibrar a fundo"
    return mode or "Sem execução"


def human_history_status(running: bool, returncode: int | None, stop_requested: bool, finished_at: float | None) -> tuple[str, str]:
    if running and stop_requested:
        return "stopping", "Parando com segurança"
    if running:
        return "running", "Rodando agora"
    if returncode == 0 and stop_requested:
        return "stopped_ok", "Parada concluída"
    if returncode == 0:
        return "success", "Concluída com sucesso"
    if returncode not in (None, 0) and stop_requested:
        return "stopped_error", "Parada com erro"
    if returncode not in (None, 0):
        return "failed", "Terminou com erro"
    if finished_at:
        return "interrupted", "Interrompida"
    return "idle", "Sem resultado ainda"


class ProcessSession:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.process: subprocess.Popen[str] | None = None
        self.mode: str | None = None
        self.command: list[str] | None = None
        self.state_dir: str | None = None
        self.ram_mb: int | None = None
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.returncode: int | None = None
        self.log_lines: deque[str] = deque(maxlen=4000)
        self.log_file = PROJECT_ROOT / ".mycelium_ui" / "session.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.session_meta_file = PROJECT_ROOT / ".mycelium_ui" / "session.json"
        self.history_file = PROJECT_ROOT / ".mycelium_ui" / "history.json"
        self.last_report_path: str | None = None
        self.last_auto_report_path: str | None = None
        self.last_error: str | None = None
        self.pending_ram_mb: int = 2048
        self.start_round_index: int = 0
        self.stop_requested: bool = False
        self.session_id: str | None = None
        self.launch_payload: dict[str, Any] | None = None
        self.history_entries: list[dict[str, Any]] = []
        self._load_history()
        self._load_meta()
        self._maybe_migrate_legacy_session_to_history()
        self._load_log()

    def append_log(self, line: str) -> None:
        timestamp = datetime.now(UTC).strftime("%H:%M:%S")
        entry = f"[{timestamp}] {line.rstrip()}"
        with self.lock:
            self.log_lines.append(entry)
            self.log_file.write_text("\n".join(self.log_lines), encoding="utf-8")

    def _load_history(self) -> None:
        try:
            if not self.history_file.exists():
                self.history_entries = []
                return
            payload = json.loads(self.history_file.read_text(encoding="utf-8"))
            self.history_entries = payload if isinstance(payload, list) else []
        except Exception:
            self.history_entries = []

    def _save_history(self) -> None:
        self.history_file.write_text(
            json.dumps(self.history_entries[:24], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _history_entry_locked(self) -> dict[str, Any]:
        process = self.process
        running = process is not None and process.poll() is None
        if self.started_at and self.finished_at:
            elapsed_seconds = max(0.0, self.finished_at - self.started_at)
        elif self.started_at:
            elapsed_seconds = max(0.0, time.time() - self.started_at)
        else:
            elapsed_seconds = 0.0
        status, status_label = human_history_status(running, self.returncode, self.stop_requested, self.finished_at)
        return {
            "id": self.session_id,
            "mode": self.mode,
            "mode_label": human_mode_label(self.mode),
            "state_dir": self.state_dir,
            "ram_mb": self.ram_mb,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": elapsed_seconds,
            "returncode": self.returncode,
            "running": running,
            "status": status,
            "status_label": status_label,
            "stop_requested": self.stop_requested,
            "last_auto_report_path": self.last_auto_report_path,
            "last_report_path": self.last_report_path,
            "last_error": self.last_error,
            "start_round_index": self.start_round_index,
            "launch_payload": self.launch_payload,
        }

    def _upsert_history(self) -> None:
        with self.lock:
            entry = self._history_entry_locked()
            existing_index = next((i for i, item in enumerate(self.history_entries) if item.get("id") == self.session_id), None)
            if existing_index is None:
                self.history_entries.insert(0, entry)
            else:
                self.history_entries[existing_index] = entry
            self.history_entries.sort(key=lambda item: float(item.get("started_at") or 0.0), reverse=True)
            self.history_entries = self.history_entries[:24]
        self._save_history()

    def _maybe_migrate_legacy_session_to_history(self) -> None:
        if self.history_entries:
            return
        if not (self.mode or self.last_auto_report_path or self.state_dir):
            return
        if not self.session_id:
            base_ts = self.started_at or self.finished_at or time.time()
            self.session_id = f"legacy-{int(base_ts * 1000)}"
        self._upsert_history()

    def recent_history(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.lock:
            history = list(self.history_entries[:limit])
        return history

    def _load_log(self) -> None:
        try:
            if not self.log_file.exists():
                return
            content = self.log_file.read_text(encoding="utf-8")
            for line in content.splitlines()[-4000:]:
                self.log_lines.append(line)
        except Exception:
            pass

    def _load_meta(self) -> None:
        try:
            if not self.session_meta_file.exists():
                return
            payload = json.loads(self.session_meta_file.read_text(encoding="utf-8"))
        except Exception:
            return
        self.session_id = payload.get("session_id")
        self.mode = payload.get("mode")
        self.command = payload.get("command")
        self.state_dir = payload.get("state_dir")
        self.ram_mb = payload.get("ram_mb")
        self.pending_ram_mb = int(payload.get("pending_ram_mb", self.pending_ram_mb) or self.pending_ram_mb)
        self.started_at = payload.get("started_at")
        self.finished_at = payload.get("finished_at")
        self.returncode = payload.get("returncode")
        self.last_auto_report_path = payload.get("last_auto_report_path")
        self.last_report_path = payload.get("last_report_path")
        self.last_error = payload.get("last_error")
        self.start_round_index = int(payload.get("start_round_index", 0) or 0)
        self.stop_requested = bool(payload.get("stop_requested", False))
        self.launch_payload = payload.get("launch_payload") or None

    def _persist_meta(self) -> None:
        with self.lock:
            process = self.process
            payload = {
                "session_id": self.session_id,
                "running": process is not None and process.poll() is None,
                "pid": process.pid if process is not None else None,
                "mode": self.mode,
                "command": self.command,
                "state_dir": self.state_dir,
                "ram_mb": self.ram_mb,
                "pending_ram_mb": self.pending_ram_mb,
                "elapsed_seconds": ((self.finished_at - self.started_at) if (self.started_at and self.finished_at) else (time.time() - self.started_at) if self.started_at else 0.0),
                "returncode": self.returncode,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "last_auto_report_path": self.last_auto_report_path,
                "last_report_path": self.last_report_path,
                "last_error": self.last_error,
                "start_round_index": self.start_round_index,
                "stop_requested": self.stop_requested,
                "launch_payload": self.launch_payload,
            }
        self.session_meta_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def is_running(self) -> bool:
        with self.lock:
            return self.process is not None and self.process.poll() is None

    def _memory_limiter(self, ram_mb: int | None):
        if not ram_mb:
            return None
        limit_bytes = int(ram_mb) * 1024 * 1024

        def _apply() -> None:
            try:
                resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
            except Exception:
                pass
            try:
                resource.setrlimit(resource.RLIMIT_DATA, (limit_bytes, limit_bytes))
            except Exception:
                pass

        return _apply

    def start(
        self,
        mode: str,
        command: list[str],
        state_dir: str,
        ram_mb: int | None,
        launch_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        runtime_before = current_runtime_summary(state_dir)
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                raise RuntimeError("Já existe um processo do MYCELIUM Auto-evolve em execução.")
            self.process = None
            self.mode = mode
            self.command = command
            self.state_dir = state_dir
            self.ram_mb = ram_mb
            self.started_at = time.time()
            self.finished_at = None
            self.returncode = None
            self.stop_requested = False
            self.session_id = f"ui-session-{int(self.started_at * 1000)}"
            self.launch_payload = dict(launch_payload or {})
            self.log_lines.clear()
            self.last_error = None
            self.last_report_path = None
            self.last_auto_report_path = None
            self.start_round_index = int(runtime_before.get("round_index", 0) or 0)
            self.log_file.write_text("", encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        preexec_fn = self._memory_limiter(ram_mb) if os.name != "nt" else None
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
            preexec_fn=preexec_fn,
        )
        with self.lock:
            self.process = process
        self._persist_meta()
        self._upsert_history()
        self.append_log(f"Modo: {mode}")
        self.append_log(f"RAM configurada: {ram_mb or 'auto'} MB")
        self.append_log(f"Comando: {' '.join(command)}")
        threading.Thread(target=self._stream_reader, args=(process.stdout, "OUT"), daemon=True).start()
        threading.Thread(target=self._stream_reader, args=(process.stderr, "ERR"), daemon=True).start()
        threading.Thread(target=self._monitor_process, args=(process,), daemon=True).start()
        return self.snapshot()

    def _stream_reader(self, pipe, label: str) -> None:
        if pipe is None:
            return
        try:
            for line in iter(pipe.readline, ""):
                if not line:
                    break
                self.append_log(f"{label} {line.rstrip()}")
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    def _monitor_process(self, process: subprocess.Popen[str]) -> None:
        returncode = process.wait()
        with self.lock:
            self.returncode = returncode
            self.finished_at = time.time()
        self._persist_meta()
        self._upsert_history()
        self.append_log(f"Processo finalizado com código {returncode}.")
        self._generate_auto_report_if_possible()
        self._upsert_history()

    def _generate_auto_report_if_possible(self) -> None:
        with self.lock:
            mode = self.mode or "run"
            state_dir = self.state_dir
            start_round_index = self.start_round_index
        latest_json = PROJECT_ROOT / ".mycelium_self_improve" / "latest.json"
        command = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "generate_auto_round_report.py"),
            "--mode",
            mode,
        ]
        if state_dir:
            command.extend(["--state-dir", str(state_dir), "--start-round", str(start_round_index)])
        if mode in {"self-improve", "focused"} and latest_json.exists():
            command.extend(["--report", str(latest_json)])
        try:
            result = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.stdout.strip():
                payload = json.loads(result.stdout)
                self.last_auto_report_path = payload.get("output_path")
                self.last_report_path = payload.get("report_path")
                self.append_log(f"Relatório automático gerado: {self.last_auto_report_path}")
            if result.returncode != 0:
                self.last_error = (result.stderr or result.stdout).strip() or "Falha desconhecida ao gerar relatório automático."
                self.append_log(f"Falha ao gerar relatório automático: {self.last_error}")
            self._persist_meta()
        except Exception as exc:
            self.last_error = str(exc)
            self.append_log(f"Erro ao gerar relatório automático: {exc}")
            self._persist_meta()

    def stop(self) -> dict[str, Any]:
        with self.lock:
            process = self.process
            state_dir = self.state_dir
            self.stop_requested = True
        if state_dir:
            try:
                kill_file = Path(state_dir) / "KILL"
                kill_file.parent.mkdir(parents=True, exist_ok=True)
                kill_file.write_text("stop", encoding="utf-8")
                self.append_log(f"Kill-switch criado em {kill_file}")
            except Exception as exc:
                self.append_log(f"Não foi possível criar kill-switch: {exc}")
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                self.append_log("Sinal de parada enviado ao processo.")
            except Exception as exc:
                self.append_log(f"Falha ao terminar processo: {exc}")
        self._persist_meta()
        self._upsert_history()
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            process = self.process
            running = process is not None and process.poll() is None
            pid = process.pid if process is not None else None
            elapsed = ((self.finished_at - self.started_at) if (self.started_at and self.finished_at) else (time.time() - self.started_at) if self.started_at else 0.0)
            log_text = "\n".join(self.log_lines)
            mode = self.mode
            command = self.command
            state_dir = self.state_dir
            ram_mb = self.ram_mb
            pending_ram_mb = self.pending_ram_mb
            returncode = self.returncode
            started_at = self.started_at
            finished_at = self.finished_at
            last_auto_report_path = self.last_auto_report_path
            last_report_path = self.last_report_path
            last_error = self.last_error
            start_round_index = self.start_round_index
            session_id = self.session_id
            stop_requested = self.stop_requested
            launch_payload = self.launch_payload
        status, status_label = human_history_status(running, returncode, stop_requested, finished_at)
        return {
            "session_id": session_id,
            "running": running,
            "pid": pid,
            "mode": mode,
            "mode_label": human_mode_label(mode),
            "command": command,
            "state_dir": state_dir,
            "ram_mb": ram_mb,
            "pending_ram_mb": pending_ram_mb,
            "elapsed_seconds": elapsed,
            "returncode": returncode,
            "started_at": started_at,
            "finished_at": finished_at,
            "log": log_text,
            "last_auto_report_path": last_auto_report_path,
            "last_report_path": last_report_path,
            "last_error": last_error,
            "start_round_index": start_round_index,
            "stop_requested": stop_requested,
            "status": status,
            "status_label": status_label,
            "launch_payload": launch_payload,
        }


SESSION = ProcessSession()


def build_project_tree(root: Path, max_depth: int = 3) -> str:
    lines = [root.name + "/"]

    def walk(path: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for index, entry in enumerate(entries):
            connector = "└── " if index == len(entries) - 1 else "├── "
            lines.append(prefix + connector + entry.name + ("/" if entry.is_dir() else ""))
            if entry.is_dir() and depth < max_depth:
                extension = "    " if index == len(entries) - 1 else "│   "
                walk(entry, prefix + extension, depth + 1)

    walk(root, "", 1)
    return "\n".join(lines)


def latest_auto_report_path() -> str | None:
    reports_dir = PROJECT_ROOT / "reports" / "auto"
    if not reports_dir.exists():
        return None
    files = sorted(reports_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(files[0]) if files else None


def load_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def current_runtime_summary(state_dir: str | None) -> dict[str, Any]:
    if not state_dir:
        return {}
    root = Path(state_dir)
    if not root.exists():
        return {}
    try:
        state = load_state(root, "auto")
        last_metric = state.metrics_history[-1] if state.metrics_history else None
        state_path = None
        state_mtime = None
        for candidate in (root / "state.pkl", root / "state.json"):
            if candidate.exists():
                state_path = str(candidate)
                state_mtime = candidate.stat().st_mtime
                break
        return {
            "state_dir": str(root),
            "state_path": state_path,
            "state_last_modified": state_mtime,
            "kill_switch_present": (root / "KILL").exists(),
            "round_index": state.round_index,
            "metrics_history_count": len(state.metrics_history),
            "macro_library_count": len(state.macro_library),
            "macro_staging_count": len(state.macro_staging),
            "frontier_archive_count": len(state.frontier_archive),
            "last_metric": last_metric,
            "climate": last_metric.get("climate") if last_metric else None,
            "frontier_difficulty": last_metric.get("frontier_difficulty") if last_metric else None,
            "best_score": last_metric.get("best_score") if last_metric else None,
            "best_exact_rate": last_metric.get("best_exact_rate") if last_metric else None,
            "solved_by_best": last_metric.get("solved_by_best") if last_metric else None,
            "capability_signal": last_metric.get("capability_signal") if last_metric else None,
            "best_program": last_metric.get("best_program") if last_metric else None,
            "challenge_oracles": last_metric.get("challenge_oracles") if last_metric else None,
            "active_niches": last_metric.get("active_niches") if last_metric else None,
            "diversity_entropy": last_metric.get("diversity_entropy") if last_metric else None,
            "macro_transfer_mean": last_metric.get("macro_transfer_mean") if last_metric else None,
            "frontier_learning_progress": last_metric.get("frontier_learning_progress") if last_metric else None,
            "frontier_status_counts": last_metric.get("frontier_status_counts") if last_metric else None,
        }
    except Exception as exc:
        return {"load_error": str(exc), "state_dir": str(root)}


def daemon_status_summary() -> dict[str, Any]:
    path = PROJECT_ROOT / ".mycelium_self_improve" / "daemon.status.json"
    if not path.exists():
        return {}
    try:
        payload = load_json_file(path)
        payload["path"] = str(path)
        payload["file_age_seconds"] = max(0.0, time.time() - path.stat().st_mtime)
        timestamp = payload.get("timestamp")
        if timestamp:
            try:
                ts = datetime.fromisoformat(timestamp).timestamp()
                payload["telemetry_age_seconds"] = max(0.0, time.time() - ts)
            except Exception:
                payload["telemetry_age_seconds"] = None
        else:
            payload["telemetry_age_seconds"] = None
        payload["stale"] = bool(payload.get("telemetry_age_seconds") and payload["telemetry_age_seconds"] > 120)
        return payload
    except Exception as exc:
        return {"load_error": str(exc), "path": str(path)}


def latest_error_summary() -> dict[str, Any]:
    path = PROJECT_ROOT / ".mycelium_self_improve" / "last_error.json"
    if not path.exists():
        return {}
    try:
        return load_json_file(path)
    except Exception as exc:
        return {"load_error": str(exc), "path": str(path)}


def normalized_launch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode", "run"))
    state_dir = str(payload.get("state_dir") or (PROJECT_ROOT / (".mycelium_state_ui_focused" if mode == "focused" else ".mycelium_state_ui")))
    return {
        "mode": mode,
        "rounds": int(payload.get("rounds", 100)),
        "minutes": int(payload.get("minutes", 25)),
        "hours": float(payload.get("hours", 8)),
        "guard_workers": int(payload.get("guard_workers", 4)),
        "ram_mb": payload.get("ram_mb"),
        "state_dir": state_dir,
    }


def run_command_from_payload(payload: dict[str, Any]) -> tuple[str, list[str], str]:
    mode = str(payload.get("mode", "run"))
    rounds = int(payload.get("rounds", 100))
    minutes = int(payload.get("minutes", 25))
    hours = float(payload.get("hours", 8))
    state_dir = str(payload.get("state_dir") or (PROJECT_ROOT / ".mycelium_state_ui"))
    guard_workers = int(payload.get("guard_workers", 4))
    if mode == "run":
        command = [
            sys.executable,
            "-m",
            "mycelium_accel",
            "run",
            "--seed",
            "101",
            "--state-dir",
            state_dir,
            "--rounds",
            str(rounds),
        ]
    elif mode == "self-improve":
        command = [
            sys.executable,
            "-m",
            "mycelium_accel",
            "self-improve",
            "--seed",
            "101",
            "--state-dir",
            state_dir,
            "--cycles",
            "999999",
            "--rounds-per-cycle",
            "20",
            "--time-budget-seconds",
            str(minutes * 60),
            "--guard-workers",
            str(guard_workers),
            "--project-root",
            str(PROJECT_ROOT),
        ]
    elif mode == "focused":
        command = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "focused_calibrate_new_mechanisms.py"),
            "--project-root",
            str(PROJECT_ROOT),
            "--seed",
            "101",
            "--state-dir",
            state_dir,
            "--rounds-per-cycle",
            "15",
            "--time-budget-seconds",
            str(int(hours * 3600)),
            "--benchmark-rounds",
            "30",
            "--benchmark-seeds",
            "101,103,107,109,113",
            "--guard-workers",
            str(guard_workers),
        ]
    else:
        raise ValueError("Modo desconhecido.")
    return mode, command, state_dir


def execute_command_text(command_text: str) -> dict[str, Any]:  # noqa: C901 — Q3.2: command dispatch (script, not product).
    text = command_text.strip()
    if not text:
        return {"output": "Digite um comando ou use /help."}
    if text == "/help":
        return {"output": HELP_TEXT}
    if text == "/status":
        snapshot = SESSION.snapshot()
        runtime = current_runtime_summary(snapshot.get("state_dir"))
        return {"output": json.dumps({"process": snapshot, "runtime": runtime}, indent=2, ensure_ascii=False)}
    if text == "/report":
        path = latest_auto_report_path()
        return {"output": f"Último relatório automático: {path or 'ainda não existe'}"}
    if text.startswith("/ram "):
        try:
            SESSION.pending_ram_mb = int(text.split()[1])
            SESSION._persist_meta()
            return {"output": f"RAM da próxima execução definida para {SESSION.pending_ram_mb} MB."}
        except Exception:
            return {"output": "Uso: /ram 2048"}
    if text == "/stop":
        SESSION.stop()
        return {"output": "Pedido de parada enviado."}
    if text.startswith("/run"):
        parts = text.split()
        rounds = int(parts[1]) if len(parts) > 1 else 100
        launch_payload = normalized_launch_payload({"mode": "run", "rounds": rounds, "ram_mb": SESSION.pending_ram_mb, "state_dir": str(PROJECT_ROOT / ".mycelium_state_ui")})
        mode, command, state_dir = run_command_from_payload(launch_payload)
        snapshot = SESSION.start(mode, command, state_dir, SESSION.pending_ram_mb, launch_payload=launch_payload)
        return {"output": f"Execução iniciada: {rounds} rounds.", "snapshot": snapshot}
    if text.startswith("/self-improve"):
        parts = text.split()
        minutes = int(parts[1]) if len(parts) > 1 else 25
        launch_payload = normalized_launch_payload({"mode": "self-improve", "minutes": minutes, "guard_workers": 4, "ram_mb": SESSION.pending_ram_mb, "state_dir": str(PROJECT_ROOT / ".mycelium_state_ui")})
        mode, command, state_dir = run_command_from_payload(launch_payload)
        snapshot = SESSION.start(mode, command, state_dir, SESSION.pending_ram_mb, launch_payload=launch_payload)
        return {"output": f"Auto melhoria iniciada por {minutes} minuto(s).", "snapshot": snapshot}
    if text.startswith("/focused"):
        parts = text.split()
        hours = float(parts[1]) if len(parts) > 1 else 8.0
        launch_payload = normalized_launch_payload({"mode": "focused", "hours": hours, "guard_workers": 4, "ram_mb": SESSION.pending_ram_mb, "state_dir": str(PROJECT_ROOT / ".mycelium_state_ui_focused")})
        mode, command, state_dir = run_command_from_payload(launch_payload)
        snapshot = SESSION.start(mode, command, state_dir, SESSION.pending_ram_mb, launch_payload=launch_payload)
        return {"output": f"Calibração focada iniciada por {hours} hora(s).", "snapshot": snapshot}
    return {"output": "Comando não reconhecido. Use /help para ver a lista."}


class Handler(BaseHTTPRequestHandler):
    server_version = "MyceliumUI/1.0"

    def _json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _text(self, payload: str, content_type: str = "text/plain; charset=utf-8", status: int = 200) -> None:
        data = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:  # noqa: C901 — Q3.2: route dispatch (script, not product).
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._text((UI_ROOT / "index.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/app.js":
            self._text((UI_ROOT / "app.js").read_text(encoding="utf-8"), "application/javascript; charset=utf-8")
            return
        if parsed.path == "/styles.css":
            self._text((UI_ROOT / "styles.css").read_text(encoding="utf-8"), "text/css; charset=utf-8")
            return
        if parsed.path == "/api/status":
            snapshot = SESSION.snapshot()
            self._json(
                {
                    "server_time": time.time(),
                    "session": snapshot,
                    "runtime": current_runtime_summary(snapshot.get("state_dir")),
                    "daemon_status": daemon_status_summary(),
                    "last_error": latest_error_summary(),
                    "latest_auto_report_path": latest_auto_report_path(),
                    "recent_history": SESSION.recent_history(),
                }
            )
            return
        if parsed.path == "/api/bootstrap":
            self._json(
                {
                    "project_tree": build_project_tree(PROJECT_ROOT, max_depth=3),
                    "help": HELP_TEXT,
                    "default_profile": load_default_profile(),
                    "recent_history": SESSION.recent_history(),
                }
            )
            return
        if parsed.path == "/api/help":
            self._json({"help": HELP_TEXT})
            return
        if parsed.path == "/api/file":
            query = parse_qs(parsed.query)
            raw_path = query.get("path", [""])[0]
            if not raw_path:
                self._json({"error": "missing path"}, status=400)
                return
            path = Path(raw_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            try:
                path = path.resolve()
            except Exception:
                self._json({"error": "invalid path"}, status=400)
                return
            if PROJECT_ROOT not in path.parents and path != PROJECT_ROOT and Path("/home/user") not in path.parents:
                self._json({"error": "path outside allowed roots"}, status=403)
                return
            if not path.exists() or not path.is_file():
                self._json({"error": "file not found"}, status=404)
                return
            self._json({"path": str(path), "content": path.read_text(encoding="utf-8", errors="replace")})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = self._body_json()
        try:
            if parsed.path == "/api/start":
                mode = str(payload.get("mode", "run"))
                if mode == "run":
                    state_dir = str(payload.get("state_dir") or (PROJECT_ROOT / ".mycelium_state_ui"))
                elif mode == "self-improve":
                    state_dir = str(payload.get("state_dir") or (PROJECT_ROOT / ".mycelium_state_ui"))
                else:
                    state_dir = str(payload.get("state_dir") or (PROJECT_ROOT / ".mycelium_state_ui_focused"))
                launch_payload = normalized_launch_payload({**payload, "state_dir": state_dir})
                mode, command, state_dir = run_command_from_payload(launch_payload)
                ram_mb = launch_payload.get("ram_mb", SESSION.pending_ram_mb)
                snapshot = SESSION.start(
                    mode,
                    command,
                    state_dir,
                    None if ram_mb in (None, "", "auto") else int(ram_mb),
                    launch_payload=launch_payload,
                )
                self._json({"ok": True, "session": snapshot})
                return
            if parsed.path == "/api/stop":
                self._json({"ok": True, "session": SESSION.stop()})
                return
            if parsed.path == "/api/command":
                result = execute_command_text(str(payload.get("command", "")))
                self._json({"ok": True, **result})
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            SESSION.append_log(f"Erro da interface: {exc}")
            self._json({"ok": False, "error": str(exc)}, status=500)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    host = os.environ.get("MYCELIUM_UI_HOST", DEFAULT_HOST)
    port = int(os.environ.get("MYCELIUM_UI_PORT", str(DEFAULT_PORT)))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"MYCELIUM Auto-evolve UI listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
