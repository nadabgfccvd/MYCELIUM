"""Explicit cross-niche transfer graph (Roadmap Phase 6/8).

Every time a solution/abstraction from niche A improves a candidate in
niche B, an edge A→B gains weight. The graph answers: which niches are
productive donors, which transfers actually pay for themselves, and whether
the ecology is accumulating *routes* of improvement instead of isolated
points.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TransferEdge:
    source_niche: str
    target_niche: str
    count: int = 0
    total_gain: float = 0.0
    total_cost: float = 0.0
    last_round: int = 0

    @property
    def mean_gain(self) -> float:
        return self.total_gain / self.count if self.count else 0.0

    @property
    def net_value(self) -> float:
        return self.total_gain - self.total_cost

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mean_gain"] = self.mean_gain
        payload["net_value"] = self.net_value
        return payload


@dataclass
class TransferGraph:
    edges: dict[tuple[str, str], TransferEdge] = field(default_factory=dict)
    rounds: int = 0

    def record(
        self,
        source_niche: str,
        target_niche: str,
        *,
        gain: float,
        cost: float = 0.0,
        round_index: int = 0,
    ) -> TransferEdge:
        key = (source_niche, target_niche)
        edge = self.edges.get(key)
        if edge is None:
            edge = TransferEdge(source_niche=source_niche, target_niche=target_niche)
            self.edges[key] = edge
        edge.count += 1
        edge.total_gain += gain
        edge.total_cost += cost
        edge.last_round = round_index
        self.rounds = max(self.rounds, round_index)
        return edge

    def useful_edges(self, min_mean_gain: float = 0.01, min_count: int = 1) -> list[TransferEdge]:
        ranked = [
            edge
            for edge in self.edges.values()
            if edge.count >= min_count and edge.mean_gain >= min_mean_gain
        ]
        ranked.sort(key=lambda edge: (-edge.net_value, -edge.count))
        return ranked

    def donor_scores(self) -> dict[str, float]:
        donors: dict[str, float] = {}
        for edge in self.edges.values():
            donors[edge.source_niche] = donors.get(edge.source_niche, 0.0) + edge.net_value
        return donors

    def expansion_rate(self, window_rounds: int = 50) -> float:
        """New useful edges per round over the recent window — a Phase-8 metric."""
        if self.rounds == 0:
            return 0.0
        cutoff = max(0, self.rounds - window_rounds)
        recent = [edge for edge in self.useful_edges() if edge.last_round >= cutoff]
        span = min(window_rounds, max(1, self.rounds))
        return len(recent) / span

    def to_dict(self) -> dict[str, Any]:
        return {
            "edges": [edge.to_dict() for edge in self.edges.values()],
            "rounds": self.rounds,
            "useful_edges": len(self.useful_edges()),
            "donor_scores": self.donor_scores(),
            "expansion_rate": self.expansion_rate(),
        }

    def persist(self, path: Path, *, state_dir: str | Path | None = None) -> Path:
        from .telemetry import stamp_provenance

        payload = stamp_provenance(self.to_dict(), "transfer_graph.persist", state_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> TransferGraph:
        graph = cls()
        if not path.exists():
            return graph
        payload = json.loads(path.read_text(encoding="utf-8"))
        graph.rounds = int(payload.get("rounds", 0))
        for edge_payload in payload.get("edges", []):
            edge = TransferEdge(
                source_niche=edge_payload["source_niche"],
                target_niche=edge_payload["target_niche"],
                count=int(edge_payload.get("count", 0)),
                total_gain=float(edge_payload.get("total_gain", 0.0)),
                total_cost=float(edge_payload.get("total_cost", 0.0)),
                last_round=int(edge_payload.get("last_round", 0)),
            )
            graph.edges[(edge.source_niche, edge.target_niche)] = edge
        return graph
