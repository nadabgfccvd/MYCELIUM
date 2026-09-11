"""Conservative paired statistical decision engine (Roadmap Phase 2).

This module replaces "compare means with fixed thresholds" by sound paired
inference over per-seed deltas, following the protocol of paired multi-seed
benchmarking (BCa bootstrap confidence intervals + sign-flip permutation
tests), with Holm/Benjamini-Hochberg multiple-testing correction and
sequential racing for early futility stopping.

Everything is dependency-free (stdlib only) and deterministic given a seed.
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from statistics import NormalDist
from typing import Any
from collections.abc import Callable, Sequence

_NORM = NormalDist()

# Advisory diagnostics deliberately live in this module and are never imported
# by the decision path.  They describe evidence quality without changing a
# verdict or acceptance threshold.
ADVISORY_POWER_TARGET = 0.80
ADVISORY_THIN_MARGIN_RATIO = 0.10
ADVISORY_NOISY_CI_RATIO = 2.0


@lru_cache(maxsize=64)
def _bootstrap_index_matrix(
    n: int, n_bootstrap: int, seed: int,
) -> tuple[tuple[int, ...], ...]:
    """Frozen resample-index matrix for one ``(n, n_bootstrap, seed)``.

    The bootstrap only depends on the *indices* drawn; the data vary per
    comparison. Within one sweep every comparison uses the same ``n`` and
    ``seed`` (compare_paired_metric defaults to seed=13), so drawing the index
    matrix once and indexing each candidate's deltas with it removes ~85% of
    the decision loop's runtime (it was dominated by ``random.randrange``).
    Indices are generated and stored in the exact order the inlined loop drew
    them, so every bootstrap mean sums its terms in the same order as before —
    bit-for-bit identical CIs (verified against frozen replay verdicts and a
    numeric snapshot, Ciclo 3/S2).
    """
    rng = random.Random(seed)
    randrange = rng.randrange
    return tuple(tuple(randrange(n) for _ in range(n)) for _ in range(n_bootstrap))


@dataclass(slots=True)
class PairedComparison:
    """Full paired comparison for a single metric."""

    metric: str
    n_pairs: int
    mean_delta: float
    median_delta: float
    ci_low: float
    ci_high: float
    confidence: float
    p_value: float
    p_value_corrected: float | None
    effect_dz: float
    prob_superior: float
    direction: int  # +1 means higher-is-better for the metric delta; -1 lower-is-better
    deltas: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def significant(self) -> bool:
        """True when the confidence interval excludes zero (on the raw delta)."""
        return self.ci_low > 0.0 or self.ci_high < 0.0


@dataclass(slots=True)
class AcceptancePolicy:
    """Conservative acceptance policy parameters.

    A candidate is accepted only if *all* of the following hold for every
    guard metric:

    * throughput metric: CI lower bound of the delta exceeds ``min_gain``;
    * quality metrics: CI lower bound of the delta exceeds ``-max_drop``;
    * the (corrected) permutation p-value is at most ``alpha`` for the
      improvement claim on the primary metric;

    Futility-only quality metrics use their raw p-value against
    ``quality_alpha`` as a *one-sided regression* alarm.
    """

    confidence: float = 0.95
    alpha: float = 0.05
    quality_alpha: float = 0.10
    correction: str = "holm"  # "holm" | "bh" | "none"
    min_pairs: int = 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def paired_deltas(
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    direction: int = 1,
) -> list[float]:
    """Deltas per paired seed, sign-adjusted so positive means improvement."""
    if len(baseline) != len(candidate):
        raise ValueError("Paired comparison requires equal-length samples (same seeds).")
    if not baseline:
        raise ValueError("Paired comparison requires at least one pair.")
    sign = 1.0 if direction >= 0 else -1.0
    return [sign * (c - b) for b, c in zip(baseline, candidate)]


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = q * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = min(lower + 1, len(sorted_values) - 1)
    frac = position - lower
    return float(sorted_values[lower] * (1.0 - frac) + sorted_values[upper] * frac)


def _legacy_float_sum(values: Any) -> float:
    """Reproduce pre-3.14 left-to-right float addition deterministically."""
    total: float | int = 0
    for value in values:
        total += value
    return float(total)


def _legacy_normal_cdf(value: float) -> float:
    """Use the pre-3.14 ``NormalDist.cdf`` arithmetic for frozen BCa values."""
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _jackknife_acceleration(data: list[float]) -> float:
    """Q3.2: BCa acceleration constant via the jackknife (extracted verbatim)."""
    n = len(data)
    jack_means: list[float] = []
    for i in range(n):
        total = 0.0
        for j, value in enumerate(data):
            if j != i:
                total += value
        jack_means.append(total / (n - 1))
    jack_mean = _legacy_float_sum(jack_means) / n
    try:
        numerator = _legacy_float_sum((jack_mean - m) ** 3 for m in jack_means)
        denominator = 6.0 * (_legacy_float_sum((jack_mean - m) ** 2 for m in jack_means) ** 1.5)
    except OverflowError:
        return 0.0  # M3: huge-but-finite data skips acceleration, never crashes
    return numerator / denominator if denominator > 0 else 0.0


def bca_bootstrap_ci(
    deltas: Sequence[float],
    *,
    confidence: float = 0.95,
    n_bootstrap: int = 5000,
    seed: int = 13,
) -> tuple[float, float]:
    """Bias-corrected and accelerated (BCa) bootstrap CI for the mean delta.

    Falls back to the percentile interval when degenerate input prevents the
    bias/acceleration correction (e.g. all deltas identical).
    """
    if not 0.0 < confidence < 1.0:  # M3: fail fast, never StatisticsError
        raise ValueError(f"BCa CI requires confidence in (0, 1), got {confidence}.")
    data = [float(v) for v in deltas]
    n = len(data)
    if n == 0:
        raise ValueError("BCa CI requires at least one observation.")
    if n == 1:
        return data[0], data[0]

    theta_hat = _legacy_float_sum(data) / n
    boot_means: list[float] = []
    for indices in _bootstrap_index_matrix(n, n_bootstrap, seed):
        total = 0.0
        for j in indices:
            total += data[j]
        boot_means.append(total / n)
    boot_means.sort()

    below = sum(1 for value in boot_means if value < theta_hat)
    prop = min(max(below / n_bootstrap, 1e-9), 1.0 - 1e-9)
    z0 = _NORM.inv_cdf(prop)

    acceleration = _jackknife_acceleration(data)

    alpha = (1.0 - confidence) / 2.0
    z_alpha_lo = _NORM.inv_cdf(alpha)
    z_alpha_hi = _NORM.inv_cdf(1.0 - alpha)

    def _adjust(z_alpha: float) -> float:
        denom = 1.0 - acceleration * (z0 + z_alpha)
        if denom == 0.0:
            denom = 1e-12
        adjusted = z0 + (z0 + z_alpha) / denom
        return _legacy_normal_cdf(adjusted)

    q_lo = min(max(_adjust(z_alpha_lo), 0.0), 1.0)
    q_hi = min(max(_adjust(z_alpha_hi), 0.0), 1.0)
    if q_lo > q_hi:
        q_lo, q_hi = q_hi, q_lo
    return _quantile(boot_means, q_lo), _quantile(boot_means, q_hi)


def percentile_ci(
    deltas: Sequence[float],
    *,
    confidence: float = 0.95,
    n_bootstrap: int = 5000,
    seed: int = 13,
) -> tuple[float, float]:
    """Plain percentile bootstrap CI for the mean (cheap fallback)."""
    if not 0.0 < confidence < 1.0:  # M3: fail fast, never StatisticsError
        raise ValueError(f"CI requires confidence in (0, 1), got {confidence}.")
    data = [float(v) for v in deltas]
    n = len(data)
    if n == 0:
        raise ValueError("CI requires at least one observation.")
    if n == 1:
        return data[0], data[0]
    boot_means: list[float] = []
    for indices in _bootstrap_index_matrix(n, n_bootstrap, seed):
        # ``fsum`` preserves the pre-memoization percentile values (notably
        # 0.1 rather than 0.09999999999999999 for decimal fixtures) while the
        # index matrix still supplies the exact historical draw sequence.
        boot_means.append(math.fsum(data[j] for j in indices) / n)
    boot_means.sort()
    alpha = (1.0 - confidence) / 2.0
    return _quantile(boot_means, alpha), _quantile(boot_means, 1.0 - alpha)


def _exact_sign_flip(data: list[float], observed: float, two_sided: bool) -> float:
    """Q3.2: exhaustive 2^n sign enumeration (extracted verbatim)."""
    n = len(data)

    def _exceeds(value: float) -> bool:
        if two_sided:
            return abs(value) >= observed - 1e-12
        return value >= observed - 1e-12

    exceed = 0
    total = 1 << n
    for mask in range(total):
        total_flip = 0.0
        for i in range(n):
            total_flip += data[i] if (mask >> i) & 1 == 0 else -data[i]
        if _exceeds(total_flip):
            exceed += 1
    return exceed / total


def sign_flip_permutation_test(
    deltas: Sequence[float],
    *,
    n_permutations: int = 10000,
    seed: int = 13,
    alternative: str = "two-sided",
) -> float:
    """Permutation test over sign flips of paired deltas.

    Under the null of no effect, the sign of each paired delta is a fair coin.
    ``alternative="two-sided"`` tests |sum| (generic); ``alternative="greater"``
    tests sum > 0 — the pre-registered directional form used by acceptance
    decisions, whose exact floor (1/2^n) gives small-n experiments real power.

    Exact enumeration (2^n) is used when 7 <= n <= 16 (two-sided floor
    2/2^n <= 1/64 is below 0.05 there); outside that range a Monte Carlo
    estimate with continuity correction is used.
    """
    data = [float(v) for v in deltas]
    n = len(data)
    if n == 0:
        raise ValueError("Permutation test requires at least one observation.")
    if any(not math.isfinite(v) for v in data):
        # Q1.5: NaN/inf deltas are uninformative — fail to reject (p = 1).
        # (NaN comparisons otherwise collapse to p = 0.0, a bogus accept.)
        return 1.0
    if alternative not in {"two-sided", "greater"}:
        raise ValueError(f"Unknown alternative: {alternative}")
    two_sided = alternative == "two-sided"
    observed = abs(sum(data)) if two_sided else sum(data)

    def _exceeds(value: float) -> bool:
        if two_sided:
            return abs(value) >= observed - 1e-12
        return value >= observed - 1e-12

    if 7 <= n <= 16:
        return _exact_sign_flip(data, observed, two_sided)

    rng = random.Random(seed)
    # bind locals; the RNG draw sequence and summation order are unchanged, so
    # the Monte Carlo p-value stays bit-for-bit identical (Ciclo 3/S2).
    random_float = rng.random
    exceed = 0
    for _ in range(n_permutations):
        total_flip = 0.0
        for value in data:
            total_flip += value if random_float() < 0.5 else -value
        if _exceeds(total_flip):
            exceed += 1
    return (exceed + 1) / (n_permutations + 1)


def effect_size(deltas: Sequence[float]) -> tuple[float, float, float]:
    """Paired effect sizes: Cohen's dz, median delta, P(improvement)."""
    data = [float(v) for v in deltas]
    n = len(data)
    if n == 0:
        raise ValueError("Effect size requires at least one observation.")
    mean_delta = sum(data) / n
    if n >= 2:
        try:
            variance = sum((v - mean_delta) ** 2 for v in data) / (n - 1)
        except OverflowError:
            variance = float("inf")  # M3: huge-but-finite deltas degrade, never crash
        std = math.sqrt(variance)
    else:
        std = 0.0
    dz = mean_delta / std if std > 0 else (0.0 if mean_delta == 0 else math.copysign(float("inf"), mean_delta))
    sorted_data = sorted(data)
    median = _quantile(sorted_data, 0.5)
    wins = sum(1 for v in data if v > 0)
    ties = sum(1 for v in data if v == 0)
    prob_superior = (wins + 0.5 * ties) / n
    return dz, median, prob_superior


