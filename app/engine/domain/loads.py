"""Common abstractions and factors for structural loads.

Ported from python_calc ``domain/loads.py`` (commit 270d23b).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class OverdesignFactor:
    """Multiplier applied to a calculated gravitational FixLoad.

    The default value keeps the unamplified load. Only positivity and a
    finite numeric value are enforced here; an engineering-specific minimum
    can be added later after its governing rule is confirmed.
    """

    value: float = 1.0

    def __post_init__(self) -> None:
        try:
            numeric_value = float(self.value)
        except (TypeError, ValueError):
            raise ValueError("Overdesign factor must be a number") from None

        if not isfinite(numeric_value) or numeric_value <= 0:
            raise ValueError(
                "Overdesign factor must be a finite number greater than zero"
            )
        object.__setattr__(self, "value", numeric_value)

    def apply(self, load_n: float) -> float:
        """Return ``load_n`` multiplied by this factor."""
        if load_n < 0:
            raise ValueError("Load cannot be negative")
        return load_n * self.value


class LoadObject(ABC):
    """Abstract base class for structural load-contributing objects.

    Subclasses own their geometry and load coefficients. The parent class
    provides only formulas that are common to every type of load object.
    """

    GRAVITY = 9.80665  # m/s²

    def __init__(self, name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Load object name cannot be empty")
        self.name = name.strip()

    @abstractmethod
    def projected_area(self, *args, **kwargs) -> float:
        """Return the projected area exposed to wind in m²."""

    @abstractmethod
    def wind_coefficient(self, *args, **kwargs) -> float:
        """Return the effective wind-force coefficient."""

    @classmethod
    def force_from_mass(cls, mass_kg: float) -> float:
        """Convert mass in kg to gravitational force in N."""
        if mass_kg < 0:
            raise ValueError("Mass cannot be negative")
        return mass_kg * cls.GRAVITY

    @staticmethod
    def calculate_wind_load(
        projected_area_m2: float,
        coefficient: float,
        wind_pressure_n_m2: float,
    ) -> float:
        """Calculate wind force in N."""
        if projected_area_m2 < 0:
            raise ValueError("Projected area cannot be negative")
        if coefficient < 0:
            raise ValueError("Wind coefficient cannot be negative")
        if wind_pressure_n_m2 < 0:
            raise ValueError("Wind pressure cannot be negative")
        return projected_area_m2 * coefficient * wind_pressure_n_m2

    @staticmethod
    def calculate_seismic_load(
        fix_load_n: float,
        k_value: float,
    ) -> float:
        """Calculate horizontal seismic load from gravitational FixLoad.

        Seismic load is a scalar load for each object and is not resolved by
        wind direction: ``SeismicLoad = FixLoad * k_value``.
        """
        if fix_load_n < 0:
            raise ValueError("FixLoad cannot be negative")
        if k_value <= 0:
            raise ValueError("Seismic K value must be greater than zero")
        return fix_load_n * k_value

    @staticmethod
    def calculate_moment(force_n: float, load_center_height_m: float) -> float:
        """Calculate moment in N·m."""
        if load_center_height_m < 0:
            raise ValueError("Load center height cannot be negative")
        return force_n * load_center_height_m

