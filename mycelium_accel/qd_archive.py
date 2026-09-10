"""Quality-Diversity archive + local competition + emitters (Roadmap Phase 6).

Replaces "one champion + linear frontier" with a *repertoire*: many
high-quality, behaviorally distinct stepping stones kept alive in parallel.

Descriptor design: program behavior is projected into a low-dimensional
descriptor (mean level, slope, curvature, parity fingerprint, node cost).
Cells hold a small number of elites; insertion competes on quality inside
the cell. For descriptor spaces where fixed grids are awkward, the
``LocalCompetitionArchive`` implements Dominated-Novelty-Search-style
competition: an entry survives if it is not dominated by its nearest
behavioral neighbors.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any
from collections.abc import Sequence

from .dsl import Node


@dataclass(slots=True)
class QDEntry:
    key: str
    signature: tuple[int, ...]
    descriptor: tuple[int, ...]
    quality: float
    cost_nodes: int
    origin: str = "seed"
    generation: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["signature"] = list(self.signature)
        payload["descriptor"] = list(self.descriptor)
        return payload


def descriptor_from_signature(
    signature: Sequence[int],
    *,
    node_count: int,
    cost_bins: int = 4,
    scale_bins: int = 5,
) -> tuple[int, ...]:
    """Project a behavior signature into a small discrete descriptor."""
    if not signature:
        return (0,)
    mean_val = sum(signature) / len(signature)
    diffs = [signature[i + 1] - signature[i] for i in range(len(signature) - 1)]
    slope = sum(diffs) / len(diffs) if diffs else 0.0
    curv = 0.0
    if len(diffs) > 1:
        d2 = [diffs[i + 1] - diffs[i] for i in range(len(diffs) - 1)]
        curv = sum(d2) / len(d2)
    parity = sum(1 for value in signature if value % 2 == 0) / len(signature)

    def _bin(value: float, edges: Sequence[float]) -> int:
        for index, edge in enumerate(edges):
            if value <= edge:
                return index
        return len(edges)

    mean_bin = _bin(mean_val, (-100, -10, 0, 10, 100))
    slope_bin = _bin(slope, (-50, -5, 0, 5, 50))
    curv_bin = _bin(curv, (-100, -1, 1, 100))
    parity_bin = _bin(parity, (0.25, 0.5, 0.75))
    cost_bin = _bin(node_count, (4, 8, 16, 32))
    return (mean_bin, slope_bin, curv_bin, parity_bin, cost_bin)


@dataclass(slots=True)
class QDArchiveSnapshot:
    generation: int
    coverage: float
    qd_score: float
    qd_auc: float
    cells: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QDArchive:
    """Grid archive with multi-occupant cells and quality competition."""

    cells_capacity: int = 256
    occupants_per_cell: int = 2
    generations: int = 0
    total_insertions: int = 0
    best_ever_quality: float = float("-inf")
    grid: dict[tuple[int, ...], list[QDEntry]] = field(default_factory=dict)
    history: list[QDArchiveSnapshot] = field(default_factory=list)
    _potential_cells: int = 512  # virtual lattice size for coverage fraction

    def insert(self, entry: QDEntry) -> bool:
        cell = entry.descriptor
        occupants = self.grid.setdefault(cell, [])
        for index, existing in enumerate(occupants):
            if existing.key == entry.key or existing.signature == entry.signature:
                if entry.quality > existing.quality:
                    occupants[index] = entry
                    self.total_insertions += 1
                    return True
                return False
        if len(occupants) < self.occupants_per_cell:
            occupants.append(entry)
            self.total_insertions += 1
            self.best_ever_quality = max(self.best_ever_quality, entry.quality)
            self._maybe_prune()
            return True
        weakest = min(range(len(occupants)), key=lambda i: occupants[i].quality)
        if entry.quality > occupants[weakest].quality:
            occupants[weakest] = entry
            self.total_insertions += 1
            self.best_ever_quality = max(self.best_ever_quality, entry.quality)
            return True
        return False

    def _maybe_prune(self) -> None:
        if len(self.grid) <= self.cells_capacity:
            return
        ranked = sorted(
            ((cell, max(e.quality for e in entries)) for cell, entries in self.grid.items()),
            key=lambda item: item[1],
            reverse=True,
        )
        keep = {cell for cell, _ in ranked[: self.cells_capacity]}
        self.grid = {cell: entries for cell, entries in self.grid.items() if cell in keep}

    # -- metrics ---------------------------------------------------------
    def coverage(self) -> float:
        occupied = len(self.grid)
        return occupied / max(1, self._potential_cells)

    def qd_score(self) -> float:
        return sum(max((entry.quality for entry in entries), default=0.0) for entries in self.grid.values())

    def record_generation(self) -> QDArchiveSnapshot:
        self.generations += 1
        coverage = self.coverage()
        score = self.qd_score()
        snapshot = QDArchiveSnapshot(
            generation=self.generations,
            coverage=coverage,
            qd_score=score,
            qd_auc=self.qd_auc(),
            cells=len(self.grid),
        )
        self.history.append(snapshot)
        return snapshot

    def qd_auc(self) -> float:
        """Area under the QD-score improvement curve (normalized trapezoid)."""
        if len(self.history) < 2:
            return 0.0
        scores = [snap.qd_score for snap in self.history]
        area = 0.0
        for first, second in zip(scores, scores[1:]):
            area += (first + second) / 2.0
        baseline = scores[0] * (len(scores) - 1)
        return area - baseline

    def elites(self) -> list[QDEntry]:
        return [max(entries, key=lambda e: e.quality) for entries in self.grid.values()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cells": {str(cell): [entry.to_dict() for entry in entries] for cell, entries in self.grid.items()},
            "generations": self.generations,
            "total_insertions": self.total_insertions,
            "coverage": self.coverage(),
            "qd_score": self.qd_score(),
            "qd_auc": self.qd_auc(),
            "history": [snap.to_dict() for snap in self.history[-64:]],
        }


@dataclass
class LocalCompetitionArchive:
    """DNS-style archive: survive if not dominated by behavioral neighbors.

    An entry is rejected only when *all* k nearest neighbors dominate it on
    quality AND the closest of those dominators is behaviorally within
    ``novelty_epsilon`` — i.e., it brings neither quality nor novelty.
    """

    k_neighbors: int = 15
    capacity: int = 1024
    domination_margin: float = 0.0
    novelty_epsilon: float = 0.10
    entries: dict[str, QDEntry] = field(default_factory=dict)

    def _distance(self, first: Sequence[int], second: Sequence[int]) -> float:
        if len(first) != len(second) or not first:
            return 1.0
        mismatch = sum(1 for a, b in zip(first, second) if a != b) / len(first)
        error = sum(math.log1p(abs(a - b)) for a, b in zip(first, second)) / (len(first) * math.log1p(10**6))
        return 0.7 * mismatch + 0.3 * min(1.0, error)

    def insert(self, entry: QDEntry) -> bool:
        existing = self.entries.get(entry.key)
        if existing is not None and existing.quality >= entry.quality:
            return False
        neighbors = self._nearest(entry.signature, self.k_neighbors)
        dominators = [
            other for other in neighbors
            if other.quality >= entry.quality - self.domination_margin
        ]
        if len(dominators) >= self.k_neighbors and self.entries:
            closest = min(self._distance(entry.signature, other.signature) for other in dominators)
            if closest < self.novelty_epsilon:
                return False  # crowded out with no behavioral novelty at all
        self.entries[entry.key] = entry
        self._evict_if_needed()
        return True

    def _nearest(self, signature: Sequence[int], k: int) -> list[QDEntry]:
        scored = sorted(
            self.entries.values(),
            key=lambda other: self._distance(signature, other.signature),
        )
        return scored[:k]

    def _evict_if_needed(self) -> None:
        if len(self.entries) <= self.capacity:
            return
        # evict the most redundant: entry with highest neighbor density & weak quality
        redundancy: list[tuple[float, float, str]] = []
        for entry in self.entries.values():
            neighbors = self._nearest(entry.signature, 3)
            density = sum(self._distance(entry.signature, n.signature) for n in neighbors) / max(1, len(neighbors))
            redundancy.append((density, entry.quality, entry.key))
        redundancy.sort(key=lambda item: (item[0], -item[1]))
        for _, _, key in redundancy[: len(self.entries) - self.capacity]:
            self.entries.pop(key, None)

    def coverage(self) -> float:
        return len(self.entries) / max(1, self.capacity)

    def qd_score(self) -> float:
        return sum(entry.quality for entry in self.entries.values())


# --------------------------------------------------------------------------- #
# emitters
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class Emission:
    source_emitter: str
    genome: Node


class Emitter:
    """Specialized candidate producer for the QD loop."""

    name = "base"

    def emit(self, archive_elites: list[QDEntry], rng: Any, context: dict[str, Any]) -> list[Emission]:
        raise NotImplementedError


class QualityEmitter(Emitter):
    """Refine the best elites with small perturbations (handled by caller's
    mutation stack; here it just picks *which* parents to refine)."""

    name = "quality"

    def emit(self, archive_elites: list[QDEntry], rng: Any, context: dict[str, Any]) -> list[Emission]:
        genomes: dict[str, Node] = context.get("genomes", {})
        ranked = sorted(archive_elites, key=lambda e: -e.quality)[:3]
        return [Emission(self.name, genomes[e.key].clone()) for e in ranked if e.key in genomes]


class NoveltyEmitter(Emitter):
    """Pick the most behaviorally isolated elites."""

    name = "novelty"

    def emit(self, archive_elites: list[QDEntry], rng: Any, context: dict[str, Any]) -> list[Emission]:
        genomes: dict[str, Node] = context.get("genomes", {})
        if len(archive_elites) < 2:
            return []
        def isolation(entry: QDEntry) -> float:
            others = [e for e in archive_elites if e.key != entry.key]
            if not others:
                return 1.0
            distances = [
                sum(1 for a, b in zip(entry.signature, e.signature) if a != b)
                for e in others
            ]
            return sum(distances) / len(distances)
        ranked = sorted(archive_elites, key=isolation, reverse=True)[:3]
        return [Emission(self.name, genomes[e.key].clone()) for e in ranked if e.key in genomes]


class SimplifierEmitter(Emitter):
    """Emit the cheapest elites (compression pressure)."""

    name = "simplifier"

    def emit(self, archive_elites: list[QDEntry], rng: Any, context: dict[str, Any]) -> list[Emission]:
        genomes: dict[str, Node] = context.get("genomes", {})
        ranked = sorted(archive_elites, key=lambda e: (e.cost_nodes, -e.quality))[:2]
        return [Emission(self.name, genomes[e.key].clone()) for e in ranked if e.key in genomes]


class RecombinationEmitter(Emitter):
    """Pair elites from *different* cells for the caller's crossover."""

    name = "recombiner"

    def emit(self, archive_elites: list[QDEntry], rng: Any, context: dict[str, Any]) -> list[Emission]:
        genomes: dict[str, Node] = context.get("genomes", {})
        if len(archive_elites) < 2:
            return []
        first, second = rng.sample(archive_elites, k=2)
        out: list[Emission] = []
        for entry in (first, second):
            if entry.key in genomes:
                out.append(Emission(self.name, genomes[entry.key].clone()))
        return out


def default_emitters() -> list[Emitter]:
    return [QualityEmitter(), NoveltyEmitter(), SimplifierEmitter(), RecombinationEmitter()]
