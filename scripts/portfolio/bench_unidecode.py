#!/usr/bin/env python3
"""P4 benchmark workload: Unidecode 1.3.8 (S2 Cycle-7 portfolio).

Transliterate a deterministic, *realistic* multilingual document (a small
vocabulary sampled with repetition, like natural text) from MYCELIUM_SEED.
Paired: baseline and variant transliterate the exact same document per seed.

The variant (docs/data/portfolio/unidecode_translate_fastpath.patch) replaces
the per-character Python loop in ``_unidecode`` with a one-shot C-level
``str.translate`` table for the default errors='ignore' path; every other
error mode and surrogates fall back to the original loop. Results are proven
identical by digest_gate_unidecode.py and by Unidecode's own 62-test suite
(see scripts/reproduce_portfolio_s2.sh).

Prints ``{"seconds": <float>, "checksum": <int>}``.
"""
from __future__ import annotations

import json
import os
import random
import time

# Unicode blocks that Unidecode ships tables for (each loads an x### module).
SCRIPT_RANGES = [
    (0x00C0, 0x024F),  # Latin Extended / IPA
    (0x0370, 0x03FF),  # Greek
    (0x0400, 0x04FF),  # Cyrillic
    (0x0590, 0x05F4),  # Hebrew
    (0x0600, 0x06FF),  # Arabic
    (0x0900, 0x097F),  # Devanagari
    (0x3040, 0x30FF),  # Hiragana + Katakana
    (0x4E00, 0x4F7F),  # CJK subset (a few dense sections)
    (0xAC00, 0xACCA),  # Hangul subset
]


def build_document(seed: int) -> str:
    rng = random.Random(seed)
    # A finite vocabulary -> realistic character repetition (this is what the
    # str.translate fast path exploits; natural text is far from uniform).
    vocab = []
    for _ in range(500):
        start, end = rng.choice(SCRIPT_RANGES)
        length = rng.randrange(3, 9)
        vocab.append("".join(chr(rng.randrange(start, end + 1)) for _ in range(length)))
    words = [rng.choice(vocab) for _ in range(60_000)]
    return " ".join(words) + ". 123 done."  # dense non-ASCII, single-space joins


def main() -> None:
    seed = int(os.environ.get("MYCELIUM_SEED", "101"))
    doc = build_document(seed)

    import unidecode  # noqa: PLC0415

    unidecode.unidecode(doc[:1000])  # prime section tables before timing
    t0 = time.perf_counter()
    out = unidecode.unidecode(doc)
    elapsed = time.perf_counter() - t0
    checksum = sum(out.encode("ascii")) + len(out)  # default mode must be pure ASCII
    print(json.dumps({"seconds": elapsed, "checksum": checksum}))


if __name__ == "__main__":
    main()
