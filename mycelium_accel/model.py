from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .dsl import Macro, Node

STATE_FORMAT_VERSION = 4


@dataclass(slots=True)
class StagedMacro:
    name: str
    tree: Node
    created_round: int
    source_family_id: str
    support: int = 0
    transfer_gain: float = 0.0
    compression_gain: float = 0.0
    reuse_count: int = 0
    last_seen_round: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tree": self.tree.to_dict(),
            "created_round": self.created_round,
            "source_family_id": self.source_family_id,
            "support": self.support,
            "transfer_gain": self.transfer_gain,
            "compression_gain": self.compression_gain,
            "reuse_count": self.reuse_count,
            "last_seen_round": self.last_seen_round,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StagedMacro:
        return cls(
            name=str(payload["name"]),
            tree=Node.from_dict(payload["tree"]),
            created_round=int(payload["created_round"]),
            source_family_id=str(payload.get("source_family_id", "")),
            support=int(payload.get("support", 0)),
            transfer_gain=float(payload.get("transfer_gain", 0.0)),
            compression_gain=float(payload.get("compression_gain", 0.0)),
            reuse_count=int(payload.get("reuse_count", 0)),
            last_seen_round=int(payload.get("last_seen_round", payload.get("created_round", 0))),
        )

    def to_compact(self) -> list[Any]:
        return [
            self.name,
            self.created_round,
            self.source_family_id,
            self.support,
            self.transfer_gain,
            self.compression_gain,
            self.reuse_count,
            self.last_seen_round,
            self.tree.to_compact(),
        ]

    @classmethod
    def from_compact(cls, payload: list[Any]) -> StagedMacro:
        return cls(
            name=str(payload[0]),
            created_round=int(payload[1]),
            source_family_id=str(payload[2]),
            support=int(payload[3]),
            transfer_gain=float(payload[4]),
            compression_gain=float(payload[5]),
            reuse_count=int(payload[6]),
            last_seen_round=int(payload[7]),
            tree=Node.from_compact(payload[8]),
        )


def pack_metric(metric: dict[str, Any]) -> list[Any]:
    return [
        metric["round"],
        metric["climate"],
        metric["frontier_difficulty"],
        metric["best_score"],
        metric["best_exact_rate"],
        metric["solved_by_best"],
        metric["macro_count"],
        metric["capability_signal"],
        metric["best_program"],
        metric["challenge_oracles"],
        metric.get("staging_macro_count", 0),
        metric.get("active_niches", 0),
        metric.get("diversity_entropy", 0.0),
        metric.get("macro_transfer_mean", 0.0),
        metric.get("frontier_learning_progress", 0.0),
        metric.get("frontier_status_counts", {"dominated": 0, "frontier": 0, "impossible": 0}),
        # F1/C1 extensions (positions 16-18); unpack guards keep old states valid.
        bool(metric.get("macro_cap_saturated", False)),
        int(metric.get("ecology_injections", 0)),
        int(metric.get("ecology_reseeds", 0)),
    ]


def unpack_metric(payload: list[Any]) -> dict[str, Any]:
    counts = payload[15] if len(payload) > 15 else {"dominated": 0, "frontier": 0, "impossible": 0}
    return {
        "round": payload[0],
        "climate": payload[1],
        "frontier_difficulty": payload[2],
        "best_score": payload[3],
        "best_exact_rate": payload[4],
        "solved_by_best": payload[5],
        "macro_count": payload[6],
        "capability_signal": payload[7],
        "best_program": payload[8],
        "challenge_oracles": payload[9],
        "staging_macro_count": payload[10] if len(payload) > 10 else 0,
        "active_niches": payload[11] if len(payload) > 11 else 0,
        "diversity_entropy": payload[12] if len(payload) > 12 else 0.0,
        "macro_transfer_mean": payload[13] if len(payload) > 13 else 0.0,
        "frontier_learning_progress": payload[14] if len(payload) > 14 else 0.0,
        "frontier_status_counts": {
            "dominated": int(counts.get("dominated", 0)),
            "frontier": int(counts.get("frontier", 0)),
            "impossible": int(counts.get("impossible", 0)),
        },
        "macro_cap_saturated": bool(payload[16]) if len(payload) > 16 else False,
        "ecology_injections": int(payload[17]) if len(payload) > 17 else 0,
        "ecology_reseeds": int(payload[18]) if len(payload) > 18 else 0,
    }


