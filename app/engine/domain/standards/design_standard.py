"""Immutable aggregate of policies for one design standard.

Ported from python_calc ``domain/standards/design_standard.py`` (commit 270d23b).
"""

from dataclasses import dataclass

from app.engine.calculation.rounding import RoundingPolicy
from app.engine.calculation.seismic import SeismicPolicy
from app.engine.calculation.stress import StressPolicy
from app.engine.calculation.wind import WindCasePolicy, WindPressurePolicy

from .codes import DesignStandardCode
from .features import CalculationFeatures


@dataclass(frozen=True)
class DesignStandard:
    """Complete policy configuration consumed by calculation services."""

    code: DesignStandardCode
    name: str
    features: CalculationFeatures
    wind_pressure_policy: WindPressurePolicy
    wind_case_policy: WindCasePolicy
    seismic_policy: SeismicPolicy
    stress_policy: StressPolicy
    rounding_policy: RoundingPolicy
