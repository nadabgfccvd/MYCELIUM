from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .prime import require_prime


@dataclass(slots=True)
class Config:
    seed: int
    state_dir: str = ".mycelium_state"
    family_count: int = 7
    family_size: int = 11
    tournament_size: int = 3
    survivors_per_extinction: int = 7
    challenges_per_round: int = 3
    train_cases: int = 8
    test_cases: int = 16
    initial_difficulty: int = 2
    max_program_depth: int = 5
    max_program_nodes: int = 63
    max_abs_value: int = 100_000
    max_eval_steps: int = 256
    max_macros: int = 24
    checkpoint_every: int = 10
    state_save_every: int = 10
    probe_challenges: int = 2
    probe_train_cases: int = 2
    probe_test_cases: int = 4
    full_rescore_top_k: int = 4
    full_rescore_random_k: int = 1
    persistence_backend: str = "json"
    climate_weight: float = 0.03
    novelty_weight: float = 0.04
    macro_potential_weight: float = 0.03
    transfer_weight: float = 0.03
    macro_support_threshold: int = 2
    macro_transfer_threshold: float = 0.12
    macro_retire_rounds: int = 12
    compositional_challenge_rate: float = 0.34
    niche_probe_count: int = 5
    frontier_archive_limit: int = 96
    frontier_window: int = 12
    gene_splice_rate: float = 0.25
    shrink_mutation_rate: float = 0.12
    semantic_mutation_rate: float = 0.0
    semantic_probe_count: int = 7
    counterexample_limit: int = 256
    counterexample_harvest_top_k: int = 8
    anti_forgetting: bool = False
    ecology_reseed_rounds: int = 0
    ecology_patience: int = 8
    adaptive_novelty: bool = False

    def __post_init__(self) -> None:  # noqa: C901 — Q3.2: declarative validation chain, one check per field.
        require_prime(self.seed)
        if self.tournament_size <= 1 or self.tournament_size % 2 == 0:
            raise ValueError("Tournament size must be odd and greater than 1.")
        if self.family_count < 5:
            raise ValueError("family_count must be at least 5 for the fusion rule.")
        if self.family_size < 10:
            raise ValueError("family_size must be at least 10 for the fusion rule.")
        if self.survivors_per_extinction != 7:
            raise ValueError("This prototype fixes survivors_per_extinction to 7.")
        if self.state_save_every < 1:
            raise ValueError("state_save_every must be at least 1.")
        if self.probe_challenges < 1:
            raise ValueError("probe_challenges must be at least 1.")
        if self.probe_train_cases < 1 or self.probe_train_cases > self.train_cases:
            raise ValueError("probe_train_cases must be between 1 and train_cases.")
        if self.probe_test_cases < 1 or self.probe_test_cases > self.test_cases:
            raise ValueError("probe_test_cases must be between 1 and test_cases.")
        if self.full_rescore_top_k < 1 or self.full_rescore_top_k > self.family_size:
            raise ValueError("full_rescore_top_k must be between 1 and family_size.")
        if self.full_rescore_random_k < 0 or self.full_rescore_random_k > self.family_size:
            raise ValueError("full_rescore_random_k must be between 0 and family_size.")
        if self.persistence_backend not in {"json", "pickle"}:
            raise ValueError("persistence_backend must be 'json' or 'pickle'.")
        if self.novelty_weight < 0.0:
            raise ValueError("novelty_weight must be non-negative.")
        if self.macro_potential_weight < 0.0:
            raise ValueError("macro_potential_weight must be non-negative.")
        if self.transfer_weight < 0.0:
            raise ValueError("transfer_weight must be non-negative.")
        if self.macro_support_threshold < 1:
            raise ValueError("macro_support_threshold must be at least 1.")
        if self.macro_transfer_threshold < 0.0:
            raise ValueError("macro_transfer_threshold must be non-negative.")
        if self.macro_retire_rounds < 1:
            raise ValueError("macro_retire_rounds must be at least 1.")
        if not 0.0 <= self.compositional_challenge_rate <= 1.0:
            raise ValueError("compositional_challenge_rate must be between 0 and 1.")
        if self.niche_probe_count < 3:
            raise ValueError("niche_probe_count must be at least 3.")
        if self.frontier_archive_limit < self.challenges_per_round:
            raise ValueError("frontier_archive_limit must be at least challenges_per_round.")
        if self.frontier_window < 3:
            raise ValueError("frontier_window must be at least 3.")
        if not 0.0 <= self.gene_splice_rate <= 1.0:
            raise ValueError("gene_splice_rate must be between 0 and 1.")
        if not 0.0 <= self.shrink_mutation_rate <= 1.0:
            raise ValueError("shrink_mutation_rate must be between 0 and 1.")
        if not 0.0 <= self.semantic_mutation_rate <= 1.0:
            raise ValueError("semantic_mutation_rate must be between 0 and 1.")
        if self.semantic_probe_count < 3:
            raise ValueError("semantic_probe_count must be at least 3.")
        if self.counterexample_limit < 8:
            raise ValueError("counterexample_limit must be at least 8.")
        if self.counterexample_harvest_top_k < 1:
            raise ValueError("counterexample_harvest_top_k must be at least 1.")
        if self.ecology_reseed_rounds < 0:
            raise ValueError("ecology_reseed_rounds must be non-negative (0 disables).")
        if self.ecology_patience < 2:
            raise ValueError("ecology_patience must be at least 2.")

    @property
    def state_path(self) -> Path:
        return Path(self.state_dir)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> Config:
        from dataclasses import fields as _fields

        known = {f.name for f in _fields(cls)}
        return cls(**{k: v for k, v in payload.items() if k in known})  # type: ignore[arg-type]
