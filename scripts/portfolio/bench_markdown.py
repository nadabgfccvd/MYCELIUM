#!/usr/bin/env python3
"""P6 benchmark workload: Markdown 3.8 under PYTHONOPTIMIZE=1 (S2 Cycle 7).

Render a deterministic markdown document with the same extensions as the
digest gate; the corpus is generated from MYCELIUM_SEED so baseline and
variant render identical input per seed. Import is timed (the -O effect on
import/assert bytecode is included).

Prints ``{"seconds": <float>, "checksum": <int>}``.
"""
from __future__ import annotations

import json
import os
import random
import time

seed = int(os.environ.get("MYCELIUM_SEED", "101"))
rng = random.Random(seed)
blocks = int(os.environ.get("PORTFOLIO_MD_BLOCKS", "6000"))


def document() -> str:
    out: list[str] = []
    for i in range(blocks):
        kind = i % 6
        if kind == 0:
            out.append(f"## Section {i}\n\nText with **bold {i}**, *em {i}* and "
                       f"`code_{i}` plus [link {i}](https://x/{i}).\n")
        elif kind == 1:
            out.append("\n".join(f"- item {i}.{j} `v{j}`" for j in range(6)) + "\n")
        elif kind == 2:
            out.append(f"```python\ndef f_{i}(x):\n    return x + {i}\n```\n")
        elif kind == 3:
            out.append(f"| A | B |\n|---|---|\n| {i} | {i * 2} |\n| {i+1} | {i-1} |\n")
        elif kind == 4:
            out.append(f"> Quote line {i}\n> continued {i+1}\n\n")
        else:
            out.append(f"1. first {i}\n2. second {i}\n3. third {i}\n\n")
    return "\n".join(out)


def main() -> None:
    start = time.perf_counter()
    import markdown  # noqa: PLC0415

    text = document()
    html = markdown.markdown(
        text, extensions=["fenced_code", "tables", "toc", "footnotes", "attr_list"])
    elapsed = time.perf_counter() - start
    print(json.dumps({"seconds": elapsed, "checksum": len(html)}))


if __name__ == "__main__":
    main()
