"""Overhead wire (OHW) input."""

from pydantic import Field, NonNegativeFloat, PositiveFloat

from app.shared.schemas.base import ApiModel
from app.shared.schemas.pole import Name


class OverheadWireInput(ApiModel):
    name: Name = Field(description="Nama kabel, harus unik di dalam overhead_wires.")
    mass_per_length_kg_m: PositiveFloat = Field(description="Massa kabel per meter (kg/m).")
    diameter_mm: PositiveFloat = Field(description="Diameter kabel (mm).")
    elevation_m: NonNegativeFloat = Field(description="Elevasi titik ikat kabel di tiang (m).")
    span_length_m: PositiveFloat = Field(description="Panjang bentang penuh (m).")
    sag_ratio_percent: PositiveFloat = Field(description="Rasio lendutan (%).")
    base_wind_coefficient: PositiveFloat = Field(description="Koefisien angin dasar (Cf), misalnya 1.0.")
    fixed_angle_deg: float = Field(default=0.0, description="Arah bentang kabel di bidang horizontal (derajat).")
    vertical_angle_deg: float = Field(
        default=0.0,
        description="Sudut kabel terhadap horizontal (derajat); cosinus-nya harus positif.",
    )
