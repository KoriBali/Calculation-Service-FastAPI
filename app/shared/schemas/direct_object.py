"""Direct Object input: one shape for Omni and Directional, as gateway stores it."""

from typing import Literal

from pydantic import Field, NonNegativeFloat, PositiveFloat, PositiveInt, model_validator

from app.shared.schemas.base import ApiModel
from app.shared.schemas.pole import Name


class DirectObjectInput(ApiModel):
    """Side area and angle exist only for Directional; Omni ignores them."""

    name: Name = Field(description="Nama objek, harus unik di dalam direct_objects.")
    object_type: Literal["Omni", "Directional"] = Field(
        description=(
            "Omni: luas proyeksi sama dari semua arah. "
            "Directional: luas bergantung arah angin (depan dan samping)."
        )
    )
    front_area_m2: PositiveFloat = Field(description="Luas proyeksi depan per unit (m²).")
    side_area_m2: NonNegativeFloat | None = Field(
        default=None,
        description="Luas proyeksi samping per unit (m²). Wajib untuk Directional, diabaikan untuk Omni.",
    )
    fixed_angle_deg: float | None = Field(
        default=None,
        description="Sudut orientasi objek (derajat). Wajib untuk Directional, diabaikan untuk Omni.",
    )
    mass_per_unit_kg: NonNegativeFloat = Field(description="Massa per unit (kg).")
    elevation_m: NonNegativeFloat = Field(description="Elevasi titik pasang objek (m).")
    base_wind_coefficient: PositiveFloat = Field(description="Koefisien angin dasar (Cf), misalnya 1.0.")
    quantity: PositiveInt = Field(description="Jumlah unit yang identik.")

    @model_validator(mode="after")
    def _directional_needs_side(self):
        if self.object_type == "Directional" and (
            self.side_area_m2 is None or self.fixed_angle_deg is None
        ):
            raise ValueError("Directional needs side_area_m2 and fixed_angle_deg")
        return self