def compare_paired_metric(
    metric: str,
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    direction: int = 1,
    confidence: float = 0.95,
    seed: int = 13,
    n_bootstrap: int = 2000,
    n_permutations: int = 10000,
    alternative: str = "two-sided",
) -> PairedComparison:
    """Full paired report for one metric under the same paired seeds."""
    deltas = paired_deltas(baseline, candidate, direction=direction)
    ci_low, ci_high = bca_bootstrap_ci(deltas, confidence=confidence, n_bootstrap=n_bootstrap, seed=seed)
    p_value = sign_flip_permutation_test(deltas, n_permutations=n_permutations, seed=seed, alternative=alternative)
    dz, median, prob_superior = effect_size(deltas)
    return PairedComparison(
        metric=metric,
        n_pairs=len(deltas),
        mean_delta=sum(deltas) / len(deltas),
        median_delta=median,
        ci_low=ci_low,
        ci_high=ci_high,
        confidence=confidence,
        p_value=p_value,
        p_value_corrected=None,
        effect_dz=dz,
        prob_superior=prob_superior,
        direction=1 if direction >= 0 else -1,
        deltas=deltas,
    )


def multiple_testing_correction(
    p_values: Sequence[float],
    *,
    method: str = "holm",
) -> list[float]:
    """Correct p-values across the family of simultaneous comparisons.

    * ``holm``: Holm-Bonferroni (FWER control, uniformly more powerful than
      Bonferroni).
    * ``bh``: Benjamini-Hochberg (FDR control).
    * ``none``: identity (for callers that handle multiplicity elsewhere).
    """
    p = [float(v) for v in p_values]
    m = len(p)
    if m == 0:
        return []
    if method == "none":
        return p
    if method not in {"holm", "bh"}:
        raise ValueError(f"Unknown correction method: {method}")

    order = sorted(range(m), key=lambda i: p[i])
    corrected = [0.0] * m
    if method == "holm":
        running = 0.0
        for rank, idx in enumerate(order):
            value = min(1.0, (m - rank) * p[idx])
            running = max(running, value)
            corrected[idx] = running
    else:  # bh
        running = 1.0
        for rank in range(m - 1, -1, -1):
            idx = order[rank]
            value = min(1.0, p[idx] * m / (rank + 1))
            running = min(running, value)
            corrected[idx] = running
    return corrected


