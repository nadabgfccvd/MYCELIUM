from __future__ import annotations

import argparse
import json
from pathlib import Path

from .acceleration import accelerate_external, accelerate_self
from .config import Config
from .engine import MyceliumEngine
from .runtime_profile import load_default_profile
from .self_improve import SelfImprover, build_guard_from_args
from .state import StateCorruptError, load_state
from datetime import UTC


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MYCELIUM-Accel statistical acceleration harness")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    subparsers = parser.add_subparsers(dest="command", required=False)

    init_parser = subparsers.add_parser("init", help="initialize persistent state")
    _add_common_args(init_parser)

    run_parser = subparsers.add_parser("run", help="run improvement rounds")
    _add_common_args(run_parser)
    run_parser.add_argument("--rounds", type=int, default=10)

    report_parser = subparsers.add_parser("report", help="print current growth report")
    _add_common_args(report_parser)

    rollback_parser = subparsers.add_parser("rollback", help="restore a checkpointed round")
    _add_common_args(rollback_parser)
    rollback_parser.add_argument("--round", dest="rollback_round", type=int, required=True)

    doctor_parser = subparsers.add_parser("doctor", help="check environment: python, gcc, git, toolchains, state perms (B3)")
    doctor_parser.add_argument("--target", default=None, help="also validate mycelium.target.json in this directory")
    doctor_parser.add_argument("--fix", action="store_true", help="apply safe manifest fixes (version stamp, allowlist sort/dedupe)")
    doctor_parser.add_argument("--state-dir", default=".mycelium_state")
    doctor_parser.add_argument("--json", action="store_true", help="machine-readable output")

    accelerate_parser = subparsers.add_parser("accelerate", help="benchmark and apply faster equivalent variants")
    accelerate_parser.add_argument("--target", default="self", help="self, path/to/module.py, or a project directory with a manifest")
    accelerate_parser.add_argument("--manifest", default=None, help="path to mycelium.target.json (generic harness, Phase 1)")
    accelerate_parser.add_argument("--seeds", default="101,103,107,109,113,127,131", help="comma-separated prime seeds for paired benchmarking")
    accelerate_parser.add_argument("--no-apply", action="store_true", help="measure only; do not persist any variant")
    accelerate_parser.add_argument("--dry-run", action="store_true", help="validate target/build/tests without measuring or writing artifacts")
    accelerate_parser.add_argument("--race", action="store_true", help="racing screen: drop futile candidates before the full sweep")
    accelerate_parser.add_argument("--race-seeds", type=int, default=3, help="seeds for the racing screen (>=2; 2 is faster but may drop close winners)")
    accelerate_parser.add_argument("--race-margin", type=float, default=0.0, help="eliminate when screen CI_high < margin")
    accelerate_parser.add_argument("--race-adaptive", action="store_true", help="S3: start screen with race_seeds-1 seeds, extend only when borderline")
    accelerate_parser.add_argument("--reference", default=None, help="reference sweep JSON for the regression gate (needs --fail-on-regression)")
    accelerate_parser.add_argument("--fail-on-regression", type=float, default=None, metavar="PCT", help="exit 1 if baseline is >PCT%% worse than --reference (dual criterion: effect + Welch CI)")
    accelerate_parser.add_argument("--adaptive-repeats", action="store_true", help="stop repeats early per seed when CI is tight (V4.2; 0 verdict flips on replay corpus)")
    accelerate_parser.add_argument("--cache", action="store_true", help="reuse sweep when target content is unchanged (V4.1; requires --no-apply)")
    accelerate_parser.add_argument("--cache-dir", default=None, help="shared cache directory (default: per-target; share across checkouts/users for CI)")
    accelerate_parser.add_argument("--sequential-seeds", action="store_true", help="S1: group-sequential look at 6/7 seeds with OBF alpha-spending (requires exactly 7 seeds)")
    accel_sub = accelerate_parser.add_subparsers(dest="accelerate_action", required=False)
    accel_init = accel_sub.add_parser("init", help="generate mycelium.target.json via auto-detection (B3)")
    accel_init.add_argument("--target", default=".", help="project directory to scaffold a manifest for")
    accel_init.add_argument("--force", action="store_true", help="overwrite an existing manifest")
    accel_init.add_argument("--wizard", action="store_true", help="interactively refine the detected manifest (5 questions)")
    accel_init.add_argument("--yes", action="store_true", help="non-interactive: accept detection, print next steps")

    history_parser = subparsers.add_parser("history", help="compare benchmark sweeps over time (offline HTML)")
    _add_common_args(history_parser)
    history_parser.add_argument("--target", default=".", help="project directory with .mycelium_benchmarks/")
    history_parser.add_argument("--benchmarks-dir", default=None, help="override sweeps directory")
    history_parser.add_argument("--out", default=None, help="output HTML path (default: <sweeps>/history.html)")
    regime_parser = subparsers.add_parser("growth-regime", help="Phase-8 honest growth metrics + regime classification")
    _add_common_args(regime_parser)
    regime_parser.add_argument("--markdown", action="store_true", help="print markdown instead of JSON")
    regime_parser.add_argument("--strict", action="store_true", help="ignore ambient artifacts from other runs (provenance-checked)")

    self_improve_parser = subparsers.add_parser("self-improve", help="run guarded self-improvement cycles")
    _add_common_args(self_improve_parser)
    self_improve_parser.add_argument("--cycles", type=int, default=1)
    self_improve_parser.add_argument("--rounds-per-cycle", type=int, default=20)
    _add_self_improve_args(self_improve_parser)

    daemon_parser = subparsers.add_parser("self-improve-daemon", help="run self-improvement continuously until kill-switch or limit")
    _add_common_args(daemon_parser)
    daemon_parser.add_argument("--rounds-per-cycle", type=int, default=20)
    daemon_parser.add_argument("--sleep-seconds", type=float, default=0.0)
    daemon_parser.add_argument("--max-cycles", type=int, default=None)
    _add_self_improve_args(daemon_parser)

    return parser


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    profile = load_default_profile()
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--state-dir", default=".mycelium_state")
    parser.add_argument("--family-count", type=int, default=profile["family_count"])
    parser.add_argument("--family-size", type=int, default=profile["family_size"])
    parser.add_argument("--challenges-per-round", type=int, default=profile["challenges_per_round"])
    parser.add_argument("--train-cases", type=int, default=profile["train_cases"])
    parser.add_argument("--test-cases", type=int, default=profile["test_cases"])
    parser.add_argument("--initial-difficulty", type=int, default=profile["initial_difficulty"])
    parser.add_argument("--max-program-depth", type=int, default=profile["max_program_depth"])
    parser.add_argument("--max-program-nodes", type=int, default=profile["max_program_nodes"])
    parser.add_argument("--max-abs-value", type=int, default=profile["max_abs_value"])
    parser.add_argument("--max-eval-steps", type=int, default=profile["max_eval_steps"])
    parser.add_argument("--max-macros", type=int, default=profile["max_macros"])
    parser.add_argument("--checkpoint-every", type=int, default=profile["checkpoint_every"])
    parser.add_argument("--state-save-every", type=int, default=profile["state_save_every"])
    parser.add_argument("--probe-challenges", type=int, default=profile["probe_challenges"])
    parser.add_argument("--probe-train-cases", type=int, default=profile["probe_train_cases"])
    parser.add_argument("--probe-test-cases", type=int, default=profile["probe_test_cases"])
    parser.add_argument("--full-rescore-top-k", type=int, default=profile["full_rescore_top_k"])
    parser.add_argument("--full-rescore-random-k", type=int, default=profile["full_rescore_random_k"])
    parser.add_argument("--persistence-backend", choices=["json", "pickle"], default=profile["persistence_backend"])
    parser.add_argument("--climate-weight", type=float, default=profile["climate_weight"])
    parser.add_argument("--novelty-weight", type=float, default=profile["novelty_weight"])
    parser.add_argument("--macro-potential-weight", type=float, default=profile["macro_potential_weight"])
    parser.add_argument("--transfer-weight", type=float, default=profile["transfer_weight"])
    parser.add_argument("--macro-support-threshold", type=int, default=profile["macro_support_threshold"])
    parser.add_argument("--macro-transfer-threshold", type=float, default=profile["macro_transfer_threshold"])
    parser.add_argument("--macro-retire-rounds", type=int, default=profile["macro_retire_rounds"])
    parser.add_argument("--compositional-challenge-rate", type=float, default=profile["compositional_challenge_rate"])
    parser.add_argument("--niche-probe-count", type=int, default=profile["niche_probe_count"])
    parser.add_argument("--frontier-archive-limit", type=int, default=profile["frontier_archive_limit"])
    parser.add_argument("--frontier-window", type=int, default=profile["frontier_window"])
    parser.add_argument("--gene-splice-rate", type=float, default=profile["gene_splice_rate"])
    parser.add_argument("--shrink-mutation-rate", type=float, default=profile["shrink_mutation_rate"])
    parser.add_argument("--semantic-mutation-rate", type=float, default=float(profile.get("semantic_mutation_rate", 0.0)), help="Phase 3: fraction of mutations delegated to semantic operators")
    parser.add_argument("--semantic-probe-count", type=int, default=int(profile.get("semantic_probe_count", 7)))
    parser.add_argument("--counterexample-limit", type=int, default=int(profile.get("counterexample_limit", 256)))
    parser.add_argument("--counterexample-harvest-top-k", type=int, default=int(profile.get("counterexample_harvest_top_k", 8)))
    parser.add_argument("--anti-forgetting", action="store_true", help="C1: re-inject elite genome after patience rounds of decline")
    parser.add_argument("--ecology-reseed-rounds", type=int, default=0, help="C1: reseed worst family after K stalled frontier rounds (0=off)")
    parser.add_argument("--ecology-patience", type=int, default=8)
    parser.add_argument("--adaptive-novelty", action="store_true", help="C1: 3x novelty when niches collapse")


