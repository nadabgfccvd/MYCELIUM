"""H1.1: `accelerate init` wizard — interactive manifest scaffolding.

Auto-detection (B3) guesses the manifest; `--wizard` refines it through 5
questions and `--yes` accepts it non-interactively. Both print copy-pasteable
next steps so a new user reaches the first HTML report in < 5 minutes.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .targets.base import TargetManifest, Variant

AskFn = Callable[[str, str], str]  # (prompt, default) -> answer


def ask_cli(prompt: str, default: str) -> str:
    try:
        answer = input(f"{prompt} [{default}]: ").strip()
    except EOFError:
        raise SystemExit(
            "mycelium-accel: init --wizard needs interactive input "
            "(stdin closed); use --yes for defaults"
        )
    return answer or default


def run_wizard(detected: TargetManifest, ask: AskFn = ask_cli) -> TargetManifest:
    """Refine an auto-detected manifest in place; returns it."""
    benchmark = ask("Benchmark command", detected.benchmark_command or "")
    if benchmark:
        detected.benchmark_command = benchmark
    detected.metric_name = ask("Metric name", detected.metric_name)
    lower = ask("Lower is better? (y/n)", "y" if detected.lower_is_better else "n")
    detected.lower_is_better = lower.strip().lower().startswith("y")
    repeats = ask("Repeats per seed", str(detected.repeats))
    try:
        detected.repeats = max(1, int(repeats))
    except ValueError:
        raise SystemExit(f"mycelium-accel: invalid repeats {repeats!r} (integer >= 1)")
    name = ask("Add one example env variant? (name, empty to skip)", "")
    if name:
        pair = ask(f"Env for variant {name!r} (VAR=value, empty for none)", "")
        env: dict[str, str] = {}
        if "=" in pair:
            key, value = pair.split("=", 1)
            if key.strip():
                env[key.strip()] = value.strip()
        detected.variants.append(Variant(
            name=name, mode="env", env=env,
            description="example variant from init wizard (edit me)"))
    return detected


def next_steps(manifest_path: Path) -> str:
    target = manifest_path.parent
    return (
        "Next steps (copy-paste):\n"
        f"  1. Review: {manifest_path}\n"
        f"  2. Check:  mycelium-accel doctor --target {target}\n"
        f"  3. Run:    mycelium-accel accelerate --target {target} --no-apply\n"
        f"  4. Open:   {target}/.mycelium_benchmarks/sweep-*.html\n"
    )
