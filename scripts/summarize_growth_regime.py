#!/usr/bin/env python3
"""Phase 8 summary: honest growth dashboard from persisted artifacts.

Aggregates the engine's metrics history with any persisted QD archive,
transfer graph and learned library, then emits the full dashboard + regime
classification (JSON and Markdown).

    python scripts/summarize_growth_regime.py --state-dir .mycelium_state \
        [--qd .mycelium_qd/qd_experiment.json] [--transfer .mycelium_transfer/transfer_graph.json]
        [--library .mycelium_semantics/learned_library.json] [--markdown]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mycelium_accel.growth_metrics import build_dashboard, summarize_dashboard
from mycelium_accel.state import load_state
from mycelium_accel.telemetry import full_history


def _load_json(path: str | None, *, state_dir: str | None = None, strict: bool = False) -> dict | None:
    import sys as _sys

    from mycelium_accel.telemetry import check_provenance

    if not path:
        return None
    candidate = Path(path)
    if not candidate.exists():
        return None
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    ok, reason = check_provenance(payload, state_dir)
    if not ok:
        _sys.stderr.write(f"warning: {path}: {reason}\n")
        if strict:
            return None
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="MYCELIUM Auto-evolve open-ended growth summary")
    parser.add_argument("--state-dir", default=".mycelium_state")
    parser.add_argument("--qd", default=".mycelium_qd/qd_experiment.json")
    parser.add_argument("--transfer", default=".mycelium_transfer/transfer_graph.json")
    parser.add_argument("--library", default=".mycelium_semantics/learned_library.json")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="ignore ambient artifacts from other runs (provenance-checked)")
    parser.add_argument("--out", default=".mycelium_transfer/growth_summary.json")
    args = parser.parse_args()

    state = load_state(Path(args.state_dir))
    history = full_history(state.metrics_history, args.state_dir)

    qd_payload = _load_json(args.qd, state_dir=args.state_dir, strict=args.strict) or {}
    transfer_payload = _load_json(args.transfer, state_dir=args.state_dir, strict=args.strict) or {}
    library_payload = _load_json(args.library, state_dir=args.state_dir, strict=args.strict) or {}

    reuse_stats = library_payload.get("reuse_stats", {})
    transfer_stats = {
        "donor_scores": transfer_payload.get("donor_scores", {}),
        "useful_edges": transfer_payload.get("useful_edges", 0),
        "expansion_rate": transfer_payload.get("expansion_rate", 0.0),
    }

    dashboard = build_dashboard(
        history,
        qd_coverage=float(qd_payload.get("final_coverage", 0.0)),
        qd_score=float(qd_payload.get("final_qd_score", 0.0)),
        qd_auc=float(qd_payload.get("final_qd_auc", 0.0)),
        abstractions_learned=int(len(library_payload.get("abstractions", []))),
        mean_abstraction_reuse=float(reuse_stats.get("mean_support", 0.0)),
        transfer_stats=transfer_stats,
    )
    payload = dashboard.to_dict()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.markdown:
        print(summarize_dashboard(dashboard))
    else:
        print(json.dumps(payload, indent=2))
    print(f"saved -> {out_path}")


if __name__ == "__main__":
    main()
