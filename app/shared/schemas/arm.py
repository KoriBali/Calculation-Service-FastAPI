"""Arm input: one single round straight arm and the objects mounted on it."""

from typing import Literal

from pydantic import Field, NonNegativeFloat, PositiveFloat, PositiveInt, model_validator

from app.shared.schemas.base import ApiModel
from app.shared.schemas.pole import Material, Name


class ArmObjectInput(ApiModel):
    """Side area exists only for Directional; Omni ignores it."""

    name: Name = Field(description="Nama objek, harus unik di dalam objects satu arm.")
    object_type: Literal["Omni", "Directional"] = Field(
        description=(
            "Omni: luas proyeksi sama dari semua arah. "
            "Directional: luas bergantung arah angin (depan dan samping)."
        )
    )
    front_area_m2: NonNegativeFloat = Field(description="Luas proyeksi depan per unit (m²).")
    side_area_m2: NonNegativeFloat | None = Field(
        default=None,
        description="Luas proyeksi samping per unit (m²). Wajib untuk Directional, diabaikan untuk Omni.",
    )
    mass_per_unit_kg: NonNegativeFloat = Field(description="Massa per unit (kg).")
    horizontal_load_distance_m: NonNegativeFloat = Field(
        description="Jarak horizontal titik beban ke tumpuan arm di tiang (m)."
    )
    base_wind_coefficient: PositiveFloat = Field(description="Koefisien angin dasar (Cf), misalnya 1.0.")
    quantity: PositiveInt = Field(description="Jumlah unit yang identik.")

    @model_validator(mode="after")
    def _directional_needs_side(self):
        if self.object_type == "Directional" and self.side_area_m2 is None:
            raise ValueError("Directional needs side_area_m2")
        return self


class ArmInput(ApiModel):
    """Only the SingleRoundStraight arm type exists in the engine."""

    name: Name = Field(description="Nama arm, harus unik di dalam arms.")
    material: Material
    diameter_mm: PositiveFloat = Field(description="Diameter luar pipa arm (mm).")
    thickness_mm: PositiveFloat = Field(description="Tebal dinding pipa arm (mm), kurang dari setengah diameter.")
    total_length_m: PositiveFloat = Field(description="Panjang total arm (m).")
    exposed_length_m: PositiveFloat = Field(
        description="Panjang arm yang terkena angin (m), tidak lebih dari total_length_m."
    )
    installation_height_m: NonNegativeFloat = Field(description="Elevasi pasang arm di tiang (m).")
    fixed_angle_deg: float = Field(default=0.0, description="Arah arm di bidang horizontal (derajat).")
    objects: list[ArmObjectInput] = Field(
        default_factory=list,
        description="Objek yang dipasang di arm. Badan arm dihitung otomatis, jangan dikirim.",
    )

    @model_validator(mode="after")
    def _unique_object_names(self):
        names = [item.name for item in self.objects]
        if len(names) != len(set(names)):
            raise ValueError("objects: name must be unique")
        return self
