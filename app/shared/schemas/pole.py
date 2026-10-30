"""Pole segment input: one shape for Straight and Taper, as gateway stores it."""

from typing import Annotated, Literal

from pydantic import AfterValidator, Field, PositiveFloat, StringConstraints, model_validator

from app.engine.domain.materials import MATERIALS
from app.shared.schemas.base import ApiModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _known_material(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in MATERIALS:
        raise ValueError(f"unknown material, expected one of {sorted(MATERIALS)}")
    return normalized


Material = Annotated[
    str,
    AfterValidator(_known_material),
    Field(description=f"Material (tidak case-sensitive): {', '.join(sorted(MATERIALS))}."),
]


class PoleSegmentInput(ApiModel):
    """Lower values always exist. Upper values exist only for Taper.

    A Straight segment uses the lower values for its whole length; upper values
    sent for it are ignored, the same as in python_calc.
    """

    name: Name = Field(description="Nama segmen, harus unik di dalam poles.")
    pole_type: Literal["Straight", "Taper"] = Field(
        description="Straight: ukuran seragam (lower). Taper: meruncing dari lower ke upper."
    )
    material: Material
    top_elevation_m: PositiveFloat = Field(
        description=(
            "Elevasi puncak segmen (m), harus unik. Segmen terbawah mulai dari "
            "base_elevation_m; segmen berikutnya mulai dari puncak segmen di bawahnya."
        )
    )
    diameter_lower_mm: PositiveFloat = Field(description="Diameter luar di ujung bawah (mm).")
    thickness_lower_mm: PositiveFloat = Field(description="Tebal dinding di ujung bawah (mm).")
    diameter_upper_mm: PositiveFloat | None = Field(
        default=None,
        description="Diameter luar di ujung atas (mm). Wajib untuk Taper, diabaikan untuk Straight.",
    )
    thickness_upper_mm: PositiveFloat | None = Field(
        default=None,
        description="Tebal dinding di ujung atas (mm). Wajib untuk Taper, diabaikan untuk Straight.",
    )

    @model_validator(mode="after")
    def _taper_needs_upper(self):
        if self.pole_type == "Taper" and (
            self.diameter_upper_mm is None or self.thickness_upper_mm is None
        ):
            raise ValueError("Taper needs diameter_upper_mm and thickness_upper_mm")
        return self
