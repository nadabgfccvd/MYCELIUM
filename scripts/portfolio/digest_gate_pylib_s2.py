#!/usr/bin/env python3
"""P5/P6 correctness gate: outputs byte-identical under PYTHONOPTIMIZE=1.

The S2 Cycle-7 env variants only set PYTHONOPTIMIZE=1 (skip assert/__debug__
bytecode); they must never change results. Hashes a fixed corpus with the
pinned library versions, normal and -O; a mismatch makes the sweep refuse to
measure. Explicit checks only (this file itself runs under -O, which strips
``assert``).

Usage: python digest_gate_pylib_s2.py natsort|markdown [--print]
"""
from __future__ import annotations

import hashlib
import sys

_PINS = {
    # natsort 8.4.0 / Markdown 3.8; pinned with -O OFF, verified identical -O ON.
    "natsort": "01efd7ff2225d0770cfefc1c5fce05397f146e07ffb9b2aa81e69db5a6f87c65",
    "markdown": "61d4a1734919e5248d7747fed1253a61e973f7e683b5c6adbe7a72b30eeef0bf",
}


def _natsort_digest() -> str:
    import natsort
    from natsort import ns

    tricky = [
        "file10.txt", "file2.txt", "file1.txt", "File20.txt", "file100.txt",
        "a-1.2", "a-1.10", "a-1.02", "b+5", "b-7", "b 009",
        "v2.0.10", "v2.0.2", "v2.0.0-beta", "v2.0.0", "v10.0",
        "img_0001.png", "IMG_002.PNG", "img_0010.jpeg",
        "12 apples", "2 apples", "1 apple", "120 apples",
        "x.5e3", "x.5e2", "x.5000", "xInf", "x-inf",
        "zero", "0", "-1", "1.0", "1.00", "1_000",
    ]
    digest = hashlib.sha256()
    algos = [ns.DEFAULT, ns.IGNORECASE, ns.REAL, ns.LOWERCASEFIRST,
             ns.GROUPLETTERS, ns.NUMAFTER]
    for alg in algos:
        digest.update(repr(natsort.natsorted(tricky, alg=alg)).encode())
        digest.update(repr(natsort.natsorted(tricky, alg=alg, reverse=True)).encode())
        digest.update(repr(natsort.order_by_index(
            tricky, natsort.index_natsorted(tricky, alg=alg))).encode())
    # numeric/version key paths
    for value in tricky[:6]:
        digest.update(repr(natsort.natsort_key(value)).encode())
    keygen = natsort.natsort_keygen(alg=ns.REAL)
    digest.update(repr([keygen(v) for v in tricky[:8]]).encode())
    return digest.hexdigest()


def _markdown_digest() -> str:
    import markdown

    doc = """# Heading One

A paragraph with **bold**, *italic*, ***both***, `inline code`, a
[link](https://example.com/path) and an ![image](img.png).

## Lists

- first
- second
  - nested alpha
  - nested beta
- third

1. one
2. two
3. three

> A blockquote spanning
> two lines.

```python
def f(x):
    return x + 1  # code fence
```

| Col A | Col B |
|-------|-------|
| 1     | 2     |
| 3     | 4     |

A footnote ref[^1] and an autolink <https://auto.example>.

Term
:   Definition

* * *

<a href="x" title="t">raw html</a> & amp; entities &#65;

[^1]: footnote body text.
"""
    digest = hashlib.sha256()
    extension_sets = [
        ["fenced_code", "tables", "toc"],
        ["fenced_code", "footnotes", "sane_lists", "attr_list"],
        ["extra", "admonition", "def_list", "md_in_html"],
    ]
    for extensions in extension_sets:
        try:
            html = markdown.markdown(
                doc, extensions=extensions, output_format="html")
        except Exception as exc:  # noqa: BLE001 - extension availability is data
            digest.update(("ERROR:" + type(exc).__name__).encode())
            continue
        digest.update(html.encode())
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in _PINS:
        print("usage: digest_gate_pylib_s2.py {natsort|markdown} [--print]",
              file=sys.stderr)
        return 2
    lib = argv[1]
    actual = _natsort_digest() if lib == "natsort" else _markdown_digest()
    if "--print" in argv or _PINS[lib].startswith("PINNED_AT_SETUP"):
        print(actual)
        return 0
    if actual != _PINS[lib]:
        print(f"digest gate FAILED ({lib}): expected {_PINS[lib]}, got {actual}",
              file=sys.stderr)
        return 1
    print(f"digest gate OK ({lib}): {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
