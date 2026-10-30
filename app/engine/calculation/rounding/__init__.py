"""Rounding policies selected by a design standard.

Ported from python_calc ``calculation/rounding/__init__.py`` (commit 270d23b).
"""

from .base import RoundingPolicy
from .decimal_rounding import DecimalRoundingPolicy
from .profile import (
    CalculationRoundingProfile,
    CalculationValueType,
    ROUNDING_RULES,
    RoundingRule,
    rounding_profile_for,
)
from .significant_figure_rounding import SignificantFigureRoundingPolicy
from .standard_policy import rounding_policy_for

__all__ = [
    "CalculationRoundingProfile",
    "CalculationValueType",
    "DecimalRoundingPolicy",
    "ROUNDING_RULES",
    "RoundingPolicy",
    "RoundingRule",
    "SignificantFigureRoundingPolicy",
    "rounding_profile_for",
    "rounding_policy_for",
]
