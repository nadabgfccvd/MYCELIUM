from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mycelium_accel.state import load_state

SELF_IMPROVE_METRICS = [
    "rounds_per_second_mean",
    "best_score_mean",
    "best_exact_rate_mean",
    "solved_by_best_mean",
    "capability_signal_mean",
    "frontier_difficulty_mean",
    "active_niches_mean",
    "diversity_entropy_mean",
    "macro_transfer_mean",
    "frontier_learning_progress_mean",
]

STATE_METRICS = [
    "best_score",
    "best_exact_rate",
    "solved_by_best",
    "capability_signal",
    "frontier_difficulty",
    "active_niches",
    "diversity_entropy",
    "macro_transfer_mean",
    "frontier_learning_progress",
]


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_self_improve(report: dict[str, Any]) -> dict[str, Any]:
    cycles = report.get("cycles", [])
    accepted = [cycle for cycle in cycles if cycle.get("applied")]
    rejected = [cycle for cycle in cycles if not cycle.get("applied")]
    changed_keys = Counter()
    metric_improvements = Counter()
    metric_regressions = Counter()
    accepted_rows = []

    for cycle in accepted:
        baseline = cycle["baseline"]
        candidate = cycle["candidate"] or {}
        base_profile = baseline.get("profile", {})
        cand_profile = candidate.get("profile", {})
        diff = {k: (base_profile.get(k), cand_profile.get(k)) for k in cand_profile if base_profile.get(k) != cand_profile.get(k)}
        for key in diff:
            changed_keys[key] += 1
        metric_deltas = {}
        for metric in SELF_IMPROVE_METRICS:
            if metric in baseline and metric in candidate:
                delta = float(candidate[metric]) - float(baseline[metric])
                metric_deltas[metric] = delta
                if delta > 0:
                    metric_improvements[metric] += 1
                elif delta < 0:
                    metric_regressions[metric] += 1
        accepted_rows.append(
            {
                "cycle": cycle["cycle_index"],
                "changed_keys": diff,
                "metric_deltas": metric_deltas,
                "guard_reasons": cycle.get("guard", {}).get("reasons", []),
            }
        )

    return {
        "cycle_count": len(cycles),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "changed_keys": changed_keys,
        "metric_improvements": metric_improvements,
        "metric_regressions": metric_regressions,
        "accepted_rows": accepted_rows,
        "latest_profile": report.get("default_profile", {}),
        "active_variant": report.get("active_variant"),
        "timestamp": report.get("timestamp"),
    }


def metric_window_from_state(state_dir: Path, start_round: int) -> dict[str, Any]:  # noqa: C901 — Q3.2: report shaping (script, not product).
    state = load_state(state_dir, "auto")
    history = list(state.metrics_history)

    previous = None
    for metric in history:
        if int(metric.get("round", 0)) <= start_round:
            previous = metric
        else:
            break

    window = [metric for metric in history if int(metric.get("round", 0)) > start_round]
    final_metric = window[-1] if window else previous

    improvement_counts = Counter()
    regression_counts = Counter()
    changed_metrics: dict[str, dict[str, float | int | None]] = {}

    comparisons: list[tuple[dict[str, Any], dict[str, Any]]] = []
    if window:
        if previous is not None:
            comparisons.append((previous, window[0]))
        comparisons.extend((window[index - 1], window[index]) for index in range(1, len(window)))

    for before, after in comparisons:
        for metric in STATE_METRICS:
            before_value = before.get(metric)
            after_value = after.get(metric)
            if before_value is None or after_value is None:
                continue
            delta = float(after_value) - float(before_value)
            if delta > 0:
                improvement_counts[metric] += 1
            elif delta < 0:
                regression_counts[metric] += 1

    baseline_metric = previous if previous is not None else (window[0] if len(window) >= 2 else None)
    if baseline_metric is not None and final_metric is not None:
        for metric in STATE_METRICS:
            before_value = baseline_metric.get(metric)
            after_value = final_metric.get(metric)
            if before_value is None or after_value is None:
                continue
            delta = float(after_value) - float(before_value)
            if delta == 0:
                continue
            changed_metrics[metric] = {
                "before": before_value,
                "after": after_value,
                "delta": delta,
            }

    return {
        "state_dir": str(state_dir),
        "start_round": start_round,
        "end_round": state.round_index,
        "rounds_executed": max(0, state.round_index - start_round),
        "window_count": len(window),
        "macro_library_count": len(state.macro_library),
        "macro_staging_count": len(state.macro_staging),
        "frontier_archive_count": len(state.frontier_archive),
        "improvement_counts": improvement_counts,
        "regression_counts": regression_counts,
        "changed_metrics": changed_metrics,
        "last_metric": final_metric,
    }


