"""Factory for complete, explicit design-standard configurations.

Ported from python_calc ``domain/standards/factory.py`` (commit 270d23b).
"""

from app.engine.calculation.rounding import rounding_policy_for
from app.engine.calculation.seismic import seismic_policy_for
from app.engine.calculation.stress import (
    CompressionBendingStressPolicy,
    LargeSignPoleStressPolicy,
    NewJILPoleStressPolicy,
    OldTrafficSignalPoleStressPolicy,
    SimpleBendingStressPolicy,
    StressPolicy,
)
from app.engine.calculation.wind import (
    wind_case_policy_for,
    wind_pressure_policy_for,
)

from .codes import DesignStandardCode
from .design_standard import DesignStandard
from .features import calculation_features_for


_STANDARD_NAMES = {
    DesignStandardCode.ACT_DISASTER_PREVENTION: "Act Disaster Prevention",
    DesignStandardCode.FIXED_WIND_DISASTER: "Fixed Wind Disaster Prevention",
    DesignStandardCode.OLD_LIGHTING_POLE: "Old Lighting Pole",
    DesignStandardCode.SMALL_SIGN_BOARD: "Small Sign Board",
    DesignStandardCode.LARGE_SIGN_BOARD: "Large Sign Board",
    DesignStandardCode.ACT_TOWER: "Act Tower",
    DesignStandardCode.NEW_JIL: "New JIL",
    DesignStandardCode.HAIDEN_KITEI: "Haiden Kitei",
    DesignStandardCode.OLD_TRAFFIC_SIGNAL: "Old Traffic Signal",
}


def _stress_policy_for(standard: DesignStandardCode) -> StressPolicy:
    if standard in {
        DesignStandardCode.ACT_DISASTER_PREVENTION,
        DesignStandardCode.FIXED_WIND_DISASTER,
        DesignStandardCode.ACT_TOWER,
    }:
        return CompressionBendingStressPolicy()
    if standard in {
        DesignStandardCode.OLD_LIGHTING_POLE,
        DesignStandardCode.SMALL_SIGN_BOARD,
    }:
        return SimpleBendingStressPolicy()
    if standard is DesignStandardCode.LARGE_SIGN_BOARD:
        return LargeSignPoleStressPolicy()
    if standard is DesignStandardCode.NEW_JIL:
        return NewJILPoleStressPolicy()
    if standard is DesignStandardCode.OLD_TRAFFIC_SIGNAL:
        return OldTrafficSignalPoleStressPolicy()
    raise AssertionError(f"Unhandled stress policy for {standard!r}")


class DesignStandardFactory:
    """Build a standard without silently substituting another policy."""

    @staticmethod
    def create(
        design_standard: int | DesignStandardCode,
        *,
        structure_height_m: float | None = None,
        area_density_code: int | None = None,
        basic_wind_speed_m_s: float | None = None,
        k_value: float | None = None,
        eqa_m_s2: float = 4.71,
        eqr: float = 1.0,
        enable_optional_seismic: bool = False,
        include_oblique: bool = False,
        include_oblique_wind: bool | None = None,
    ) -> DesignStandard:
        standard = DesignStandardCode(design_standard)
        standard.ensure_calculation_is_available()
        if structure_height_m is None:
            raise ValueError("structure_height_m is required")
        if include_oblique_wind is not None:
            if include_oblique and not include_oblique_wind:
                raise ValueError(
                    "include_oblique and include_oblique_wind conflict"
                )
            include_oblique = bool(include_oblique_wind)

        return DesignStandard(
            code=standard,
            name=_STANDARD_NAMES[standard],
            features=calculation_features_for(standard),
            wind_pressure_policy=wind_pressure_policy_for(
                standard,
                structure_height_m=structure_height_m,
                area_density_code=area_density_code,
                basic_wind_speed_m_s=basic_wind_speed_m_s,
            ),
            wind_case_policy=wind_case_policy_for(
                standard,
                include_oblique=include_oblique,
            ),
            seismic_policy=seismic_policy_for(
                standard,
                k_value=k_value,
                eqa_m_s2=eqa_m_s2,
                eqr=eqr,
                enable_optional_seismic=enable_optional_seismic,
            ),
            stress_policy=_stress_policy_for(standard),
            rounding_policy=rounding_policy_for(standard),
        )
