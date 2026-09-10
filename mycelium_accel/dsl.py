from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Iterable, Mapping, Sequence


UNARY_OPS = ("neg", "abs", "inc", "dec", "square")
BINARY_OPS = ("add", "sub", "mul", "max", "min", "mod")
TERMINALS = ("const", "input")

OP_CONST = 0
OP_INPUT = 1
OP_NEG = 2
OP_ABS = 3
OP_INC = 4
OP_DEC = 5
OP_SQUARE = 6
OP_ADD = 7
OP_SUB = 8
OP_MUL = 9
OP_MAX = 10
OP_MIN = 11
OP_MOD = 12

UNARY_OPCODE = {
    "neg": OP_NEG,
    "abs": OP_ABS,
    "inc": OP_INC,
    "dec": OP_DEC,
    "square": OP_SQUARE,
}
BINARY_OPCODE = {
    "add": OP_ADD,
    "sub": OP_SUB,
    "mul": OP_MUL,
    "max": OP_MAX,
    "min": OP_MIN,
    "mod": OP_MOD,
}
SERIAL_KIND_TO_CODE = {
    "const": 0,
    "input": 1,
    "macro": 2,
    "neg": 3,
    "abs": 4,
    "inc": 5,
    "dec": 6,
    "square": 7,
    "add": 8,
    "sub": 9,
    "mul": 10,
    "max": 11,
    "min": 12,
    "mod": 13,
}
SERIAL_CODE_TO_KIND = {value: key for key, value in SERIAL_KIND_TO_CODE.items()}


@dataclass(slots=True)
class Node:
    kind: str
    value: int | str | None = None
    children: list[Node] = field(default_factory=list)
    _node_count: int | None = field(default=None, init=False, repr=False)
    _depth_cache: int | None = field(default=None, init=False, repr=False)
    _render_cache: str | None = field(default=None, init=False, repr=False)

    def clone(self) -> Node:
        cloned = Node(self.kind, self.value, [child.clone() for child in self.children])
        cloned._node_count = self._node_count
        cloned._depth_cache = self._depth_cache
        cloned._render_cache = self._render_cache
        return cloned

    def count_nodes(self) -> int:
        cached = self._node_count
        if cached is not None:
            return cached
        cached = 1 + sum(child.count_nodes() for child in self.children)
        self._node_count = cached
        return cached

    def depth(self) -> int:
        cached = self._depth_cache
        if cached is not None:
            return cached
        cached = 1 if not self.children else 1 + max(child.depth() for child in self.children)
        self._depth_cache = cached
        return cached

    def complexity_score(self) -> int:
        return self.count_nodes() * 3 + self.depth()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Node:
        return cls(
            kind=payload["kind"],
            value=payload.get("value"),
            children=[cls.from_dict(child) for child in payload.get("children", [])],
        )

    def to_compact(self) -> list[Any]:
        code = SERIAL_KIND_TO_CODE[self.kind]
        if self.kind == "const":
            return [code, const_int(self)]
        if self.kind == "input":
            return [code]
        if self.kind == "macro":
            return [code, str(self.value)]
        return [code, [child.to_compact() for child in self.children]]

    @classmethod
    def from_compact(cls, payload: list[Any]) -> Node:
        kind = SERIAL_CODE_TO_KIND[int(payload[0])]
        if kind == "const":
            return cls(kind, value=int(payload[1]))
        if kind == "input":
            return cls(kind)
        if kind == "macro":
            return cls(kind, value=str(payload[1]))
        return cls(kind, children=[cls.from_compact(child) for child in payload[1]])

    def render(self) -> str:
        cached = self._render_cache
        if cached is not None:
            return cached
        if self.kind == "const":
            cached = str(self.value)
        elif self.kind == "input":
            cached = "x"
        elif self.kind == "macro":
            cached = f"@{self.value}(x)"
        elif len(self.children) == 1:
            cached = f"{self.kind}({self.children[0].render()})"
        else:
            cached = f"{self.kind}({', '.join(child.render() for child in self.children)})"
        self._render_cache = cached
        return cached