def _add_self_improve_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--benchmark-rounds", type=int, default=30)
    parser.add_argument("--benchmark-seeds", default="101,103,107,109,113,127,131")
    parser.add_argument("--guard-workers", type=int, default=4)
    parser.add_argument("--time-budget-seconds", type=int, default=None)
    parser.add_argument("--min-speedup-ratio", type=float, default=0.01)
    parser.add_argument("--max-best-score-drop", type=float, default=0.0)
    parser.add_argument("--max-exact-rate-drop", type=float, default=0.0)
    parser.add_argument("--max-solved-drop", type=float, default=0.0)
    parser.add_argument("--max-capability-drop", type=float, default=0.0)
    parser.add_argument("--max-frontier-drop", type=float, default=0.35)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--no-paired-stats", action="store_true", help="fall back to fixed-threshold guard even with per-seed data")
    parser.add_argument("--stats-confidence", type=float, default=0.95)
    parser.add_argument("--stats-alpha", type=float, default=0.05)
    parser.add_argument("--stats-quality-alpha", type=float, default=0.10)
    parser.add_argument("--stats-min-pairs", type=int, default=3)
    parser.add_argument("--stats-correction", choices=["holm", "bh", "none"], default="holm")
    parser.add_argument("--no-screen", action="store_true", help="disable the cheap candidate-screening stage (full benchmark for every candidate)")
    parser.add_argument("--screen-rounds", type=int, default=0, help="screen rounds per seed; 0 = auto (max(2, benchmark_rounds // 4))")
    parser.add_argument("--screen-seeds", type=int, default=3)
    parser.add_argument("--screen-keep-top", type=int, default=8, help="max candidates confirmed with the full paired benchmark")


