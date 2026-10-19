"""Direct Object input. ``object_type`` decides which fields exist."""

from typing import Annotated, Literal

from pydantic import Field, NonNegativeFloat, PositiveFloat, PositiveInt

from app.shared.schemas.base import ApiModel
from app.shared.schemas.pole import Name


class _DirectObjectBase(ApiModel):
    name: Name = Field(description="Nama objek, harus unik di dalam direct_objects.")
    front_area_m2: PositiveFloat = Field(description="Luas proyeksi depan per unit (m²).")
    mass_per_unit_kg: NonNegativeFloat = Field(description="Massa per unit (kg).")
    elevation_m: NonNegativeFloat = Field(description="Elevasi titik pasang objek (m).")
    base_wind_coefficient: PositiveFloat = Field(description="Koefisien angin dasar (Cf), misalnya 1.0.")
    quantity: PositiveInt = Field(description="Jumlah unit yang identik.")


class OmniObjectInput(_DirectObjectBase):
    """Same projected area from every direction: no side area, no angle."""

    object_type: Literal["Omni"] = Field(
        description="Luas proyeksi sama dari semua arah. Jangan kirim side_area_m2 atau fixed_angle_deg."
    )


class DirectionalObjectInput(_DirectObjectBase):
    object_type: Literal["Directional"] = Field(
        description="Luas proyeksi bergantung arah angin (depan dan samping)."
    )
    side_area_m2: NonNegativeFloat = Field(description="Luas proyeksi samping per unit (m²).")
    fixed_angle_deg: float = Field(description="Sudut orientasi objek (derajat).")


DirectObjectInput = Annotated[
    OmniObjectInput | DirectionalObjectInput,
    Field(discriminator="object_type"),
]
