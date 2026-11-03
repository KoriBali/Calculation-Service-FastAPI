"""Significant-figure rounding compatible with the VBA ``Fkb_SF`` rule.

Ported from python_calc ``calculation/significant_figure.py`` (commit 270d23b).
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN


@dataclass(frozen=True)
class SignificantFigureRounder:
    """Round numerical calculation results to a fixed significant-figure count.

    A value exactly halfway between two results uses round-half-to-even, matching
    the explicit even/odd handling in the VBA ``Fkb_SF`` function.
    """

    significant_figures: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.significant_figures, bool)
            or not isinstance(self.significant_figures, int)
            or self.significant_figures <= 0
        ):
            raise ValueError("Significant figures must be a positive integer")

    def apply(self, value: int | float | Decimal) -> float:
        """Return ``value`` rounded to the configured significant figures."""
        if isinstance(value, bool):
            raise TypeError("Value must be a real number, not bool")

        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise TypeError("Value must be a real number") from None

        if not decimal_value.is_finite():
            raise ValueError("Value must be finite")
        if decimal_value.is_zero():
            return 0.0

        rounding_exponent = (
            decimal_value.adjusted() - self.significant_figures + 1
        )
        quantum = Decimal(1).scaleb(rounding_exponent)
        rounded_value = decimal_value.quantize(
            quantum,
            rounding=ROUND_HALF_EVEN,
        )
        return float(rounded_value)

    def __call__(self, value: int | float | Decimal) -> float:
        """Allow a configured rounder to be called like a function."""
        return self.apply(value)
