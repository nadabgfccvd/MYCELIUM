"""Open-ended growth metrics + regime classification (Roadmap Phase 8).

A single ``capability_signal`` curve cannot tell *accumulation of leverage*
from *spinning in place*. This module computes the full dashboard the
roadmap demands and classifies the system's growth into one of five honest
regimes:

* ``local_stagnation``
* ``exploration_without_accumulation``
* ``compression_growth``
* ``transfer_growth``
* ``open_ended_compound``
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from collections.abc import Sequence

REGIMES = (
    "local_stagnation",
    "exploration_without_accumulation",
    "compression_growth",
    "transfer_growth",
    "open_ended_compound",
)


@dataclass(slots=True)
class GrowthDashboard:
    coverage: float = 0.0
    qd_score: float = 0.0
    qd_auc: float = 0.0
    abstractions_per_1000_rounds: float = 0.0
    mean_abstraction_reuse: float = 0.0
    mean_cross_niche_transfer_gain: float = 0.0
    effective_compositional_depth: float = 0.0
    frontier_solve_time: float = 0.0
    skill_half_life: float = 0.0
    regression_rate: float = 0.0
    graph_expansion_rate: float = 0.0
    cumulative_slope: float = 0.0
    cumulative_curvature: float = 0.0
    points: int = 0
    regime: str = "local_stagnation"
    regime_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _slope(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return 0.0
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values)) / var_x


def _curvature(values: Sequence[float]) -> float:
    if len(values) < 3:
        return 0.0
    d1 = [values[i + 1] - values[i] for i in range(len(values) - 1)]
    d2 = [d1[i + 1] - d1[i] for i in range(len(d1) - 1)]
    return sum(d2) / len(d2) if d2 else 0.0


def skill_half_life(values: Sequence[float], window: int = 12) -> float:
    """Rounds until a windowed mean capability halves relative to its peak.

    0.0 means "skills never decayed below half of peak within the horizon" —
    the good case. Values < 0 mean the metric never even reached a peak.
    """
    if len(values) < window * 2:
        return 0.0
    windows = [
        sum(values[i : i + window]) / window
        for i in range(0, len(values) - window + 1)
    ]
    peak_index = max(range(len(windows)), key=lambda i: windows[i])
    peak = windows[peak_index]
    if peak <= 0:
        return -1.0
    for later in range(peak_index + 1, len(windows)):
        if windows[later] <= peak / 2:
            return float(later - peak_index)
    return 0.0


def regression_rate(values: Sequence[float], tolerance: float = 1e-9) -> float:
    """Fraction of consecutive steps that regress (anti-forgetting signal)."""
    if len(values) < 2:
        return 0.0
    drops = sum(1 for a, b in zip(values, values[1:]) if b < a - tolerance)
    return drops / (len(values) - 1)


def frontier_solve_time(history: Sequence[dict[str, Any]]) -> float:
    """Mean rounds between difficulty frontier promotions (lower = faster)."""
    difficulties = [float(m.get("frontier_difficulty", 0.0)) for m in history]
    promotions = 0
    for a, b in zip(difficulties, difficulties[1:]):
        if b > a:
            promotions += 1
    if promotions == 0:
        return float(len(history)) if history else 0.0
    return len(history) / promotions


def effective_compositional_depth(history: Sequence[dict[str, Any]]) -> float:
    """How deep programs get *while still winning* (mean champion depth proxy:
    node count of best program renders + macro usage chain depth)."""
    depths: list[float] = []
    for metric in history:
        render = str(metric.get("best_program", ""))
        if not render:
            continue
        depth = 0
        cursor = 0
        for ch in render:
            if ch == "(":
                cursor += 1
                depth = max(depth, cursor)
            elif ch == ")":
                cursor = max(0, cursor - 1)
        depths.append(float(depth))
    return sum(depths) / len(depths) if depths else 0.0


def classification_inputs_ok(dashboard: GrowthDashboard) -> bool:
    return dashboard.points >= 10


def classify_growth(dashboard: GrowthDashboard) -> GrowthDashboard:
    """Assign the honest regime label from the dashboard signals."""
    reasons: list[str] = []
    if not classification_inputs_ok(dashboard):
        dashboard.regime = "local_stagnation"
        dashboard.regime_reasons = [f"insufficient history ({dashboard.points} points)"]
        return dashboard

    accumulating = dashboard.qd_auc > 0 and dashboard.cumulative_slope > 0
    via_compression = dashboard.mean_abstraction_reuse >= 2.0 and dashboard.abstractions_per_1000_rounds > 0.0
    via_transfer = dashboard.mean_cross_niche_transfer_gain > 0.0 and dashboard.graph_expansion_rate > 0.0
    sustained_coverage = dashboard.coverage > 0.05 and dashboard.qd_score > 0.0
    compound_curvature = dashboard.cumulative_curvature > 0 and dashboard.cumulative_slope > 0

    if sustained_coverage and via_compression and via_transfer and compound_curvature and dashboard.regression_rate < 0.5:
        dashboard.regime = "open_ended_compound"
        reasons.append("coverage + compression reuse + transfer + positive curvature simultaneously")
    elif via_transfer and accumulating:
        dashboard.regime = "transfer_growth"
        reasons.append("growth present and driven by cross-niche transfer")
    elif via_compression and accumulating:
        dashboard.regime = "compression_growth"
        reasons.append("growth present and driven by abstraction/reuse")
    elif sustained_coverage and not accumulating:
        dashboard.regime = "exploration_without_accumulation"
        reasons.append("archive grows but cumulative metrics do not")
    else:
        dashboard.regime = "local_stagnation"
        reasons.append("no sustained coverage, compression, or transfer signals")

    if dashboard.skill_half_life > 0:
        reasons.append(f"warning: skills decay with half-life {dashboard.skill_half_life:.0f} windows")
    if dashboard.regression_rate >= 0.5:
        reasons.append("warning: majority of rounds regress — anti-forgetting pressure needed")
    dashboard.regime_reasons = reasons
    return dashboard


def build_dashboard(
    history: Sequence[dict[str, Any]],
    *,
    qd_coverage: float = 0.0,
    qd_score: float = 0.0,
    qd_auc: float = 0.0,
    abstractions_learned: int = 0,
    mean_abstraction_reuse: float = 0.0,
    transfer_stats: dict[str, Any] | None = None,
    window: int = 64,
) -> GrowthDashboard:
    """Assemble the dashboard from engine history + optional QD/transfer/lib data."""
    capability = [float(m.get("capability_signal", 0.0)) for m in history]
    macro_counts = [float(m.get("macro_count", 0.0)) for m in history]
    recent_capability = capability[-window:] if len(capability) > window else capability

    dashboard = GrowthDashboard(
        coverage=qd_coverage,
        qd_score=qd_score,
        qd_auc=qd_auc,
        points=len(history),
        cumulative_slope=_slope(recent_capability),
        cumulative_curvature=_curvature(recent_capability),
        frontier_solve_time=frontier_solve_time(history),
        skill_half_life=skill_half_life(capability),
        regression_rate=regression_rate(capability),
        effective_compositional_depth=effective_compositional_depth(history),
    )
    rounds = max(1, len(history))
    dashboard.abstractions_per_1000_rounds = abstractions_learned / rounds * 1000.0
    dashboard.mean_abstraction_reuse = mean_abstraction_reuse

    if transfer_stats:
        donors = transfer_stats.get("donor_scores", {})
        useful = transfer_stats.get("useful_edges", 0)
        dashboard.graph_expansion_rate = float(transfer_stats.get("expansion_rate", 0.0))
        gains = [float(v) for v in donors.values() if float(v) > 0]
        dashboard.mean_cross_niche_transfer_gain = sum(gains) / len(gains) if gains else 0.0
        if useful == 0 and dashboard.graph_expansion_rate == 0.0:
            dashboard.mean_cross_niche_transfer_gain = 0.0

    # reuse signal fallback: macro count growth implies reuse accumulation
    if dashboard.mean_abstraction_reuse == 0.0 and len(macro_counts) >= 2:
        dashboard.mean_abstraction_reuse = macro_counts[-1] / max(1.0, macro_counts[0] + 1.0)

    return classify_growth(dashboard)


def summarize_dashboard(dashboard: GrowthDashboard) -> str:
    lines = [
        "# Growth regime summary",
        "",
        f"Regime: **{dashboard.regime}** ({dashboard.points} rounds)",
        "",
        "| metric | value |",
        "|---|---|",
        f"| coverage | {dashboard.coverage:.3f} |",
        f"| qd_score | {dashboard.qd_score:.3g} |",
        f"| qd_auc | {dashboard.qd_auc:.3g} |",
        f"| abstractions / 1000 rounds | {dashboard.abstractions_per_1000_rounds:.2f} |",
        f"| mean abstraction reuse | {dashboard.mean_abstraction_reuse:.2f} |",
        f"| mean cross-niche transfer gain | {dashboard.mean_cross_niche_transfer_gain:.4g} |",
        f"| effective compositional depth | {dashboard.effective_compositional_depth:.2f} |",
        f"| frontier solve time (rounds/promotion) | {dashboard.frontier_solve_time:.2f} |",
        f"| skill half-life (windows, 0=none) | {dashboard.skill_half_life:.0f} |",
        f"| regression rate | {dashboard.regression_rate:.3f} |",
        f"| transfer graph expansion rate | {dashboard.graph_expansion_rate:.3f} |",
        f"| cumulative slope | {dashboard.cumulative_slope:.4g} |",
        f"| cumulative curvature | {dashboard.cumulative_curvature:.4g} |",
        "",
        "## Verdict",
    ]
    for reason in dashboard.regime_reasons:
        lines.append(f"- {reason}")
    return "\n".join(lines) + "\n"