@dataclass(slots=True)
class Macro:
    name: str
    tree: Node
    created_round: int
    uses: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tree": self.tree.to_dict(),
            "created_round": self.created_round,
            "uses": self.uses,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Macro:
        return cls(
            name=payload["name"],
            tree=Node.from_dict(payload["tree"]),
            created_round=payload["created_round"],
            uses=payload.get("uses", 0),
        )

    def to_compact(self) -> list[Any]:
        return [self.name, self.created_round, self.uses, self.tree.to_compact()]

    @classmethod
    def from_compact(cls, payload: list[Any]) -> Macro:
        return cls(
            name=str(payload[0]),
            created_round=int(payload[1]),
            uses=int(payload[2]),
            tree=Node.from_compact(payload[3]),
        )


@dataclass(slots=True)
class ProgramExecutor:
    instructions: tuple[tuple[int, int], ...]
    max_abs_value: int
    max_stack_depth: int
    instruction_count: int

    def run(self, x: int) -> int:
        return _execute_program(self.instructions, self.max_abs_value, self.max_stack_depth, x)

    def score_pairs(self, pairs: Sequence[tuple[int, int]]) -> tuple[float, float]:
        return _score_pairs_program(self.instructions, self.max_abs_value, self.max_stack_depth, pairs, None)

    def score_pairs_limit(self, pairs: Sequence[tuple[int, int]], limit: int) -> tuple[float, float]:
        return _score_pairs_program(self.instructions, self.max_abs_value, self.max_stack_depth, pairs, limit)


MacroNodeMap = Mapping[str, Node | Macro]


def _normalize_macro_nodes(macros: MacroNodeMap | None) -> dict[str, Node]:
    if not macros:
        return {}
    normalized: dict[str, Node] = {}
    for name, value in macros.items():
        normalized[name] = value.tree if isinstance(value, Macro) else value
    return normalized


def const_int(node: Node) -> int:
    """Q3.1: const payload as int; missing value is a friendly ValueError."""
    if node.value is None:
        raise ValueError(f"const node is missing its value: {node!r}")
    return int(node.value)


def _clip(value: int, max_abs: int) -> int:
    if value > max_abs:
        return max_abs
    if value < -max_abs:
        return -max_abs
    return value


def _execute_program(  # noqa: C901 — Q3.2: opcode dispatch table, 1-2 lines per arm.
    instructions: tuple[tuple[int, int], ...],
    max_abs_value: int,
    max_stack_depth: int,
    x: int,
) -> int:
    if x > max_abs_value:
        x = max_abs_value
    elif x < -max_abs_value:
        x = -max_abs_value

    stack = [0] * max_stack_depth
    top = 0
    for opcode, argument in instructions:
        if opcode == OP_CONST:
            stack[top] = argument
            top += 1
            continue
        if opcode == OP_INPUT:
            stack[top] = x
            top += 1
            continue

        if opcode == OP_NEG:
            stack[top - 1] = -stack[top - 1]
        elif opcode == OP_ABS:
            stack[top - 1] = abs(stack[top - 1])
        elif opcode == OP_INC:
            stack[top - 1] += 1
        elif opcode == OP_DEC:
            stack[top - 1] -= 1
        elif opcode == OP_SQUARE:
            stack[top - 1] *= stack[top - 1]
        else:
            right = stack[top - 1]
            left = stack[top - 2]
            top -= 1
            if opcode == OP_ADD:
                stack[top - 1] = left + right
            elif opcode == OP_SUB:
                stack[top - 1] = left - right
            elif opcode == OP_MUL:
                stack[top - 1] = left * right
            elif opcode == OP_MAX:
                stack[top - 1] = left if left >= right else right
                continue
            elif opcode == OP_MIN:
                stack[top - 1] = left if left <= right else right
                continue
            else:
                stack[top - 1] = left % (abs(right) % 97 + 1)

        value = stack[top - 1]
        if value > max_abs_value:
            stack[top - 1] = max_abs_value
        elif value < -max_abs_value:
            stack[top - 1] = -max_abs_value
    return stack[top - 1]


