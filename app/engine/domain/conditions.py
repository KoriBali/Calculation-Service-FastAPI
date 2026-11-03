"""Wind and seismic conditions used by the calculation engine.

Ported from python_calc ``domain/conditions.py`` (commit 270d23b).
"""

from dataclasses import dataclass
from math import pi

from app.engine.calculation.wind.wind_pressure_policies import (
    act_common_parameters,
    calculate_kz,
    wind_pressure_policy_for,
)
from app.engine.domain.standards import DesignStandardCode


def std_act_common(
    area_density_code: int,
    hstr: float,
) -> dict[str, float | str]:
    """Compatibility wrapper for the extracted Act pressure policy helper."""
    return act_common_parameters(area_density_code, hstr)


def calc_kz(
    z_height: float,
    hstr: float,
    zb: float,
    alpha: float,
) -> float:
    """Compatibility wrapper for the extracted Kz helper."""
    return calculate_kz(z_height, hstr, zb, alpha)


@dataclass(frozen=True)
class WindDirection:
    """Named wind direction and its angle in radians."""

    name: str
    angle_rad: float


WIND_DIRECTIONS: tuple[WindDirection, ...] = (
    WindDirection("N", pi * 2 / 4),
    WindDirection("S", pi * 6 / 4),
    WindDirection("E", pi * 0 / 4),
    WindDirection("W", pi * 4 / 4),
    WindDirection("NE", pi * 1 / 4),
    WindDirection("SW", pi * 5 / 4),
    WindDirection("NW", pi * 3 / 4),
    WindDirection("SE", pi * 7 / 4),
)


class WindCondition:
    """Wind inputs delegating pressure calculation to a standard policy."""

    def __init__(
        self,
        design_standard: int,
        structure_height_m: float,
        area_density_code: int | None = None,
        basic_wind_speed_m_s: float | None = None,
    ) -> None:
        self.design_standard = int(DesignStandardCode(design_standard))
        self.structure_height_m = float(structure_height_m)
        self.area_density_code = area_density_code
        self.basic_wind_speed_m_s = basic_wind_speed_m_s
        if self.structure_height_m <= 0:
            raise ValueError("Structure height must be greater than zero")
        self._pressure_policy = wind_pressure_policy_for(
            self.design_standard,
            structure_height_m=self.structure_height_m,
            area_density_code=self.area_density_code,
            basic_wind_speed_m_s=self.basic_wind_speed_m_s,
        )

    @property
    def directions(self) -> tuple[WindDirection, ...]:
        return WIND_DIRECTIONS

    @property
    def common_parameters(self) -> dict | None:
        common = self._pressure_policy.common_parameters
        return None if common is None else dict(common)

    def kz_at(self, top_elevation_m: float) -> float:
        """Return Kz at the top elevation of an individual pole segment."""
        return self._pressure_policy.kz_at(top_elevation_m)

    def wind_pressure_at(self, top_elevation_m: float) -> float:
        """Return pole wind pressure in N/m2 according to the VBA rules."""
        return self._pressure_policy.wind_pressure_at(top_elevation_m)


class SeismicCondition:
    """Seismic condition currently supplied as a dimensionless K value."""

    ROOFTOP_K_VALUES = {"A": 1.5, "B": 1.0, "S": 2.0}

    def __init__(
        self,
        position: str,
        k_value: float,
        seismic_class: str | None = None,
    ) -> None:
        normalized_position = position.strip().title()
        if normalized_position not in {"Ground", "Rooftop"}:
            raise ValueError("Position must be 'Ground' or 'Rooftop'")
        if k_value <= 0:
            raise ValueError("Seismic K value must be greater than zero")

        self.position = normalized_position
        self.k_value = float(k_value)
        self.seismic_class = seismic_class

    @classmethod
    def ground(cls, k_value: float) -> "SeismicCondition":
        return cls(position="Ground", k_value=k_value)

    @classmethod
    def rooftop(cls, seismic_class: str) -> "SeismicCondition":
        normalized_class = seismic_class.strip().upper()
        try:
            k_value = cls.ROOFTOP_K_VALUES[normalized_class]
        except KeyError:
            raise ValueError("Seismic class must be A, B, or S") from None
        return cls("Rooftop", k_value, normalized_class)