def config_from_args(args: argparse.Namespace) -> Config:
    return Config(
        seed=args.seed,
        state_dir=args.state_dir,
        family_count=args.family_count,
        family_size=args.family_size,
        challenges_per_round=args.challenges_per_round,
        train_cases=args.train_cases,
        test_cases=args.test_cases,
        initial_difficulty=args.initial_difficulty,
        max_program_depth=args.max_program_depth,
        max_program_nodes=args.max_program_nodes,
        max_abs_value=args.max_abs_value,
        max_eval_steps=args.max_eval_steps,
        max_macros=args.max_macros,
        checkpoint_every=args.checkpoint_every,
        state_save_every=args.state_save_every,
        probe_challenges=args.probe_challenges,
        probe_train_cases=args.probe_train_cases,
        probe_test_cases=args.probe_test_cases,
        full_rescore_top_k=args.full_rescore_top_k,
        full_rescore_random_k=args.full_rescore_random_k,
        persistence_backend=args.persistence_backend,
        climate_weight=args.climate_weight,
        novelty_weight=args.novelty_weight,
        macro_potential_weight=args.macro_potential_weight,
        transfer_weight=args.transfer_weight,
        macro_support_threshold=args.macro_support_threshold,
        macro_transfer_threshold=args.macro_transfer_threshold,
        macro_retire_rounds=args.macro_retire_rounds,
        compositional_challenge_rate=args.compositional_challenge_rate,
        niche_probe_count=args.niche_probe_count,
        frontier_archive_limit=args.frontier_archive_limit,
        frontier_window=args.frontier_window,
        gene_splice_rate=args.gene_splice_rate,
        shrink_mutation_rate=args.shrink_mutation_rate,
        semantic_mutation_rate=getattr(args, "semantic_mutation_rate", 0.0),
        semantic_probe_count=getattr(args, "semantic_probe_count", 7),
        counterexample_limit=getattr(args, "counterexample_limit", 256),
        counterexample_harvest_top_k=getattr(args, "counterexample_harvest_top_k", 8),
        anti_forgetting=getattr(args, "anti_forgetting", False),
        ecology_reseed_rounds=getattr(args, "ecology_reseed_rounds", 0),
        ecology_patience=getattr(args, "ecology_patience", 8),
        adaptive_novelty=getattr(args, "adaptive_novelty", False),
    )


