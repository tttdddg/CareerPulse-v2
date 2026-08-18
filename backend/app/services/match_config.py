"""Central deterministic configuration for ability matching."""

from __future__ import annotations

from types import MappingProxyType


CALCULATION_VERSION = "deterministic-match-v2"
LEGACY_ALGORITHM_VERSION = "deterministic-v1"
WEIGHT_TOLERANCE = 1e-6
CONFIDENCE_FLOOR = 0.3
SCORING_COVERAGE_FLOOR = 0.5

# Ordered from the highest threshold to the lowest.  Keeping the mapping here
# prevents score semantics from being scattered across Service and Agent code.
MATCH_LEVEL_THRESHOLDS = (
    (80.0, "high"),
    (60.0, "good"),
    (40.0, "fair"),
    (20.0, "weak"),
    (0.0, "low"),
)

# Confidence describes result reliability, not student ability.  Missing
# components are omitted and the remaining component weights are normalized.
CONFIDENCE_COMPONENT_WEIGHTS = MappingProxyType(
    {
        "evidence_quality": 0.6,
        "required_skill_coverage": 0.3,
        "profile_completeness": 0.1,
    }
)

IMPORTANCE_ORDER = MappingProxyType(
    {"critical": 0, "important": 1, "nice_to_have": 2}
)


__all__ = [
    "CALCULATION_VERSION",
    "CONFIDENCE_COMPONENT_WEIGHTS",
    "CONFIDENCE_FLOOR",
    "IMPORTANCE_ORDER",
    "LEGACY_ALGORITHM_VERSION",
    "MATCH_LEVEL_THRESHOLDS",
    "SCORING_COVERAGE_FLOOR",
    "WEIGHT_TOLERANCE",
]
