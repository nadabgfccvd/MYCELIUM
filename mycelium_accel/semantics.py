"""Semantic signatures of program (sub)trees + a bank of behaviors (Phase 3).

Every subtree can be summarized by its *behavior vector*: the outputs it
produces on a canonical set of probe inputs. Two subtrees with equal renders
are syntactic duplicates; equal signatures are semantic duplicates. The bank
below stores subtrees indexed by signature, tracks their complexity and
their observed evolutionary success, and answers nearest-neighbor queries so
that mutations can ask "what behaves similarly to this, but better?".
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any
from collections.abc import Iterable, Sequence

from .dsl import Macro, Node, compile_program, iter_path_nodes

CANONICAL_PROBES = (-11, -7, -5, -3, -2, -1, 0, 1, 2, 3, 5, 7, 11)


def canonical_probes(count: int = 7) -> tuple[int, ...]:
    count = max(3, min(count, len(CANONICAL_PROBES)))
    return CANONICAL_PROBES[:count]


@dataclass(slots=True)
class SemanticEntry:
    render: str
    signature: tuple[int, ...]
    node_count: int
    depth: int
    success_count: int = 0
    failure_count: int = 0
    first_seen_round: int = 0
    last_used_round: int = 0

    @property
    def fitness_estimate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total else 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["signature"] = list(self.signature)
        payload["fitness_estimate"] = self.fitness_estimate
        return payload


def safe_signature(
    tree: Node,
    macros: dict[str, Node] | None,
    probes: Sequence[int],
    *,
    max_nodes: int,
    max_abs_value: int,
    max_steps: int,
) -> tuple[int, ...] | None:
    """Behavior vector of a tree on probes; None when the tree is unrunnable."""
    try:
        executor = compile_program(
            tree,
            macros,
            max_nodes=max_nodes,
            max_abs_value=max_abs_value,
            max_steps=max_steps,
        )
    except Exception:
        return None
    outputs: list[int] = []
    try:
        for probe in probes:
            outputs.append(executor.run(int(probe)))
    except Exception:
        return None
    return tuple(outputs)


def signature_distance(first: Sequence[int], second: Sequence[int]) -> float:
    """0.0 = identical behavior on all probes; 1.0 = maximally different."""
    if not first or not second or len(first) != len(second):
        return 1.0
    exact_mismatches = 0
    soft_error = 0.0
    for a, b in zip(first, second):
        delta = abs(a - b)
        if delta:
            exact_mismatches += 1
        soft_error += math.log1p(delta)
    exact = exact_mismatches / len(first)
    soft = soft_error / (len(first) * math.log1p(10**6))
    return 0.6 * exact + 0.4 * min(1.0, soft)


@dataclass
class SemanticBank:
    """Behavior-indexed store of subtrees with success tracking."""

    probes: tuple[int, ...] = (CANONICAL_PROBES[:7])
    capacity: int = 512
    entries: dict[str, SemanticEntry] = field(default_factory=dict)
    trees: dict[str, Node] = field(default_factory=dict)  # render -> live Node (in-memory only)

    def _evict_if_needed(self) -> None:
        if len(self.entries) <= self.capacity:
            return
        ranked = sorted(
            self.entries.values(),
            key=lambda entry: (
                -entry.fitness_estimate,
                -(entry.success_count + 1) / (entry.last_used_round + 1),
                entry.node_count,
            ),
        )
        keep = ranked[: self.capacity]
        self.entries = {entry.render: entry for entry in keep}
        self.trees = {render: self.trees[render] for render in self.entries if render in self.trees}

    def register(
        self,
        tree: Node,
        macros: dict[str, Node] | None,
        round_index: int,
        *,
        max_nodes: int,
        max_abs_value: int,
        max_steps: int,
        internal_subtrees: bool = True,
    ) -> SemanticEntry | None:
        """Insert tree (and optionally its subtrees) into the bank."""
        registered: SemanticEntry | None = None
        nodes_to_add: Iterable[Node] = self._collect(tree, internal_subtrees)
        for node in nodes_to_add:
            signature = safe_signature(
                node, macros, self.probes,
                max_nodes=max_nodes, max_abs_value=max_abs_value, max_steps=max_steps,
            )
            if signature is None:
                continue
            render = node.render()
            entry = self.entries.get(render)
            if entry is None:
                entry = SemanticEntry(
                    render=render,
                    signature=signature,
                    node_count=node.count_nodes(),
                    depth=node.depth(),
                    first_seen_round=round_index,
                    last_used_round=round_index,
                )
                self.entries[render] = entry
                self.trees[render] = node.clone()
            else:
                entry.last_used_round = round_index
            if registered is None:
                registered = entry
        self._evict_if_needed()
        return registered

    def _collect(self, tree: Node, internal_subtrees: bool) -> list[Node]:
        if not internal_subtrees:
            return [tree]
        collected = [tree]
        for _, node in iter_path_nodes(tree):
            if node.children and 2 <= node.count_nodes() <= 16:
                collected.append(node)
        return collected

    def nearest(
        self,
        signature: Sequence[int],
        *,
        exclude_render: str | None = None,
        k: int = 5,
        min_success: int = 0,
    ) -> list[tuple[float, SemanticEntry]]:
        """k nearest stored behaviors to a signature (ascending distance)."""
        scored: list[tuple[float, SemanticEntry]] = []
        for entry in self.entries.values():
            if exclude_render is not None and entry.render == exclude_render:
                continue
            if entry.success_count < min_success:
                continue
            distance = signature_distance(signature, entry.signature)
            scored.append((distance, entry))
        scored.sort(key=lambda item: (item[0], item[1].node_count, -item[1].fitness_estimate))
        return scored[: max(1, k)]

    def record_outcome(self, render: str, improved: bool, round_index: int) -> None:
        entry = self.entries.get(render)
        if entry is None:
            return
        if improved:
            entry.success_count += 1
        else:
            entry.failure_count += 1
        entry.last_used_round = round_index

    def size(self) -> int:
        return len(self.entries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "probes": list(self.probes),
            "capacity": self.capacity,
            "entries": [entry.to_dict() for entry in self.entries.values()],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SemanticBank:
        bank = cls(probes=tuple(payload.get("probes", CANONICAL_PROBES[:7])), capacity=int(payload.get("capacity", 512)))
        for entry_payload in payload.get("entries", []):
            entry = SemanticEntry(
                render=entry_payload["render"],
                signature=tuple(entry_payload["signature"]),
                node_count=int(entry_payload["node_count"]),
                depth=int(entry_payload["depth"]),
                success_count=int(entry_payload.get("success_count", 0)),
                failure_count=int(entry_payload.get("failure_count", 0)),
                first_seen_round=int(entry_payload.get("first_seen_round", 0)),
                last_used_round=int(entry_payload.get("last_used_round", 0)),
            )
            bank.entries[entry.render] = entry
        return bank


def macro_node_map(macros: dict[str, Node] | dict[str, Macro]) -> dict[str, Node]:
    normalized: dict[str, Node] = {}
    for name, value in macros.items():
        normalized[name] = value.tree if isinstance(value, Macro) else value
    return normalized
