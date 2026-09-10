"""Static single-file HTML reports (Fase 3.2).

Renders a ``BenchmarkSweep`` dict as one self-contained ``.html`` file:
inline CSS + inline SVG bar chart (mean ± 1 stddev, HONESTLY LABELED —
confidence intervals live in the table, never in the whiskers). No network,
no JS, opens with a double-click.
"""
from __future__ import annotations

import html
import math
from typing import Any

_CSS = """
.flaky{color:#9a5b00;font-weight:bold;font-size:11px;border:1px solid #9a5b00;padding:0 4px;border-radius:3px;}
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
h1{font-size:1.4rem}h2{font-size:1.1rem;margin-top:2rem}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{border:1px solid #ccc;padding:.35rem .5rem;text-align:right}
th:first-child,td:first-child{text-align:left}
th{background:#f4f4f4}
.meta{color:#555;font-size:.9rem}
.win{background:#e8f5e9}
.chart{background:#fafafa;border:1px solid #ddd}
.note{font-size:.8rem;color:#666}
"""


def _svg_bars(summaries: list[dict[str, Any]], lower_is_better: bool) -> str:
    rows = [s for s in summaries if math.isfinite(s.get("mean", float("nan")))]
    if not rows:
        return "<p>No finite means to chart.</p>"
    rows.sort(key=lambda s: s["mean"], reverse=not lower_is_better)
    width, bar_h, gap, label_w = 640, 26, 10, 180
    max_v = max(s["mean"] + s.get("stddev", 0.0) for s in rows) or 1.0
    height = len(rows) * (bar_h + gap) + 30
    parts = [f'<svg class="chart" width="{width + label_w + 20}" height="{height}" role="img">']
    for i, s in enumerate(rows):
        y = 10 + i * (bar_h + gap)
        mean, sd = s["mean"], s.get("stddev", 0.0) or 0.0
        bar_w = max(2.0, mean / max_v * width)
        sd_w = sd / max_v * width
        name = html.escape(str(s.get("candidate", "?")))
        parts.append(f'<text x="0" y="{y + 18}" font-size="13">{name}</text>')
        parts.append(f'<rect x="{label_w}" y="{y}" width="{bar_w:.1f}" height="{bar_h}" fill="#4a90d9"/>')
        x0, x1 = label_w + bar_w - sd_w, label_w + bar_w + sd_w
        parts.append(
            f'<line x1="{x0:.1f}" y1="{y + bar_h / 2}" x2="{x1:.1f}" y2="{y + bar_h / 2}" stroke="#222" stroke-width="2"/>'
        )
        parts.append(f'<text x="{label_w + bar_w + sd_w + 6:.1f}" y="{y + 18}" font-size="12">{mean:.4g}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def html_from_sweep(sweep: dict[str, Any], *, verdict: str = "") -> str:
    """Render loop-free HTML from ``BenchmarkSweep.to_dict()`` output."""
    target = html.escape(str(sweep.get("target", "?")))
    metric = html.escape(str(sweep.get("metric", "?")))
    direction = "lower is better" if sweep.get("lower_is_better") else "higher is better"
    summaries = list(sweep.get("summaries", []))
    comparisons = list(sweep.get("comparisons", []))

    rows_html = []
    for s in sorted(summaries, key=lambda x: (not math.isfinite(x.get("mean", float("inf"))), x.get("mean", 0))):
        rows_html.append(
            "<tr><td>{}{}</td><td>{:.6g}</td><td>{:.3g}</td><td>{:.6g}</td>"
            "<td>{:.6g}</td><td>{:.6g}</td><td>{}</td></tr>".format(
                html.escape(str(s.get("candidate", "?"))),
                ' <span class="flaky">FLAKY</span>' if s.get("flaky") else "",
                s.get("mean", float("nan")), s.get("stddev", float("nan")),
                s.get("median", float("nan")), s.get("minimum", float("nan")),
                s.get("maximum", float("nan")), len(s.get("runs", [])),
            )
        )
    comp_html = []
    for c in comparisons:
        corr = c.get("p_value_corrected")
        corr_s = f"{corr:.4f}" if isinstance(corr, float) else "—"
        sig = isinstance(corr, float) and corr <= 0.05 and c.get("ci_low", 0) > 0
        comp_html.append(
            '<tr class="{}"><td>{}</td><td>{:+.6g}</td><td>{:+.6g}</td><td>{:+.6g}</td>'
            "<td>{:.4f}</td><td>{}</td><td>{:.3f}</td></tr>".format(
                "win" if sig else "", html.escape(str(c.get("candidate", "?"))),
                c.get("mean_delta", 0), c.get("ci_low", 0), c.get("ci_high", 0),
                c.get("p_value", 1.0), corr_s, c.get("effect_dz", 0.0),
            )
        )
    verdict_html = f"<p><strong>Verdict:</strong> {html.escape(verdict)}</p>" if verdict else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Benchmark sweep — {target}</title>
<style>{_CSS}</style></head>
<body>
<h1>Benchmark sweep</h1>
<p class="meta">target: <code>{target}</code> · metric: <code>{metric}</code> ({direction})</p>
{verdict_html}
<h2>Means (whiskers = ±1 stddev, NOT confidence intervals)</h2>
{_svg_bars(summaries, bool(sweep.get("lower_is_better")))}
<h2>Summary</h2>
<table><tr><th>candidate</th><th>mean</th><th>stddev</th><th>median</th><th>min</th><th>max</th><th>runs</th></tr>
{"".join(rows_html)}</table>
<h2>Paired comparisons (per-seed deltas, BCa CI + corrected p)</h2>
<table><tr><th>candidate</th><th>mean Δ</th><th>CI low</th><th>CI high</th><th>p</th><th>p (corr)</th><th>dz</th></tr>
{"".join(comp_html)}</table>
<p class="note">Green rows: CI excludes 0 with corrected p ≤ 0.05. Generated by mycelium-accel (stdlib-only, offline).</p>
</body></html>
"""
