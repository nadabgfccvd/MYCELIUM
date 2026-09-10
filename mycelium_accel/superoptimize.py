"""Local superoptimization of small hot integer functions (Roadmap Phase 5,
Track D — Souper/SuperStack-style).

Enumerates straight-line integer expressions by increasing cost, checks
exact behavioral equivalence against the target on (a) a deterministic
exhaustive domain window and (b) paired random probes, and returns the
cheapest exactly-equivalent program found. Only *pure* single-integer-input
functions are in scope — exactly the small hot windows the roadmap says are
worth superoptimizing.
"""
from __future__ import annotations

import random
import time
from dataclasses import asdict, dataclass
from typing import Any
from collections.abc import Callable

from .prime import next_prime


@dataclass(slots=True)
class SuperoptResult:
    target_cases: int
    equivalent: bool
    expr_source: str | None
    cost_before: int
    cost_after: int
    candidates_checked: int
    seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _apply_op(op: str, left: int, right: int, clip: int) -> int | None:  # noqa: C901 — Q3.2: operator dispatch.
    try:
        if op == "add":
            value = left + right
        elif op == "sub":
            value = left - right
        elif op == "mul":
            value = left * right
        elif op == "floordiv2":
            value = left >> 1
        elif op == "neg":
            value = -left
        elif op == "abs":
            value = abs(left)
        elif op == "max":
            value = left if left >= right else right
        elif op == "min":
            value = left if left <= right else right
        else:
            return None
    except Exception:
        return None
    if value > clip or value < -clip:
        return None
    return value


def _op_cost(op: str) -> int:
    return {
        "add": 1, "sub": 1, "neg": 1, "abs": 1,
        "floordiv2": 1, "max": 2, "min": 2, "mul": 3,
    }[op]


def _eval_expr(expr: str, x: int, clip: int = 10**9) -> int | None:
    """Tiny postfix expression evaluator: tokens space-separated.

    Tokens: ``x``, integer constants, and ops {neg,abs,add,sub,mul,max,min,floordiv2}.
    """
    stack: list[int] = []
    for token in expr.split():
        if token == "x":
            stack.append(x)
        elif token.lstrip("-").isdigit():
            stack.append(int(token))
        else:
            if token in {"neg", "abs", "floordiv2"}:
                if not stack:
                    return None
                value = _apply_op(token, stack.pop(), 0, clip)
                if value is None:
                    return None
                stack.append(value)
            else:
                if len(stack) < 2:
                    return None
                right = stack.pop()
                left = stack.pop()
                value = _apply_op(token, left, right, clip)
                if value is None:
                    return None
                stack.append(value)
    if len(stack) != 1:
        return None
    return stack[0]


def _expr_cost(expr: str) -> int:
    cost = 0
    for token in expr.split():
        if token == "x" or token.lstrip("-").isdigit():
            cost += 1
        else:
            cost += _op_cost(token)
    return cost


def enumerate_expressions(  # noqa: C901 — Q3.2: enumerator dispatch.
    max_cost: int,
    constants: tuple[int, ...] = (-2, -1, 0, 1, 2),
) -> list[str]:
    """All distinct postfix expressions with cost <= max_cost, cheap first.

    Cost-ordered DP: an expression of cost C is a leaf (cost 1), a unary op
    over an expression of cost C-1, or a binary op over subexpressions whose
    costs sum with the op cost to C. Commutative ops skip symmetric pairs.
    """
    unary = ("neg", "abs", "floordiv2")
    binary = ("add", "sub", "mul", "max", "min")
    commutative = {"add", "mul", "max", "min"}
    by_cost: dict[int, list[str]] = {1: ["x"] + [str(c) for c in constants]}
    seen: set[str] = set(by_cost[1])

    for target_cost in range(2, max_cost + 1):
        level: list[str] = []
        # unary: op cost 1 over expressions of cost target_cost - 1
        for expr in by_cost.get(target_cost - 1, []):
            for op in unary:
                if _op_cost(op) + _expr_cost(expr) != target_cost:
                    continue
                candidate = f"{expr} {op}"
                if candidate not in seen:
                    seen.add(candidate)
                    level.append(candidate)
        # binary: cost(a) + cost(b) + op_cost == target_cost
        for op in binary:
            op_cost = _op_cost(op)
            for cost_a in range(1, target_cost - op_cost):
                cost_b = target_cost - op_cost - cost_a
                if cost_b < 1:
                    continue
                left_pool = by_cost.get(cost_a, [])
                right_pool = by_cost.get(cost_b, [])
                for left in left_pool:
                    for right in right_pool:
                        if op in commutative and cost_a == cost_b and left > right:
                            continue  # canonical commutativity cut
                        candidate = f"{left} {right} {op}"
                        if candidate not in seen:
                            seen.add(candidate)
                            level.append(candidate)
        if level:
            by_cost[target_cost] = level

    ordered: list[str] = []
    for cost in sorted(by_cost):
        ordered.extend(sorted(by_cost[cost], key=lambda expr: (len(expr), expr)))
    return ordered