def apply_correction(comparisons: list[PairedComparison], *, method: str = "holm") -> None:
    """Fill ``p_value_corrected`` in-place across a family of comparisons."""
    corrected = multiple_testing_correction([c.p_value for c in comparisons], method=method)
    for comparison, value in zip(comparisons, corrected):
        comparison.p_value_corrected = value


@dataclass(slots=True)
class RaceResult:
    """Outcome of sequential racing over a candidate set."""

    champion: str
    eliminated: list[str]
    rounds_run: int
    comparisons: dict[str, PairedComparison]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["comparisons"] = {key: value.to_dict() for key, value in self.comparisons.items()}
        return payload


def sequential_racing(
    candidates: dict[str, Callable[[int, int], float]],
    seeds: Sequence[int],
    *,
    higher_is_better: bool = True,
    min_rounds: int | None = None,
    confidence: float = 0.95,
    futility_margin: float = 0.0,
    seed: int = 13,
) -> RaceResult:
    """Race candidates round-by-round over paired seeds, dropping losers early.

    Each callable receives ``(round_index, seed)`` and must deterministically
    return that round's paired measurement. After ``min_rounds`` rounds, any
    challenger whose BCa CI upper bound against the current incumbent falls
    below ``futility_margin`` (i.e. it cannot plausibly win) is eliminated.
    """
    if not candidates:
        raise ValueError("sequential_racing needs at least one candidate.")
    names = list(candidates)
    alive = set(names)
    direction = 1 if higher_is_better else -1
    min_rounds = min_rounds if min_rounds is not None else max(2, min(3, len(seeds)))
    scores: dict[str, list[float]] = {name: [] for name in names}
    eliminated: list[str] = []
    comparisons: dict[str, PairedComparison] = {}

    rounds_run = 0
    for round_index, pair_seed in enumerate(seeds):
        rounds_run += 1
        for name in list(alive):
            scores[name].append(candidates[name](round_index, pair_seed))
        if rounds_run < min_rounds or len(alive) <= 1:
            continue

        def _mean(name: str) -> float:
            values = scores[name]
            return sum(values) / len(values)

        incumbent = max(alive, key=lambda name: direction * _mean(name))
        for name in list(alive):
            if name == incumbent:
                continue
            comparison = compare_paired_metric(
                f"race:{name}",
                scores[incumbent],
                scores[name],
                direction=direction,
                confidence=confidence,
                seed=seed + rounds_run,
            )
            comparisons[name] = comparison
            if comparison.ci_high < futility_margin:
                alive.remove(name)
                eliminated.append(name)

    champion = max(alive, key=lambda name: direction * (sum(scores[name]) / len(scores[name])))
    return RaceResult(
        champion=champion,
        eliminated=eliminated,
        rounds_run=rounds_run,
        comparisons=comparisons,
    )


