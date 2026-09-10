from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mycelium_accel.config import Config
from mycelium_accel.engine import MyceliumEngine
from mycelium_accel.runtime_profile import load_default_profile
from mycelium_accel.state import state_file


def bench(label: str, **config_kwargs: object) -> dict[str, object]:
    temp_dir = tempfile.mkdtemp(prefix="mycelium-bench-")
    try:
        state_dir = Path(temp_dir) / "state"
        config = Config(state_dir=str(state_dir), **config_kwargs)
        engine = MyceliumEngine(config)
        engine.init_state()
        started = time.perf_counter()
        summary = engine.run(30)
        elapsed = time.perf_counter() - started
        state_path = state_file(state_dir, config.persistence_backend)
        return {
            "profile": label,
            "rounds": summary.rounds_executed,
            "seconds": elapsed,
            "rounds_per_second": summary.rounds_executed / elapsed,
            "growth_regime": summary.growth_regime,
            "persistence_backend": config.persistence_backend,
            "state_bytes": state_path.stat().st_size,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> None:
    active_profile = load_default_profile()
    results = [
        bench(
            "default",
            seed=101,
            **active_profile,
        ),
        bench(
            "default_json_compare",
            seed=101,
            **(active_profile | {"persistence_backend": "json"}),
        ),
        bench(
            "default_pickle_compare",
            seed=101,
            **(active_profile | {"persistence_backend": "pickle"}),
        ),
        bench(
            "quality_reference",
            seed=101,
            family_count=9,
            family_size=15,
            challenges_per_round=3,
            train_cases=8,
            test_cases=16,
            checkpoint_every=10,
            state_save_every=10,
            probe_challenges=2,
            probe_train_cases=3,
            probe_test_cases=6,
            full_rescore_top_k=6,
            full_rescore_random_k=1,
            persistence_backend="json",
        ),
        bench(
            "turbo",
            seed=101,
            family_count=7,
            family_size=10,
            challenges_per_round=2,
            train_cases=6,
            test_cases=10,
            max_program_depth=4,
            max_program_nodes=31,
            checkpoint_every=20,
            state_save_every=10,
            probe_challenges=2,
            probe_train_cases=2,
            probe_test_cases=4,
            full_rescore_top_k=4,
            full_rescore_random_k=1,
            persistence_backend="json",
        ),
    ]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
