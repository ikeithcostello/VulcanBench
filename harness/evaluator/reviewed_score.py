"""Explicit opt-in reporting revision; never rewrites legacy run scores."""

import math
from typing import Any

PROFILE = "swe-v4-reviewed-2026-09-05"
WEIGHTS = {"functional": 0.50, "quality": 0.15, "security": 0.15, "human_like": 0.20}

# Locked 2026-09-07 with the code-quality-maintenance-v3 protocol. Weight moved
# from the automated lint/complexity metric (which rewards compressed code via
# the maintainability index's line-count term) to the reviewed Code quality
# score. This is a policy choice, not a fitted weight; PROFILE stays available
# as the sensitivity comparison.
PROFILE_V3 = "swe-v4-reviewed-2026-09-07"
WEIGHTS_V3 = {"functional": 0.50, "quality": 0.085, "security": 0.085, "human_like": 0.33}


def reviewed_score(metrics: dict[str, Any], weights: dict[str, float] = WEIGHTS) -> float:
    """Require all four factors. Missing metrics do not change the weights."""
    for key in weights:
        value = metrics.get(key)
        if not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"Missing or invalid {key}")
    return float(sum(metrics[key] * weight for key, weight in weights.items()))