def _score_pairs_program(  # noqa: C901 — Q3.2: scoring loop with opcode dispatch.
    instructions: tuple[tuple[int, int], ...],
    max_abs_value: int,
    max_stack_depth: int,
    pairs: Sequence[tuple[int, int]],
    limit: int | None,
) -> tuple[float, float]:
    total_soft = 0.0
    exact_hits = 0
    count = 0
    stack = [0] * max_stack_depth

    for x, expected in pairs:
        if limit is not None and count >= limit:
            break
        count += 1
        if x > max_abs_value:
            x = max_abs_value
        elif x < -max_abs_value:
            x = -max_abs_value

        top = 0
        for opcode, argument in instructions:
            if opcode == OP_CONST:
                stack[top] = argument
                top += 1
                continue
            if opcode == OP_INPUT:
                stack[top] = x
                top += 1
                continue

            if opcode == OP_NEG:
                stack[top - 1] = -stack[top - 1]
            elif opcode == OP_ABS:
                stack[top - 1] = abs(stack[top - 1])
            elif opcode == OP_INC:
                stack[top - 1] += 1
            elif opcode == OP_DEC:
                stack[top - 1] -= 1
            elif opcode == OP_SQUARE:
                stack[top - 1] *= stack[top - 1]
            else:
                right = stack[top - 1]
                left = stack[top - 2]
                top -= 1
                if opcode == OP_ADD:
                    stack[top - 1] = left + right
                elif opcode == OP_SUB:
                    stack[top - 1] = left - right
                elif opcode == OP_MUL:
                    stack[top - 1] = left * right
                elif opcode == OP_MAX:
                    stack[top - 1] = left if left >= right else right
                    continue
                elif opcode == OP_MIN:
                    stack[top - 1] = left if left <= right else right
                    continue
                else:
                    stack[top - 1] = left % (abs(right) % 97 + 1)

            value = stack[top - 1]
            if value > max_abs_value:
                stack[top - 1] = max_abs_value
            elif value < -max_abs_value:
                stack[top - 1] = -max_abs_value

        predicted = stack[top - 1]
        error = predicted - expected
        if error < 0:
            error = -error
        total_soft += 1.0 / (1.0 + error)
        if error == 0:
            exact_hits += 1

    if count == 0:
        return 0.0, 0.0
    return total_soft / count, exact_hits / count


def _compile_program_instructions(tree: Node, macro_nodes: dict[str, Node]) -> tuple[tuple[tuple[int, int], ...], int]:  # noqa: C901 — Q3.2: compiler recursion over node kinds.
    compiled_macros: dict[str, tuple[tuple[tuple[int, int], ...], int]] = {}
    visiting_macros: set[str] = set()

    def compile_macro(name: str) -> tuple[tuple[tuple[int, int], ...], int]:
        if name in compiled_macros:
            return compiled_macros[name]
        if name in visiting_macros:
            raise RuntimeError(f"Recursive macro detected: {name}")
        if name not in macro_nodes:
            raise RuntimeError(f"Unknown macro: {name}")
        visiting_macros.add(name)
        buffer: list[tuple[int, int]] = []
        compile_node(macro_nodes[name], buffer)
        visiting_macros.remove(name)
        result = (tuple(buffer), _max_stack_depth(buffer))
        compiled_macros[name] = result
        return result

    def compile_node(node: Node, buffer: list[tuple[int, int]]) -> None:
        kind = node.kind
        if kind == "const":
            buffer.append((OP_CONST, _clip(const_int(node), 10**18)))
            return
        if kind == "input":
            buffer.append((OP_INPUT, 0))
            return
        if kind == "macro":
            fragment, _ = compile_macro(str(node.value))
            buffer.extend(fragment)
            return
        if kind in UNARY_OPCODE:
            compile_node(node.children[0], buffer)
            buffer.append((UNARY_OPCODE[kind], 0))
            return
        if kind in BINARY_OPCODE:
            compile_node(node.children[0], buffer)
            compile_node(node.children[1], buffer)
            buffer.append((BINARY_OPCODE[kind], 0))
            return
        raise RuntimeError(f"Unsupported node kind: {kind}")

    buffer: list[tuple[int, int]] = []
    compile_node(tree, buffer)
    instructions = tuple(buffer)
    return instructions, _max_stack_depth(instructions)


