"""Domain objects for horizontal arms and equipment mounted on them.

Ported from python_calc ``domain/arm.py`` (commit 270d23b).
"""

from dataclasses import dataclass
from enum import Enum
from math import isfinite, pi

from .loads import LoadObject
from .materials import PoleMaterial, get_pole_material


class ArmType(str, Enum):
    """Arm geometries currently supported by the calculation engine."""

    SINGLE_ROUND_STRAIGHT = "SingleRoundStraight"


class ArmObjectType(str, Enum):
    """Wind exposure behaviour of an object mounted on an arm."""

    DIRECTIONAL = "Directional"
    OMNI = "Omni"
    ARM_BODY = "ArmBody"


def _finite(value: float, name: str) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number") from None
    if not isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


@dataclass(frozen=True)
class Arm:
    """Physical input for one single, round, straight arm.

    Lengths are metres; diameter and thickness are millimetres. The wind
    The round-arm shape factor is fixed at 0.7. Future square or rectangular
    Arm types will use 1.3 after those geometries are implemented.
    """

    name: str
    diameter_mm: float
    thickness_mm: float
    total_length_m: float
    exposed_length_m: float
    installation_height_m: float
    material: PoleMaterial | str
    fixed_angle_deg: float = 0.0
    arm_type: ArmType | str = ArmType.SINGLE_ROUND_STRAIGHT

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Arm name cannot be empty")
        try:
            arm_type = ArmType(self.arm_type)
        except ValueError:
            raise ValueError(
                "Only the SingleRoundStraight arm type is currently supported"
            ) from None
        material = (
            get_pole_material(self.material)
            if isinstance(self.material, str)
            else self.material
        )
        if not isinstance(material, PoleMaterial):
            raise ValueError("material must be a PoleMaterial or recognized name")

        numeric = {
            "diameter_mm": _finite(self.diameter_mm, "diameter_mm"),
            "thickness_mm": _finite(self.thickness_mm, "thickness_mm"),
            "total_length_m": _finite(self.total_length_m, "total_length_m"),
            "exposed_length_m": _finite(
                self.exposed_length_m, "exposed_length_m"
            ),
            "installation_height_m": _finite(
                self.installation_height_m, "installation_height_m"
            ),
            "fixed_angle_deg": _finite(self.fixed_angle_deg, "fixed_angle_deg"),
        }
        for name in (
            "diameter_mm",
            "thickness_mm",
            "total_length_m",
            "exposed_length_m",
        ):
            if numeric[name] <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if numeric["installation_height_m"] < 0:
            raise ValueError("installation_height_m cannot be negative")
        if numeric["exposed_length_m"] > numeric["total_length_m"]:
            raise ValueError("exposed_length_m cannot exceed total_length_m")
        if 2 * numeric["thickness_mm"] >= numeric["diameter_mm"]:
            raise ValueError("thickness_mm must be less than half the diameter")

        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "arm_type", arm_type)
        object.__setattr__(self, "material", material)
        for name, value in numeric.items():
            object.__setattr__(self, name, value)

    @property
    def shape_factor(self) -> float:
        """Return the confirmed nC/Cf for the supported round Arm."""
        return 0.7


@dataclass(frozen=True)
class ArmLoadObject:
    """One piece of equipment carried by an arm."""

    name: str
    object_type: ArmObjectType | str
    front_area_m2: float
    side_area_m2: float
    mass_per_unit_kg: float
    horizontal_load_distance_m: float
    base_wind_coefficient: float
    quantity: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Arm Object name cannot be empty")
        try:
            object_type = ArmObjectType(self.object_type)
        except ValueError:
            raise ValueError(
                "object_type must be Directional, Omni, or ArmBody"
            ) from None
        numeric = {
            "front_area_m2": _finite(self.front_area_m2, "front_area_m2"),
            "side_area_m2": _finite(self.side_area_m2, "side_area_m2"),
            "mass_per_unit_kg": _finite(
                self.mass_per_unit_kg, "mass_per_unit_kg"
            ),
            "horizontal_load_distance_m": _finite(
                self.horizontal_load_distance_m,
                "horizontal_load_distance_m",
            ),
            "base_wind_coefficient": _finite(
                self.base_wind_coefficient, "base_wind_coefficient"
            ),
        }
        if numeric["front_area_m2"] < 0 or numeric["side_area_m2"] < 0:
            raise ValueError("Arm Object areas cannot be negative")
        if numeric["front_area_m2"] == numeric["side_area_m2"] == 0:
            raise ValueError("At least one Arm Object area must be positive")
        if numeric["mass_per_unit_kg"] < 0:
            raise ValueError("mass_per_unit_kg cannot be negative")
        if numeric["horizontal_load_distance_m"] < 0:
            raise ValueError("horizontal_load_distance_m cannot be negative")
        if numeric["base_wind_coefficient"] <= 0:
            raise ValueError("base_wind_coefficient must be greater than zero")
        quantity = int(self.quantity)
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if object_type is ArmObjectType.ARM_BODY and numeric["side_area_m2"] != 0:
            raise ValueError("A single round Arm body must have zero side area")

        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "object_type", object_type)
        object.__setattr__(self, "quantity", quantity)
        for name, value in numeric.items():
            object.__setattr__(self, name, value)

    @property
    def is_omni(self) -> bool:
        return self.object_type is ArmObjectType.OMNI

    def total_mass_kg(self) -> float:
        return self.mass_per_unit_kg * self.quantity

    def fix_load_n(
        self,
        gravity_m_s2: float = LoadObject.GRAVITY,
    ) -> float:
        if gravity_m_s2 <= 0:
            raise ValueError("gravity_m_s2 must be greater than zero")
        return self.total_mass_kg() * gravity_m_s2

    @staticmethod
    def angle_of_attack_rad(
        arm_fixed_angle_deg: float,
        wind_angle_rad: float,
    ) -> float:
        """Use the angle of the Arm on which this object is installed."""
        return float(arm_fixed_angle_deg) / 180 * pi - float(wind_angle_rad)


@dataclass(frozen=True)
class ArmPart:
    """One arm and the equipment supported by it."""

    arm: Arm
    mounted_objects: tuple[ArmLoadObject, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.arm, Arm):
            raise TypeError("arm must be an Arm")
        objects = tuple(self.mounted_objects)
        if any(not isinstance(item, ArmLoadObject) for item in objects):
            raise TypeError("mounted_objects must contain ArmLoadObject instances")
        if any(item.object_type is ArmObjectType.ARM_BODY for item in objects):
            raise ValueError("ArmBody is generated from Arm and cannot be mounted")
        ordered = tuple(
            sorted(
                objects,
                key=lambda item: item.horizontal_load_distance_m,
                reverse=True,
            )
        )
        object.__setattr__(self, "mounted_objects", ordered)


@dataclass(frozen=True)
class ArmAssembly:
    """All arm parts installed on one pole structure."""

    arm_parts: tuple[ArmPart, ...]

    def __post_init__(self) -> None:
        parts = tuple(self.arm_parts)
        if any(not isinstance(item, ArmPart) for item in parts):
            raise TypeError("arm_parts must contain ArmPart instances")
        object.__setattr__(self, "arm_parts", parts)

