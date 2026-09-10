#!/usr/bin/env python3
"""F3: verifica continuidade de runs fatiadas no audit.log.jsonl + telemetry."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mycelium_accel.telemetry import metrics_count  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="verify sliced-run continuity")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--min-rounds", type=int, default=1)
    args = parser.parse_args()

    state_dir = Path(args.state_dir)
    audit = state_dir / "audit.log.jsonl"
    if not audit.exists():
        print(f"FALHA: {audit} não existe")
        return 1

    rounds: list[int] = []
    exceptions = 0
    for line in audit.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "round":
            rounds.append(int(event.get("payload", {}).get("round", -1)))
        if event.get("event") in {"exception", "error"}:
            exceptions += 1

    checks = []
    checks.append(("rounds>0", len(rounds) > 0, f"{len(rounds)} rounds no audit"))
    monotonic = all(b > a for a, b in zip(rounds, rounds[1:])) if rounds else False
    checks.append(("rounds crescentes sem reset", monotonic, f"primeiro={rounds[0] if rounds else '-'} último={rounds[-1] if rounds else '-'}"))
    checks.append(("rounds >= min", len(rounds) >= args.min_rounds, f"{len(rounds)}>={args.min_rounds}"))
    durable = metrics_count(state_dir)
    checks.append(("telemetry cobre audit", durable >= len(rounds), f"jsonl={durable} audit={len(rounds)}"))
    checks.append(("sem exceções", exceptions == 0, f"exceptions={exceptions}"))

    ok = True
    for name, passed, detail in checks:
        print(f"[{'OK' if passed else 'FALHA'}] {name}: {detail}")
        ok = ok and passed
    print("CONTINUIDADE VERIFICADA" if ok else "CONTINUIDADE FALHOU")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
