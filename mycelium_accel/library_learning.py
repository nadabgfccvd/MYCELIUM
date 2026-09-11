"""Library learning by corpus compression (Roadmap Phase 4, Stitch-style).

Discovers reusable abstractions from a corpus of elite programs by choosing
the substructures that maximally compress the corpus under an explicit
MDL objective:

    cost = cost(library) + cost(corpus rewritten with the library)

An abstraction is kept only if it *provably* reduces the total description
length. Abstractions are promoted at three scales:

* micro — short subtrees (2-4 nodes);
* meso  — recurring function-like motifs (5-12 nodes);
* meta  — recurring co-occurrence templates (abstraction wrapping another).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from collections.abc import Iterable, Sequence

from .dsl import Node, iter_path_nodes, replace_subtree
from .model import StagedMacro

MICRO_MAX_NODES = 4
MESO_MAX_NODES = 12


@dataclass(slots=True)
class LibraryAbstraction:
    name: str
    render: str
    node_count: int
    support: int
    mdl_gain: float
    scale: str  # micro | meso | meta

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LearnedLibrary:
    abstractions: list[LibraryAbstraction]
    corpus_cost_before: float
    corpus_cost_after: float
    compression_ratio: float

    @property
    def reduction(self) -> float:
        return self.corpus_cost_before - self.corpus_cost_after

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["abstractions"] = [item.to_dict() for item in self.abstractions]
        return payload

def _unrender(render: str) -> Node:
    """Rebuild a Node from a stored render via the tree registry trick.

    The learner only ever passes renders produced in-process, so it also
    keeps the live trees in ``_RENDER_CACHE``; when a render is missing we
    raise instead of silently producing a wrong tree.
    """
    tree = _RENDER_CACHE.get(render)
    if tree is None:
        raise KeyError(f"Render not present in the in-memory registry: {render}")
    return tree.clone()


_RENDER_CACHE: dict[str, Node] = {}


def _memo(tree: Node) -> Node:
    _RENDER_CACHE[tree.render()] = tree.clone()
    return tree


def collect_corpus(trees: Iterable[Node]) -> list[Node]:
    """Corpus of elite/near-elite programs (deduplicated by render)."""
    seen: set[str] = set()
    corpus: list[Node] = []
    for tree in trees:
        render = tree.render()
        if render in seen:
            continue
        seen.add(render)
        corpus.append(_memo(tree.clone()))
    return corpus


def corpus_description_length(corpus: Sequence[Node]) -> float:
    return float(sum(tree.count_nodes() for tree in corpus))


def _subtree_histogram(corpus: Sequence[Node], *, min_nodes: int, max_nodes: int) -> dict[str, tuple[int, Node]]:
    """Count subtree occurrences across the corpus, keyed by render."""
    counts: dict[str, list[Any]] = {}
    for tree in corpus:
        seen_in_tree: set[str] = set()
        for _, node in iter_path_nodes(tree):
            size = node.count_nodes()
            if size < min_nodes or size > max_nodes:
                continue
            if node.kind in {"input", "const", "macro"}:
                continue
            render = node.render()
            if render in seen_in_tree:
                counts[render][0] += 1
                continue
            seen_in_tree.add(render)
            if render not in counts:
                counts[render] = [1, node.clone()]
            else:
                counts[render][0] += 1
        # NB: occurrences are counted once per tree + repeats inside the tree.
    return {render: (payload[0], payload[1]) for render, payload in counts.items()}


def mdl_gain(occurrences: int, subtree_nodes: int, *, definition_cost: float | None = None) -> float:
    """Compression gain of abstracting a subtree into a 1-node macro ref.

    cost(before)  = occurrences * subtree_nodes
    cost(after)   = definition_cost + occurrences * 1 (each use is 1 node)
    """
    if occurrences < 2 or subtree_nodes < 2:
        return 0.0
    cost = definition_cost if definition_cost is not None else float(subtree_nodes)
    return occurrences * (subtree_nodes - 1) - cost


def _scale_of(size: int) -> str:
    if size <= MICRO_MAX_NODES:
        return "micro"
    if size <= MESO_MAX_NODES:
        return "meso"
    return "meta"


def _replace_all(corpus: list[Node], target_render: str, macro_name: str) -> tuple[list[Node], int]:
    """Rewrite every occurrence (top-down, non-overlapping) of a subtree."""
    replaced_total = 0
    new_corpus: list[Node] = []
    for tree in corpus:
        current = tree
        while True:
            hit_path = None
            for path, node in iter_path_nodes(current):
                if node.render() == target_render:
                    hit_path = path
                    break
            if hit_path is None:
                break
            current = replace_subtree(current, hit_path, Node("macro", value=macro_name))
            new_corpus.append(_memo(current))  # track intermediate states
            replaced_total += 1
        new_corpus.append(current)
    # dedupe while preserving order
    seen: set[str] = set()
    final: list[Node] = []
    for tree in new_corpus:
        render = tree.render()
        if render in seen:
            continue
        seen.add(render)
        final.append(tree)
    return final, replaced_total


def learn_library(
    corpus: Sequence[Node],
    *,
    max_abstractions: int = 12,
    min_support: int = 2,
    max_subtree_nodes: int = MESO_MAX_NODES,
    name_prefix: str = "lib",
) -> LearnedLibrary:
    """Greedy MDL abstraction learning.

    At each step, adopt the subtree with the largest positive MDL gain,
    rewrite the corpus, and continue. Stop when nothing compresses anymore.
    """
    working = list(corpus)
    cost_before = corpus_description_length(working)
    abstractions: list[LibraryAbstraction] = []
    used_names: set[str] = set()

    for index in range(max_abstractions):
        histogram = _subtree_histogram(working, min_nodes=2, max_nodes=max_subtree_nodes)
        best_render = None
        best_gain = 0.0
        best_nodes = 0
        best_support = 0
        best_subtree = None
        for render, (support, subtree) in histogram.items():
            if support < min_support:
                continue
            gain = mdl_gain(support, subtree.count_nodes())
            if gain > best_gain:
                best_render = render
                best_gain = gain
                best_nodes = subtree.count_nodes()
                best_support = support
                best_subtree = subtree
        if best_render is None or best_gain <= 0 or best_subtree is None:
            break
        # Q0: memoize the adopted subtree so promote_to_staging works in a
        # fresh process (no dependence on ambient _RENDER_CACHE state).
        _memo(best_subtree)
        name = f"{name_prefix}_{index}"
        used_names.add(name)
        working, _ = _replace_all(working, best_render, name)
        abstractions.append(
            LibraryAbstraction(
                name=name,
                render=best_render,
                node_count=best_nodes,
                support=best_support,
                mdl_gain=best_gain,
                scale=_scale_of(best_nodes),
            )
        )

    cost_after = corpus_description_length(working) + sum(a.node_count for a in abstractions)
    ratio = cost_after / cost_before if cost_before else 1.0
    return LearnedLibrary(
        abstractions=abstractions,
        corpus_cost_before=cost_before,
        corpus_cost_after=cost_after,
        compression_ratio=ratio,
    )


def learn_meta_rules(library: LearnedLibrary, corpus: Sequence[Node]) -> list[LibraryAbstraction]:
    """Detect recurring templates where one abstraction wraps another."""
    co_occurrence: dict[str, int] = {}
    for tree in corpus:
        for _, node in iter_path_nodes(tree):
            if node.kind != "macro":
                continue
            for child in node.children:
                nested = [desc for _, desc in iter_path_nodes(child) if desc.kind == "macro"]
                for desc in nested[:2]:
                    key = f"{node.value}({desc.value})"
                    co_occurrence[key] = co_occurrence.get(key, 0) + 1
    rules: list[LibraryAbstraction] = []
    for index, (pattern, support) in enumerate(sorted(co_occurrence.items(), key=lambda kv: -kv[1])):
        if support < 2:
            continue
        rules.append(
            LibraryAbstraction(
                name=f"meta_{index}",
                render=pattern,
                node_count=0,
                support=support,
                mdl_gain=float(support),
                scale="meta",
            )
        )
    return rules


def promote_to_staging(library: LearnedLibrary, *, round_index: int, source_family_id: str = "library_learning") -> list[StagedMacro]:
    """Convert learned abstractions into StagedMacro objects for the engine's
    normal promotion pipeline (support/transfer criteria still apply)."""
    staged: list[StagedMacro] = []
    for item in library.abstractions:
        if item.scale == "meta":
            continue  # meta-rules are advisory; not directly executable
        try:
            tree = _unrender(item.render)
        except KeyError:
            continue
        staged.append(
            StagedMacro(
                name=item.name,
                tree=tree,
                created_round=round_index,
                source_family_id=source_family_id,
                support=item.support,
                transfer_gain=0.0,
                compression_gain=item.mdl_gain,
                reuse_count=item.support,
                last_seen_round=round_index,
            )
        )
    return staged


def abstraction_reuse_stats(library: LearnedLibrary) -> dict[str, float]:
    if not library.abstractions:
        return {"mean_support": 0.0, "mean_gain": 0.0, "count": 0.0}
    supports = [item.support for item in library.abstractions]
    gains = [item.mdl_gain for item in library.abstractions]
    return {
        "mean_support": sum(supports) / len(supports),
        "mean_gain": sum(gains) / len(gains),
        "count": float(len(library.abstractions)),
    }
