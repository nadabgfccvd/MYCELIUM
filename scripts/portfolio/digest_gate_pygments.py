#!/usr/bin/env python3
"""P1 correctness gate for the first-char-dispatch variant (Cycle 7).

Lexes a fixed, varied corpus with 9 lexers using get_tokens_unprocessed and
prints a sha256 over the exact token stream. The digest produced by the
patched lexer must equal the pinned upstream digest; the MYCELIUM manifest
runs this as test_command *under the variant*, so a dispatch bug that changes
tokens makes the sweep refuse to measure anything.

The official pygments test suite (5215 tests) is the stronger gate and is run
by reproduce_portfolio.sh with an exact-count assertion; this script is the
fast per-sweep gate that needs no pytest.

Usage: python digest_gate_pygments.py [--print]
Exits 0 when the digest matches EXPECTED, 1 otherwise.
"""
from __future__ import annotations

import hashlib
import sys

from pygments.lexers import (
    ArturoLexer,
    BashLexer,
    CppLexer,
    HtmlLexer,
    JavascriptLexer,
    JsonLexer,
    MarkdownLexer,
    PythonLexer,
    SqlLexer,
)

# Pinned digest computed on pristine pygments 2.20.0 (tag checkout @ 708197d).
# Baseline and the first-char-dispatch variant both produce it; the corpus
# exercises the end-of-text path (Markdown links/tables, HTML comments and the
# Arturo '---' EOF-string state, whose zero-width \Z closing token is emitted
# *at* pos == len(text) -- the exact edge an early "if pos >= ln: return"
# implementation drops).
EXPECTED = "89221512d18c359ea3cdc8ece6b29fca48c4ad2408275e4adf517c10ff238bc6"

_CORPUS: dict[str, list[str]] = {
    "py": [
        "def f(x):\n    return [i for i in range(x) if i%2==0]\n",
        "class A:\n    def m(self):\n        return {'a': 1, \"b\": [1,2]}\n",
        "import os\nprint(f'{x=}', 1e-3, None, True, ...)",
    ],
    "sql": [
        "SELECT a, b FROM t WHERE a > 1 AND b IS NULL ORDER BY a;\n",
        "INSERT INTO t VALUES (1, 'x''y', 2.0);\n",
        "CREATE VIEW v AS SELECT * FROM t JOIN u ON t.id=u.id;\n",
    ],
    "html": [
        "<html><body class='x'><a href=\"/a?b=1&c=2\">l</a><!-- c --></body></html>\n",
        "<div id=d style='color:red'>text &amp; <b>b</b></div>\n",
    ],
    "json": [
        '{"a": [1, 2.0, null, true, -3], "b": "str\\n"}\n',
        '[{}, {"x": 3.14e-2}]',
    ],
    "bash": [
        "#!/bin/bash\nfor i in $(seq 1 3); do\n  echo \"i=$i\" && ls -la | grep -v '^d'\ndone\n",
        "if [ -f /etc/hosts ]; then cat /etc/hosts; fi\n",
    ],
    "cpp": [
        "#include <vector>\nint main(){ auto v = std::vector<int>{1,2}; return v.size(); }\n",
        "template<class T> T add(T a,T b){return a+b;} // c\n",
    ],
    "js": [
        "const f = async (x) => x?.y ?? 0;\n",
        "class A extends B { constructor(){ super(); this.x = `t ${1+2}`; } }\n",
    ],
    "md": [
        "# H\n\n- a **b** `c`\n\n```python\nprint(1)\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n[link](http://x.com?a=1)\n",
    ],
    # End-of-text zero-width rule: '---' enters Arturo's inside-eof-string
    # state, whose r'\Z' rule emits a closing quote token at pos == len(text).
    "arturo": ["---abc", "x --- y"],
}


def compute_digest() -> str:
    order = [
        PythonLexer, SqlLexer, HtmlLexer, JsonLexer, BashLexer,
        CppLexer, JavascriptLexer, MarkdownLexer, ArturoLexer,
    ]
    digest = hashlib.sha256()
    for lexer_cls, samples in zip(order, _CORPUS.values()):
        lexer = lexer_cls()
        for text in samples:
            tokens = list(lexer.get_tokens_unprocessed(text))
            digest.update(repr(tokens).encode("utf-8"))
    return digest.hexdigest()


def main() -> int:
    actual = compute_digest()
    if "--print" in sys.argv or EXPECTED == "PINNED_AT_SETUP":
        print(actual)
    if EXPECTED == "PINNED_AT_SETUP":
        return 0
    if actual != EXPECTED:
        print(f"digest gate FAILED: expected {EXPECTED}, got {actual}", file=sys.stderr)
        return 1
    print(f"digest gate OK: {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
