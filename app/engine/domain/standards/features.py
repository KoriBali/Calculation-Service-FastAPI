"""Calculation capabilities declared by each design standard.

This module describes which calculation paths are applicable.  It does not
contain or execute engineering formulas.
"""

from dataclasses import dataclass
from enum import Enum

from .codes import DesignStandardCode


class WindCaseMode(str, Enum):
    """Wind-case families confirmed for the design standards."""

    OMNI = "omni"
    STRAIGHT = "straight"
    STRAIGHT_AND_OBLIQUE = "straight_and_oblique"
    EIGHT_DIRECTIONS = "eight_directions"


@dataclass(frozen=True)
class CalculationFeatures:
    """Immutable capability declaration for one design standard."""

    wind_case_mode: WindCaseMode
    calculates_bending_stress: bool
    calculates_compression_stress: bool
    calculates_torque: bool
    calculates_seismic_by_default: bool
    supports_optional_seismic: bool
    supports_oblique_wind: bool
    includes_arm_safety_check: bool


_FEATURES_BY_STANDARD: dict[DesignStandardCode, CalculationFeatures] = {
    DesignStandardCode.ACT_DISASTER_PREVENTION: CalculationFeatures(
        wind_case_mode=WindCaseMode.OMNI,
        calculates_bending_stress=True,
        calculates_compression_stress=True,
        calculates_torque=False,
        calculates_seismic_by_default=True,
        supports_optional_seismic=False,
        supports_oblique_wind=False,
        includes_arm_safety_check=False,
    ),
    DesignStandardCode.FIXED_WIND_DISASTER: CalculationFeatures(
        wind_case_mode=WindCaseMode.OMNI,
        calculates_bending_stress=True,
        calculates_compression_stress=True,
        calculates_torque=False,
        calculates_seismic_by_default=True,
        supports_optional_seismic=False,
        supports_oblique_wind=False,
        includes_arm_safety_check=False,
    ),
    DesignStandardCode.OLD_LIGHTING_POLE: CalculationFeatures(
        wind_case_mode=WindCaseMode.STRAIGHT,
        calculates_bending_stress=True,
        calculates_compression_stress=False,
        calculates_torque=False,
        calculates_seismic_by_default=False,
        supports_optional_seismic=True,
        supports_oblique_wind=True,
        includes_arm_safety_check=True,
    ),
    DesignStandardCode.SMALL_SIGN_BOARD: CalculationFeatures(
        wind_case_mode=WindCaseMode.STRAIGHT,
        calculates_bending_stress=True,
        calculates_compression_stress=False,
        calculates_torque=False,
        calculates_seismic_by_default=False,
        supports_optional_seismic=True,
        supports_oblique_wind=True,
        includes_arm_safety_check=False,
    ),
    DesignStandardCode.LARGE_SIGN_BOARD: CalculationFeatures(
        wind_case_mode=WindCaseMode.STRAIGHT_AND_OBLIQUE,
        calculates_bending_stress=True,
        calculates_compression_stress=True,
        calculates_torque=True,
        calculates_seismic_by_default=False,
        supports_optional_seismic=True,
        supports_oblique_wind=True,
        includes_arm_safety_check=True,
    ),
    DesignStandardCode.ACT_TOWER: CalculationFeatures(
        wind_case_mode=WindCaseMode.OMNI,
        calculates_bending_stress=True,
        calculates_compression_stress=True,
        calculates_torque=False,
        calculates_seismic_by_default=True,
        supports_optional_seismic=False,
        supports_oblique_wind=False,
        includes_arm_safety_check=False,
    ),
    DesignStandardCode.NEW_JIL: CalculationFeatures(
        wind_case_mode=WindCaseMode.EIGHT_DIRECTIONS,
        calculates_bending_stress=True,
        calculates_compression_stress=True,
        calculates_torque=True,
        calculates_seismic_by_default=True,
        supports_optional_seismic=False,
        supports_oblique_wind=False,
        includes_arm_safety_check=True,
    ),
    DesignStandardCode.OLD_TRAFFIC_SIGNAL: CalculationFeatures(
        wind_case_mode=WindCaseMode.EIGHT_DIRECTIONS,
        calculates_bending_stress=True,
        calculates_compression_stress=False,
        calculates_torque=True,
        calculates_seismic_by_default=False,
        supports_optional_seismic=True,
        supports_oblique_wind=False,
        includes_arm_safety_check=True,
    ),
}


def calculation_features_for(
    design_standard: int | DesignStandardCode,
) -> CalculationFeatures:
    """Return the declared features without running any calculation."""
    standard = DesignStandardCode(design_standard)
    standard.ensure_calculation_is_available()
    return _FEATURES_BY_STANDARD[standard]
