"""Domain model for one straight or tapered pole segment.

Ported from python_calc ``domain/pole.py``.
DEVIATION: rounding follows VBA (see app/engine/rounding.py).
"""

from dataclasses import dataclass
from enum import Enum

from app.engine import rounding, sections

from app.engine.loads.base import LoadObject, OverdesignFactor
from app.engine.materials import PoleMaterial, get_pole_material


@dataclass(frozen=True)
class PoleSectionProperties:
    """Cross-sectional properties at an evaluated position.

    Units follow ``M_Func_Basic.bas``: area in cm², section modulus in cm³,
    moment of inertia in cm⁴, and radius of gyration in cm.
    """

    diameter_mm: float
    thickness_mm: float
    cross_section_area_cm2: float
    section_modulus_cm3: float
    moment_of_inertia_cm4: float
    second_moment_pair_cm4: float
    radius_of_gyration_cm: float


class PoleType(str, Enum):
    """Supported pole geometries."""

    STRAIGHT = "Straight"
    TAPERED = "Taper"


class PoleObject(LoadObject):
    """Represent permanent data and behaviour of one physical pole segment.

    Units
    -----
    - diameter and thickness: mm
    - elevation and length: m
    - projected area: m²

    Values that depend on an evaluated position are calculated and returned;
    they are not stored as mutable state on this object.
    """

    def __init__(
        self,
        name: str,
        pole_type: PoleType | str,
        diameter_lower_mm: float,
        diameter_upper_mm: float,
        thickness_lower_mm: float,
        thickness_upper_mm: float,
        material: PoleMaterial | str,
        top_elevation_m: float,
        quantity: int = 1,
    ) -> None:
        super().__init__(name=name)

        try:
            self.pole_type = PoleType(pole_type)
        except ValueError:
            raise ValueError("pole_type must be 'Straight' or 'Taper'") from None

        self.diameter_lower_mm = float(diameter_lower_mm)
        self.diameter_upper_mm = float(diameter_upper_mm)
        self.thickness_lower_mm = float(thickness_lower_mm)
        self.thickness_upper_mm = float(thickness_upper_mm)
        self.material = (
            get_pole_material(material) if isinstance(material, str) else material
        )
        self.top_elevation_m = float(top_elevation_m)
        self.quantity = int(quantity)
        self._validate()

    def _validate(self) -> None:
        dimensions = {
            "diameter_lower_mm": self.diameter_lower_mm,
            "diameter_upper_mm": self.diameter_upper_mm,
            "thickness_lower_mm": self.thickness_lower_mm,
            "thickness_upper_mm": self.thickness_upper_mm,
            "top_elevation_m": self.top_elevation_m,
        }
        for name, value in dimensions.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")

        if not isinstance(self.material, PoleMaterial):
            raise ValueError("material must be a PoleMaterial or recognized name")
        if self.quantity != 1:
            raise ValueError("Pole quantity is currently limited to 1")

    @property
    def is_tapered(self) -> bool:
        return self.pole_type is PoleType.TAPERED

    def taper_ratio_mm_per_m(self, full_length_m: float) -> float:
        """Return diameter change in mm for each metre of pole length."""
        self._validate_length(full_length_m, "full_length_m")
        if not self.is_tapered:
            return 0.0
        return (
            self.diameter_lower_mm - self.diameter_upper_mm
        ) / full_length_m

    def diameter_at(
        self,
        distance_from_top_m: float,
        full_length_m: float,
    ) -> float:
        """Return diameter in mm at a distance measured from the pole top."""
        self._validate_distance(distance_from_top_m, full_length_m)
        if not self.is_tapered:
            return self.diameter_lower_mm
        return self.diameter_upper_mm + (
            self.taper_ratio_mm_per_m(full_length_m) * distance_from_top_m
        )

    def thickness_at_evaluated_position(self) -> float:
        """Return thickness used at the evaluated position.

        This intentionally follows the current VBA rule, which uses the lower
        thickness. No thickness interpolation is introduced here.
        """
        return self.thickness_lower_mm

    def section_properties(
        self,
        diameter_at_position_mm: float,
    ) -> PoleSectionProperties:
        """Calculate cross-sectional properties at an evaluated position.

        The thickness follows the existing VBA rule: ``thc_L`` is used with
        the diameter calculated at the evaluated position.
        """
        if diameter_at_position_mm <= 0:
            raise ValueError("diameter_at_position_mm must be greater than zero")

        thickness = self.thickness_at_evaluated_position()
        moment_of_inertia = sections.moment_of_inertia_cm4(
            diameter_at_position_mm,
            thickness,
        )
        return PoleSectionProperties(
            diameter_mm=diameter_at_position_mm,
            thickness_mm=thickness,
            cross_section_area_cm2=sections.cross_section_area_cm2(
                diameter_at_position_mm,
                thickness,
            ),
            section_modulus_cm3=sections.section_modulus_cm3(
                diameter_at_position_mm,
                thickness,
            ),
            moment_of_inertia_cm4=moment_of_inertia,
            second_moment_pair_cm4=rounding.SECOND_MOMENT_PAIR(moment_of_inertia * 2),
            radius_of_gyration_cm=sections.radius_of_gyration_cm(
                diameter_at_position_mm,
                thickness,
            ),
        )

    def mass_kg(
        self,
        active_length_m: float,
        diameter_at_active_bottom_mm: float,
        diameter_at_active_top_mm: float,
    ) -> float:
        """Return mass of the active pole portion using BasicFunction.py.

        A tapered pole uses both lower/upper diameter and both lower/upper
        thickness exactly as supplied to the object. Thickness is not
        interpolated.
        """
        if active_length_m < 0:
            raise ValueError("active_length_m cannot be negative")
        if active_length_m == 0:
            return 0.0

        if not self.is_tapered:
            mass = sections.straight_pole_mass_kg(
                diameter_mm=self.diameter_lower_mm,
                thickness_mm=self.thickness_lower_mm,
                length_m=active_length_m,
            )
        else:
            mass = sections.taper_pole_mass_kg(
                diameter_upper_mm=diameter_at_active_top_mm,
                diameter_lower_mm=diameter_at_active_bottom_mm,
                thickness_upper_mm=self.thickness_upper_mm,
                thickness_lower_mm=self.thickness_lower_mm,
                length_m=active_length_m,
            )

        return mass

    def fix_load_n(
        self,
        active_length_m: float,
        diameter_at_active_bottom_mm: float,
        diameter_at_active_top_mm: float,
        overdesign_factor: OverdesignFactor | None = None,
    ) -> float:
        """Return amplified gravitational FixLoad of the active pole in N."""
        mass = self.mass_kg(
            active_length_m=active_length_m,
            diameter_at_active_bottom_mm=diameter_at_active_bottom_mm,
            diameter_at_active_top_mm=diameter_at_active_top_mm,
        )
        factor = overdesign_factor or OverdesignFactor()
        weight = rounding.SIG3(self.force_from_mass(mass))
        return rounding.SIG3(factor.apply(weight))

    @staticmethod
    def slenderness_ratio(active_length_m: float, diameter_mm: float) -> float:
        """Return HpB using length and diameter expressed in the same unit."""
        if active_length_m < 0:
            raise ValueError("active_length_m cannot be negative")
        if diameter_mm <= 0:
            raise ValueError("diameter_mm must be greater than zero")
        return active_length_m / (diameter_mm / 1000)

    @classmethod
    def base_wind_coefficient(
        cls,
        active_length_m: float,
        diameter_mm: float,
        design_standard: int,
    ) -> float:
        """Return nnC as reported (rounded)."""
        return rounding.NNC(
            cls._unrounded_wind_coefficient(active_length_m, diameter_mm, design_standard)
        )

    @classmethod
    def _unrounded_wind_coefficient(
        cls,
        active_length_m: float,
        diameter_mm: float,
        design_standard: int,
    ) -> float:
        """Calculate pole nnC according to the selected design standard.

        Standards 1 and 6 use the pole HpB ratio. Standards 2 through 5
        use the fixed value 0.7, following ``Pole_each.Calc_Cf`` in VBA.
        """
        if design_standard not in {1, 2, 3, 4, 5, 6}:
            raise ValueError("Design standard must be between 1 and 6")
        if design_standard not in {1, 6}:
            return 0.7

        hpb = cls.slenderness_ratio(active_length_m, diameter_mm)
        if hpb <= 1:
            nnc = 0.7
        elif hpb < 8:
            nnc = (0.2 / 7) * hpb + 0.67144
        else:
            nnc = 0.9
        return nnc

    def wind_coefficient(
        self,
        active_length_m: float,
        diameter_at_active_bottom_mm: float,
        design_standard: int,
        kz: float = 1.0,
    ) -> float:
        """Return effective CF using the diameter at the active pole bottom.

        HpB and nnC use the actual diameter at ``EvaluatedPosition`` when it
        cuts through this pole. For a whole segment above that position, the
        diameter at the physical bottom of the segment is used.
        """
        nnc = rounding.NNC_INTO_CF(self._unrounded_wind_coefficient(
            active_length_m=active_length_m,
            diameter_mm=diameter_at_active_bottom_mm,
            design_standard=design_standard,
        ))
        cf = nnc * kz if design_standard == 1 else nnc
        return rounding.CF(cf)

    def projected_area(
        self,
        active_length_m: float,
        diameter_at_bottom_mm: float,
        diameter_at_top_mm: float,
    ) -> float:
        """Return projected wind area of the active pole portion in m²."""
        if active_length_m < 0:
            raise ValueError("active_length_m cannot be negative")
        if diameter_at_bottom_mm <= 0 or diameter_at_top_mm <= 0:
            raise ValueError("Active pole diameters must be greater than zero")

        average_diameter_m = (
            (diameter_at_bottom_mm + diameter_at_top_mm) / 2
        ) / 1000
        return rounding.SIG3(average_diameter_m * active_length_m)

    def local_load_center(
        self,
        active_length_m: float,
        diameter_at_bottom_mm: float,
        diameter_at_top_mm: float,
    ) -> float:
        """Return load center above the bottom of the active portion, in m."""
        if active_length_m < 0:
            raise ValueError("active_length_m cannot be negative")
        if active_length_m == 0:
            return 0.0
        if not self.is_tapered:
            return rounding.SIG3(active_length_m / 2)

        diameter_sum = diameter_at_bottom_mm + diameter_at_top_mm
        if diameter_sum <= 0:
            raise ValueError("Sum of active pole diameters must be positive")
        return rounding.SIG3(
            active_length_m
            / 3
            * (2 * diameter_at_top_mm + diameter_at_bottom_mm)
            / diameter_sum
        )

    @staticmethod
    def _validate_length(length_m: float, name: str) -> None:
        if length_m <= 0:
            raise ValueError(f"{name} must be greater than zero")

    @classmethod
    def _validate_distance(
        cls,
        distance_from_top_m: float,
        full_length_m: float,
    ) -> None:
        cls._validate_length(full_length_m, "full_length_m")
        if not 0 <= distance_from_top_m <= full_length_m:
            raise ValueError(
                "distance_from_top_m must be between zero and full_length_m"
            )

