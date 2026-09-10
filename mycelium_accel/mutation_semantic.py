"""Deep semantic mutation operators (Roadmap Phase 3).

These operators differ from the classic syntactic ones in one crucial way:
each one *knows which behavior it wants to change* before touching the tree.
They are driven by (a) the semantic signature bank, (b) the counterexample
bank, and (c) verified probes — and every operator except the intentional
exploration ones verifies its effect on concrete cases before returning.

Operators
---------
* ``semantic_nearest_subtree_replace`` — replace a subtree by a banked
  neighbor with similar signature but better track record / smaller size.
* ``counterexample_patch_mutation`` — correct the median residual on the
  champion's failing cases, verified against those very cases.
* ``behavior_preserving_simplify`` — algebraic simplification whose
  equivalence is *verified on probes* before acceptance (anti-bloat).
* ``semantic_block_mutation`` — time-varying block size/base so the search
  is not trapped by one rigid semantic partition.
* ``library_instantiation_mutation`` — instantiate a library macro when a
  subtree's signature is close to the macro's own behavior.
* ``residual_fit_mutation`` — least-squares affine correction fitted on
  counterexamples, kept only if total residual strictly decreases.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from statistics import median
from collections.abc import Sequence

from .counterexamples import CounterexampleBank
from .dsl import (
    Node,
    compile_program,
    iter_path_nodes,
    random_tree,
    replace_subtree,
)
from .semantics import SemanticBank, canonical_probes, safe_signature, signature_distance

OPERATOR_NAMES = (
    "semantic_nearest_subtree_replace",
    "counterexample_patch_mutation",
    "behavior_preserving_simplify",
    "semantic_block_mutation",
    "library_instantiation_mutation",
    "residual_fit_mutation",
)


@dataclass
class SemanticMutationContext:
    """Shared state for semantic operators (banks, probes, VM limits)."""

    bank: SemanticBank
    counterexamples: CounterexampleBank
    probes: tuple[int, ...] = field(default_factory=lambda: canonical_probes(7))
    max_nodes: int = 63
    max_abs_value: int = 100_000
    max_steps: int = 256
    macro_nodes: dict[str, Node] = field(default_factory=dict)
    round_index: int = 0
    block_mutation_period: int = 25  # base refreshed every N rounds
    stats: dict[str, int] = field(default_factory=lambda: {name: 0 for name in OPERATOR_NAMES})

    def probe_signature(self, tree: Node) -> tuple[int, ...] | None:
        return safe_signature(
            tree,
            self.macro_nodes,
            self.probes,
            max_nodes=self.max_nodes,
            max_abs_value=self.max_abs_value,
            max_steps=self.max_steps,
        )

    def run_on(self, tree: Node, x: int) -> int | None:
        try:
            executor = compile_program(
                tree,
                self.macro_nodes,
                max_nodes=self.max_nodes,
                max_abs_value=self.max_abs_value,
                max_steps=self.max_steps,
            )
            return executor.run(x)
        except Exception:
            return None

    def note(self, operator: str) -> None:
        self.stats[operator] = self.stats.get(operator, 0) + 1


# --------------------------------------------------------------------------- #
# 3.2 substitution by semantic neighborhood
# --------------------------------------------------------------------------- #
def semantic_nearest_subtree_replace(
    tree: Node,
    ctx: SemanticMutationContext,
    rng: random.Random,
    *,
    k: int = 5,
) -> Node | None:
    if ctx.bank.size() < 4:
        return None
    path_nodes = [(path, node) for path, node in iter_path_nodes(tree) if 1 <= node.count_nodes() <= 16]
    if not path_nodes:
        return None
    rng.shuffle(path_nodes)
    for target_path, target in path_nodes[:6]:
        signature = ctx.probe_signature(target)
        if signature is None:
            continue
        neighbors = ctx.bank.nearest(signature, exclude_render=target.render(), k=k, min_success=0)
        for distance, entry in neighbors:
            if distance >= 0.35:
                continue
            # prefer successors with evidence or a strictly smaller program
            if entry.fitness_estimate <= 0.0 and entry.node_count >= target.count_nodes():
                continue
            replacement = _parse_render(entry.render, ctx)
            if replacement is None:
                continue
            candidate = replace_subtree(tree, target_path, replacement)
            if candidate.count_nodes() > ctx.max_nodes:
                continue
            ctx.note("semantic_nearest_subtree_replace")
            ctx.bank.record_outcome(entry.render, improved=True, round_index=ctx.round_index)
            return candidate
    return None


def _parse_render(render: str, ctx: SemanticMutationContext) -> Node | None:
    """Re-materialize a banked subtree from the bank's stored tree (if present).

    The bank indexes by render; when the originating Node object is not at
    hand we rebuild a cheap approximation: macros become macro nodes,
    otherwise a fresh small random-shape expression is *not* acceptable, so
    we only support renders we can rebuild deterministically.
    """
    if render in ctx.bank.trees:
        return ctx.bank.trees[render].clone()
    if render.startswith("@") and render.endswith("(x)"):
        name = render[1:-3]
        if name in ctx.macro_nodes:
            return Node("macro", value=name)
    return None


# --------------------------------------------------------------------------- #
# 3.1 counterexample guided patch
# --------------------------------------------------------------------------- #
def counterexample_patch_mutation(
    tree: Node,
    ctx: SemanticMutationContext,
    rng: random.Random,
    *,
    sample_size: int = 8,
) -> Node | None:
    if ctx.counterexamples.size() == 0:
        return None
    sample = ctx.counterexamples.sample(rng, sample_size)
    errors: list[int] = []
    current_total = 0
    usable: list[tuple[int, int, int]] = []  # (x, expected, predicted)
    for item in sample:
        predicted = ctx.run_on(tree, item.x)
        if predicted is None:
            continue
        usable.append((item.x, item.expected, predicted))
        errors.append(predicted - item.expected)
        current_total += abs(predicted - item.expected)
        item.predicted = predicted  # refresh stale residual info
    if not errors or all(error == 0 for error in errors):
        return None

    correction = int(round(median(errors)))
    if correction == 0:
        # residual is zero on median but individual cases differ: try affine.
        return residual_fit_mutation(tree, ctx, rng)

    patched = Node("sub", children=[tree.clone(), Node("const", value=correction)])
    if patched.count_nodes() > ctx.max_nodes:
        return None
    patched_total = 0
    for x, expected, _ in usable:
        predicted = ctx.run_on(patched, x)
        if predicted is None:
            return None
        patched_total += abs(predicted - expected)
    if patched_total >= current_total:
        return None  # the patch must strictly help on the failing set
    ctx.note("counterexample_patch_mutation")
    return patched


# --------------------------------------------------------------------------- #
# 3.4 behavior preserving simplification (verified)
# --------------------------------------------------------------------------- #
_SIMPLIFY_RULES: tuple[tuple[str, str], ...] = (
    ("add(x,0)", "x"),
    ("add(0,x)", "x"),
    ("sub(x,0)", "x"),
    ("mul(x,1)", "x"),
    ("mul(1,x)", "x"),
    ("mul(x,0)", "0"),
    ("mul(0,x)", "0"),
    ("min(x,x)", "x"),
    ("max(x,x)", "x"),
    ("sub(x,x)", "0"),
    ("inc(dec(x))", "x"),
    ("dec(inc(x))", "x"),
    ("neg(neg(x))", "x"),
    ("abs(abs(x))", "abs(x)"),
)


def _rule_candidates(tree: Node) -> list[tuple[tuple[int, ...], Node]]:  # noqa: C901 — Q3.2: rewrite-rule pattern arms.
    """Pattern-match algebraic simplifications at every subtree position."""
    found: list[tuple[tuple[int, ...], Node]] = []
    for path, node in iter_path_nodes(tree):
        kind = node.kind
        kids = node.children
        if kind == "add" and len(kids) == 2:
            if _is_const(kids[1], 0):
                found.append((path, kids[0]))
            elif _is_const(kids[0], 0):
                found.append((path, kids[1]))
        elif kind == "sub" and len(kids) == 2:
            if _is_const(kids[1], 0):
                found.append((path, kids[0]))
            elif kids[0].render() == kids[1].render():
                found.append((path, Node("const", value=0)))
        elif kind == "mul" and len(kids) == 2:
            if _is_const(kids[1], 1):
                found.append((path, kids[0]))
            elif _is_const(kids[0], 1):
                found.append((path, kids[1]))
            elif _is_const(kids[1], 0) or _is_const(kids[0], 0):
                found.append((path, Node("const", value=0)))
        elif kind in {"min", "max"} and len(kids) == 2 and kids[0].render() == kids[1].render():
            found.append((path, kids[0]))
        elif kind == "inc" and len(kids) == 1 and kids[0].kind == "dec":
            found.append((path, kids[0].children[0]))
        elif kind == "dec" and len(kids) == 1 and kids[0].kind == "inc":
            found.append((path, kids[0].children[0]))
        elif kind == "neg" and len(kids) == 1 and kids[0].kind == "neg":
            found.append((path, kids[0].children[0]))
        elif kind == "abs" and len(kids) == 1 and kids[0].kind == "abs":
            found.append((path, kids[0]))
        # constant folding of input-free, macro-free subtrees
        if _is_constant_tree(node) and node.kind != "const":
            value = _eval_constant(node)
            if value is not None and abs(value) <= 10**6:
                found.append((path, Node("const", value=value)))
    return found


def _is_const(node: Node, value: int) -> bool:
    if node.kind != "const" or node.value is None:
        return False
    try:
        return int(node.value) == value
    except (TypeError, ValueError):
        return False


def _is_constant_tree(node: Node) -> bool:
    if node.kind in {"input", "macro"}:
        return False
    return all(_is_constant_tree(child) for child in node.children)


def _eval_constant(node: Node) -> int | None:
    try:
        return compile_program(node, {}, max_nodes=128, max_abs_value=10**9, max_steps=1024).run(0)
    except Exception:
        return None


def behavior_preserving_simplify(
    tree: Node,
    ctx: SemanticMutationContext,
    rng: random.Random,
    *,
    max_passes: int = 4,
) -> Node | None:
    """Simplify with probe-verified equivalence — simplification must not
    change behavior *nor* may it rely on the algebraic rule being right in
    the presence of the VM's clipping semantics."""
    current = tree.clone()
    original_signature = ctx.probe_signature(current)
    if original_signature is None:
        return None
    changed = False
    for _ in range(max_passes):
        candidates = _rule_candidates(current)
        if not candidates:
            break
        path, replacement = rng.choice(candidates) if rng.random() < 0.3 else candidates[0]
        trial = replace_subtree(current, path, replacement)
        trial_signature = ctx.probe_signature(trial)
        if trial_signature == original_signature:
            current = trial
            changed = True
        else:
            break
    if changed and current.count_nodes() < tree.count_nodes():
        ctx.note("behavior_preserving_simplify")
        return current
    return None