@dataclass(slots=True)
class Organism:
    organism_id: str
    family_id: str
    genome: Node
    lineage_depth: int
    birth_round: int
    score: float = 0.0
    exact_rate: float = 0.0
    soft_rate: float = 0.0
    solved_challenges: int = 0
    notes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "organism_id": self.organism_id,
            "family_id": self.family_id,
            "genome": self.genome.to_dict(),
            "lineage_depth": self.lineage_depth,
            "birth_round": self.birth_round,
            "score": self.score,
            "exact_rate": self.exact_rate,
            "soft_rate": self.soft_rate,
            "solved_challenges": self.solved_challenges,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Organism:
        return cls(
            organism_id=payload["organism_id"],
            family_id=payload["family_id"],
            genome=Node.from_dict(payload["genome"]),
            lineage_depth=payload["lineage_depth"],
            birth_round=payload["birth_round"],
            score=payload.get("score", 0.0),
            exact_rate=payload.get("exact_rate", 0.0),
            soft_rate=payload.get("soft_rate", 0.0),
            solved_challenges=payload.get("solved_challenges", 0),
            notes=payload.get("notes", {}),
        )

    def to_compact(self, *, nested_family: bool = True) -> list[Any]:
        base = [self.organism_id, self.lineage_depth, self.birth_round, self.genome.to_compact()]
        if nested_family:
            return base
        return [self.organism_id, self.family_id, self.lineage_depth, self.birth_round, self.genome.to_compact()]

    @classmethod
    def from_compact(cls, payload: list[Any], family_id: str | None = None) -> Organism:
        if family_id is None:
            organism_id, original_family_id, lineage_depth, birth_round, genome = payload
            return cls(
                organism_id=str(organism_id),
                family_id=str(original_family_id),
                lineage_depth=int(lineage_depth),
                birth_round=int(birth_round),
                genome=Node.from_compact(genome),
            )
        organism_id, lineage_depth, birth_round, genome = payload
        return cls(
            organism_id=str(organism_id),
            family_id=family_id,
            lineage_depth=int(lineage_depth),
            birth_round=int(birth_round),
            genome=Node.from_compact(genome),
        )


@dataclass(slots=True)
class Family:
    family_id: str
    created_round: int
    lineage_depth: int
    phase: int
    members: list[Organism] = field(default_factory=list)
    gene_bank: list[Node] = field(default_factory=list)
    last_score: float = 0.0
    last_diversity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "created_round": self.created_round,
            "lineage_depth": self.lineage_depth,
            "phase": self.phase,
            "members": [member.to_dict() for member in self.members],
            "gene_bank": [node.to_dict() for node in self.gene_bank],
            "last_score": self.last_score,
            "last_diversity": self.last_diversity,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Family:
        return cls(
            family_id=payload["family_id"],
            created_round=payload["created_round"],
            lineage_depth=payload["lineage_depth"],
            phase=payload["phase"],
            members=[Organism.from_dict(item) for item in payload.get("members", [])],
            gene_bank=[Node.from_dict(node) for node in payload.get("gene_bank", [])],
            last_score=payload.get("last_score", 0.0),
            last_diversity=payload.get("last_diversity", 0.0),
        )

    def to_compact(self) -> list[Any]:
        return [
            self.family_id,
            self.created_round,
            self.lineage_depth,
            self.phase,
            self.last_score,
            self.last_diversity,
            [member.to_compact(nested_family=True) for member in self.members],
            [node.to_compact() for node in self.gene_bank],
        ]

    @classmethod
    def from_compact(cls, payload: list[Any]) -> Family:
        family_id = str(payload[0])
        return cls(
            family_id=family_id,
            created_round=int(payload[1]),
            lineage_depth=int(payload[2]),
            phase=int(payload[3]),
            last_score=float(payload[4]),
            last_diversity=float(payload[5]),
            members=[Organism.from_compact(item, family_id=family_id) for item in payload[6]],
            gene_bank=[Node.from_compact(node) for node in payload[7]],
        )


