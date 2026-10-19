from typing import Annotated

from pydantic import Field, PositiveFloat, model_validator

from app.shared.schemas.base import ApiModel
from app.shared.schemas.conditions import SeismicInput, WindInput
from app.shared.schemas.direct_object import DirectObjectInput
from app.shared.schemas.pole import PoleSegmentInput


class SectionCheckRequest(ApiModel):
    """Every component except the pole is optional: sent = calculated.

    ``overhead_wires`` is not accepted yet (waits for decision D6).
    """

    wind: WindInput = Field(
        description="Kondisi angin. design_standard menentukan field lain yang wajib dikirim."
    )
    seismic: SeismicInput | None = Field(
        default=None,
        description=(
            'Kondisi seismik (opsional). {"position": "Ground", "k_value": ...} atau '
            '{"position": "Rooftop", "seismic_class": "A"|"B"|"S"}. '
            "Kalau tidak dikirim, hanya cek angin yang dihitung."
        ),
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
        description="Objek yang dipasang di tiang (lampu, rambu, dll.). Opsional.",
    )
    evaluated_positions_m: Annotated[list[float], Field(min_length=1)] = Field(
        description=(
            "Elevasi (m) tempat penampang dicek, minimal satu. Harus unik, tidak boleh "
            "di bawah base_elevation_m, dan harus di bawah puncak tiang tertinggi."
        )
    )

    @model_validator(mode="after")
    def _check_consistency(self):
        for label, items in (("poles", self.poles), ("direct_objects", self.direct_objects)):
            names = [item.name for item in items]
            if len(names) != len(set(names)):
                raise ValueError(f"{label}: name must be unique")

        positions = self.evaluated_positions_m
        if len(positions) != len(set(positions)):
            raise ValueError("evaluated_positions_m: positions must be unique")
        if any(position < self.base_elevation_m for position in positions):
            raise ValueError("evaluated_positions_m: position cannot be below base_elevation_m")
        return self
