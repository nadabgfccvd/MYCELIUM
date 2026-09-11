#!/usr/bin/env python3
"""P2/P3 correctness gate: outputs must be byte-identical under -O.

The variant only sets PYTHONOPTIMIZE=1; it must never change results, only
skip debug overhead. This gate renders a fixed corpus and compares its
sha256 against the pinned digest computed on the unoptimized interpreter.
It runs as test_command *under the variant env*; a digest mismatch makes the
sweep refuse to measure.

Uses explicit checks (not ``assert``) because -O strips assert statements
from this very file.

Usage: python digest_gate_pylib.py sqlparse
       python digest_gate_pylib.py tabulate [--print]
"""
from __future__ import annotations

import hashlib
import sys

_PINS = {
    # Pinned on sqlparse 0.6.0 / tabulate 0.10.0 with -O OFF; both modes must
    # match. Re-pin deliberately if the corpus or the pinned library changes.
    "sqlparse": "f310104ca3d121e746cd45c438606460aaaa548a502927a7c6e7dfb0f724de95",
    "tabulate": "df90f74d3244efc7afea608177a8b6f9258168f8dc410e50396e3e848f83a74b",
}


def _sqlparse_digest() -> str:
    import sqlparse

    statements = [
        "SELECT a, b FROM t WHERE a > 1 AND b IS NULL ORDER BY a;",
        "INSERT INTO t VALUES (1, 'x''y', 2.0), (3, 'z', NULL);",
        "WITH w AS (SELECT id, row_number() OVER (PARTITION BY a ORDER BY b) "
        "AS rn FROM t) SELECT * FROM w WHERE rn <= 2;",
        "select foo,bar from baz where qux='lit''eral' -- trailing\n;",
    ]
    digest = hashlib.sha256()
    for text in statements:
        parsed = sqlparse.parse(text)
        digest.update(repr([(t.ttype, t.value) for t in parsed[0].flatten()]).encode())
        digest.update(
            sqlparse.format(text, reindent=True, keyword_case="upper").encode()
        )
    return digest.hexdigest()


def _tabulate_digest() -> str:
    from tabulate import tabulate

    table = [
        ["spam", 41.9999, "and eggs"],
        ["eggs", 451.0, "more (spam)"],
        ["more", 0.1, ""],
    ]
    headers = ["item", "qty", "notes"]
    digest = hashlib.sha256()
    for fmt in ("grid", "fancy_grid", "pipe", "orgtbl", "rst", "mediawiki",
                "latex", "tsv"):
        digest.update(tabulate(table, headers=headers, tablefmt=fmt).encode())
        digest.update(
            tabulate(
                [[1, 2.0 / 3.0], [4, 5.0 / 7.0]],
                headers=("a", "b"),
                tablefmt=fmt,
                floatfmt=".6f",
            ).encode()
        )
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in _PINS:
        print("usage: digest_gate_pylib.py {sqlparse|tabulate} [--print]",
              file=sys.stderr)
        return 2
    lib = argv[1]
    actual = _sqlparse_digest() if lib == "sqlparse" else _tabulate_digest()
    if "--print" in argv or _PINS[lib].startswith("PINNED_AT_SETUP"):
        print(actual)
        if _PINS[lib].startswith("PINNED_AT_SETUP"):
            return 0
    if actual != _PINS[lib]:
        print(f"digest gate FAILED ({lib}): expected {_PINS[lib]}, got {actual}",
              file=sys.stderr)
        return 1
    print(f"digest gate OK ({lib}): {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
