#!/usr/bin/env python3
"""P1 benchmark workload for the Cycle-7 portfolio (pygments first-char dispatch).

Run from the root of a pygments checkout so ``import pygments`` resolves to the
local tree (the MYCELIUM patch-mode variant replaces pygments/lexer.py and
restores it afterwards). One timed pass over a deterministic 4-lexer mix
(Python, SQL, HTML, JavaScript); the harness (warmup=1, repeats=5) calls this
as a fresh subprocess per repeat and takes the median.

The corpus is generated from MYCELIUM_SEED, so baseline and variant see
byte-identical inputs for the same seed (paired design). Prints
``{"seconds": <float>}`` on stdout for the json_stdout metrics parser.

NOTE: absolute seconds and the exact speedup vary by host; the archived run
(0.687 -> 0.621 s, -9.6%) was on the original machine. This script reproduces
the *methodology* and the acceptance decision, not the host-specific number.
"""
from __future__ import annotations

import json
import os
import random
import time

from pygments import lex
from pygments.lexers import (
    HtmlLexer,
    JavascriptLexer,
    PythonLexer,
    SqlLexer,
)

seed = int(os.environ.get("MYCELIUM_SEED", "101"))
rng = random.Random(seed)

# Deterministic, code-shaped corpus generators (fixed templates, seed picks
# sizes/identifiers so every seed is a slightly different but stable mix).
_PY_TEMPLATE = """\
def fib{n}(a, b={d}):
    out = [x for x in range(a, b) if x % {m} == 0]
    return {{k: v for k, v in zip("abc", out) if v > 1}}

class C{n}:
    def m(self, x=[1, 2, 3], *args, **kw):
        assert len(out) >= 0 or x is None
        return sum(out) + {d} / 7.0
"""

_SQL_TEMPLATE = (
    "SELECT id_{n}, name_{n}, count(*) AS c_{n} FROM users u{n} "
    "JOIN orders o{n} ON u{n}.id = o{n}.uid WHERE o{n}.total > {d} "
    "GROUP BY id_{n}, name_{n} HAVING count(*) > {m} ORDER BY id_{n} DESC;\n"
)

_HTML_TEMPLATE = (
    "<html><head><title>t{n}</title><style>.a{n}{{color:red}}</style></head>"
    "<body><div class='x{n}' id='y{n}'>hello &amp; <b>world {n}</b>"
    "<a href='/p?a={d}&b={m}'>link {n}</a></div>"
    "<script>var a{n}={d};</script></body></html>\n"
)

_JS_TEMPLATE = """\
async function f{n}(x) {{
    const y = await g_{n}(x);
    return y?.z ?? [1, 2, 3].map(v => v * {m}).filter(v => v > {d});
}}
class A{n} extends B{n} {{
    constructor() {{ super(); this.t = `template ${{1 + {d}}}`; }}
}}
"""


# Repeat counts sized so one pass is on the order of 0.6-0.7 s (the archived
# run's magnitude), keeping the small per-seed deltas measurable over noise.
_REPEATS = (
    int(os.environ.get("PORTFOLIO_PY_REPEATS", "320")),
    int(os.environ.get("PORTFOLIO_SQL_REPEATS", "960")),
    int(os.environ.get("PORTFOLIO_HTML_REPEATS", "320")),
    int(os.environ.get("PORTFOLIO_JS_REPEATS", "480")),
)


def corpus() -> list[tuple[object, str]]:
    d, m, n = rng.randint(2, 9), rng.randint(2, 9), rng.randint(0, 9999)
    jobs = [
        (PythonLexer, _PY_TEMPLATE, _REPEATS[0]),
        (SqlLexer, _SQL_TEMPLATE, _REPEATS[1]),
        (HtmlLexer, _HTML_TEMPLATE, _REPEATS[2]),
        (JavascriptLexer, _JS_TEMPLATE, _REPEATS[3]),
    ]
    mixes: list[tuple[object, str]] = []
    for lexer_cls, template, repeats in jobs:
        mixes.append((lexer_cls(), template.format(d=d, m=m, n=n) * repeats))
    return mixes


def main() -> None:
    mixes = corpus()

    def pass_once() -> int:
        token_count = 0
        for lexer, text in mixes:
            # Materialize the generator: this is the hot lexing loop.
            for _token in lex(text, lexer):
                token_count += 1
        return token_count

    pass_once()  # in-process warmup (harness also does a warmup repeat)
    start = time.perf_counter()
    token_count = pass_once()
    elapsed = time.perf_counter() - start
    print(json.dumps({"seconds": elapsed, "tokens": token_count}))


if __name__ == "__main__":
    main()