def to_markdown(  # noqa: C901 — Q3.2: report templating (script, not product).
    *,
    report_path: Path | None,
    self_improve_summary: dict[str, Any] | None,
    state_summary: dict[str, Any] | None,
    mode: str,
) -> str:
    lines: list[str] = []
    lines.append("# Relatório automático da rodada MYCELIUM Auto-evolve")
    lines.append("")
    lines.append(f"Modo: **{mode}**")
    if report_path is not None:
        lines.append(f"Origem do relatório de auto melhoria: `{report_path}`")
    if state_summary is not None:
        lines.append(f"Origem do estado: `{state_summary['state_dir']}`")
    lines.append(f"Gerado em: `{datetime.now(UTC).isoformat()}`")
    lines.append("")

    if state_summary is not None:
        lines.append("## Resumo do trecho executado")
        lines.append("")
        lines.append(f"- rounds executados nesta sessão: **{state_summary['rounds_executed']}**")
        lines.append(f"- round inicial observado: **{state_summary['start_round']}**")
        lines.append(f"- round final observado: **{state_summary['end_round']}**")
        lines.append(f"- macros globais no final: **{state_summary['macro_library_count']}**")
        lines.append(f"- macros em staging no final: **{state_summary['macro_staging_count']}**")
        lines.append(f"- itens no frontier archive no final: **{state_summary['frontier_archive_count']}**")
        lines.append("")
        lines.append("## Métricas que mudaram no trecho")
        lines.append("")
        if state_summary["changed_metrics"]:
            for metric, payload in state_summary["changed_metrics"].items():
                delta = float(payload["delta"])
                sign = "+" if delta >= 0 else ""
                lines.append(f"- `{metric}`: `{payload['before']}` -> `{payload['after']}` (**{sign}{delta:.6f}**)" )
        else:
            lines.append("- Nenhuma mudança mensurável em relação ao ponto inicial observado.")
        lines.append("")
        lines.append("## Quantas vezes cada métrica melhorou durante o trecho")
        lines.append("")
        if state_summary["improvement_counts"] or state_summary["regression_counts"]:
            for metric in STATE_METRICS:
                improved = state_summary["improvement_counts"].get(metric, 0)
                regressed = state_summary["regression_counts"].get(metric, 0)
                if improved or regressed:
                    lines.append(f"- `{metric}`: melhorou **{improved}** vez(es), piorou **{regressed}** vez(es)")
        else:
            lines.append("- Não houve dados suficientes para contar melhorias rodada a rodada.")
        lines.append("")
        if state_summary.get("last_metric"):
            lines.append("## Última métrica observada")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(state_summary["last_metric"], indent=2, ensure_ascii=False))
            lines.append("```")
            lines.append("")

    if self_improve_summary is not None:
        lines.append("## Resumo do guarda de auto melhoria")
        lines.append("")
        lines.append(f"- ciclos totais: **{self_improve_summary['cycle_count']}**")
        lines.append(f"- ciclos aprovados: **{self_improve_summary['accepted_count']}**")
        lines.append(f"- ciclos rejeitados: **{self_improve_summary['rejected_count']}**")
        lines.append(f"- variante ativa final: **{self_improve_summary['active_variant']}**")
        lines.append("")
        lines.append("## Quantas vezes cada configuração mudou")
        lines.append("")
        if self_improve_summary["changed_keys"]:
            for key, count in self_improve_summary["changed_keys"].most_common():
                lines.append(f"- `{key}`: **{count}** vez(es)")
        else:
            lines.append("- Nenhuma mudança aprovada.")
        lines.append("")
        lines.append("## Quantas vezes cada métrica do guarda melhorou")
        lines.append("")
        if self_improve_summary["metric_improvements"]:
            for key in SELF_IMPROVE_METRICS:
                if key in self_improve_summary["metric_improvements"] or key in self_improve_summary["metric_regressions"]:
                    lines.append(
                        f"- `{key}`: melhorou **{self_improve_summary['metric_improvements'].get(key, 0)}** vez(es), piorou **{self_improve_summary['metric_regressions'].get(key, 0)}** vez(es)"
                    )
        else:
            lines.append("- Nenhuma melhoria aprovada para contar.")
        lines.append("")
        lines.append("## Aprovações por ciclo")
        lines.append("")
        if self_improve_summary["accepted_rows"]:
            for row in self_improve_summary["accepted_rows"]:
                lines.append(f"### Ciclo {row['cycle']}")
                lines.append("")
                lines.append("Mudanças de configuração:")
                lines.append("")
                for key, (before, after) in row["changed_keys"].items():
                    lines.append(f"- `{key}`: `{before}` -> `{after}`")
                lines.append("")
                lines.append("Mudanças nas métricas:")
                lines.append("")
                for metric, delta in row["metric_deltas"].items():
                    sign = "+" if delta >= 0 else ""
                    lines.append(f"- `{metric}`: **{sign}{delta:.6f}**")
                lines.append("")
        else:
            lines.append("Nenhum ciclo foi aprovado.")
            lines.append("")
        lines.append("## Perfil final")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(self_improve_summary["latest_profile"], indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an automatic readable round report from MYCELIUM Auto-evolve output")
    parser.add_argument("--report", default=None)
    parser.add_argument("--state-dir", default=None)
    parser.add_argument("--start-round", type=int, default=0)
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "reports" / "auto"))
    parser.add_argument("--mode", default="run")
    args = parser.parse_args()

    report_path = Path(args.report).resolve() if args.report else None
    state_dir = Path(args.state_dir).resolve() if args.state_dir else None
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    self_improve_summary = None
    if report_path is not None and report_path.exists():
        self_improve_summary = summarize_self_improve(load_report(report_path))

    state_summary = None
    if state_dir is not None and state_dir.exists():
        state_summary = metric_window_from_state(state_dir, args.start_round)

    if self_improve_summary is None and state_summary is None:
        raise SystemExit("No usable report or state directory was found.")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"mycelium-round-report-{timestamp}.md"
    output_path.write_text(
        to_markdown(
            report_path=report_path if self_improve_summary is not None else None,
            self_improve_summary=self_improve_summary,
            state_summary=state_summary,
            mode=str(args.mode),
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "report_path": str(report_path) if report_path is not None else None,
                "state_dir": str(state_dir) if state_dir is not None else None,
                "output_path": str(output_path),
                "mode": args.mode,
                "start_round": args.start_round,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
