"""Excel-compatible decimal-place rounding for non-New-JIL standards.

Ported from python_calc ``calculation/rounding/decimal_rounding.py`` (commit 270d23b).
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .base import RoundingPolicy


class DecimalRoundingPolicy(RoundingPolicy):
    """Round decimal places like Excel ``ROUND`` (half away from zero)."""

    def apply(
        self,
        value: int | float | Decimal,
        precision: int,
    ) -> float:
        """Return ``value`` rounded to ``precision`` decimal places."""
        if isinstance(precision, bool) or not isinstance(precision, int):
            raise ValueError("Decimal precision must be a non-negative integer")
        if precision < 0:
            raise ValueError("Decimal precision must be a non-negative integer")
        if isinstance(value, bool):
            raise TypeError("Value must be a real number, not bool")

        try:
            # Excel calculates numeric values with at most 15 significant
            # decimal digits. Normalizing Python floats to that precision
            # removes binary representation noise such as
            # 0.175 * 0.1 -> 0.017499999999999998 before applying ROUND.
            if isinstance(value, Decimal):
                decimal_value = value
            elif isinstance(value, int):
                decimal_value = Decimal(value)
            else:
                decimal_value = Decimal(format(float(value), ".15g"))
            quantum = Decimal(1).scaleb(-precision)
            rounded_value = decimal_value.quantize(
                quantum,
                rounding=ROUND_HALF_UP,
            )
        except (InvalidOperation, TypeError, ValueError):
            raise TypeError("Value must be a real number") from None
        return float(rounded_value)
