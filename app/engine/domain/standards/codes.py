"""Stable numeric identities for supported design standards.

Ported from python_calc ``domain/standards/codes.py`` (commit 270d23b).
"""

from enum import IntEnum


class DesignStandardCode(IntEnum):
    """Design-standard codes shared by Python, API, and database layers."""

    ACT_DISASTER_PREVENTION = 1
    FIXED_WIND_DISASTER = 2
    OLD_LIGHTING_POLE = 3
    SMALL_SIGN_BOARD = 4
    LARGE_SIGN_BOARD = 5
    ACT_TOWER = 6
    NEW_JIL = 7
    HAIDEN_KITEI = 8
    OLD_TRAFFIC_SIGNAL = 9

    @property
    def calculation_is_available(self) -> bool:
        """Return whether this standard currently has a calculation method."""
        return self is not DesignStandardCode.HAIDEN_KITEI

    def ensure_calculation_is_available(self) -> None:
        """Raise a clear alert before an unavailable calculation is started."""
        if not self.calculation_is_available:
            raise NotImplementedError(
                "Calculation has not been prepared for the Haiden Kitei "
                "design standard (d_st = 8)"
            )