def _warn_legacy_alias() -> None:
    """Ciclo 5 (P): the legacy ``mycelium`` console script is deprecated.

    README has promised deprecation "desde 1.0 — remoção prevista na 2.0",
    but the alias never warned. A deprecation cycle users can actually see:
    one stderr line per invocation when launched as ``mycelium`` (exact
    argv[0] basename). ``mycelium-accel`` and ``python -m mycelium_accel``
    stay silent; ``python -m mycelium`` fails at the interpreter (module
    renamed), so there is nothing to warn about there.
    """
    import os
    import sys

    try:
        invoked_as = os.path.basename(sys.argv[0]) if sys.argv else ""
    except (IndexError, TypeError):  # pragma: no cover - defensive
        return
    if invoked_as == "mycelium":
        sys.stderr.write(
            "mycelium-accel: warning: the 'mycelium' command is deprecated "
            "since 1.0 and will be removed in 2.0; use 'mycelium-accel'.\n"
        )


def main() -> None:
    """Q2.1: every command degrades to exit 130 on Ctrl-C (no tracebacks)."""
    _warn_legacy_alias()
    try:  # Q2.2: `cmd | head` dies silently with SIGPIPE instead of traceback
        from signal import SIG_DFL, SIGPIPE, signal

        signal(SIGPIPE, SIG_DFL)
    except (ImportError, AttributeError, OSError, RuntimeError):
        pass  # Windows / embedded: no SIGPIPE
    try:
        _main()
    except KeyboardInterrupt:
        import sys as _sys_ki

        _sys_ki.stderr.write(
            "mycelium-accel: interrupted — partial artifacts (if any) were exported.\n"
        )
        raise SystemExit(130)
    except StateCorruptError as exc:
        # Ciclo 4 (R): corrupt/unreadable state or checkpoint files degrade to
        # one actionable line, not a raw json/pickle traceback. Same friendliness
        # contract as manifest/scaffold errors (tests/test_cli_state_errors.py).
        import sys as _sys_corrupt

        _sys_corrupt.stderr.write(f"mycelium-accel: {exc}\n")
        _sys_corrupt.stderr.write(
            "Options: restore an earlier checkpoint "
            "(mycelium-accel rollback --state-dir <dir> --round <N>),\n"
            "or re-init the state dir (move it aside and run init).\n"
        )
        raise SystemExit(1) from exc