# --------------------------------------------------------------------------- #
# 3.3 variable block mutation
# --------------------------------------------------------------------------- #
def semantic_block_mutation(
    tree: Node,
    ctx: SemanticMutationContext,
    rng: random.Random,
) -> Node | None:
    """Time-varying block mutation: the size/base of the semantic unit being
    swapped changes over rounds, so the search does not freeze into one rigid
    partition of program space."""
    period = max(2, ctx.block_mutation_period)
    phase = (ctx.round_index // period) % 4
    max_block = (2, 4, 8, 12)[phase]
    path_nodes = [
        (path, node)
        for path, node in iter_path_nodes(tree)
        if node.children and 2 <= node.count_nodes() <= max_block
    ]
    if not path_nodes:
        return None
    target_path, target = rng.choice(path_nodes)

    # base = banked subtrees of similar size first, else fresh random block
    similar = [
        entry
        for entry in ctx.bank.entries.values()
        if abs(entry.node_count - target.count_nodes()) <= 2 and entry.fitness_estimate > 0.0
    ]
    replacement: Node | None = None
    if similar and rng.random() < 0.6:
        entry = rng.choice(similar)
        replacement = _parse_render(entry.render, ctx)
    if replacement is None:
        replacement = random_tree(
            rng,
            max_depth=2 + phase,
            constant_scale=6,
            macro_names=tuple(ctx.macro_nodes),
        )
    candidate = replace_subtree(tree, target_path, replacement)
    if candidate.count_nodes() > ctx.max_nodes:
        return None
    ctx.note("semantic_block_mutation")
    return candidate


# --------------------------------------------------------------------------- #
# library instantiation
# --------------------------------------------------------------------------- #
def library_instantiation_mutation(  # noqa: C901 — Q3.2: search guards + shortlist loop.
    tree: Node,
    ctx: SemanticMutationContext,
    rng: random.Random,
) -> Node | None:
    """Use a library macro where a subtree already behaves almost like it."""
    if not ctx.macro_nodes:
        return None
    path_nodes = [(path, node) for path, node in iter_path_nodes(tree) if node.count_nodes() >= 2]
    rng.shuffle(path_nodes)
    macro_signatures: list[tuple[str, tuple[int, ...]]] = []
    for name, macro_tree in ctx.macro_nodes.items():
        signature = ctx.probe_signature(macro_tree)
        if signature is not None:
            macro_signatures.append((name, signature))
    if not macro_signatures:
        return None
    for target_path, target in path_nodes[:8]:
        signature = ctx.probe_signature(target)
        if signature is None:
            continue
        best_name = None
        best_distance = 1.0
        for name, macro_signature in macro_signatures:
            distance = signature_distance(signature, macro_signature)
            if distance < best_distance:
                best_distance = distance
                best_name = name
        if best_name is None or best_distance > 0.25:
            continue
        candidate = replace_subtree(tree, target_path, Node("macro", value=best_name))
        if candidate.count_nodes() > ctx.max_nodes:
            continue
        ctx.note("library_instantiation_mutation")
        return candidate
    return None


# --------------------------------------------------------------------------- #
# residual fit (affine correction, least squares)
# --------------------------------------------------------------------------- #
def residual_fit_mutation(  # noqa: C901 — Q3.2: guard chain + least-squares fit.
    tree: Node,
    ctx: SemanticMutationContext,
    rng: random.Random,
    *,
    sample_size: int = 12,
) -> Node | None:
    pairs = ctx.counterexamples.as_training_pairs(sample_size, rng)
    if len(pairs) < 3:
        pairs = ctx.counterexamples.blame_pairs(sample_size)
    if len(pairs) < 3:
        return None
    xs: list[int] = []
    ys: list[int] = []
    for x, expected in pairs:
        predicted = ctx.run_on(tree, x)
        if predicted is None:
            return None
        xs.append(predicted)
        ys.append(expected)

    # least squares on expected ~= a * predicted + b
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((value - mean_x) ** 2 for value in xs)
    if var_x < 1e-9:
        a, b = 1.0, mean_y - mean_x
    else:
        a = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / var_x
        b = mean_y - a * mean_x
    a_int = int(round(a))
    b_int = int(round(b))
    if abs(a_int) > 9 or abs(b_int) > ctx.max_abs_value // 4:
        return None
    if a_int == 1 and b_int == 0:
        return None

    patched = tree.clone()
    if a_int != 1:
        if a_int == 0:
            return None
        patched = Node("mul", children=[patched, Node("const", value=a_int)])
    if b_int != 0:
        op = "add" if b_int > 0 else "sub"
        patched = Node(op, children=[patched, Node("const", value=abs(b_int))])
        if patched.count_nodes() > ctx.max_nodes:
            return None

    before = sum(abs(x - y) for x, y in zip(xs, ys))
    after = 0
    for x, expected in pairs:
        predicted = ctx.run_on(patched, x)
        if predicted is None:
            return None
        after += abs(predicted - expected)
    if after >= before:
        return None
    ctx.note("residual_fit_mutation")
    return patched


# --------------------------------------------------------------------------- #
# dispatcher
# --------------------------------------------------------------------------- #
DEFAULT_OPERATOR_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("counterexample_patch_mutation", 0.30),
    ("semantic_nearest_subtree_replace", 0.20),
    ("behavior_preserving_simplify", 0.15),
    ("semantic_block_mutation", 0.15),
    ("library_instantiation_mutation", 0.10),
    ("residual_fit_mutation", 0.10),
)

