#!/usr/bin/env python3
"""P4 correctness gate: the translate fast-path must be byte-identical.

Renders a FIXED multilingual corpus (plus edge codepoints) under every public
``errors`` policy and hashes the results. Baseline (pristine 1.3.8) and the
patched variant must produce the same sha256; a mismatch makes the sweep
refuse to measure. The digest is also identical under ``PYTHONOPTIMIZE=1``.

Uses explicit ``if``/``sys.exit`` (not ``assert``) so it also works with -O.

Usage: python digest_gate_unidecode.py            # verify (needs unidecode)
       python digest_gate_unidecode.py --print    # print the digest for pinning
"""
from __future__ import annotations

import hashlib
import sys

# Pinned on Unidecode 1.3.8 (commit a31eb5f, tag unidecode-1.3.8). Verified
# byte-identical on pristine vs the translate-fast-path patch, normal and -O.
# Re-pin deliberately if the corpus or the pinned version changes.
PINNED = "1706a5922b4dab0fb14ab23fb3dbaf8f3a4b40c2a3fb852fcb42716c98bd526c"

CORPUS = [
    # Latin-1 / Latin Extended (accented European)
    "À peine garçon ça été über München naïve coeur Ångström naïveté résumé.",
    # Greek + punctuation
    "Ξεσκεπάζω τὴν ψυχοφθόρα βδελυγμία. Αλφάβητος αβγ δεζ ήθικλ μνξ οπρς τυφχψω!",
    # Cyrillic
    "Съешь же ещё этих мягких французских булок, да выпей чаю. Привет, мир 123.",
    # Hebrew
    "זהו משפט לבדיקה בעברית עם מילים ואפילו מספרים 12345 וסימנים.",
    # Arabic
    "هذا اختبار للتحويل الصوتي للحروف العربية مع أرقام ١٢٣ وعلامات، مرحبا.",
    # Devanagari (Hindi)
    "यह हिंदी में एक परीक्षण वाक्य है जिसमें संख्या १२३ और विराम हैं।",
    # Japanese hiragana + katakana + CJK
    "これはテストです。カタカナとひらがな、漢字の混在。東京は日本の首都です。",
    # Hangul
    "이것은 한국어 테스트 문장입니다. 숫자 123과 마침표. 안녕하세요 세계.",
    # ASCII must pass through untouched
    "Plain ASCII: The quick brown fox jumps over the lazy dog. 0123456789.",
    # Edge codepoints: unassigned-BMP/PUA (>0xeffff), <0x80, a nonbreaking space
    "Edge: \uf000 (PUA BMP), \U0010ffff (above tables),\xa0done.",
]


def render_all() -> bytes:
    import warnings

    from unidecode import unidecode

    h = hashlib.sha256()
    for text in CORPUS:
        for errors, replace in (
            ("ignore", "?"),
            ("replace", "#"),
            ("preserve", "?"),
        ):
            h.update(repr(unidecode(text, errors=errors, replace_str=replace)).encode())
    # strict policy must raise on the PUA text, with a stable index
    try:
        unidecode("a\uf000b", errors="strict")
        h.update(b"NO_STRICT_RAISE")
    except Exception as exc:  # noqa: BLE001 - hashing the exact type+index
        h.update((type(exc).__name__ + ":" + str(getattr(exc, "index", None))).encode())
    # Surrogates: warnings expected, but output still defined
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        h.update(repr(unidecode("a\ud83db")).encode())
        h.update(f"surrogate_warnings:{len(caught)}".encode())
    return h.hexdigest().encode()


def main(argv: list[str]) -> int:
    digest = render_all().decode()
    if "--print" in argv or PINNED.startswith("PINNED_AT_SETUP"):
        print(digest)
        return 0
    if digest != PINNED:
        print(
            f"digest gate FAILED (unidecode): expected {PINNED}, got {digest}",
            file=sys.stderr,
        )
        return 1
    print(f"digest gate OK (unidecode): {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
