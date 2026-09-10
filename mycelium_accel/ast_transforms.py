"""Python AST source-to-source transforms (Roadmap Phase 5, Track B).

Only *safe, local* transforms are implemented — every rewrite is designed to
be behavioral-equivalence verifiable afterwards:
* constant folding of pure arithmetic on literals;
* strength reduction (mul -> add/shift patterns, identity elimination);
* conservative loop-invariant hoisting (pure expressions only).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass


PURE_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)
SAFE_UNARY = (ast.UAdd, ast.USub, ast.Invert)


@dataclass(slots=True)
class TransformResult:
    source: str
    changed: bool
    applied_rules: list[str]


class ConstantFolder(ast.NodeTransformer):
    def __init__(self) -> None:
        self.changed = False
        self.rules: list[str] = []

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
            if isinstance(node.op, PURE_BINOPS) and isinstance(node.left.value, (int, float)) and isinstance(node.right.value, (int, float)):
                if isinstance(node.op, (ast.FloorDiv, ast.Mod)) and node.right.value == 0:
                    return node
                try:
                    if isinstance(node.op, ast.Add):
                        value = node.left.value + node.right.value
                    elif isinstance(node.op, ast.Sub):
                        value = node.left.value - node.right.value
                    elif isinstance(node.op, ast.Mult):
                        value = node.left.value * node.right.value
                    elif isinstance(node.op, ast.FloorDiv):
                        value = node.left.value // node.right.value
                    else:
                        value = node.left.value % node.right.value
                except Exception:
                    return node
                self.changed = True
                self.rules.append("fold-binop")
                return ast.copy_location(ast.Constant(value=value), node)
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, int) and isinstance(node.op, SAFE_UNARY):
            if isinstance(node.op, ast.UAdd):
                value = +node.operand.value
            elif isinstance(node.op, ast.USub):
                value = -node.operand.value
            else:
                value = ~node.operand.value
            self.changed = True
            self.rules.append("fold-unary")
            return ast.copy_location(ast.Constant(value=value), node)
        return node


class StrengthReducer(ast.NodeTransformer):
    def __init__(self) -> None:
        self.changed = False
        self.rules: list[str] = []

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.op, ast.Mult):
            # x * 2 -> x + x ; x * 1 -> x ; x * 0 -> 0
            for side, other in ((node.left, node.right), (node.right, node.left)):
                if isinstance(other, ast.Constant) and isinstance(other.value, int):
                    if other.value == 2:
                        self.changed = True
                        self.rules.append("mul2-to-add")
                        dup = ast.fix_missing_locations(ast.parse(ast.unparse(side), mode="eval").body)
                        return ast.copy_location(ast.BinOp(left=side, op=ast.Add(), right=dup), node)
                    if other.value == 1:
                        self.changed = True
                        self.rules.append("mul1-remove")
                        return side
                    if other.value == 0:
                        self.changed = True
                        self.rules.append("mul0-to-const")
                        return ast.copy_location(ast.Constant(value=0), node)
        if isinstance(node.op, (ast.Add,)) and isinstance(node.right, ast.Constant) and node.right.value == 0:
            self.changed = True
            self.rules.append("add0-remove")
            return node.left
        if isinstance(node.op, ast.Sub) and isinstance(node.right, ast.Constant) and node.right.value == 0:
            self.changed = True
            self.rules.append("sub0-remove")
            return node.left
        if isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant) and node.right.value == 2:
            self.changed = True
            self.rules.append("pow2-to-mul")
            dup = ast.fix_missing_locations(ast.parse(ast.unparse(node.left), mode="eval").body)
            return ast.copy_location(ast.BinOp(left=node.left, op=ast.Mult(), right=dup), node)
        return node


class _AssignedNames(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)


class LoopInvariantHoister(ast.NodeTransformer):
    """Hoist loop-invariant pure expressions out of simple for-loops."""

    def __init__(self) -> None:
        self.changed = False
        self.rules: list[str] = []
        self._counter = 0

    def visit_For(self, node: ast.For) -> ast.AST | list[ast.stmt]:
        self.generic_visit(node)
        assigned = _AssignedNames()
        for stmt in node.body:
            assigned.visit(stmt)
        assigned_names = set(assigned.names)

        def loop_var_names() -> set[str]:
            names: set[str] = set()
            target = node.target
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                names.update(elt.id for elt in target.elts if isinstance(elt, ast.Name))
            return names

        forbidden = assigned_names | loop_var_names()
        hoisted_any = False
        new_body: list[ast.stmt] = []
        prefix: list[ast.stmt] = []
        for stmt in node.body:
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and _is_pure_expression(stmt.value, forbidden)
            ):
                temp_name = f"_mycelium_inv_{self._counter}"
                self._counter += 1
                prefix.append(
                    ast.Assign(targets=[ast.Name(id=temp_name, ctx=ast.Store())], value=stmt.value)
                )
                stmt = ast.Assign(
                    targets=[stmt.targets[0]],
                    value=ast.Name(id=temp_name, ctx=ast.Load()),
                )
                hoisted_any = True
            new_body.append(stmt)
        if hoisted_any:
            self.changed = True
            self.rules.append("hoist-invariant")
            node.body = new_body
            return prefix + [node]
        return node


def _is_pure_expression(node: ast.AST, forbidden_names: set[str]) -> bool:
    """Pure = only constants, names outside the forbidden set, pure binops."""
    for child in ast.walk(node):
        if isinstance(child, (ast.Call, ast.Attribute, ast.Subscript, ast.Yield, ast.Await)):
            return False
        if isinstance(child, ast.Name) and child.id in forbidden_names:
            return False
        if isinstance(child, ast.BinOp) and not isinstance(child.op, PURE_BINOPS):
            return False
        if isinstance(child, ast.UnaryOp) and not isinstance(child.op, SAFE_UNARY):
            return False
    return True


def apply_source_transforms(source: str, *, max_rounds: int = 3) -> TransformResult:
    """Run all safe transforms to a fixpoint and return the rewritten source."""
    tree = ast.parse(source)
    applied: list[str] = []
    changed_any = False
    for _ in range(max_rounds):
        changed_round = False
        for transformer_cls in (ConstantFolder, StrengthReducer, LoopInvariantHoister):
            transformer = transformer_cls()
            tree = transformer.visit(tree)
            if transformer.changed:
                changed_round = True
                changed_any = True
                applied.extend(transformer.rules)
        if not changed_round:
            break
    ast.fix_missing_locations(tree)
    return TransformResult(source=ast.unparse(tree), changed=changed_any, applied_rules=applied)
