"""Domain model for equipment mounted directly on a pole.

Ported from python_calc ``domain/direct_object.py`` (commit 270d23b).
"""

from enum import Enum
from math import cos, pi, sin

from .loads import LoadObject


class DirectObjectType(str, Enum):
    """Wind-exposure behaviour supported by the VBA calculation."""

    DIRECTIONAL = "Directional"
    OMNI = "Omni"


class DirectObject(LoadObject):
    """Represent equipment mounted directly on a pole."""

    def __init__(
        self,
        name: str,
        object_type: DirectObjectType | str,
        front_area_m2: float,
        side_area_m2: float,
        mass_per_unit_kg: float,
        elevation_m: float,
        base_wind_coefficient: float,
        quantity: int,
        fixed_angle_deg: float,
    ) -> None:
        super().__init__(name=name)
        try:
            self.object_type = DirectObjectType(object_type)
        except ValueError:
            raise ValueError(
                "object_type must be 'Directional' or 'Omni'"
            ) from None

        self.front_area_m2 = float(front_area_m2)
        self.side_area_m2 = float(side_area_m2)
        self.mass_per_unit_kg = float(mass_per_unit_kg)
        self.elevation_m = float(elevation_m)
        self.base_wind_coefficient = float(base_wind_coefficient)
        self.quantity = int(quantity)
        self.fixed_angle_deg = float(fixed_angle_deg)
        self._validate()

    def _validate(self) -> None:
        if self.front_area_m2 <= 0:
            raise ValueError("front_area_m2 must be greater than zero")
        if self.side_area_m2 < 0:
            raise ValueError("side_area_m2 cannot be negative")
        if self.mass_per_unit_kg < 0:
            raise ValueError("mass_per_unit_kg cannot be negative")
        if self.elevation_m < 0:
            raise ValueError("elevation_m cannot be negative")
        if self.base_wind_coefficient <= 0:
            raise ValueError("base_wind_coefficient must be greater than zero")
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")

    @property
    def is_omni(self) -> bool:
        return self.object_type is DirectObjectType.OMNI

    def total_mass_kg(self) -> float:
        """Return total mass for all units of this Direct Object."""
        return self.mass_per_unit_kg * self.quantity

    def fix_load_n(self, gravity_m_s2: float = LoadObject.GRAVITY) -> float:
        """Return FixLoad without a Pole OverdesignFactor."""
        if gravity_m_s2 <= 0:
            raise ValueError("gravity_m_s2 must be greater than zero")
        return self.total_mass_kg() * gravity_m_s2

    def load_center_height_m(self, evaluated_position_m: float) -> float:
        """Return the load-center height above an EvaluatedPosition."""
        height = self.elevation_m - float(evaluated_position_m)
        if height < 0:
            raise ValueError("Direct Object is below the EvaluatedPosition")
        return height

    def angle_of_attack_rad(self, wind_angle_rad: float) -> float:
        """Return fixed object angle minus wind direction angle."""
        return self.fixed_angle_deg / 180 * pi - wind_angle_rad

    def direction_factors(self, wind_angle_rad: float) -> tuple[float, float]:
        """Return VBA-compatible rounded sine and cosine factors."""
        angle = self.angle_of_attack_rad(wind_angle_rad)
        return round(sin(angle), 3), round(cos(angle), 3)

    def projected_area(self, wind_angle_rad: float) -> float:
        """Return total effective wind area for one wind direction."""
        if self.is_omni:
            area_per_unit = self.front_area_m2
        else:
            sine, cosine = self.direction_factors(wind_angle_rad)
            area_per_unit = (
                self.front_area_m2 * abs(sine)
                + self.side_area_m2 * abs(cosine)
            )
        return area_per_unit * self.quantity

    def wind_coefficient(
        self,
        design_standard: int,
        kz: float = 1.0,
    ) -> float:
        """Return CF following ``DO_each.Calc_Cf``."""
        if design_standard not in {1, 2, 3, 4, 5, 6, 7, 9}:
            raise ValueError("Design standard must be one of 1-7 or 9")
        coefficient = (
            self.base_wind_coefficient * kz
            if design_standard == 1
            else self.base_wind_coefficient
        )
        return round(coefficient, 3)

