"""Domain model for equipment mounted directly on a pole.

Ported from python_calc ``domain/direct_object.py``.
DEVIATION: rounding follows VBA (see app/engine/rounding.py); wind load and FixLoad are built in the VBA order so the rounding points exist.
"""

from enum import Enum
from math import cos, pi, sin

from app.engine import rounding
from app.engine.loads.base import LoadObject


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
        return rounding.SIG3(self.mass_per_unit_kg * self.quantity)

    def weight_per_unit_n(self) -> float:
        """Return the gravity force of one unit (DO_each ``fl_n``)."""
        return rounding.SIG3(self.force_from_mass(self.mass_per_unit_kg))

    def fix_load_n(self) -> float:
        """Return FixLoad without a Pole OverdesignFactor (``fld_n``)."""
        return rounding.SIG3(self.weight_per_unit_n() * self.quantity)


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
        return (
            rounding.DIRECTION_FACTOR(sin(angle)),
            rounding.DIRECTION_FACTOR(cos(angle)),
        )

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
    
    def wind_load_n(
        self,
        wind_angle_rad: float,
        cf: float,
        wind_pressure_n_m2: float,
    ) -> float:
        """Return total wind load in the order of ``DO_each.Calc_wld``."""
        front_load = rounding.SIG3(
            self.calculate_wind_load(self.front_area_m2, cf, wind_pressure_n_m2)
            * self.quantity
        )
        if self.is_omni:
            return front_load
        side_load = rounding.SIG3(
            self.calculate_wind_load(self.side_area_m2, cf, wind_pressure_n_m2)
            * self.quantity
        )
        sine, cosine = self.direction_factors(wind_angle_rad)
        return rounding.SIG3(front_load * abs(sine) + side_load * abs(cosine))

    def wind_coefficient(
        self,
        design_standard: int,
        kz: float = 1.0,
    ) -> float:
        """Return CF following ``DO_each.Calc_Cf``."""
        if design_standard not in {1, 2, 3, 4, 5, 6}:
            raise ValueError("Design standard must be between 1 and 6")
        coefficient = (
            self.base_wind_coefficient * kz
            if design_standard == 1
            else self.base_wind_coefficient
        )
        return rounding.CF(coefficient)
