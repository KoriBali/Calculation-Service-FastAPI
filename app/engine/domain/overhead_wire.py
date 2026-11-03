"""Domain model for one overhead wire (OHW).

Ported from python_calc ``domain/overhead_wire.py`` (commit 270d23b).
"""

from math import cos, pi, radians, sin, sqrt

from .loads import LoadObject


class OverheadWire(LoadObject):
    """Represent one wire and its confirmed engineering behaviour."""

    def __init__(
        self,
        name: str,
        mass_per_length_kg_m: float,
        diameter_mm: float,
        elevation_m: float,
        span_length_m: float,
        sag_ratio_percent: float,
        base_wind_coefficient: float,
        fixed_angle_deg: float,
        vertical_angle_deg: float,
    ) -> None:
        super().__init__(name=name)
        self.mass_per_length_kg_m = float(mass_per_length_kg_m)
        self.diameter_mm = float(diameter_mm)
        self.elevation_m = float(elevation_m)
        self.span_length_m = float(span_length_m)
        self.sag_ratio_percent = float(sag_ratio_percent)
        self.base_wind_coefficient = float(base_wind_coefficient)
        self.fixed_angle_deg = float(fixed_angle_deg)
        self.vertical_angle_deg = float(vertical_angle_deg)
        self._validate()

    def _validate(self) -> None:
        positive_values = {
            "mass_per_length_kg_m": self.mass_per_length_kg_m,
            "diameter_mm": self.diameter_mm,
            "span_length_m": self.span_length_m,
            "sag_ratio_percent": self.sag_ratio_percent,
            "base_wind_coefficient": self.base_wind_coefficient,
        }
        for name, value in positive_values.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.elevation_m < 0:
            raise ValueError("elevation_m cannot be negative")
        if self.vertical_angle_cosine <= 0:
            raise ValueError(
                "vertical_angle_deg must produce a positive cosine"
            )

    @property
    def fixed_angle_rad(self) -> float:
        return radians(self.fixed_angle_deg)

    @property
    def vertical_angle_rad(self) -> float:
        return radians(self.vertical_angle_deg)

    @property
    def vertical_angle_cosine(self) -> float:
        return cos(self.vertical_angle_rad)

    @property
    def sag_ratio(self) -> float:
        return self.sag_ratio_percent / 100

    def tributary_horizontal_length_m(self) -> float:
        """Return the half-span contributing to the support."""
        return self.span_length_m / 2

    def tributary_wire_length_m(self) -> float:
        return (
            self.tributary_horizontal_length_m()
            / self.vertical_angle_cosine
        )

    def total_mass_kg(self) -> float:
        return self.mass_per_length_kg_m * self.tributary_wire_length_m()

    def fix_load_per_length_n_m(
        self,
        gravity_m_s2: float = LoadObject.GRAVITY,
    ) -> float:
        if gravity_m_s2 <= 0:
            raise ValueError("gravity_m_s2 must be greater than zero")
        return self.mass_per_length_kg_m * gravity_m_s2

    def fix_load_n(
        self,
        gravity_m_s2: float = LoadObject.GRAVITY,
    ) -> float:
        """Return OHW FixLoad without a Pole OverdesignFactor."""
        if gravity_m_s2 <= 0:
            raise ValueError("gravity_m_s2 must be greater than zero")
        return self.total_mass_kg() * gravity_m_s2

    def load_center_height_m(self, evaluated_position_m: float) -> float:
        height = self.elevation_m - float(evaluated_position_m)
        if height < 0:
            raise ValueError("OHW is below the EvaluatedPosition")
        return height

    def angle_of_attack_rad(self, wind_angle_rad: float) -> float:
        return self.fixed_angle_rad - wind_angle_rad

    def direction_factors(self, wind_angle_rad: float) -> tuple[float, float]:
        angle = self.angle_of_attack_rad(wind_angle_rad)
        return round(sin(angle), 3), round(cos(angle), 3)

    def projected_area(self, wind_angle_rad: float | None = None) -> float:
        """Return base or direction-adjusted projected area in m2."""
        area = self.diameter_mm / 1000 * self.tributary_wire_length_m()
        if wind_angle_rad is None:
            return area
        sine, _ = self.direction_factors(wind_angle_rad)
        return area * abs(sine)

    def wind_coefficient(
        self,
        design_standard: int,
        kz: float = 1.0,
    ) -> float:
        if design_standard not in {1, 2, 3, 4, 5, 6, 7, 9}:
            raise ValueError("Design standard must be one of 1-7 or 9")
        coefficient = (
            self.base_wind_coefficient * kz
            if design_standard == 1
            else self.base_wind_coefficient
        )
        return round(coefficient, 3)

    def directional_wind_line_load_n_m(
        self,
        wind_pressure_n_m2: float,
        coefficient: float,
        wind_angle_rad: float,
    ) -> float:
        sine, _ = self.direction_factors(wind_angle_rad)
        return (
            wind_pressure_n_m2
            * coefficient
            * (self.diameter_mm / 1000)
            / self.vertical_angle_cosine
            * sine
        )

    def combined_wind_line_load_n_m(
        self,
        wind_pressure_n_m2: float,
        coefficient: float,
        wind_angle_rad: float,
    ) -> float:
        wind_line_load = self.directional_wind_line_load_n_m(
            wind_pressure_n_m2,
            coefficient,
            wind_angle_rad,
        )
        return sqrt(self.fix_load_per_length_n_m() ** 2 + wind_line_load**2)

    def tension_from_line_load(self, line_load_n_m: float) -> float:
        if line_load_n_m < 0:
            raise ValueError("Line load cannot be negative")
        return (
            line_load_n_m
            * self.span_length_m**2
            / (8 * self.span_length_m * self.sag_ratio)
        )

    def wind_tension_n(
        self,
        wind_pressure_n_m2: float,
        coefficient: float,
        wind_angle_rad: float,
    ) -> float:
        return self.tension_from_line_load(
            self.combined_wind_line_load_n_m(
                wind_pressure_n_m2,
                coefficient,
                wind_angle_rad,
            )
        )

    def wind_tension_components_n(self, tension_n: float) -> tuple[float, float]:
        """Resolve wind tension using AoF in radians, following VBA."""
        return (
            tension_n * round(cos(self.fixed_angle_rad), 3),
            tension_n * round(sin(self.fixed_angle_rad + pi), 3),
        )

    def seismic_tension_n(self) -> float:
        """Return VBA seismic tension without applying seismic k_value."""
        seismic_line_load = (
            self.fix_load_per_length_n_m() / self.vertical_angle_cosine
        )
        return self.tension_from_line_load(seismic_line_load)

