from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import mean

from .acceleration import aggregate_scores
from .audit import AuditLog, resolve_checkpoint_file
from .challenge import Challenge, ChallengeFactory
from .config import Config
from .dsl import (
    Macro,
    Node,
    ProgramExecutor,
    compile_program,
    crossover,
    dedupe_motifs,
    iter_path_nodes,
    mutate,
    random_tree,
    repeated_pattern_tree,
    replace_subtree,
    subtree_motifs,
)
from .model import EngineState, Family, Organism, StagedMacro
from .prime import next_prime
from .state import StateCorruptError, kill_switch_file, load_state, save_state, state_file
from .counterexamples import CounterexampleBank, harvest_counterexamples
from .mutation_semantic import SemanticMutationContext, apply_semantic_mutation
from .semantics import SemanticBank, canonical_probes
from .telemetry import append_metric
from .ecology_loop import EliteArchive, decline_streak, frontier_stalled, novelty_boost

PHASE_REAL = (1, 0, -1, 0)
BEHAVIOR_PROBE_INPUTS = (-11, -5, 2, 7, 13, 19, 29)


@dataclass(slots=True)
class RunSummary:
    rounds_executed: int
    stopped_by_kill_switch: bool
    best_score: float
    frontier_difficulty: int
    growth_regime: str