def superoptimize_function(
    target: Callable[[int], int],
    *,
    name: str = "target",
    max_cost: int = 7,
    domain_window: tuple[int, int] = (-64, 64),
    n_random_probes: int = 96,
    random_span: int = 1000,
    seed: int = 101,
    timeout_seconds: float = 5.0,
) -> SuperoptResult:
    """Search the cheapest program exactly equivalent to ``target``.

    Equivalence = exact match on the full domain window plus deterministic
    random probes. Only step-1 "peephole" scale is claimed — precisely the
    scale Souper/SuperStack operate at.
    """
    started = time.perf_counter()
    seed = next_prime(seed)
    rng = random.Random(seed)
    probes = list(range(domain_window[0], domain_window[1] + 1))
    probes += [rng.randint(-random_span, random_span) for _ in range(n_random_probes)]

    reference: dict[int, int] = {}
    for x in probes:
        try:
            reference[x] = int(target(x))
        except Exception:
            return SuperoptResult(
                target_cases=0, equivalent=False, expr_source=None,
                cost_before=0, cost_after=0, candidates_checked=0,
                seconds=time.perf_counter() - started,
            )

    checked = 0
    best_expr: str | None = None
    best_cost = 10**9
    for expr in enumerate_expressions(max_cost):
        if time.perf_counter() - started > timeout_seconds:
            break
        cost = _expr_cost(expr)
        if cost >= best_cost:
            continue
        checked += 1
        ok = True
        for x, expected in reference.items():
            if _eval_expr(expr, x) != expected:
                ok = False
                break
        if ok:
            best_expr = expr
            best_cost = cost
            break  # enumeration is cost-ordered: first hit is optimal
    return SuperoptResult(
        target_cases=len(reference),
        equivalent=best_expr is not None,
        expr_source=best_expr,
        cost_before=max_cost + 1,
        cost_after=best_cost if best_expr else 0,
        candidates_checked=checked,
        seconds=time.perf_counter() - started,
    )


def postfix_to_python(expr: str, *, arg: str = "x") -> str:
    """Render a postfix expression as an inline Python expression."""
    stack: list[str] = []
    for token in expr.split():
        if token == "x":
            stack.append(arg)
        elif token.lstrip("-").isdigit():
            stack.append(token)
        elif token in {"neg", "abs", "floordiv2"}:
            a = stack.pop()
            if token == "neg":
                stack.append(f"(-({a}))")
            elif token == "abs":
                stack.append(f"abs({a})")
            else:
                stack.append(f"(({a}) >> 1)")
        else:
            b = stack.pop()
            a = stack.pop()
            symbol = {"add": "+", "sub": "-", "mul": "*", "max": None, "min": None}[token]
            if symbol is not None:
                stack.append(f"(({a}) {symbol} ({b}))")
            else:
                stack.append(f"{token}(({a}), ({b}))")
    return stack[0]


def superoptimize_to_lambda(
    target: Callable[[int], int],
    **kwargs: Any,
) -> tuple[SuperoptResult, Callable[[int], int] | None]:
    """Convenience wrapper returning a compiled Python lambda when found."""
    result = superoptimize_function(target, **kwargs)
    if not result.equivalent or result.expr_source is None:
        return result, None
    python_expr = postfix_to_python(result.expr_source)
    fn = eval(f"lambda x: {python_expr}", {"abs": abs, "max": max, "min": min})
    # final exact re-verification of the compiled lambda
    for x in range(-64, 65):
        if fn(x) != target(x):
            return SuperoptResult(
                target_cases=result.target_cases,
                equivalent=False,
                expr_source=None,
                cost_before=result.cost_before,
                cost_after=0,
                candidates_checked=result.candidates_checked,
                seconds=result.seconds,
            ), None
    return result, fn