def paired_power(
    effect_dz: float,
    n_pairs: int,
    *,
    alpha: float = 0.05,
) -> float:
    """Approximate one-sided paired-test power for a standardized effect.

    This is an advisory normal approximation, not part of any acceptance
    decision.  At a null effect it returns ``alpha``; positive effects gain
    power as pairs increase, while negative effects lose it.  Invalid inputs
    are rejected explicitly so a diagnostic cannot silently manufacture a
    reassuring number.
    """
    if isinstance(n_pairs, bool) or not isinstance(n_pairs, int) or n_pairs <= 0:
        raise ValueError(f"n_pairs must be a positive integer, got {n_pairs!r}.")
    if not isinstance(effect_dz, (int, float)) or isinstance(effect_dz, bool):
        raise ValueError(f"effect_dz must be numeric, got {effect_dz!r}.")
    if not isinstance(alpha, (int, float)) or isinstance(alpha, bool):
        raise ValueError(f"alpha must be numeric, got {alpha!r}.")
    alpha = float(alpha)
    if not math.isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha!r}.")
    effect = float(effect_dz)
    if math.isnan(effect) or effect == float("-inf"):
        return 0.0
    if effect == float("inf"):
        return 1.0
    critical = _NORM.inv_cdf(1.0 - alpha)
    power = _NORM.cdf(effect * math.sqrt(n_pairs) - critical)
    return min(1.0, max(0.0, power))