class MyceliumEngine:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.challenge_factory = ChallengeFactory(
            max_program_depth=config.max_program_depth,
            max_program_nodes=config.max_program_nodes,
            max_abs_value=config.max_abs_value,
            max_eval_steps=config.max_eval_steps,
            train_cases=config.train_cases,
            test_cases=config.test_cases,
        )
        self.audit = AuditLog(config.state_path, checkpoint_backend=config.persistence_backend)
        self._climate_multipliers = (
            1.0 + config.climate_weight * math.log(math.pi),
            1.0 - config.climate_weight * math.log(2.967),
        )
        self._executor_cache: dict[str, ProgramExecutor | None] = {}
        self._executor_cache_limit = 4096
        self._behavior_probe_inputs = BEHAVIOR_PROBE_INPUTS[: max(3, min(len(BEHAVIOR_PROBE_INPUTS), config.niche_probe_count))]
        self._semantic_ctx: SemanticMutationContext | None = None
        self._elite_archive = EliteArchive()  # C1: per-process anti-forgetting

    def _get_semantic_ctx(self, state: EngineState, macro_nodes: dict[str, Node], round_index: int) -> SemanticMutationContext:
        if self._semantic_ctx is None:
            self._semantic_ctx = SemanticMutationContext(
                bank=SemanticBank(probes=canonical_probes(self.config.semantic_probe_count)),
                counterexamples=CounterexampleBank(capacity=self.config.counterexample_limit),
                probes=canonical_probes(self.config.semantic_probe_count),
                max_nodes=self.config.max_program_nodes,
                max_abs_value=self.config.max_abs_value,
                max_steps=self.config.max_eval_steps,
            )
        self._semantic_ctx.round_index = round_index
        self._semantic_ctx.macro_nodes = macro_nodes
        return self._semantic_ctx

    def init_state(self) -> EngineState:
        self.config.state_path.mkdir(parents=True, exist_ok=True)
        rng = random.Random(self.config.seed)
        state = EngineState(
            config=self.config.to_dict(),
            round_index=0,
            next_family_index=1,
            next_organism_index=1,
            frontier_difficulty=self.config.initial_difficulty,
            climate_mode=0,
            total_families_created=0,
        )
        for _ in range(self.config.family_count):
            state.families.append(self._make_fresh_family(state, rng, created_round=0))
        save_state(self.config.state_path, state, self.config.persistence_backend)
        self.audit.append(
            "init",
            {
                "seed": self.config.seed,
                "families": self.config.family_count,
                "family_size": self.config.family_size,
            },
        )
        self.audit.checkpoint(state)
        return state

    def load_or_init_state(self) -> EngineState:
        if state_file(self.config.state_path, "auto").exists():
            return load_state(self.config.state_path, self.config.persistence_backend)
        return self.init_state()

    def run(self, rounds: int) -> RunSummary:
        state = self.load_or_init_state()
        executed = 0
        stopped = False
        checkpoint_every = self.config.checkpoint_every
        state_save_every = self.config.state_save_every
        state_dir = self.config.state_path
        audit = self.audit
        dirty = False

        for _ in range(rounds):
            if kill_switch_file(state_dir).exists():
                audit.append("kill_switch", {"round": state.round_index})
                stopped = True
                break
            state = self._run_round(state)
            executed += 1
            dirty = True
            if state.round_index % state_save_every == 0:
                save_state(state_dir, state, self.config.persistence_backend)
                dirty = False
            if state.round_index % checkpoint_every == 0:
                audit.checkpoint(state)

        if dirty:
            save_state(state_dir, state, self.config.persistence_backend)

        report = self.growth_report(state)
        best_score = max((metric["best_score"] for metric in state.metrics_history), default=0.0)
        return RunSummary(
            rounds_executed=executed,
            stopped_by_kill_switch=stopped,
            best_score=best_score,
            frontier_difficulty=state.frontier_difficulty,
            growth_regime=str(report["regime"]),
        )

    def rollback(self, round_index: int) -> EngineState:
        checkpoint = resolve_checkpoint_file(self.config.state_path / "checkpoints", round_index)
        # Ciclo 4 (R): corrupt checkpoint -> StateCorruptError (friendly CLI),
        # not a raw json/pickle traceback.
        from .state import load_checkpoint_payload

        try:
            payload = load_checkpoint_payload(checkpoint)
            state = EngineState.from_dict(payload)
        except (KeyError, TypeError, AttributeError) as exc:
            raise StateCorruptError(
                f"checkpoint {checkpoint} has invalid content ({type(exc).__name__}: {exc})"
            ) from exc
        save_state(self.config.state_path, state, self.config.persistence_backend)
        self.audit.append("rollback", {"round": round_index, "checkpoint": str(checkpoint)})
        return state

    def growth_report(self, state: EngineState | None = None) -> dict[str, float | str | int]:
        state = state or self.load_or_init_state()
        history = state.metrics_history
        if len(history) < 5:
            return {
                "regime": "insufficient_data",
                "points": len(history),
                "linear_r2": 0.0,
                "exp_r2": 0.0,
                "linear_slope": 0.0,
                "exp_log_slope": 0.0,
                "recent_regime": "insufficient_data",
                "recent_points": min(len(history), self.config.frontier_window),
                "recent_linear_slope": 0.0,
                "recent_exp_log_slope": 0.0,
            }

        full = self._growth_summary(history)
        recent_history = history[-max(5, self.config.frontier_window):]
        recent = self._growth_summary(recent_history)
        return {
            "regime": full["regime"],
            "points": len(history),
            "linear_r2": full["linear_r2"],
            "exp_r2": full["exp_r2"],
            "linear_slope": full["linear_slope"],
            "exp_log_slope": full["exp_log_slope"],
            "recent_regime": recent["regime"],
            "recent_points": len(recent_history),
            "recent_linear_slope": recent["linear_slope"],
            "recent_exp_log_slope": recent["exp_log_slope"],
        }

    def _run_round(self, state: EngineState) -> EngineState:
        round_index = state.round_index + 1
        rng = random.Random(next_prime(self.config.seed + round_index * 101))
        macro_nodes = self._macro_nodes(state)
        challenges = self._make_round_challenges(state, rng, macro_nodes)
        # C1: adaptive novelty — boost when niches collapsed last round.
        _novelty_saved = self.config.novelty_weight
        try:
            if state.metrics_history:
                last_niches = int(state.metrics_history[-1].get("active_niches", 99))
                self.config.novelty_weight = _novelty_saved * novelty_boost(
                    last_niches, self.config.adaptive_novelty
                )
            evaluation = self._evaluate_population(state, challenges, macro_nodes, rng)
        finally:
            self.config.novelty_weight = _novelty_saved

        champion = max(
            (member for family in state.families for member in family.members),
            key=lambda item: item.score,
        )
        if self.config.semantic_mutation_rate > 0.0:
            ctx = self._get_semantic_ctx(state, macro_nodes, round_index)
            champion_executor = self._executor_for(champion.genome, macro_nodes, self._executor_cache)
            for challenge in challenges:
                failing = harvest_counterexamples(
                    champion_executor,
                    challenge.train_pairs + challenge.test_pairs,
                    source_seed=challenge.seed,
                    round_index=round_index,
                    limit=self.config.counterexample_harvest_top_k,
                )
                ctx.counterexamples.add_batch(failing)
            for family in state.families:
                best = max(family.members, key=lambda item: item.score, default=None)
                if best is not None:
                    ctx.bank.register(
                        best.genome,
                        macro_nodes,
                        round_index,
                        max_nodes=self.config.max_program_nodes,
                        max_abs_value=self.config.max_abs_value,
                        max_steps=self.config.max_eval_steps,
                    )
        applied_climate = self._climate_label(state.climate_mode)

        frontier_counts = self._update_frontier_archive(state, champion, challenges, macro_nodes, round_index)
        self._update_macro_ecosystem(state, champion, challenges, macro_nodes, round_index)
        self._apply_fusion_rule(state, rng)
        self._apply_character_events(state, rng, round_index)
        self._extinguish_one_family(state, rng, round_index)
        ecology_stats = self._apply_ecology_loop(state, champion, rng, round_index)

        for family in state.families:
            family.lineage_depth += 1
            family.phase = (family.phase + 1) % 4
            self._breed_family(state, family, rng, round_index)

        state.round_index = round_index
        state.climate_mode = 1 - state.climate_mode
        self._adapt_difficulty(state, champion)

        frontier_progress = self._frontier_learning_progress(state.frontier_archive)
        capability_signal = (
            state.frontier_difficulty
            + champion.solved_challenges / max(1, self.config.challenges_per_round)
            + champion.exact_rate
            + min(1.0, frontier_progress)
        )
        metric = {
            "round": round_index,
            "climate": applied_climate,
            "frontier_difficulty": state.frontier_difficulty,
            "best_score": champion.score,
            "best_exact_rate": champion.exact_rate,
            "solved_by_best": champion.solved_challenges,
            "macro_count": len(state.macro_library),
            "macro_cap_saturated": bool(len(state.macro_library) >= self.config.max_macros),
            "staging_macro_count": len(state.macro_staging),
            "capability_signal": capability_signal,
            "best_program": champion.genome.render(),
            "challenge_oracles": [challenge.oracle_repr for challenge in challenges],
            "active_niches": int(evaluation["active_niches"]),
            "diversity_entropy": float(evaluation["diversity_entropy"]),
            "macro_transfer_mean": float(evaluation["macro_transfer_mean"]),
            "frontier_learning_progress": frontier_progress,
            "frontier_status_counts": frontier_counts,
            "ecology_injections": ecology_stats["injections"],
            "ecology_reseeds": ecology_stats["reseeds"],
        }
        state.metrics_history.append(metric)
        state.metrics_history = state.metrics_history[-512:]
        self.audit.append("round", metric)
        # F1: durable telemetry — append-only JSONL, never truncates. The
        # in-memory cap above stays for backward compatibility; readers that
        # need full history use telemetry.full_history().
        append_metric(self.config.state_path, metric)
        return state

    def _apply_ecology_loop(
        self,
        state: EngineState,
        champion: Organism,
        rng: random.Random,
        round_index: int,
    ) -> dict[str, int]:
        """C1: elite archive + anti-forgetting injection + stagnation reseed.

        No-ops (recording only the archive note) when all flags are off, so the
        default engine path is bit-identical with or without this call.
        """
        self._elite_archive.note(champion.genome, champion.score, round_index)
        stats = {"injections": 0, "reseeds": 0}
        history = state.metrics_history
        if self.config.anti_forgetting and self._elite_archive.best_genome is not None:
            scores = [float(m.get("best_score", 0.0)) for m in history]
            if decline_streak(scores, self.config.ecology_patience):
                elite = self._elite_archive.elite_genome()
                if elite is not None and state.families:
                    worst_family = min(
                        state.families,
                        key=lambda fam: max((m.score for m in fam.members), default=float("-inf")),
                    )
                    if worst_family.members:
                        victim = min(worst_family.members, key=lambda m: m.score)
                        idx = worst_family.members.index(victim)
                        worst_family.members[idx] = self._new_organism(
                            state, worst_family.family_id, elite,
                            lineage_depth=victim.lineage_depth, birth_round=round_index,
                        )
                        stats["injections"] = 1
                        self._elite_archive.injections += 1
                        self.audit.append("ecology_injection", {"round": round_index})
        if self.config.ecology_reseed_rounds > 0 and state.families:
            diffs = [m.get("frontier_difficulty", 0) for m in history]
            if frontier_stalled(diffs, self.config.ecology_reseed_rounds):
                worst_family = min(
                    state.families,
                    key=lambda fam: max((m.score for m in fam.members), default=float("-inf")),
                )
                idx = state.families.index(worst_family)
                state.families[idx] = self._make_fresh_family(state, rng, round_index)
                stats["reseeds"] = 1
                self._elite_archive.reseeds += 1
                self.audit.append("ecology_reseed", {"round": round_index})
        return stats

    def _growth_summary(self, history: list[dict[str, float | str | int]]) -> dict[str, float | str]:
        xs = [float(index + 1) for index in range(len(history))]
        ys = [max(0.001, float(item["capability_signal"])) for item in history]
        linear = self._linear_fit(xs, ys)
        exp = self._linear_fit(xs, [math.log(value) for value in ys])
        if exp["r2"] > linear["r2"] + 0.05 and exp["slope"] > 0.02:
            regime = "exponential"
        elif linear["slope"] > 0.03:
            regime = "linear"
        elif linear["slope"] > 0.0:
            regime = "sublinear"
        else:
            regime = "stalled_or_declining"
        return {
            "regime": regime,
            "linear_r2": linear["r2"],
            "exp_r2": exp["r2"],
            "linear_slope": linear["slope"],
            "exp_log_slope": exp["slope"],
        }

    def _linear_fit(self, xs: list[float], ys: list[float]) -> dict[str, float]:
        x_mean = sum(xs) / len(xs)
        y_mean = sum(ys) / len(ys)
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
        denominator = sum((x - x_mean) ** 2 for x in xs) or 1.0
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        predicted = [intercept + slope * x for x in xs]
        ss_res = sum((y - p) ** 2 for y, p in zip(ys, predicted))
        ss_tot = sum((y - y_mean) ** 2 for y in ys) or 1.0
        r2 = 1 - ss_res / ss_tot
        return {"slope": slope, "intercept": intercept, "r2": r2}

    def _macro_nodes(self, state: EngineState) -> dict[str, Node]:
        nodes = {macro.name: macro.tree for macro in state.macro_library}
        for staged in state.macro_staging:
            if staged.transfer_gain >= -0.05:
                nodes[staged.name] = staged.tree
        return nodes

    def _make_fresh_family(self, state: EngineState, rng: random.Random, created_round: int) -> Family:
        family_id = f"F{state.next_family_index:04d}"
        state.next_family_index += 1
        state.total_families_created += 1
        members: list[Organism] = []
        macro_names = tuple(self._macro_nodes(state))
        for _ in range(self.config.family_size):
            genome = self._bounded_tree(rng, self.config.max_program_depth, 6, macro_names)
            members.append(self._new_organism(state, family_id, genome, lineage_depth=0, birth_round=created_round))
        return Family(
            family_id=family_id,
            created_round=created_round,
            lineage_depth=0,
            phase=state.next_family_index % 4,
            members=members,
        )

    def _bounded_tree(
        self,
        rng: random.Random,
        max_depth: int,
        constant_scale: int,
        macro_names: tuple[str, ...],
    ) -> Node:
        max_nodes = self.config.max_program_nodes
        for _ in range(50):
            tree = random_tree(rng, max_depth=max_depth, constant_scale=constant_scale, macro_names=macro_names)
            if tree.count_nodes() <= max_nodes:
                return tree
        return Node("input")

    def _new_organism(
        self,
        state: EngineState,
        family_id: str,
        genome: Node,
        *,
        lineage_depth: int,
        birth_round: int,
    ) -> Organism:
        organism_id = f"O{state.next_organism_index:06d}"
        state.next_organism_index += 1
        return Organism(
            organism_id=organism_id,
            family_id=family_id,
            genome=genome,
            lineage_depth=lineage_depth,
            birth_round=birth_round,
        )

    def _make_round_challenges(
        self,
        state: EngineState,
        rng: random.Random,
        macro_nodes: dict[str, Node],
    ) -> list[Challenge]:
        frontier = self._frontier_summary(state.frontier_archive)
        center = state.frontier_difficulty
        shift = 0
        if frontier["dominated_ratio"] >= 0.55 and frontier["learning_progress"] >= 0.0:
            shift = 1
        elif frontier["impossible_ratio"] >= 0.60 and frontier["learning_progress"] < 0.0:
            shift = -1
        center = max(1, center + shift)
        difficulties = [max(1, center + ((index % 3) - 1)) for index in range(self.config.challenges_per_round)]
        challenges = []
        for idx, difficulty in enumerate(difficulties):
            seed = next_prime(self.config.seed + state.round_index * 1000 + idx * 13 + difficulty * 17)
            force_compositional = bool(macro_nodes) and (
                difficulty >= center
                or frontier["frontier_ratio"] >= 0.25
                or rng.random() < self.config.compositional_challenge_rate
            )
            challenges.append(
                self.challenge_factory.build(
                    seed,
                    difficulty,
                    macro_nodes,
                    force_compositional=force_compositional,
                )
            )
        rng.shuffle(challenges)
        return challenges

    def _evaluate_population(
        self,
        state: EngineState,
        challenges: list[Challenge],
        macro_nodes: dict[str, Node],
        rng: random.Random,
    ) -> dict[str, float | int]:
        climate_multiplier = self._climate_multipliers[state.climate_mode]
        executor_cache = self._executor_cache
        probe_challenges = challenges[: min(self.config.probe_challenges, len(challenges))]
        probe_train_cases = self.config.probe_train_cases
        probe_test_cases = self.config.probe_test_cases
        full_rescore_top_k = self.config.full_rescore_top_k
        full_rescore_random_k = self.config.full_rescore_random_k
        global_signature_counts: dict[str, int] = {}
        family_signature_counts: dict[str, dict[str, int]] = {}
        known_renders = {macro.tree.render() for macro in state.macro_library}
        known_renders.update(staged.tree.render() for staged in state.macro_staging)
        macro_quality = self._macro_quality_map(state)

        for family in state.families:
            family_signatures: dict[str, int] = {}
            for member in family.members:
                member.score, member.exact_rate, member.soft_rate, member.solved_challenges = self._score_organism(
                    member,
                    probe_challenges,
                    macro_nodes,
                    executor_cache,
                    total_challenge_count=len(challenges),
                    train_case_limit=probe_train_cases,
                    test_case_limit=probe_test_cases,
                )
                executor = self._executor_for(member.genome, macro_nodes, executor_cache)
                signature = self._behavior_signature(executor)
                macro_refs = self._macro_references(member.genome)
                member.notes = {
                    "nodes": member.genome.count_nodes(),
                    "depth": member.genome.depth(),
                    "behavior_signature": signature,
                    "macro_refs": macro_refs,
                    "selection_bonus": 0.0,
                    "novelty_bonus": 0.0,
                    "macro_potential_bonus": 0.0,
                    "transfer_bonus": 0.0,
                }
                global_signature_counts[signature] = global_signature_counts.get(signature, 0) + 1
                family_signatures[signature] = family_signatures.get(signature, 0) + 1
            family_signature_counts[family.family_id] = family_signatures

        diversity_entropy = self._signature_entropy(global_signature_counts)
        active_niches = len(global_signature_counts)

        for family in state.families:
            for member in family.members:
                novelty_bonus = self.config.novelty_weight / math.sqrt(
                    max(1, global_signature_counts.get(str(member.notes["behavior_signature"]), 1))
                )
                macro_potential_bonus = self.config.macro_potential_weight * self._macro_potential(member, known_renders)
                transfer_bonus = self.config.transfer_weight * self._macro_transfer_bonus(member, macro_quality)
                selection_bonus = novelty_bonus + macro_potential_bonus + transfer_bonus
                member.score += selection_bonus
                member.notes["selection_bonus"] = selection_bonus
                member.notes["novelty_bonus"] = novelty_bonus
                member.notes["macro_potential_bonus"] = macro_potential_bonus
                member.notes["transfer_bonus"] = transfer_bonus

            ranked_indices = sorted(range(len(family.members)), key=lambda idx: family.members[idx].score, reverse=True)
            finalist_indices = set(ranked_indices[: min(full_rescore_top_k, len(ranked_indices))])
            remaining = ranked_indices[len(finalist_indices):]
            if full_rescore_random_k > 0 and remaining:
                random_picks = rng.sample(remaining, k=min(full_rescore_random_k, len(remaining)))
                finalist_indices.update(random_picks)

            for index in finalist_indices:
                member = family.members[index]
                member.score, member.exact_rate, member.soft_rate, member.solved_challenges = self._score_organism(
                    member,
                    challenges,
                    macro_nodes,
                    executor_cache,
                    total_challenge_count=len(challenges),
                )
                member.score += float(member.notes.get("selection_bonus", 0.0))

            member_scores = [member.score for member in family.members]
            base_score, score_diversity = aggregate_scores(member_scores)
            vigor = math.exp(-family.lineage_depth / math.e)
            phase_factor = self._phase_multiplier(family.phase, family.last_diversity)
            niche_entropy = self._signature_entropy(family_signature_counts.get(family.family_id, {}))
            family.last_score = base_score * vigor * climate_multiplier * phase_factor
            family.last_diversity = (score_diversity + niche_entropy) / 2.0
            self._refresh_gene_bank(family)

        self._refresh_macro_usage(state, state.round_index + 1)
        return {
            "active_niches": active_niches,
            "diversity_entropy": diversity_entropy,
            "macro_transfer_mean": self._mean_macro_transfer(state),
        }

    def _score_organism(
        self,
        organism: Organism,
        challenges: list[Challenge],
        macro_nodes: dict[str, Node],
        executor_cache: dict[str, ProgramExecutor | None],
        *,
        total_challenge_count: int,
        train_case_limit: int | None = None,
        test_case_limit: int | None = None,
    ) -> tuple[float, float, float, int]:
        executor = self._executor_for(organism.genome, macro_nodes, executor_cache)
        if executor is None:
            return -0.1, 0.0, 0.0, 0

        total_soft = 0.0
        total_exact = 0.0
        solved = 0
        evaluations = len(challenges)
        for challenge in challenges:
            train_soft, _ = self._score_dataset(executor, challenge.train_pairs, train_case_limit)
            test_soft, test_exact = self._score_dataset(executor, challenge.test_pairs, test_case_limit)
            total_soft += 0.45 * train_soft + 0.75 * test_soft
            total_exact += test_exact
            if test_exact == 1.0:
                solved += 1
        challenge_scale = total_challenge_count / max(1, evaluations)
        parsimony_penalty = organism.genome.complexity_score() * 0.003
        score = (total_soft + total_exact * 1.4) * challenge_scale - parsimony_penalty
        return score, total_exact / max(1, evaluations), total_soft / max(1, evaluations), solved

    def _score_tree(
        self,
        tree: Node,
        challenges: list[Challenge],
        macro_nodes: dict[str, Node],
        *,
        total_challenge_count: int,
        train_case_limit: int | None = None,
        test_case_limit: int | None = None,
    ) -> float:
        organism = Organism("TMP", "TMP", tree, 0, 0)
        score, _, _, _ = self._score_organism(
            organism,
            challenges,
            macro_nodes,
            self._executor_cache,
            total_challenge_count=total_challenge_count,
            train_case_limit=train_case_limit,
            test_case_limit=test_case_limit,
        )
        return score

    def _executor_for(
        self,
        genome: Node,
        macro_nodes: dict[str, Node],
        executor_cache: dict[str, ProgramExecutor | None],
    ) -> ProgramExecutor | None:
        key = genome.render()
        if key in executor_cache:
            return executor_cache[key]
        try:
            executor = compile_program(
                genome,
                macro_nodes,
                max_nodes=self.config.max_program_nodes,
                max_abs_value=self.config.max_abs_value,
                max_steps=self.config.max_eval_steps,
            )
        except Exception:
            executor = None
        if len(executor_cache) >= self._executor_cache_limit:
            executor_cache.clear()
        executor_cache[key] = executor
        return executor

    def _score_dataset(
        self,
        executor: ProgramExecutor,
        pairs: list[tuple[int, int]],
        pair_limit: int | None = None,
    ) -> tuple[float, float]:
        if pair_limit is None or pair_limit >= len(pairs):
            return executor.score_pairs(pairs)
        return executor.score_pairs_limit(pairs, pair_limit)

    def _phase_multiplier(self, phase: int, last_diversity: float) -> float:
        phase_real = PHASE_REAL[phase % 4]
        if phase_real == 1:
            return 1.02
        if phase_real == -1:
            return 0.98 + last_diversity * 0.05
        return 1.0

    def _refresh_gene_bank(self, family: Family) -> None:
        elite = sorted(family.members, key=lambda member: member.score, reverse=True)[:3]
        motifs = list(family.gene_bank)
        for member in elite:
            motifs.extend(subtree_motifs(member.genome))
        family.gene_bank = dedupe_motifs(motifs, limit=18)

    def _tournament_pick(self, family: Family, rng: random.Random) -> Organism:
        contenders = rng.sample(family.members, k=self.config.tournament_size)
        phase_real = PHASE_REAL[family.phase % 4]
        scored = sorted(contenders, key=lambda member: member.score)
        if phase_real == 1:
            return scored[-1]
        if phase_real == -1:
            return scored[0]
        return scored[len(scored) // 2]

    def _breed_family(self, state: EngineState, family: Family, rng: random.Random, round_index: int) -> None:
        if not family.members:
            family.members.append(
                self._new_organism(
                    state,
                    family.family_id,
                    Node("input"),
                    lineage_depth=family.lineage_depth,
                    birth_round=round_index,
                )
            )
        ordered = sorted(family.members, key=lambda member: member.score, reverse=True)
        next_members: list[Organism] = ordered[:2]
        macro_names = tuple(self._macro_nodes(state))
        family_size = self.config.family_size
        max_program_nodes = self.config.max_program_nodes
        max_depth = self.config.max_program_depth
        constant_scale = 8 + state.frontier_difficulty
        gene_bank = family.gene_bank

        while len(next_members) < family_size:
            parent_a = self._tournament_pick(family, rng)
            parent_b = self._tournament_pick(family, rng)
            genome = crossover(parent_a.genome, parent_b.genome, rng) if rng.random() < 0.7 else parent_a.genome.clone()
            if gene_bank and rng.random() < self.config.gene_splice_rate:
                genome = crossover(genome, rng.choice(gene_bank), rng)
            if rng.random() < 0.9:
                genome = self._mutate_with_policy(
                    genome,
                    rng,
                    max_depth=max_depth,
                    constant_scale=constant_scale,
                    macro_names=macro_names,
                    gene_bank=gene_bank,
                )
            if genome.count_nodes() > max_program_nodes:
                genome = self._shrink_tree(parent_a.genome.clone(), rng)
            next_members.append(
                self._new_organism(
                    state,
                    family.family_id,
                    genome,
                    lineage_depth=family.lineage_depth,
                    birth_round=round_index,
                )
            )
        family.members = next_members[:family_size]

    def _mutate_with_policy(
        self,
        genome: Node,
        rng: random.Random,
        *,
        max_depth: int,
        constant_scale: int,
        macro_names: tuple[str, ...],
        gene_bank: list[Node],
    ) -> Node:
        semantic_rate = self.config.semantic_mutation_rate
        if semantic_rate > 0.0 and self._semantic_ctx is not None and rng.random() < semantic_rate:
            semantic_candidate = apply_semantic_mutation(genome, self._semantic_ctx, rng)
            if semantic_candidate is not None:
                if semantic_candidate.depth() <= self.config.max_program_depth:
                    return semantic_candidate
                return self._shrink_tree(semantic_candidate, rng)

        roll = rng.random()
        if gene_bank and roll < self.config.gene_splice_rate:
            candidate = crossover(genome, rng.choice(gene_bank), rng)
        elif macro_names and roll < self.config.gene_splice_rate + 0.18:
            candidate = self._inject_macro_ref(genome, rng, macro_names)
        elif roll < self.config.gene_splice_rate + 0.18 + self.config.shrink_mutation_rate:
            candidate = self._shrink_tree(genome, rng)
        else:
            candidate = mutate(
                genome,
                rng,
                max_depth=max_depth,
                constant_scale=constant_scale,
                macro_names=macro_names,
            )
        if candidate.depth() > self.config.max_program_depth:
            return self._shrink_tree(candidate, rng)
        return candidate

    def _inject_macro_ref(self, genome: Node, rng: random.Random, macro_names: tuple[str, ...]) -> Node:
        if not macro_names:
            return genome.clone()
        path, _ = rng.choice(iter_path_nodes(genome))
        return replace_subtree(genome, path, Node("macro", value=rng.choice(macro_names)))

    def _shrink_tree(self, genome: Node, rng: random.Random) -> Node:
        candidates = [(path, node) for path, node in iter_path_nodes(genome) if node.children]
        if not candidates:
            return genome.clone()
        path, node = rng.choice(candidates)
        child = rng.choice(node.children)
        return replace_subtree(genome, path, child)

    def _update_macro_ecosystem(
        self,
        state: EngineState,
        champion: Organism,
        challenges: list[Challenge],
        macro_nodes: dict[str, Node],
        round_index: int,
    ) -> None:
        motif_support = self._collect_motif_support(state)
        staging_limit = max(4, self.config.max_macros // 2)
        kept: list[StagedMacro] = []
        for staged in state.macro_staging:
            render = staged.tree.render()
            support = len(motif_support.get(render, set()))
            staged.support = max(staged.support, support)
            if support > 0 or staged.reuse_count > 0:
                staged.last_seen_round = round_index
            staged.compression_gain = float(max(0, staged.tree.count_nodes() - 1))
            staged.transfer_gain = self._estimate_macro_transfer_gain(staged.tree, challenges, macro_nodes)
            if self._should_promote_staged_macro(state, staged):
                state.macro_library.append(
                    Macro(
                        name=staged.name,
                        tree=staged.tree.clone(),
                        created_round=staged.created_round,
                        uses=staged.reuse_count,
                    )
                )
                self.audit.append(
                    "macro_promoted",
                    {
                        "name": staged.name,
                        "round": round_index,
                        "support": staged.support,
                        "transfer_gain": staged.transfer_gain,
                        "compression_gain": staged.compression_gain,
                    },
                )
                continue
            if self._should_retire_staged_macro(staged, round_index):
                self.audit.append(
                    "macro_retired",
                    {
                        "name": staged.name,
                        "round": round_index,
                        "support": staged.support,
                        "transfer_gain": staged.transfer_gain,
                    },
                )
                continue
            kept.append(staged)
        state.macro_staging = kept

        if len(state.macro_staging) >= staging_limit or len(state.macro_library) >= self.config.max_macros:
            return

        existing_renders = {macro.tree.render() for macro in state.macro_library}
        existing_renders.update(staged.tree.render() for staged in state.macro_staging)
        candidates = dedupe_motifs(subtree_motifs(champion.genome, min_nodes=3, max_nodes=10), limit=16)
        candidates.sort(
            key=lambda node: (len(motif_support.get(node.render(), set())), node.complexity_score()),
            reverse=True,
        )
        for motif in candidates:
            render = motif.render()
            if render in existing_renders:
                continue
            transfer_gain = self._estimate_macro_transfer_gain(motif, challenges, macro_nodes)
            support = len(motif_support.get(render, set()))
            compression_gain = float(max(0, motif.count_nodes() - 1))
            if support == 0 and transfer_gain < 0.0:
                continue
            staged = StagedMacro(
                name=self._next_macro_name(state),
                tree=motif.clone(),
                created_round=round_index,
                source_family_id=champion.family_id,
                support=support,
                transfer_gain=transfer_gain,
                compression_gain=compression_gain,
                reuse_count=0,
                last_seen_round=round_index,
            )
            state.macro_staging.append(staged)
            self.audit.append(
                "macro_staged",
                {
                    "name": staged.name,
                    "tree": render,
                    "round": round_index,
                    "support": support,
                    "transfer_gain": transfer_gain,
                },
            )
            break

    def _estimate_macro_transfer_gain(
        self,
        motif: Node,
        challenges: list[Challenge],
        macro_nodes: dict[str, Node],
    ) -> float:
        sample_challenges = challenges[: min(2, len(challenges))]
        if not sample_challenges:
            return 0.0
        probe_name = "__probe_macro__"
        probe_macros = dict(macro_nodes)
        probe_macros[probe_name] = motif
        candidate_score = self._score_tree(
            Node("macro", value=probe_name),
            sample_challenges,
            probe_macros,
            total_challenge_count=len(challenges),
            train_case_limit=self.config.probe_train_cases,
            test_case_limit=self.config.probe_test_cases,
        )
        baseline_score = max(
            self._score_tree(
                Node("input"),
                sample_challenges,
                macro_nodes,
                total_challenge_count=len(challenges),
                train_case_limit=self.config.probe_train_cases,
                test_case_limit=self.config.probe_test_cases,
            ),
            self._score_tree(
                Node("const", value=0),
                sample_challenges,
                macro_nodes,
                total_challenge_count=len(challenges),
                train_case_limit=self.config.probe_train_cases,
                test_case_limit=self.config.probe_test_cases,
            ),
        )
        normalized = (candidate_score - baseline_score) / max(1, len(sample_challenges))
        return max(-1.0, min(2.0, normalized))

    def _should_promote_staged_macro(self, state: EngineState, staged: StagedMacro) -> bool:
        return (
            len(state.macro_library) < self.config.max_macros
            and staged.support >= self.config.macro_support_threshold
            and staged.transfer_gain >= self.config.macro_transfer_threshold
            and staged.compression_gain >= 2.0
        )

    def _should_retire_staged_macro(self, staged: StagedMacro, round_index: int) -> bool:
        age = round_index - staged.last_seen_round
        return age >= self.config.macro_retire_rounds and (
            staged.support < self.config.macro_support_threshold or staged.transfer_gain < 0.0
        )

    def _next_macro_name(self, state: EngineState) -> str:
        used = {macro.name for macro in state.macro_library}
        used.update(macro.name for macro in state.macro_staging)
        index = 1
        while True:
            name = f"M{index:03d}"
            if name not in used:
                return name
            index += 1

    def _collect_motif_support(self, state: EngineState) -> dict[str, set[str]]:
        support: dict[str, set[str]] = {}
        for family in state.families:
            family_renders: set[str] = set()
            elite = sorted(family.members, key=lambda member: member.score, reverse=True)[:2]
            for member in elite:
                for motif in subtree_motifs(member.genome, min_nodes=3, max_nodes=8):
                    family_renders.add(motif.render())
            for render in family_renders:
                support.setdefault(render, set()).add(family.family_id)
        return support

    def _macro_references(self, node: Node) -> list[str]:
        refs: list[str] = []
        stack = [node]
        while stack:
            current = stack.pop()
            if current.kind == "macro":
                refs.append(str(current.value))
            stack.extend(reversed(current.children))
        return refs

    def _macro_quality_map(self, state: EngineState) -> dict[str, float]:
        total_population = max(1, sum(len(family.members) for family in state.families))
        quality: dict[str, float] = {}
        for macro in state.macro_library:
            quality[macro.name] = min(1.0, macro.uses / total_population)
        for staged in state.macro_staging:
            quality[staged.name] = min(1.0, max(0.0, staged.transfer_gain))
        return quality

    def _macro_potential(self, organism: Organism, known_renders: set[str]) -> float:
        motifs = dedupe_motifs(subtree_motifs(organism.genome, min_nodes=3, max_nodes=6), limit=6)
        fresh = [motif for motif in motifs if motif.render() not in known_renders]
        if not fresh:
            return 0.0
        avg_size = sum(motif.count_nodes() for motif in fresh) / len(fresh)
        return min(1.0, len(fresh) / 4.0) * min(1.0, avg_size / 6.0)

    def _macro_transfer_bonus(self, organism: Organism, macro_quality: dict[str, float]) -> float:
        names = set(str(name) for name in organism.notes.get("macro_refs", []))
        if not names:
            return 0.0
        return min(1.5, sum(macro_quality.get(name, 0.0) for name in names))

    def _refresh_macro_usage(self, state: EngineState, round_index: int) -> None:
        usage_counts: dict[str, int] = {}
        for family in state.families:
            for member in family.members:
                for name in self._macro_references(member.genome):
                    usage_counts[name] = usage_counts.get(name, 0) + 1
        for macro in state.macro_library:
            macro.uses += usage_counts.get(macro.name, 0)
        for staged in state.macro_staging:
            hits = usage_counts.get(staged.name, 0)
            staged.reuse_count += hits
            if hits > 0:
                staged.last_seen_round = round_index

    def _mean_macro_transfer(self, state: EngineState) -> float:
        transfers = [staged.transfer_gain for staged in state.macro_staging if staged.transfer_gain > 0.0]
        if not transfers:
            return 0.0
        return mean(transfers)

    def _behavior_signature(self, executor: ProgramExecutor | None) -> str:
        if executor is None:
            return "invalid"
        outputs = [executor.run(value) for value in self._behavior_probe_inputs]
        buckets = tuple(max(-4, min(4, int(round(output / 8.0)))) for output in outputs)
        deltas = []
        for left, right in zip(outputs, outputs[1:]):
            if right > left:
                deltas.append(1)
            elif right < left:
                deltas.append(-1)
            else:
                deltas.append(0)
        return f"{buckets}|{tuple(deltas)}"

    def _signature_entropy(self, counts: dict[str, int]) -> float:
        total = sum(counts.values())
        if total <= 0:
            return 0.0
        entropy = 0.0
        for value in counts.values():
            probability = value / total
            entropy -= probability * math.log(probability + 1e-12, 2)
        return entropy

    def _update_frontier_archive(
        self,
        state: EngineState,
        champion: Organism,
        challenges: list[Challenge],
        macro_nodes: dict[str, Node],
        round_index: int,
    ) -> dict[str, int]:
        counts = {"dominated": 0, "frontier": 0, "impossible": 0}
        executor = self._executor_for(champion.genome, macro_nodes, self._executor_cache)
        if executor is None:
            return counts
        for challenge in challenges:
            soft, exact = self._score_dataset(executor, challenge.test_pairs)
            if exact >= 1.0:
                status = "dominated"
            elif soft >= 0.45:
                status = "frontier"
            else:
                status = "impossible"
            counts[status] += 1
            state.frontier_archive.append(
                {
                    "round": round_index,
                    "seed": challenge.seed,
                    "difficulty": challenge.difficulty,
                    "oracle": challenge.oracle_repr,
                    "oracle_kind": challenge.oracle_kind,
                    "best_soft": soft,
                    "best_exact": exact,
                    "status": status,
                }
            )
        state.frontier_archive = state.frontier_archive[-self.config.frontier_archive_limit :]
        return counts

    def _frontier_summary(self, archive: list[dict[str, object]]) -> dict[str, float]:
        if not archive:
            return {
                "dominated_ratio": 0.0,
                "frontier_ratio": 0.0,
                "impossible_ratio": 0.0,
                "learning_progress": 0.0,
            }
        window = archive[-min(len(archive), self.config.frontier_window * self.config.challenges_per_round) :]
        total = len(window)
        dominated = sum(1 for item in window if item.get("status") == "dominated")
        frontier = sum(1 for item in window if item.get("status") == "frontier")
        impossible = total - dominated - frontier
        return {
            "dominated_ratio": dominated / total,
            "frontier_ratio": frontier / total,
            "impossible_ratio": impossible / total,
            "learning_progress": self._frontier_learning_progress(archive),
        }

    def _frontier_learning_progress(self, archive: list[dict[str, object]]) -> float:
        block = self.config.frontier_window * self.config.challenges_per_round
        if len(archive) < block * 2:
            return 0.0
        previous = archive[-block * 2 : -block]
        current = archive[-block:]
        return self._frontier_block_score(current) - self._frontier_block_score(previous)

    def _frontier_block_score(self, block: list[dict[str, object]]) -> float:
        values = []
        for item in block:
            status = str(item.get("status", "impossible"))
            base = 1.0 if status == "dominated" else 0.5 if status == "frontier" else 0.0
            best_soft = item.get("best_soft", 0.0)
            soft = float(best_soft) if isinstance(best_soft, (int, float)) else 0.0
            values.append(base * 0.5 + soft * 0.5)
        return mean(values) if values else 0.0

    def _apply_fusion_rule(self, state: EngineState, rng: random.Random) -> None:
        if len(state.families) < 5:
            return
        ranked = sorted(state.families, key=lambda family: family.last_score, reverse=True)
        best_family = ranked[0]
        fifth_worst = ranked[-5]
        if len(best_family.members) < 10 or len(fifth_worst.members) < 3:
            return
        best_members = sorted(best_family.members, key=lambda member: member.score, reverse=True)
        donor_members = sorted(fifth_worst.members, key=lambda member: member.score, reverse=True)
        left = best_members[9]
        right = donor_members[2]
        fused = crossover(left.genome, right.genome, rng)
        if fused.count_nodes() > self.config.max_program_nodes:
            return
        child = self._new_organism(
            state,
            best_family.family_id,
            fused,
            lineage_depth=best_family.lineage_depth,
            birth_round=state.round_index,
        )
        weakest_index = min(range(len(best_family.members)), key=lambda idx: best_family.members[idx].score)
        best_family.members[weakest_index] = child
        self.audit.append(
            "fusion",
            {
                "best_family": best_family.family_id,
                "source_family": fifth_worst.family_id,
                "left": left.organism_id,
                "right": right.organism_id,
            },
        )

    def _apply_character_events(self, state: EngineState, rng: random.Random, round_index: int) -> None:
        if round_index % 3 == 0:
            weakest = min(state.families, key=lambda family: family.last_score)
            art = repeated_pattern_tree(rng)
            weakest_index = min(range(len(weakest.members)), key=lambda idx: weakest.members[idx].score)
            weakest.members[weakest_index] = self._new_organism(
                state,
                weakest.family_id,
                art,
                lineage_depth=weakest.lineage_depth,
                birth_round=round_index,
            )
            self.audit.append("artist", {"family": weakest.family_id, "program": art.render(), "round": round_index})

        if round_index % 7 == 0:
            recent = [item for item in state.graveyard if item["round"] >= round_index - 9]
            if recent:
                best = max(recent, key=lambda item: item["score"])
                weakest = min(state.families, key=lambda family: family.last_score)
                raw_organism = best["organism"]
                revived_source = (
                    Organism.from_compact(raw_organism)
                    if isinstance(raw_organism, list)
                    else Organism.from_dict(raw_organism)
                )
                revived = self._new_organism(
                    state,
                    weakest.family_id,
                    revived_source.genome.clone(),
                    lineage_depth=weakest.lineage_depth,
                    birth_round=round_index,
                )
                weakest_index = min(range(len(weakest.members)), key=lambda idx: weakest.members[idx].score)
                weakest.members[weakest_index] = revived
                self.audit.append("cleric", {"family": weakest.family_id, "revived": revived.organism_id, "round": round_index})

        threshold = state.total_families_created // 15
        if state.total_families_created > 0 and state.total_families_created % 15 == 0 and threshold not in state.thief_thresholds_seen:
            state.thief_thresholds_seen.append(threshold)
            host = rng.choice(state.families)
            top_families = sorted(state.families, key=lambda family: family.last_score, reverse=True)[:3]
            victims = rng.sample(top_families, k=min(2, len(top_families)))
            stolen: list[str] = []
            for victim in victims:
                ranked_members = sorted(victim.members, key=lambda member: member.score, reverse=True)
                limit = min(5, len(ranked_members))
                target = ranked_members[rng.randrange(limit)]
                host_index = min(range(len(host.members)), key=lambda idx: host.members[idx].score)
                host.members[host_index] = self._new_organism(
                    state,
                    host.family_id,
                    target.genome.clone(),
                    lineage_depth=host.lineage_depth,
                    birth_round=round_index,
                )
                stolen.append(target.organism_id)
            self.audit.append("thief", {"host": host.family_id, "stolen": stolen, "round": round_index})

    def _extinguish_one_family(self, state: EngineState, rng: random.Random, round_index: int) -> None:
        ranked = sorted(
            state.families,
            key=lambda family: family.last_score + family.last_diversity * 0.25,
            reverse=True,
        )
        eliminated = ranked[-1]
        survivors = sorted(eliminated.members, key=lambda member: member.score, reverse=True)[:7]
        state.graveyard.extend(
            {
                "round": round_index,
                "score": member.score,
                "organism": member.to_compact(nested_family=False),
            }
            for member in survivors
        )
        state.graveyard = state.graveyard[-128:]
        state.families = [family for family in state.families if family.family_id != eliminated.family_id]

        hosts = state.families[:]
        rng.shuffle(hosts)
        rng.shuffle(survivors)
        reproducers = survivors[:3]
        donors = survivors[3:]
        for survivor, host in zip(reproducers, hosts):
            host.members.append(
                self._new_organism(
                    state,
                    host.family_id,
                    survivor.genome.clone(),
                    lineage_depth=host.lineage_depth,
                    birth_round=round_index,
                )
            )
        for donor, host in zip(donors, hosts[3:] + hosts[:3]):
            motifs = subtree_motifs(donor.genome)
            if motifs:
                host.gene_bank.extend(motifs[:1])
                host.gene_bank = dedupe_motifs(host.gene_bank, limit=18)

        fresh_family = self._make_fresh_family(state, rng, created_round=round_index)
        state.families.append(fresh_family)
        self.audit.append(
            "extinction",
            {
                "round": round_index,
                "eliminated_family": eliminated.family_id,
                "survivors": [member.organism_id for member in survivors],
                "fresh_family": fresh_family.family_id,
            },
        )

    def _adapt_difficulty(self, state: EngineState, champion: Organism) -> None:
        frontier = self._frontier_summary(state.frontier_archive)
        solved_ratio = champion.solved_challenges / max(1, self.config.challenges_per_round)
        if frontier["dominated_ratio"] >= 0.55 and frontier["learning_progress"] >= 0.01:
            state.frontier_difficulty += 1
        elif frontier["impossible_ratio"] >= 0.65 and frontier["learning_progress"] <= -0.02 and state.frontier_difficulty > 1:
            state.frontier_difficulty -= 1
        elif solved_ratio >= 2 / 3 and champion.exact_rate >= 0.5:
            state.frontier_difficulty += 1
        elif solved_ratio == 0 and champion.soft_rate < 0.25 and state.frontier_difficulty > 1:
            state.frontier_difficulty -= 1

    def _climate_label(self, climate_mode: int) -> str:
        return "multiply_pi" if climate_mode == 0 else "divide_2.967"
