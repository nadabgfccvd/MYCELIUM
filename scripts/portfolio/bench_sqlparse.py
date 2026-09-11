#!/usr/bin/env python3
"""P2 benchmark workload: sqlparse under PYTHONOPTIMIZE=1 (Cycle 7 portfolio).

Timed one-pass parse+format over a deterministic corpus generated from
MYCELIUM_SEED (paired: baseline and variant get the same SQL per seed). The
archived effect was small (-2.1% on the whole command, p=0.031); this script
reproduces the methodology, not the host-specific number.
Prints ``{"seconds": <float>}``.
"""
from __future__ import annotations

import json
import os
import random
import time

# NOTE: sqlparse is imported lazily inside main(), inside the timed region,
# so the PYTHONOPTIMIZE effect on import/assert bytecode is measured.

seed = int(os.environ.get("MYCELIUM_SEED", "101"))
rng = random.Random(seed)


def corpus() -> list[str]:
    statements = [
        "SELECT id_{n}, name_{n}, count(*) AS c_{n} FROM users u{n} "
        "JOIN orders o{n} ON u{n}.id = o{n}.uid WHERE o{n}.total > {d} "
        "GROUP BY id_{n}, name_{n} HAVING count(*) > {m} ORDER BY id_{n} DESC;",
        "INSERT INTO t{n} (a, b, c) VALUES ({d}, 'str {n}', {m}), "
        "({d}, 'other {n}', NULL);",
        "CREATE VIEW v{n} AS SELECT * FROM t{n} JOIN u{n} ON t{n}.id = u{n}.id;",
        "WITH w{n} AS (SELECT id, row_number() OVER (PARTITION BY a ORDER BY b) "
        "AS rn FROM t{n}) SELECT * FROM w{n} WHERE rn <= {d};",
    ]
    count = int(os.environ.get("PORTFOLIO_SQL_COUNT", "440"))
    out: list[str] = []
    for _ in range(count):
        tpl = rng.choice(statements)
        out.append(tpl.format(n=rng.randrange(10_000), d=rng.randrange(1, 99),
                              m=rng.randrange(2, 50)))
    return out


def main() -> None:
    # The archived run timed nearly the whole command (metric ~= wall time,
    # import included): the timer wraps library import + corpus + one pass so
    # the PYTHONOPTIMIZE effect on import/assert code is measured.
    start = time.perf_counter()
    import sqlparse  # noqa: PLC0415

    sql = corpus()
    checksum = 0
    for text in sql:
        parsed = sqlparse.parse(text)
        rendered = sqlparse.format(
            text, reindent=True, keyword_case="upper", identifier_case="lower"
        )
        checksum += len(parsed[0].tokens) + len(rendered)
    elapsed = time.perf_counter() - start
    print(json.dumps({"seconds": elapsed, "checksum": checksum}))


if __name__ == "__main__":
    main()