def _max_stack_depth(instructions: Sequence[tuple[int, int]]) -> int:
    depth = 0
    max_depth = 0
    for opcode, _ in instructions:
        if opcode in (OP_CONST, OP_INPUT):
            depth += 1
        elif opcode in (OP_NEG, OP_ABS, OP_INC, OP_DEC, OP_SQUARE):
            pass
        else:
            depth -= 1
        if depth > max_depth:
            max_depth = depth
    return max(1, max_depth)


def compile_program(
    tree: Node,
    macros: MacroNodeMap | None,
    *,
    max_nodes: int,
    max_abs_value: int,
    max_steps: int,
) -> ProgramExecutor:
    if tree.count_nodes() > max_nodes:
        raise RuntimeError("Program exceeds node cap.")
    instructions, max_stack_depth = _compile_program_instructions(tree, _normalize_macro_nodes(macros))
    instruction_count = len(instructions)
    step_limit = min(max_steps, max_nodes * 8)
    if instruction_count > step_limit:
        raise RuntimeError("Program exceeded combined node budget.")
    if max_abs_value < 10**18:
        clipped_instructions = []
        for opcode, argument in instructions:
            if opcode == OP_CONST:
                clipped_instructions.append((opcode, _clip(argument, max_abs_value)))
            else:
                clipped_instructions.append((opcode, argument))
        instructions = tuple(clipped_instructions)
    return ProgramExecutor(
        instructions=instructions,
        max_abs_value=max_abs_value,
        max_stack_depth=max_stack_depth,
        instruction_count=instruction_count,
    )


def run_program(
    tree: Node,
    x: int,
    macros: MacroNodeMap | None,
    *,
    max_nodes: int,
    max_abs_value: int,
    max_steps: int,
) -> int:
    return compile_program(
        tree,
        macros,
        max_nodes=max_nodes,
        max_abs_value=max_abs_value,
        max_steps=max_steps,
    ).run(x)


def random_const(rng: random.Random, scale: int) -> int:
    value = rng.randint(-scale, scale)
    if value == 0 and rng.random() < 0.4:
        value = 1
    return value


def random_tree(
    rng: random.Random,
    max_depth: int,
    constant_scale: int,
    macro_names: Iterable[str] | None = None,
) -> Node:
    macros = tuple(macro_names or ())
    if max_depth <= 1 or rng.random() < 0.28:
        terminal_roll = rng.random()
        if macros and terminal_roll < 0.18:
            return Node("macro", value=rng.choice(macros))
        if terminal_roll < 0.58:
            return Node("input")
        return Node("const", value=random_const(rng, constant_scale))

    if rng.random() < 0.45:
        op = rng.choice(UNARY_OPS)
        return Node(op, children=[random_tree(rng, max_depth - 1, constant_scale, macros)])

    op = rng.choice(BINARY_OPS)
    left = random_tree(rng, max_depth - 1, constant_scale, macros)
    right = random_tree(rng, max_depth - 1, constant_scale, macros)
    return Node(op, children=[left, right])


def iter_path_nodes(node: Node) -> list[tuple[tuple[int, ...], Node]]:
    stack: list[tuple[tuple[int, ...], Node]] = [((), node)]
    items: list[tuple[tuple[int, ...], Node]] = []
    while stack:
        path, current = stack.pop()
        items.append((path, current))
        for index in range(len(current.children) - 1, -1, -1):
            stack.append((path + (index,), current.children[index]))
    return items


