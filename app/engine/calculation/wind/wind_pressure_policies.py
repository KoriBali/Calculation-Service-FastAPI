"""Wind-pressure policies selected by design standard.

This module contains the confirmed pressure rules only. It does not calculate
object area, coefficient, load, moment, or stress.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.engine.domain.standards.codes import DesignStandardCode


def act_common_parameters(
    area_density_code: int,
    structure_height_m: float,
) -> dict[str, float | str]:
    """Return confirmed Act parameters for an Area Density Code."""
    area_density_parameters = {
        1: (5.0, 250.0, 0.1, "I"),
        2: (5.0, 350.0, 0.15, "II"),
        3: (5.0, 450.0, 0.2, "III"),
        4: (10.0, 550.0, 0.27, "IV"),
    }
    try:
        zb, zg, alpha, symbol = area_density_parameters[
            int(area_density_code)
        ]
        area_density_code = int(area_density_code)
    except (KeyError, TypeError, ValueError):
        raise ValueError("Area Density Code must be between 1 and 4") from None

    structure_height_m = float(structure_height_m)
    if structure_height_m <= 0:
        raise ValueError("Structure height must be greater than zero")

    if area_density_code == 1:
        gf = 2.0 if structure_height_m <= 10 else (
            (-0.2 / 30) * (structure_height_m - 10) + 2.0
            if structure_height_m < 40 else 1.8
        )
    elif area_density_code == 2:
        gf = 2.2 if structure_height_m <= 10 else (
            (-0.2 / 30) * (structure_height_m - 10) + 2.2
            if structure_height_m < 40 else 2.0
        )
    elif area_density_code == 3:
        gf = 2.5 if structure_height_m <= 10 else (
            (-0.4 / 30) * (structure_height_m - 10) + 2.5
            if structure_height_m < 40 else 2.1
        )
    else:
        gf = 3.1 if structure_height_m <= 10 else (
            (-0.8 / 30) * (structure_height_m - 10) + 3.1
            if structure_height_m < 40 else 2.3
        )

    gf = round(gf, 3)
    er_reference_height = (
        zb if structure_height_m <= zb else structure_height_m
    )
    er = round(1.7 * (er_reference_height / zg) ** alpha, 3)
    air_density_factor = round(er**2 * gf, 3)

    return {
        "Hstr": structure_height_m,
        "zb": zb,
        "zg": zg,
        "alpha": alpha,
        "Gf": gf,
        "Er": er,
        "Ds_air": air_density_factor,
        "area_density_code": area_density_code,
        "area_density_code_symbol": symbol,
    }


def calculate_kz(
    top_elevation_m: float,
    structure_height_m: float,
    zb: float,
    alpha: float,
) -> float:
    """Return confirmed Kz using metre-based heights."""
    try:
        top_elevation_m = float(top_elevation_m)
        structure_height_m = float(structure_height_m)
        zb = float(zb)
        alpha = float(alpha)
    except (TypeError, ValueError):
        raise ValueError("Kz parameters must be numbers") from None

    if top_elevation_m < 0:
        raise ValueError("Object height (top_elevation_m) cannot be negative")
    if structure_height_m <= 0:
        raise ValueError("Structure height must be greater than zero")
    if zb <= 0:
        raise ValueError("zb must be greater than zero")
    if alpha < 0:
        raise ValueError("alpha cannot be negative")

    if structure_height_m <= zb:
        kz = 1.0
    elif top_elevation_m <= zb:
        kz = (zb / structure_height_m) ** (2 * alpha)
    else:
        kz = (top_elevation_m / structure_height_m) ** (2 * alpha)
    return round(kz, 3)


class WindPressurePolicy(ABC):
    """Interface for standard-specific wind-pressure rules."""

    @property
    def common_parameters(self) -> dict[str, float | str] | None:
        return None

    def kz_at(self, top_elevation_m: float) -> float:
        """Return 1.0 when a standard does not use Kz."""
        return 1.0

    @abstractmethod
    def wind_pressure_at(self, top_elevation_m: float) -> float:
        """Return wind pressure at the supplied top elevation in N/m2."""


@dataclass(frozen=True)
class ActWindPressurePolicy(WindPressurePolicy):
    """Act Disaster Prevention wind pressure for d_st = 1."""

    structure_height_m: float
    area_density_code: int
    basic_wind_speed_m_s: float
    _common: dict[str, float | str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if float(self.basic_wind_speed_m_s) <= 0:
            raise ValueError("Basic wind speed must be greater than zero")
        object.__setattr__(
            self,
            "_common",
            act_common_parameters(
                self.area_density_code,
                self.structure_height_m,
            ),
        )

    @property
    def common_parameters(self) -> dict[str, float | str]:
        return dict(self._common)

    def kz_at(self, top_elevation_m: float) -> float:
        return calculate_kz(
            top_elevation_m,
            self.structure_height_m,
            self._common["zb"],
            self._common["alpha"],
        )

    def wind_pressure_at(self, top_elevation_m: float) -> float:
        return round(
            0.6 * self._common["Ds_air"] * self.basic_wind_speed_m_s**2,
            3,
        )


@dataclass(frozen=True)
class FixedWindPressurePolicy(WindPressurePolicy):
    """Fixed density and wind-speed pressure for d_st 2, 3, 4, 5, 7, 9."""

    wind_speed_m_s: float
    air_density_kg_m3: float = 1.23
    calculation_decimal_places: int = 3

    def __post_init__(self) -> None:
        if float(self.wind_speed_m_s) <= 0:
            raise ValueError("Wind speed must be greater than zero")
        if float(self.air_density_kg_m3) <= 0:
            raise ValueError("Air density must be greater than zero")
        if self.calculation_decimal_places < 0:
            raise ValueError("Calculation decimal places cannot be negative")

    def wind_pressure_at(self, top_elevation_m: float) -> float:
        pressure = (
            0.5 * self.air_density_kg_m3 * self.wind_speed_m_s**2
        )
        # Preserve standard-specific VBA/current-Python intermediate precision.
        return round(pressure, self.calculation_decimal_places)


@dataclass(frozen=True)
class ActTowerWindPressurePolicy(ActWindPressurePolicy):
    """Act Tower pressure with Kz, factor 1.42, and minimum 2350 N/m2."""

    minimum_pressure_n_m2: float = 2350.0
    tower_factor: float = 1.42

    def wind_pressure_at(self, top_elevation_m: float) -> float:
        kz = self.kz_at(top_elevation_m)
        base_pressure = round(
            0.6 * self._common["Ds_air"] * self.basic_wind_speed_m_s**2,
            3,
        )
        pressure_with_kz = base_pressure * self.tower_factor * kz
        if pressure_with_kz > self.minimum_pressure_n_m2:
            return round(pressure_with_kz, 3)
        return float(self.minimum_pressure_n_m2)


@dataclass(frozen=True)
class HaidenKiteiWindPressurePolicy(WindPressurePolicy):
    """Explicit unavailable placeholder for d_st = 8."""

    def wind_pressure_at(self, top_elevation_m: float) -> float:
        raise NotImplementedError(
            "Wind pressure has not been prepared for the Haiden Kitei "
            "design standard (d_st = 8)"
        )


def wind_pressure_policy_for(
    design_standard: int | DesignStandardCode,
    *,
    structure_height_m: float,
    area_density_code: int | None = None,
    basic_wind_speed_m_s: float | None = None,
) -> WindPressurePolicy:
    """Create the confirmed pressure policy for a design standard."""
    standard = DesignStandardCode(design_standard)
    structure_height_m = float(structure_height_m)
    if structure_height_m <= 0:
        raise ValueError("Structure height must be greater than zero")

    if standard is DesignStandardCode.HAIDEN_KITEI:
        return HaidenKiteiWindPressurePolicy()

    if standard in {
        DesignStandardCode.ACT_DISASTER_PREVENTION,
        DesignStandardCode.ACT_TOWER,
    }:
        if area_density_code is None:
            raise ValueError(
                "Area Density Code 1-4 is required for standard 1 or 6"
            )
        if basic_wind_speed_m_s is None:
            raise ValueError(
                "Basic wind speed is required for standard 1 or 6"
            )
        policy_type = (
            ActWindPressurePolicy
            if standard is DesignStandardCode.ACT_DISASTER_PREVENTION
            else ActTowerWindPressurePolicy
        )
        return policy_type(
            structure_height_m=structure_height_m,
            area_density_code=area_density_code,
            basic_wind_speed_m_s=basic_wind_speed_m_s,
        )

    default_wind_speed_by_standard = {
        DesignStandardCode.FIXED_WIND_DISASTER: 60.0,
        DesignStandardCode.OLD_LIGHTING_POLE: 60.0,
        DesignStandardCode.SMALL_SIGN_BOARD: 40.0,
        DesignStandardCode.LARGE_SIGN_BOARD: 50.0,
        DesignStandardCode.NEW_JIL: 60.0,
        DesignStandardCode.OLD_TRAFFIC_SIGNAL: 60.0,
    }
    input_enabled_standards = {
        DesignStandardCode.OLD_LIGHTING_POLE,
        DesignStandardCode.SMALL_SIGN_BOARD,
        DesignStandardCode.LARGE_SIGN_BOARD,
        DesignStandardCode.NEW_JIL,
        DesignStandardCode.OLD_TRAFFIC_SIGNAL,
    }
    wind_speed = default_wind_speed_by_standard[standard]
    if standard in input_enabled_standards and basic_wind_speed_m_s is not None:
        wind_speed = basic_wind_speed_m_s

    decimal_places_by_standard = {
        DesignStandardCode.FIXED_WIND_DISASTER: 4,
        DesignStandardCode.OLD_LIGHTING_POLE: 4,
        DesignStandardCode.SMALL_SIGN_BOARD: 3,
        DesignStandardCode.LARGE_SIGN_BOARD: 3,
        DesignStandardCode.NEW_JIL: 4,
        DesignStandardCode.OLD_TRAFFIC_SIGNAL: 4,
    }
    return FixedWindPressurePolicy(
        wind_speed_m_s=wind_speed,
        calculation_decimal_places=decimal_places_by_standard[standard],
    )