@dataclass(slots=True)
class EngineState:
    config: dict[str, Any]
    round_index: int
    next_family_index: int
    next_organism_index: int
    frontier_difficulty: int
    climate_mode: int
    total_families_created: int
    thief_thresholds_seen: list[int] = field(default_factory=list)
    families: list[Family] = field(default_factory=list)
    macro_library: list[Macro] = field(default_factory=list)
    macro_staging: list[StagedMacro] = field(default_factory=list)
    graveyard: list[dict[str, Any]] = field(default_factory=list)
    metrics_history: list[dict[str, Any]] = field(default_factory=list)
    frontier_archive: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "round_index": self.round_index,
            "next_family_index": self.next_family_index,
            "next_organism_index": self.next_organism_index,
            "frontier_difficulty": self.frontier_difficulty,
            "climate_mode": self.climate_mode,
            "total_families_created": self.total_families_created,
            "thief_thresholds_seen": self.thief_thresholds_seen,
            "families": [family.to_dict() for family in self.families],
            "macro_library": [macro.to_dict() for macro in self.macro_library],
            "macro_staging": [macro.to_dict() for macro in self.macro_staging],
            "graveyard": self.graveyard,
            "metrics_history": self.metrics_history,
            "frontier_archive": self.frontier_archive,
        }

    def to_compact(self) -> dict[str, Any]:
        return {
            "format": STATE_FORMAT_VERSION,
            "config": self.config,
            "round_index": self.round_index,
            "next_family_index": self.next_family_index,
            "next_organism_index": self.next_organism_index,
            "frontier_difficulty": self.frontier_difficulty,
            "climate_mode": self.climate_mode,
            "total_families_created": self.total_families_created,
            "thief_thresholds_seen": self.thief_thresholds_seen,
            "families": [family.to_compact() for family in self.families],
            "macro_library": [macro.to_compact() for macro in self.macro_library],
            "macro_staging": [macro.to_compact() for macro in self.macro_staging],
            "graveyard": [
                [
                    entry["round"],
                    entry["score"],
                    entry["organism"]
                    if isinstance(entry["organism"], list)
                    else [
                        entry["organism"]["organism_id"],
                        entry["organism"]["family_id"],
                        entry["organism"]["lineage_depth"],
                        entry["organism"]["birth_round"],
                        Node.from_dict(entry["organism"]["genome"]).to_compact(),
                    ],
                ]
                for entry in self.graveyard
            ],
            "metrics_history": [pack_metric(metric) for metric in self.metrics_history],
            "frontier_archive": self.frontier_archive,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EngineState:
        if payload.get("format") in {2, 3, STATE_FORMAT_VERSION}:
            return cls.from_compact(payload)
        return cls(
            config=payload["config"],
            round_index=payload["round_index"],
            next_family_index=payload["next_family_index"],
            next_organism_index=payload["next_organism_index"],
            frontier_difficulty=payload["frontier_difficulty"],
            climate_mode=payload["climate_mode"],
            total_families_created=payload["total_families_created"],
            thief_thresholds_seen=payload.get("thief_thresholds_seen", []),
            families=[Family.from_dict(item) for item in payload.get("families", [])],
            macro_library=[Macro.from_dict(item) for item in payload.get("macro_library", [])],
            macro_staging=[StagedMacro.from_dict(item) for item in payload.get("macro_staging", [])],
            graveyard=payload.get("graveyard", []),
            metrics_history=payload.get("metrics_history", []),
            frontier_archive=payload.get("frontier_archive", []),
        )

    @classmethod
    def from_compact(cls, payload: dict[str, Any]) -> EngineState:
        format_version = int(payload.get("format", 2))
        raw_metrics = payload.get("metrics_history", [])
        metrics_history = (
            [unpack_metric(item) for item in raw_metrics]
            if format_version >= 3
            else raw_metrics
        )
        return cls(
            config=payload["config"],
            round_index=int(payload["round_index"]),
            next_family_index=int(payload["next_family_index"]),
            next_organism_index=int(payload["next_organism_index"]),
            frontier_difficulty=int(payload["frontier_difficulty"]),
            climate_mode=int(payload["climate_mode"]),
            total_families_created=int(payload["total_families_created"]),
            thief_thresholds_seen=[int(value) for value in payload.get("thief_thresholds_seen", [])],
            families=[Family.from_compact(item) for item in payload.get("families", [])],
            macro_library=[Macro.from_compact(item) for item in payload.get("macro_library", [])],
            macro_staging=[StagedMacro.from_compact(item) for item in payload.get("macro_staging", [])],
            graveyard=[
                {
                    "round": int(entry[0]),
                    "score": float(entry[1]),
                    "organism": entry[2],
                }
                for entry in payload.get("graveyard", [])
            ],
            metrics_history=metrics_history,
            frontier_archive=list(payload.get("frontier_archive", [])),
        )
