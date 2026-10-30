"""Gravity selection confirmed for each design-standard calculation.

Ported from python_calc ``calculation/gravity.py`` (commit 270d23b).
"""

from app.engine.domain.standards import DesignStandardCode


STANDARD_GRAVITY_M_S2 = 9.80665
NEW_JIL_GRAVITY_M_S2 = 9.81


def gravity_for_standard(
    design_standard: int | DesignStandardCode,
) -> float:
    """Return the gravity used by the selected calculation method."""
    standard = DesignStandardCode(design_standard)
    if standard is DesignStandardCode.NEW_JIL:
        return NEW_JIL_GRAVITY_M_S2
    return STANDARD_GRAVITY_M_S2
