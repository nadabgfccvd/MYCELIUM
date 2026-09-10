#!/usr/bin/env python3
"""Phase 4 pipeline: evolve, collect elite corpus, learn library by compression.

Runs the engine for N rounds, gathers elites + near-elites + niche winners,
learns abstractions by corpus MDL compression, and persists the learned
library under .mycelium_semantics/ together with reuse statistics. When
--stage is given, abstractions are injected into the engine state staging
area (the normal promotion pipeline still applies).

    python scripts/learn_macro_library.py --rounds 12 --seed 101 --max-abstractions 8 --stage
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mycelium_accel.config import Config
from mycelium_accel.engine import MyceliumEngine
from mycelium_accel.library_learning import (
    abstraction_reuse_stats,
    collect_corpus,
    learn_library,
    learn_meta_rules,
    promote_to_staging,
)
from mycelium_accel.state import load_state, save_state


def main() -> None:
    parser = argparse.ArgumentParser(description="MYCELIUM Auto-evolve corpus-compression library learner")
    parser.add_argument("--rounds", type=int, default=12)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--state-dir", default=".mycelium_state_library")
    parser.add_argument("--max-abstractions", type=int, default=8)
    parser.add_argument("--min-support", type=int, default=2)
    parser.add_argument("--stage", action="store_true", help="inject learned abstractions into macro staging")
    parser.add_argument("--out", default=".mycelium_semantics/learned_library.json")
    args = parser.parse_args()

    config = Config(seed=args.seed, state_dir=args.state_dir)
    engine = MyceliumEngine(config)
    engine.init_state()
    engine.run(args.rounds)
    state = load_state(Path(args.state_dir), config.persistence_backend)

    # corpus: elites + near-elites (top 3) first-class, then whole population for support
    corpus_source = []
    for family in state.families:
        ranked = sorted(family.members, key=lambda m: -m.score)
        corpus_source.extend(member.genome for member in ranked[:3])
    corpus_source.extend(macro.tree for macro in state.macro_library)
    corpus_source.extend(staged.tree for staged in state.macro_staging)
    for family in state.families:  # full population widens support detection
        corpus_source.extend(member.genome for member in family.members)
    corpus = collect_corpus(corpus_source)

    library = learn_library(corpus, max_abstractions=args.max_abstractions, min_support=args.min_support)
    meta_rules = learn_meta_rules(library, corpus)
    stats = abstraction_reuse_stats(library)

    payload = {
        "rounds": args.rounds,
        "corpus_size": len(corpus),
        "corpus_cost_before": library.corpus_cost_before,
        "corpus_cost_after": library.corpus_cost_after,
        "compression_ratio": library.compression_ratio,
        "description_length_reduction": library.reduction,
        "reuse_stats": stats,
        "abstractions": [item.to_dict() for item in library.abstractions],
        "meta_rules": [item.to_dict() for item in meta_rules],
    }
    from mycelium_accel.telemetry import stamp_provenance

    stamp_provenance(payload, "learn_macro_library", args.state_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.stage and library.abstractions:
        staged = promote_to_staging(library, round_index=state.round_index)
        existing = {macro.name for macro in state.macro_staging}
        for macro in staged:
            if macro.name not in existing:
                state.macro_staging.append(macro)
        save_state(Path(args.state_dir), state, config.persistence_backend)
        payload["staged"] = [macro.name for macro in staged]

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
