"""Correctness validators for optimization layers (Roadmap Phase 5).

Layered verification: cheap behavioral equivalence first, metamorphic
relations second, formal translation validation (Alive2 / MLIR equality
saturation) when the toolchains exist on the host.
"""
from .behavioral import (
    EquivalenceReport,
    verify_equivalent,
    verify_equivalent_with_cases,
)
from .metamorphic import MetamorphicRelation, verify_metamorphic

__all__ = [
    "EquivalenceReport",
    "MetamorphicRelation",
    "verify_equivalent",
    "verify_equivalent_with_cases",
    "verify_metamorphic",
]
