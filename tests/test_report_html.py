"""Fase 3.2: static HTML report — offline-safe, honest whiskers, verdict shown."""
from __future__ import annotations

import unittest

from mycelium_accel.report_html import html_from_sweep

SWEEP = {
    "target": "/tmp/demo",
    "metric": "seconds",
    "lower_is_better": True,
    "summaries": [
        {"candidate": "baseline", "mean": 1.0, "stddev": 0.1, "median": 1.0,
         "minimum": 0.9, "maximum": 1.1, "runs": [{}, {}, {}]},
        {"candidate": "fast", "mean": 0.5, "stddev": 0.05, "median": 0.5,
         "minimum": 0.45, "maximum": 0.55, "runs": [{}, {}, {}]},
    ],
    "comparisons": [
        {"candidate": "fast", "mean_delta": 0.5, "ci_low": 0.4, "ci_high": 0.6,
         "p_value": 0.0078, "p_value_corrected": 0.0156, "effect_dz": 3.1},
    ],
}


class ReportHtmlTests(unittest.TestCase):
    def test_offline_safe_with_chart_and_verdict(self) -> None:
        doc = html_from_sweep(SWEEP, verdict="fast accepted")
        self.assertIn("<svg", doc)
        self.assertIn("fast accepted", doc)
        self.assertIn("NOT confidence intervals", doc)
        for banned in ("http://", "https://", "<script", "@import"):
            self.assertNotIn(banned, doc)

    def test_empty_sweep_does_not_crash(self) -> None:
        doc = html_from_sweep({"target": "x", "metric": "s", "summaries": [], "comparisons": []})
        self.assertIn("No finite means", doc)

    def test_dark_mode_print_and_captions(self) -> None:
        doc = html_from_sweep(SWEEP, verdict="fast accepted")
        self.assertIn("@media (prefers-color-scheme:dark)", doc)
        self.assertIn("@media print", doc)
        self.assertEqual(doc.count("<caption>"), 2)
        self.assertIn('scope="col"', doc)
        for banned in ("http://", "https://", "<script", "@import"):
            self.assertNotIn(banned, doc)


if __name__ == "__main__":
    unittest.main()