_DISPATCH = {
    "semantic_nearest_subtree_replace": semantic_nearest_subtree_replace,
    "counterexample_patch_mutation": counterexample_patch_mutation,
    "behavior_preserving_simplify": behavior_preserving_simplify,
    "semantic_block_mutation": semantic_block_mutation,
    "library_instantiation_mutation": library_instantiation_mutation,
    "residual_fit_mutation": residual_fit_mutation,
}


def apply_semantic_mutation(
    tree: Node,
    ctx: SemanticMutationContext,
    rng: random.Random,
    *,
    operator_weights: Sequence[tuple[str, float]] = DEFAULT_OPERATOR_WEIGHTS,
    max_attempts: int = 3,
) -> Node | None:
    """Pick operators with probability proportional to weight + rolling
    success, trying several before giving up (None → caller falls back to the
    classic syntactic mutation)."""
    weights: list[tuple[str, float]] = []
    for name, base in operator_weights:
        success_bias = 1.0 + 0.1 * ctx.stats.get(name, 0)
        weights.append((name, base * success_bias))
    total = sum(weight for _, weight in weights)

    for _ in range(max_attempts):
        roll = rng.random() * total
        cursor = 0.0
        chosen = weights[-1][0]
        for name, weight in weights:
            cursor += weight
            if roll <= cursor:
                chosen = name
                break
        operator = _DISPATCH[chosen]
        candidate = operator(tree, ctx, rng)
        if candidate is not None and candidate.count_nodes() <= ctx.max_nodes:
            return candidate
    return None
