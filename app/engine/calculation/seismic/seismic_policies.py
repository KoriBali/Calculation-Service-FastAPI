"""Confirmed seismic methods selected by design standard.

Ported from python_calc ``calculation/seismic/seismic_policies.py`` (commit 270d23b).
"""

from dataclasses import dataclass

from app.engine.domain.standards.codes import DesignStandardCode

from .base import SeismicPolicy


def _non_negative(value: float, name: str) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number") from None
    if value < 0:
        raise ValueError(f"{name} cannot be negative")
    return value


@dataclass(frozen=True)
class NoSeismicPolicy(SeismicPolicy):
    """Explicitly disable seismic load for a standard's default calculation."""

    @property
    def enabled(self) -> bool:
        return False

    def calculate_load_n(
        self,
        *,
        fix_load_n: float,
        mass_kg: float,
    ) -> float:
        return 0.0


@dataclass(frozen=True)
class FixLoadCoefficientSeismicPolicy(SeismicPolicy):
    """Use ``FixLoad [N] * k_value`` for d_st 1, 2, and 6."""

    k_value: float

    def __post_init__(self) -> None:
        try:
            value = float(self.k_value)
        except (TypeError, ValueError):
            raise ValueError("k_value must be a number") from None
        if value <= 0:
            raise ValueError("k_value must be greater than zero")
        object.__setattr__(self, "k_value", value)

    @property
    def enabled(self) -> bool:
        return True

    def calculate_load_n(
        self,
        *,
        fix_load_n: float,
        mass_kg: float,
    ) -> float:
        fix_load_n = _non_negative(fix_load_n, "fix_load_n")
        return fix_load_n * self.k_value


@dataclass(frozen=True)
class NewJILSeismicPolicy(SeismicPolicy):
    """Use original mass [kg] times EQa [m/s2] and EQr for d_st = 7."""

    eqa_m_s2: float = 4.71
    eqr: float = 1.0

    def __post_init__(self) -> None:
        try:
            eqa = float(self.eqa_m_s2)
            eqr = float(self.eqr)
        except (TypeError, ValueError):
            raise ValueError("EQa and EQr must be numbers") from None
        if eqa <= 0:
            raise ValueError("EQa must be greater than zero")
        if eqr <= 0:
            raise ValueError("EQr must be greater than zero")
        object.__setattr__(self, "eqa_m_s2", eqa)
        object.__setattr__(self, "eqr", eqr)

    @property
    def enabled(self) -> bool:
        return True

    def calculate_load_n(
        self,
        *,
        fix_load_n: float,
        mass_kg: float,
    ) -> float:
        mass_kg = _non_negative(mass_kg, "mass_kg")
        return mass_kg * self.eqa_m_s2 * self.eqr


def seismic_policy_for(
    design_standard: int | DesignStandardCode,
    *,
    k_value: float | None = None,
    eqa_m_s2: float = 4.71,
    eqr: float = 1.0,
    enable_optional_seismic: bool = False,
) -> SeismicPolicy:
    """Return the confirmed default seismic policy for one standard."""
    standard = DesignStandardCode(design_standard)
    standard.ensure_calculation_is_available()

    if standard in {
        DesignStandardCode.ACT_DISASTER_PREVENTION,
        DesignStandardCode.FIXED_WIND_DISASTER,
        DesignStandardCode.ACT_TOWER,
    }:
        if k_value is None:
            raise ValueError("k_value is required for standard 1, 2, or 6")
        return FixLoadCoefficientSeismicPolicy(k_value)

    if standard is DesignStandardCode.NEW_JIL:
        return NewJILSeismicPolicy(eqa_m_s2=eqa_m_s2, eqr=eqr)

    if enable_optional_seismic and standard in {
        DesignStandardCode.OLD_LIGHTING_POLE,
        DesignStandardCode.SMALL_SIGN_BOARD,
        DesignStandardCode.LARGE_SIGN_BOARD,
        DesignStandardCode.OLD_TRAFFIC_SIGNAL,
    }:
        if k_value is None:
            raise ValueError(
                "k_value is required when optional seismic is enabled"
            )
        return FixLoadCoefficientSeismicPolicy(k_value)

    return NoSeismicPolicy()
