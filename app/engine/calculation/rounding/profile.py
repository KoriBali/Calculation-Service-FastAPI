"""Precision rules for calculated values, selected by design standard.

Ported from python_calc ``calculation/rounding/profile.py`` (commit 270d23b).
"""

from dataclasses import dataclass
from enum import Enum

from app.engine.domain.standards.codes import DesignStandardCode

from .base import RoundingPolicy
from .decimal_rounding import DecimalRoundingPolicy
from .significant_figure_rounding import SignificantFigureRoundingPolicy
from .standard_policy import rounding_policy_for


class CalculationValueType(str, Enum):
    """Calculated-result categories that have confirmed precision rules."""

    CALCULATED_POLE_DIAMETER = "calculated_pole_diameter"
    LOAD_CENTER_HEIGHT = "load_center_height"
    PROJECTED_AREA = "projected_area"
    CROSS_SECTION_AREA = "cross_section_area"
    MOMENT_OF_INERTIA = "moment_of_inertia"
    RADIUS_OF_GYRATION = "radius_of_gyration"
    SECTION_MODULUS = "section_modulus"
    WEIGHT_PER_METER = "weight_per_meter"
    WIRE_LOAD_COMBINATION = "wire_load_combination"
    WIND_PRESSURE = "wind_pressure"
    LOAD = "load"
    MOMENT = "moment"
    STRESS = "stress"
    SAFETY_FACTOR = "safety_factor"


@dataclass(frozen=True)
class RoundingRule:
    """Decimal and significant-figure precision for one calculated result."""

    decimal_places: int | None
    significant_figures: int | None


ROUNDING_RULES: dict[CalculationValueType, RoundingRule] = {
    CalculationValueType.CALCULATED_POLE_DIAMETER: RoundingRule(1, 4),
    CalculationValueType.LOAD_CENTER_HEIGHT: RoundingRule(3, 3),
    CalculationValueType.PROJECTED_AREA: RoundingRule(3, 3),
    CalculationValueType.CROSS_SECTION_AREA: RoundingRule(2, 3),
    CalculationValueType.MOMENT_OF_INERTIA: RoundingRule(2, 3),
    CalculationValueType.RADIUS_OF_GYRATION: RoundingRule(2, 3),
    CalculationValueType.SECTION_MODULUS: RoundingRule(2, 3),
    CalculationValueType.WEIGHT_PER_METER: RoundingRule(2, 3),
    CalculationValueType.WIRE_LOAD_COMBINATION: RoundingRule(2, 4),
    CalculationValueType.WIND_PRESSURE: RoundingRule(0, 4),
    CalculationValueType.LOAD: RoundingRule(1, 3),
    CalculationValueType.MOMENT: RoundingRule(1, 3),
    CalculationValueType.STRESS: RoundingRule(1, 3),
    CalculationValueType.SAFETY_FACTOR: RoundingRule(3, 3),
}


@dataclass(frozen=True)
class CalculationRoundingProfile:
    """Apply the confirmed precision for calculated results only."""

    design_standard: DesignStandardCode
    policy: RoundingPolicy

    def apply(
        self,
        value: int | float,
        value_type: CalculationValueType,
    ) -> float:
        """Round a calculation result; return it unchanged when rule says so."""
        if not isinstance(value_type, CalculationValueType):
            raise TypeError("value_type must be a CalculationValueType")

        rule = ROUNDING_RULES[value_type]
        if isinstance(self.policy, DecimalRoundingPolicy):
            if (
                value_type is CalculationValueType.WIND_PRESSURE
                and self.design_standard
                in {
                    DesignStandardCode.ACT_DISASTER_PREVENTION,
                    DesignStandardCode.ACT_TOWER,
                }
            ):
                precision = 1
            else:
                precision = rule.decimal_places
        elif isinstance(self.policy, SignificantFigureRoundingPolicy):
            precision = rule.significant_figures
        else:
            raise TypeError("Unsupported rounding policy")

        if precision is None:
            return float(value)
        return self.policy.apply(value, precision)


def rounding_profile_for(
    design_standard: int | DesignStandardCode,
) -> CalculationRoundingProfile:
    """Return the calculated-result rounding profile for one standard."""
    standard = DesignStandardCode(design_standard)
    return CalculationRoundingProfile(
        design_standard=standard,
        policy=rounding_policy_for(standard),
    )