def iter_paths(node: Node, path: tuple[int, ...] = ()) -> list[tuple[int, ...]]:
    if path:
        raise ValueError("iter_paths no longer accepts a non-root starting path.")
    return [item[0] for item in iter_path_nodes(node)]


def get_subtree(node: Node, path: tuple[int, ...]) -> Node:
    current = node
    for index in path:
        current = current.children[index]
    return current


def replace_subtree(node: Node, path: tuple[int, ...], new_subtree: Node) -> Node:
    if not path:
        return new_subtree.clone()
    index = path[0]
    children = list(node.children)
    children[index] = replace_subtree(children[index], path[1:], new_subtree)
    return Node(node.kind, value=node.value, children=children)


def mutate(
    node: Node,
    rng: random.Random,
    *,
    max_depth: int,
    constant_scale: int,
    macro_names: Iterable[str] | None = None,
) -> Node:
    macro_names = tuple(macro_names or ())
    path_nodes = iter_path_nodes(node)
    target_path, target = rng.choice(path_nodes)

    if target.kind == "const" and rng.random() < 0.4:
        replacement = Node("const", value=const_int(target) + rng.randint(-3, 3))
        return replace_subtree(node, target_path, replacement)

    mode = rng.random()
    if mode < 0.35:
        replacement = random_tree(
            rng,
            max_depth=max(1, max_depth // 2),
            constant_scale=constant_scale,
            macro_names=macro_names,
        )
        return replace_subtree(node, target_path, replacement)
    if mode < 0.6:
        op = rng.choice(UNARY_OPS)
        replacement = Node(op, children=[target.clone()])
        return replace_subtree(node, target_path, replacement)
    if mode < 0.85:
        op = rng.choice(BINARY_OPS)
        sibling = random_tree(
            rng,
            max_depth=max(1, max_depth // 2),
            constant_scale=constant_scale,
            macro_names=macro_names,
        )
        if rng.random() < 0.5:
            replacement = Node(op, children=[target.clone(), sibling])
        else:
            replacement = Node(op, children=[sibling, target.clone()])
        return replace_subtree(node, target_path, replacement)

    if macro_names:
        replacement = Node("macro", value=rng.choice(macro_names))
        return replace_subtree(node, target_path, replacement)
    return replace_subtree(node, target_path, Node("const", value=random_const(rng, constant_scale)))


def crossover(first: Node, second: Node, rng: random.Random) -> Node:
    path_first, _ = rng.choice(iter_path_nodes(first))
    _, donor = rng.choice(iter_path_nodes(second))
    return replace_subtree(first, path_first, donor)


def subtree_motifs(node: Node, *, min_nodes: int = 2, max_nodes: int = 8) -> list[Node]:
    motifs: list[Node] = []
    for _, sub in iter_path_nodes(node):
        size = sub.count_nodes()
        if min_nodes <= size <= max_nodes:
            motifs.append(sub.clone())
    return motifs


def repeated_pattern_tree(rng: random.Random) -> Node:
    base = rng.randint(1, 9)
    repeated = int(str(base) * rng.randint(2, 4))
    left = Node("const", value=repeated)
    right = Node("const", value=int(str(rng.randint(1, 9)) * 2))
    if rng.random() < 0.5:
        return Node("add", children=[left, Node("input")])
    return Node("mul", children=[Node("input"), Node("max", children=[left, right])])


def complexity(tree: Node) -> int:
    return tree.complexity_score()


def dedupe_motifs(motifs: Iterable[Node], limit: int) -> list[Node]:
    seen: set[str] = set()
    unique: list[Node] = []
    for motif in motifs:
        key = motif.render()
        if key in seen:
            continue
        seen.add(key)
        unique.append(motif)
        if len(unique) >= limit:
            break
    return unique