def _load_initialized_state(state_dir: Path):
    """Load state for a read-only command or fail with one actionable line.

    The engine treats an absent state dir as "start fresh" (and keeps
    load_state raising FileNotFoundError, pinned by tests); but a user
    running `report`/`growth-regime` on an uninitialized dir made the CLI
    emit a raw traceback. Translate that into a clear SystemExit (exit 1).
    """
    try:
        return load_state(state_dir)
    except FileNotFoundError:
        raise SystemExit(
            f"mycelium-accel: no state found in {state_dir} — nothing to report.\n"
            f"Initialize it first: mycelium-accel init --state-dir {state_dir}"
        )


def _main() -> None:  # noqa: C901 — Q3.2: command-dispatch if-chain, one arm per command.
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "version", False):
        from . import __version__
        print(f"mycelium-accel {__version__}")
        return

    if not args.command:
        parser.print_help()
        raise SystemExit(2)

    if args.command == "doctor":
        from .doctor import main as doctor_main
        argv = ["--state-dir", args.state_dir] + (["--json"] if args.json else [])
        if args.target:
            argv += ["--target", args.target]
        if args.fix:
            argv += ["--fix"]
        raise SystemExit(doctor_main(argv))

    if args.command == "history":
        from .history import write_history
        root = Path(args.target)
        bench_dir = Path(args.benchmarks_dir) if args.benchmarks_dir else root / ".mycelium_benchmarks"
        if not bench_dir.is_dir():
            raise SystemExit(f"mycelium-accel: no benchmarks dir: {bench_dir} (run accelerate first)")
        dest, count = write_history(bench_dir, Path(args.out) if args.out else None)
        print(json.dumps({"history": str(dest), "sweeps": count}, indent=2))
        return

    if args.command == "accelerate" and getattr(args, "accelerate_action", None) == "init":
        from .targets import KIND_TO_DEFAULT_MANIFEST, detect_kind
        from .targets.base import MANIFEST_FILENAME
        root = Path(args.target).resolve()
        if not root.is_dir():
            raise SystemExit(f"Target directory not found: {root}")
        out = root / MANIFEST_FILENAME
        if out.exists() and not args.force:
            raise SystemExit(f"{out} exists (use --force to overwrite)")
        kind = detect_kind(root)
        manifest = KIND_TO_DEFAULT_MANIFEST[kind](root)
        if args.wizard:
            from .scaffold import run_wizard
            manifest = run_wizard(manifest)
        out.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"manifest": str(out), "kind": kind}, indent=2))
        if args.wizard or args.yes:
            from .scaffold import next_steps
            print(next_steps(out))
        return

    if args.command == "accelerate":
        target_path = Path(args.target)
        # S2 Ciclo 10: a nonexistent target previously fell through to the
        # legacy module loader and leaked a raw RuntimeError traceback.
        if args.target != "self" and not target_path.exists():
            import sys as _sys_missing_target

            _sys_missing_target.stderr.write(
                "mycelium-accel: accelerate failed: target not found: "
                f"{target_path}; pass an existing project directory or benchmark "
                "module, or run 'mycelium-accel accelerate init --target <dir>'.\n"
            )
            raise SystemExit(1)
        use_generic_harness = (
            args.manifest is not None
            or target_path.is_dir()
        )
        if use_generic_harness:
            import sys as _sys2

            from .accelerate_generic import accelerate_target
            from .targets.base import TargetSafetyError as _SafetyError

            seeds = [int(item.strip()) for item in str(args.seeds).split(",") if item.strip()]
            try:
                outcome = accelerate_target(
                target_path,
                manifest_path=Path(args.manifest) if args.manifest else None,
                seeds=seeds,
                apply=not args.no_apply,
                race=args.race,
                race_seeds=args.race_seeds,
                race_margin=args.race_margin,
                race_adaptive=args.race_adaptive,
                reference=Path(args.reference) if args.reference else None,
                fail_on_regression=args.fail_on_regression,
                adaptive_repeats=args.adaptive_repeats,
                cache=args.cache,
                cache_dir=Path(args.cache_dir) if args.cache_dir else None,
                sequential_seeds=args.sequential_seeds,
                dry_run=args.dry_run,
                )
            except (_SafetyError, ValueError, FileNotFoundError, RuntimeError, OSError) as exc:
                detail = " ".join(str(exc).splitlines())
                _sys2.stderr.write(f"mycelium-accel: accelerate failed: {detail}\n")
                raise SystemExit(1)
            print(json.dumps(outcome.to_dict(), indent=2))
            if outcome.interrupted:
                _sys2.stderr.write(
                    "mycelium-accel: interrupted — no decision on partial data "
                    f"(see {outcome.sweep_path}).\n"
                )
                raise SystemExit(130)
            if outcome.regression:
                _sys2.stderr.write(
                    "mycelium-accel: accelerate failed: performance regression "
                    "vs --reference (see decision_reasons)\n")
                raise SystemExit(1)
            return
        # S2 Ciclo 10: the legacy module path must be as friendly as the
        # generic-harness branch (one actionable line, no raw traceback).
        try:
            if args.target == "self":
                ext_outcome = accelerate_self(Path.cwd())
            else:
                ext_outcome = accelerate_external(target_path)
        except (
            RuntimeError, OSError, ValueError, SyntaxError, AttributeError,
            ImportError,
        ) as exc:
            import sys as _sys_ext

            _sys_ext.stderr.write(f"mycelium-accel: accelerate failed: {exc}\n")
            raise SystemExit(1) from exc
        print(json.dumps({
            "module": ext_outcome.module_path,
            "baseline": ext_outcome.baseline,
            "best_variant": ext_outcome.best_variant,
            "timings": [{"variant": item.variant, "seconds": item.seconds} for item in ext_outcome.timings],
        }, indent=2))
        return

    config = config_from_args(args)

    # S2 Ciclo 10: an existing *file* passed as --state-dir later leaked a raw
    # NotADirectoryError from AuditLog.mkdir; reject it once with a clear line.
    _state_dir = Path(config.state_dir)
    if _state_dir.exists() and not _state_dir.is_dir():
        import sys as _sys_statefile

        _sys_statefile.stderr.write(
            f"mycelium-accel: --state-dir must be a directory, got a file: {_state_dir}\n"
        )
        raise SystemExit(1)

    if args.command == "self-improve":
        improver = SelfImprover(Path(args.project_root).resolve(), config, build_guard_from_args(args))
        summary = improver.run(
            args.cycles,
            args.rounds_per_cycle,
            time_budget_seconds=args.time_budget_seconds,
        )
        print(json.dumps(summary.to_dict(), indent=2))
        return

    if args.command == "self-improve-daemon":
        improver = SelfImprover(Path(args.project_root).resolve(), config, build_guard_from_args(args))
        summary = improver.run_daemon(
            args.rounds_per_cycle,
            time_budget_seconds=args.time_budget_seconds,
            sleep_seconds=args.sleep_seconds,
            max_cycles=args.max_cycles,
        )
        print(json.dumps(summary.to_dict(), indent=2))
        return

    engine = MyceliumEngine(config)

    if args.command == "init":
        state = engine.init_state()
        print(json.dumps({"state_dir": config.state_dir, "families": len(state.families), "round": state.round_index}, indent=2))
        return

    if args.command == "run":
        run_summary = engine.run(args.rounds)
        print(json.dumps({
            "rounds_executed": run_summary.rounds_executed,
            "stopped_by_kill_switch": run_summary.stopped_by_kill_switch,
            "best_score": run_summary.best_score,
            "frontier_difficulty": run_summary.frontier_difficulty,
            "growth_regime": run_summary.growth_regime,
        }, indent=2))
        try:
            from datetime import datetime
            reports = Path(".mycelium_benchmarks")
            reports.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            (reports / f"run-{stamp}.md").write_text(
                f"# run {stamp}\n\n"
                f"- rounds_executed: {run_summary.rounds_executed}\n"
                f"- stopped_by_kill_switch: {run_summary.stopped_by_kill_switch}\n"
                f"- best_score: {run_summary.best_score}\n"
                f"- frontier_difficulty: {run_summary.frontier_difficulty}\n"
                f"- growth_regime: {run_summary.growth_regime}\n"
                f"- state_dir: {config.state_dir}\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        return

    if args.command == "report":
        state = _load_initialized_state(Path(config.state_dir))
        report = engine.growth_report(state)
        print(json.dumps(report, indent=2))
        return

    if args.command == "growth-regime":
        from .growth_metrics import build_dashboard, summarize_dashboard
        from .telemetry import full_history

        import sys as _sys

        from .telemetry import check_provenance

        def _load_json(path: str) -> dict:
            candidate = Path(path)
            if not candidate.exists():
                return {}
            # S2 Ciclo 10: an unreadable/truncated/non-object sidecar is an
            # optional derived input; degrade to zeros with a warning rather
            # than a raw json traceback from the dashboard command.
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                _sys.stderr.write(f"warning: {path}: unreadable ({type(exc).__name__}); ignoring\n")
                return {}
            if not isinstance(payload, dict):
                _sys.stderr.write(f"warning: {path}: expected a JSON object; ignoring\n")
                return {}
            ok, reason = check_provenance(payload, config.state_dir)
            if not ok:
                _sys.stderr.write(f"warning: {path}: {reason}\n")
                if args.strict:
                    return {}
            return payload

        state = _load_initialized_state(Path(config.state_dir))
        qd_payload = _load_json(".mycelium_qd/qd_experiment.json")
        transfer_payload = _load_json(".mycelium_transfer/transfer_graph.json")
        library_payload = _load_json(".mycelium_semantics/learned_library.json")
        reuse_stats = library_payload.get("reuse_stats", {})
        dashboard = build_dashboard(
            full_history(state.metrics_history, config.state_dir),
            qd_coverage=float(qd_payload.get("final_coverage", 0.0)),
            qd_score=float(qd_payload.get("final_qd_score", 0.0)),
            qd_auc=float(qd_payload.get("final_qd_auc", 0.0)),
            abstractions_learned=len(library_payload.get("abstractions", [])),
            mean_abstraction_reuse=float(reuse_stats.get("mean_support", 0.0)),
            transfer_stats={
                "donor_scores": transfer_payload.get("donor_scores", {}),
                "useful_edges": transfer_payload.get("useful_edges", 0),
                "expansion_rate": transfer_payload.get("expansion_rate", 0.0),
            },
        )
        if args.markdown:
            print(summarize_dashboard(dashboard))
        else:
            print(json.dumps(dashboard.to_dict(), indent=2))
        return

    if args.command == "rollback":
        try:
            state = engine.rollback(args.rollback_round)
        except FileNotFoundError as exc:
            import sys as _sys_rb

            _sys_rb.stderr.write(f"mycelium-accel: {exc}\n")
            _sys_rb.stderr.write(
                "Nothing to roll back: initialize and run first (init/run); "
                "available checkpoints are under "
                f"{config.state_dir}/checkpoints.\n"
            )
            raise SystemExit(1) from exc
        print(json.dumps({"round": state.round_index, "state_dir": config.state_dir}, indent=2))
        return


if __name__ == "__main__":
    main()
