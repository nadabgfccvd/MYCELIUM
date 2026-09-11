"""S2.6 — permanent dead-code guard (vulture reachability).

Ciclo 6 (Limpeza Geral) found the shipped package and ``scripts/`` to be free
of unreachable code at vulture confidence >= 90 (only *certain* findings;
dynamic/entry-point code reports ~60 and never trips this). This test keeps
that true: a new unused function/method/class/import/variable in the code we
ship fails the suite before it can accumulate.

``tests/`` is deliberately NOT scanned: test doubles, callbacks (e.g.
``lambda ri, s: ...``) and context-manager ``__exit__`` stubs legitimately
declare parameters that satisfy a protocol but go unused, which would be
noise rather than dead code.
"""
from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

try:
    import vulture  # noqa: F401  (import-as-feature-flag)
except ImportError:  # pragma: no cover - minimal envs without [dev]
    vulture = None  # type: ignore[assignment]


@unittest.skipUnless(vulture is not None, "vulture is a [dev] extra (dead-code gate)")
class NoDeadCodeTests(unittest.TestCase):
    CONFIDENCE = 90

    def test_shipped_code_has_no_certainly_unused_definitions(self) -> None:
        v = vulture.Vulture()
        v.scavenge([ROOT / "mycelium_accel", ROOT / "scripts"])
        dead = [
            item for item in v.get_unused_code()
            if item.confidence >= self.CONFIDENCE
        ]
        self.assertEqual(
            [(i.filename, i.first_lineno, i.typ, i.name) for i in dead],
            [],
            msg=(
                "vulture: ship-worthy code must not contain certainly-unused "
                "definitions; delete the code or, if it is a real public/"
                "dynamic entry point, lower-confidence is already tolerated "
                "(threshold 90)."
            ),
        )


if __name__ == "__main__":
    unittest.main()