def diagnose_comparison(comparison: PairedComparison) -> dict[str, Any]:
    """Return descriptive evidence-quality diagnostics for one comparison.

    The returned sheet is intentionally stable and contains no verdict field.
    It can be displayed in reports or used to explain why a result is noisy,
    underpowered, or close to its decision boundary without affecting the
    registered statistical decision path.
    """
    n_pairs = int(comparison.n_pairs)
    ci_width = float(comparison.ci_high - comparison.ci_low)
    margin_above_zero = max(0.0, float(comparison.ci_low))
    if comparison.mean_delta == 0.0:
        rel_margin: float | None = None
    else:
        rel_margin = margin_above_zero / abs(float(comparison.mean_delta))

    approx_power = paired_power(comparison.effect_dz, n_pairs)
    notes: list[str] = []
    min_pairs = AcceptancePolicy().min_pairs
    if n_pairs < min_pairs:
        notes.append(
            f"n_pairs={n_pairs} is below the policy min_pairs={min_pairs}; "
            "the comparison is descriptive only."
        )
    elif n_pairs < 7:
        notes.append(
            "Monte-Carlo permutation resolution is limited below 7 paired seeds."
        )
    if approx_power < ADVISORY_POWER_TARGET:
        notes.append(
            f"approximate power {approx_power:.3f} is below the "
            f"{ADVISORY_POWER_TARGET:.2f} advisory target."
        )
    if rel_margin is not None and 0.0 < rel_margin < ADVISORY_THIN_MARGIN_RATIO:
        notes.append(
            f"thin margin: the CI lower bound is only {rel_margin:.1%} of the mean effect."
        )
    if comparison.mean_delta != 0.0 and ci_width / abs(float(comparison.mean_delta)) > ADVISORY_NOISY_CI_RATIO:
        notes.append(
            f"noisy CI: width/effect ratio exceeds {ADVISORY_NOISY_CI_RATIO:.1f}."
        )

    exact_p_floor = 1.0 / (2 ** n_pairs) if 7 <= n_pairs <= 16 else None
    return {
        "metric": comparison.metric,
        "n_pairs": n_pairs,
        "effect_dz": comparison.effect_dz,
        "approx_power_one_sided": approx_power,
        "power_alpha": 1.0 - comparison.confidence,
        "ci_width": ci_width,
        "margin_above_zero": margin_above_zero,
        "rel_margin": rel_margin,
        "exact_p_floor": exact_p_floor,
        "notes": notes,
    }


