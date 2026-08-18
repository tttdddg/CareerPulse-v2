"""Central deterministic configuration for career-path planning."""

from __future__ import annotations

from types import MappingProxyType


CALCULATION_VERSION = "deterministic-path-v1"
PATH_ALGORITHM_VERSION = "graph-search-v1"
MAX_PATH_NODES = 6
MAX_CONSECUTIVE_LATERAL = 2
MAX_CANDIDATE_PATHS = 3
ENTRY_EXPERIENCE_THRESHOLD = 1.0
MIN_PATH_DATA_CONFIDENCE = 0.5

LEVEL_ORDER = MappingProxyType(
    {"entry": 0, "junior": 1, "mid": 2, "senior": 3, "lead": 4}
)
DEFAULT_DURATION_MONTHS = MappingProxyType(
    {"entry": 12, "junior": 18, "mid": 24, "senior": 30, "lead": 36}
)
RISK_VALUES = MappingProxyType({"low": 0.0, "medium": 1.0, "high": 2.0})
SCORE_WEIGHTS = MappingProxyType(
    {
        "industry_preference": 5.0,
        "job_preference": 5.0,
        "preferred_path_type": 2.0,
        "industry_continuity": 5.0,
        "region_fit": 5.0,
        "risk": 2.0,
        "transfer_months": 6.0,
    }
)
DATA_CONFIDENCE_PENALTIES = MappingProxyType(
    {
        "skill_fallback": 0.2,
        "risk_fallback": 0.2,
        "fallback_target": 0.3,
        "unknown_node_skills": 0.1,
    }
)


__all__ = [
    "CALCULATION_VERSION",
    "DATA_CONFIDENCE_PENALTIES",
    "DEFAULT_DURATION_MONTHS",
    "ENTRY_EXPERIENCE_THRESHOLD",
    "LEVEL_ORDER",
    "MAX_CANDIDATE_PATHS",
    "MAX_CONSECUTIVE_LATERAL",
    "MAX_PATH_NODES",
    "MIN_PATH_DATA_CONFIDENCE",
    "PATH_ALGORITHM_VERSION",
    "RISK_VALUES",
    "SCORE_WEIGHTS",
]
