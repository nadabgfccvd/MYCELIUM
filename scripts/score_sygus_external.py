#!/usr/bin/env python3
"""C2 validation: score an engine champion against EXTERNAL SyGuS ground truth.

Trains the engine once (procedural internal challenges), then freezes the
champion and measures exact-match on held-out SyGuS pairs — oracle and
solution fully decoupled (structural cause #2 of saturation, addressed as a
measurement channel).

Expected honest outcome: LOW scores (the engine never saw these functions).
The deliverable is the channel + the number, not transfer.

Usage:
    python scripts/score_sygus_external.py --corpus /tmp/sygus-benchmarks/comp \
        --rounds 200 --seed 101 --out .mycelium_benchmarks/sygus_external.json
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mycelium_accel.config import Config  # noqa: E402
from mycelium_accel.engine import MyceliumEngine  # noqa: E402
from mycelium_accel.sygus_adapter import (  # noqa: E402
    extract_task,
    scan_corpus,
    score_callable,
    split_pairs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="C2 external-oracle scoring")
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--rounds", type=int, default=200)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--min-examples", type=int, default=5)
    parser.add_argument("--out", default=".mycelium_benchmarks/sygus_external.json")
    args = parser.parse_args()

    scan = scan_corpus(args.corpus, min_examples=args.min_examples)
    print(f"corpus: {scan['n_files']} files, {scan['n_valid']} valid tasks")

    with tempfile.TemporaryDirectory() as tmp:
        engine = MyceliumEngine(Config(seed=args.seed, state_dir=str(Path(tmp) / "s")))
        engine.init_state()
        engine.run(args.rounds)
        state = engine.load_or_init_state()
        champion = max(
            (m for f in state.families for m in f.members), key=lambda o: o.score
        )
        macro_nodes = engine._macro_nodes(state)
        executor = engine._executor_for(champion.genome, macro_nodes, {})

    if executor is None:
        raise SystemExit("champion did not compile (honest abort)")

    rows = []
    for entry in scan["tasks"]:
        task = extract_task(entry["path"], min_examples=args.min_examples)
        _, test = split_pairs(task.examples, args.seed)
        result = score_callable(executor.run, test)
        rows.append({"task": Path(entry["path"]).name, "n_test": len(test),
                     "exact": result["exact"]})
    mean_exact = sum(r["exact"] for r in rows) / len(rows) if rows else 0.0
    report = {
        "champion": champion.genome.render(),
        "champion_score_internal": champion.score,
        "n_tasks": len(rows),
        "mean_external_exact": mean_exact,
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"n_tasks": len(rows), "mean_external_exact": round(mean_exact, 4),
                      "report": str(out)}, indent=2))


if __name__ == "__main__":
    main()
