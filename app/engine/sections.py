"""Cross-section and mass formulas for round steel pipe.

Units: diameter and thickness in mm, length in m, results in cm², cm³, cm⁴,
cm, and kg.
"""
from app.engine import rounding

PI = 3.14159265358979  # same literal as VBA, not math.pi
DENSITY = 7850  # kg/m³, steel


def cross_section_area_cm2(diameter_mm: float, thickness_mm: float) -> float:
    """BasicFunction.Cross_AreaP."""
    return rounding.SECTION_PROPERTY(
        PI / 4 * (diameter_mm**2 - (diameter_mm - 2 * thickness_mm) ** 2) / 100,
    )


def moment_of_inertia_cm4(diameter_mm: float, thickness_mm: float) -> float:
    """BasicFunction.Moment_Inertia."""
    return rounding.SECTION_PROPERTY(
        (PI / 64)
        * ((diameter_mm**4) - (diameter_mm - 2 * thickness_mm) ** 4)
        / 10000,
    )


def section_modulus_cm3(diameter_mm: float, thickness_mm: float) -> float:
    """BasicFunction.Section_Modulus."""
    return rounding.SECTION_PROPERTY(
        PI
        * (diameter_mm**4 - (diameter_mm - thickness_mm * 2) ** 4)
        / (32 * diameter_mm)
        / 1000,
    )


def radius_of_gyration_cm(diameter_mm: float, thickness_mm: float) -> float:
    """BasicFunction.Radius_Gyration."""
    return rounding.SECTION_PROPERTY(
        ((1 / 16) * (diameter_mm**2 + (diameter_mm - 2 * thickness_mm) ** 2) / 100)
        ** 0.5,
    )


def straight_pole_mass_kg(
    diameter_mm: float,
    thickness_mm: float,
    length_m: float,
) -> float:
    """BasicFunction.Pole_WeightKg_Straight."""
    mass = (
        (PI / 4)
        * (diameter_mm**2 - (diameter_mm - 2 * thickness_mm) ** 2)
        / (10**6)
        * DENSITY
        * length_m
    )
    return rounding.POLE_MASS(mass)


def taper_pole_mass_kg(
    diameter_upper_mm: float,
    diameter_lower_mm: float,
    thickness_upper_mm: float,
    thickness_lower_mm: float,
    length_m: float,
) -> float:
    """BasicFunction.Pole_WeightKg_Taper."""
    mass = (
        (PI * length_m / 4)
        * (
            ((diameter_lower_mm - diameter_upper_mm) / 2 + diameter_upper_mm) ** 2
            - (
                (
                    (diameter_lower_mm - 2 * thickness_lower_mm)
                    - (diameter_upper_mm - 2 * thickness_upper_mm)
                )
                / 2
                + (diameter_upper_mm - 2 * thickness_upper_mm)
            )
            ** 2
        )
        / 10**6
        * DENSITY
    )
    return rounding.POLE_MASS(mass)