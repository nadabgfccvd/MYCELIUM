"""In-loop ecology (Roadmap C1): anti-forgetting + stagnation reseed.

Lives behind Config flags (default OFF). The engine calls into this module
once per round; all decisions are local, deterministic and cheap:

* **EliteArchive** — remembers the best genome ever seen *in this process*
  (per-process by design; slices rebuild it — documented limitation).
* **decline_streak** — triggers elite re-injection when best_score keeps
  falling for ``patience`` rounds (anti-forgetting).
* **frontier_stalled** — triggers family reseed when frontier_difficulty has
  not moved for ``reseed_rounds`` (stagnation escape hatch).
* **novelty_boost** — scales novelty weight when niches collapse (< 3 active).
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from collections.abc import Sequence


@dataclass(slots=True)
class EliteArchive:
    best_genome: Any = None
    best_score: float = float("-inf")
    best_round: int = -1
    injections: int = 0
    reseeds: int = 0

    def note(self, genome: Any, score: float, round_index: int) -> bool:
        """Record a champion. Returns True if it is the new all-time best."""
        if float(score) > self.best_score:
            self.best_genome = deepcopy(genome)
            self.best_score = float(score)
            self.best_round = int(round_index)
            return True
        return False

    def elite_genome(self) -> Any | None:
        return deepcopy(self.best_genome) if self.best_genome is not None else None


def decline_streak(scores: Sequence[float], patience: int) -> bool:
    """True when the last ``patience`` scores never beat the window start.

    (Strictly weaker than 'monotonic decline': any flat-or-falling window of
    length ``patience`` counts — forgetting looks like a ceiling, not a slope.)
    """
    if patience < 2 or len(scores) < patience:
        return False
    window = [float(s) for s in scores[-patience:]]
    return max(window[1:]) <= window[0]


def frontier_stalled(difficulties: Sequence[float | int], reseed_rounds: int) -> bool:
    """True when frontier difficulty has not moved for ``reseed_rounds``."""
    if reseed_rounds < 2 or len(difficulties) < reseed_rounds:
        return False
    tail = list(difficulties[-reseed_rounds:])
    return all(d == tail[0] for d in tail)


def novelty_boost(active_niches: int, enabled: bool) -> float:
    """Adaptive novelty multiplier: ×3 when niches collapse below 3."""
    if not enabled:
        return 1.0
    return 3.0 if int(active_niches) < 3 else 1.0
