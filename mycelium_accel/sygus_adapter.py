"""External oracle adapter (Roadmap C2): SyGuS benchmarks -> tasks.

Maps SyGuS-Comp benchmarks (SyGuS-Org/benchmarks) with a SINGLE Int argument
and Int return into external-ground-truth tasks for the f(x)->int DSL:

    (synth-fun f ((x Int)) Int ...)
    (constraint (= (f 3) 30))   <- external I/O pair, no internal generator

A task is VALID iff it has >= ``min_examples`` point constraints on the
synth-fun with integer literal input and output. Multi-arg, BV/String, and
invariant benchmarks are honestly EXCLUDED (counted, reported, not fudged).

stdlib only. Deterministic train/test split by prime seed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def parse_sexp(text: str) -> list[Any]:  # noqa: C901 — Q3.2: recursive-descent parser arms.
    """Minimal S-expression parser (comments ';' stripped, strings kept)."""
    tokens: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == ";":
            while i < n and text[i] != "\n":
                i += 1
        elif ch in " \t\r\n":
            i += 1
        elif ch in "()":
            tokens.append(ch)
            i += 1
        elif ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            tokens.append(text[i:j + 1])
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in " \t\r\n();\"":
                j += 1
            tokens.append(text[i:j])
            i = j

    stack: list[list[Any]] = [[]]
    for tok in tokens:
        if tok == "(":
            stack.append([])
        elif tok == ")":
            if len(stack) < 2:
                raise ValueError("unbalanced parens in .sl")
            node = stack.pop()
            stack[-1].append(node)
        else:
            stack[-1].append(tok)
    if len(stack) != 1:
        raise ValueError("unbalanced parens in .sl")
    return stack[0]


@dataclass(slots=True)
class SyGuSTask:
    path: str
    logic: str
    func: str
    examples: list[tuple[int, int]] = field(default_factory=list)
    n_constraints: int = 0
    excluded_reason: str = ""

    @property
    def valid(self) -> bool:
        return not self.excluded_reason


def _as_int(token: Any) -> int | None:
    if isinstance(token, str):
        token = token.strip()
        if token.startswith("-") and token[1:].isdigit():
            return -int(token[1:])
        if token.isdigit():
            return int(token)
    return None


def extract_task(path: str | Path, *, min_examples: int = 5) -> SyGuSTask:  # noqa: C901 — Q3.2: recursive-descent parser arms.
    """Parse one .sl file into a task (valid or excluded-with-reason)."""
    path = Path(path)
    task = SyGuSTask(path=str(path), logic="", func="")
    try:
        forms = parse_sexp(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as exc:
        task.excluded_reason = f"parse-error: {exc}"
        return task

    synth: list[Any] | None = None
    for form in forms:
        if not isinstance(form, list) or not form:
            continue
        head = form[0]
        if head == "set-logic" and len(form) > 1:
            task.logic = str(form[1])
        elif head == "synth-fun":
            if synth is not None:
                task.excluded_reason = "multi-synth-fun"
                return task
            synth = form

    if synth is None or len(synth) < 4:
        task.excluded_reason = "no-synth-fun"
        return task
    task.func = str(synth[1])
    arg_spec = synth[2]
    ret_sort = str(synth[3])
    if not isinstance(arg_spec, list) or len(arg_spec) != 1:
        task.excluded_reason = f"arity!=1 ({len(arg_spec) if isinstance(arg_spec, list) else '?'})"
        return task
    arg = arg_spec[0]
    if not (isinstance(arg, list) and len(arg) == 2 and str(arg[1]) == "Int"):
        task.excluded_reason = f"arg-not-Int ({arg})"
        return task
    if ret_sort != "Int":
        task.excluded_reason = f"ret-not-Int ({ret_sort})"
        return task

    for form in forms:
        if not (isinstance(form, list) and form and form[0] == "constraint"):
            continue
        task.n_constraints += 1
        if len(form) != 2 or not isinstance(form[1], list):
            continue
        eq = form[1]
        if len(eq) != 3 or eq[0] != "=":
            continue
        app, out = eq[1], eq[2]
        if not (isinstance(app, list) and len(app) == 2 and app[0] == task.func):
            continue
        x = _as_int(app[1])
        y = _as_int(out)
        # SyGuS also encodes negatives as (- 5); handle that shape too.
        if x is None and isinstance(app[1], list) and len(app[1]) == 2 and app[1][0] == "-":
            neg = _as_int(app[1][1])
            x = -neg if neg is not None else None
        if y is None and isinstance(out, list) and len(out) == 2 and out[0] == "-":
            neg = _as_int(out[1])
            y = -neg if neg is not None else None
        if x is not None and y is not None:
            task.examples.append((x, y))

    # dedupe, keep order
    seen: set[tuple[int, int]] = set()
    uniq: list[tuple[int, int]] = []
    for pair in task.examples:
        if pair not in seen:
            seen.add(pair)
            uniq.append(pair)
    task.examples = uniq
    if len(task.examples) < min_examples:
        task.excluded_reason = f"only-{len(task.examples)}-point-examples"
        return task
    return task


def scan_corpus(root: str | Path, *, min_examples: int = 5) -> dict[str, Any]:
    """Walk ``root`` for .sl files; return valid tasks + exclusion histogram."""
    root = Path(root)
    files = sorted(root.rglob("*.sl"))
    valid: list[SyGuSTask] = []
    excluded: dict[str, int] = {}
    for file in files:
        task = extract_task(file, min_examples=min_examples)
        if task.valid:
            valid.append(task)
        else:
            excluded[task.excluded_reason] = excluded.get(task.excluded_reason, 0) + 1
    return {
        "root": str(root),
        "n_files": len(files),
        "n_valid": len(valid),
        "excluded": excluded,
        "tasks": [{"path": t.path, "logic": t.logic, "func": t.func,
                   "n_examples": len(t.examples)} for t in valid],
    }


def split_pairs(examples: list[tuple[int, int]], seed: int, *, train_frac: float = 0.6) -> tuple[list, list]:
    """Deterministic train/test split (rotation by seed — stable, no RNG)."""
    if not examples:
        return [], []
    k = seed % len(examples)
    rotated = examples[k:] + examples[:k]
    cut = max(1, int(len(rotated) * train_frac))
    return rotated[:cut], rotated[cut:]


def score_callable(fn: Any, pairs: list[tuple[int, int]]) -> dict[str, float]:
    """Exact-match score of a callable f(x)->int on external pairs."""
    if not pairs:
        return {"exact": 0.0, "total": 0}
    hits = 0
    for x, y in pairs:
        try:
            if int(fn(x)) == y:
                hits += 1
        except Exception:  # noqa: BLE001 - oracle faults count as misses
            pass
    return {"exact": hits / len(pairs), "total": float(len(pairs))}
