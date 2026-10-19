"""Pole segment input. ``pole_type`` decides which dimensions exist."""

from typing import Annotated, Literal

from pydantic import Field, PositiveFloat, StringConstraints, field_validator

from app.engine.materials import MATERIALS
from app.shared.schemas.base import ApiModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _PoleSegmentBase(ApiModel):
    name: Name = Field(description="Nama segmen, harus unik di dalam poles.")
    material: Name = Field(
        description=f"Material tiang (tidak case-sensitive): {', '.join(sorted(MATERIALS))}."
    )
    top_elevation_m: PositiveFloat = Field(
        description=(
            "Elevasi puncak segmen (m), harus unik. Segmen terbawah mulai dari "
            "base_elevation_m; segmen berikutnya mulai dari puncak segmen di bawahnya."
        )
    )

    @field_validator("material")
    @classmethod
    def _known_material(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in MATERIALS:
            raise ValueError(f"unknown material, expected one of {sorted(MATERIALS)}")
        return normalized


class StraightPoleInput(_PoleSegmentBase):
    """Straight segment: one diameter and one thickness."""

    pole_type: Literal["Straight"] = Field(description="Segmen lurus: diameter dan tebal seragam.")
    diameter_mm: PositiveFloat = Field(description="Diameter luar (mm).")
    thickness_mm: PositiveFloat = Field(description="Tebal dinding (mm).")


class TaperPoleInput(_PoleSegmentBase):
    pole_type: Literal["Taper"] = Field(
        description="Segmen meruncing: diameter dan tebal berbeda di bawah dan di atas."
    )
    diameter_lower_mm: PositiveFloat = Field(description="Diameter luar di ujung bawah (mm).")
    diameter_upper_mm: PositiveFloat = Field(description="Diameter luar di ujung atas (mm).")
    thickness_lower_mm: PositiveFloat = Field(description="Tebal dinding di ujung bawah (mm).")
    thickness_upper_mm: PositiveFloat = Field(description="Tebal dinding di ujung atas (mm).")


PoleSegmentInput = Annotated[
    StraightPoleInput | TaperPoleInput,
    Field(discriminator="pole_type"),
]
