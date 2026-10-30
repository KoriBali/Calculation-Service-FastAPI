from typing import Annotated, Literal

from pydantic import Field, PositiveFloat, model_validator

from app.shared.schemas.arm import ArmInput
from app.shared.schemas.base import ApiModel
from app.shared.schemas.direct_object import DirectObjectInput
from app.shared.schemas.overhead_wire import OverheadWireInput
from app.shared.schemas.pole import PoleSegmentInput


class PoleCalculationRequest(ApiModel):
    """Design standard 3 (Old Lighting Pole). Every component except the pole is optional.

    Other design standards get their own request model later; the union is
    discriminated by ``design_standard``.
    """

    design_standard: Literal[3] = Field(
        description="Design standard. Saat ini hanya 3 (Old Lighting Pole) yang dibuka."
    )
    include_oblique_wind: bool = Field(
        default=False,
        description="true = hitung juga angin miring 45° (OBLIQUE) selain angin lurus 90° (STRAIGHT).",
    )
    overdesign_factor: PositiveFloat = Field(
        default=1.0,
        description="Pengali beban gravitasi tiang (FixLoad). 1.0 = tanpa amplifikasi.",
    )
    base_elevation_m: float = Field(
        default=0.0,
        description="Elevasi dasar tiang (m), yaitu titik bawah segmen terbawah.",
    )
    poles: Annotated[list[PoleSegmentInput], Field(min_length=1)] = Field(
        description="Segmen tiang, minimal satu. Urutan bebas; diurutkan menurut top_elevation_m."
    )
    direct_objects: list[DirectObjectInput] = Field(
        default_factory=list,
        description="Objek yang dipasang langsung di tiang (lampu, rambu, dll.).",
    )
    overhead_wires: list[OverheadWireInput] = Field(
        default_factory=list,
        description="Kabel udara yang diikat ke tiang.",
    )
    arms: list[ArmInput] = Field(
        default_factory=list,
        description="Arm dan objek yang dipasang di arm.",
    )
    evaluated_positions_m: Annotated[list[float], Field(min_length=1)] = Field(
        description=(
            "Elevasi (m) tempat penampang dicek, minimal satu. Harus unik, tidak boleh "
            "di bawah base_elevation_m, dan harus di bawah puncak tiang tertinggi."
        )
    )

    @model_validator(mode="after")
    def _check_consistency(self):
        for label, items in (
            ("poles", self.poles),
            ("direct_objects", self.direct_objects),
            ("overhead_wires", self.overhead_wires),
            ("arms", self.arms),
        ):
            names = [item.name for item in items]
            if len(names) != len(set(names)):
                raise ValueError(f"{label}: name must be unique")

        tops = [pole.top_elevation_m for pole in self.poles]
        if len(tops) != len(set(tops)):
            raise ValueError("poles: top_elevation_m must be unique")

        positions = self.evaluated_positions_m
        if len(positions) != len(set(positions)):
            raise ValueError("evaluated_positions_m: positions must be unique")
        if any(position < self.base_elevation_m for position in positions):
            raise ValueError("evaluated_positions_m: position cannot be below base_elevation_m")
        return self
