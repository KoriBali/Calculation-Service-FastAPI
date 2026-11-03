"""Significant-figure rounding policy for New JIL calculations.

Ported from python_calc ``calculation/rounding/significant_figure_rounding.py`` (commit 270d23b).
"""

from decimal import Decimal

from app.engine.calculation.significant_figure import SignificantFigureRounder

from .base import RoundingPolicy


class SignificantFigureRoundingPolicy(RoundingPolicy):
    """Delegate rounding to the VBA-compatible significant-figure object."""

    def apply(
        self,
        value: int | float | Decimal,
        precision: int,
    ) -> float:
        """Return ``value`` rounded to ``precision`` significant figures."""
        return SignificantFigureRounder(precision).apply(value)
