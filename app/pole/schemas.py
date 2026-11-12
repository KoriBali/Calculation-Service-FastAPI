"""Pole calculation requests, one model per design standard.

The body is a union discriminated by ``design_standard``; the route declares
the discriminator (``Body(discriminator=...)``), so a body is validated only
against the model of its own standard.
"""

from typing import Annotated, Literal

from pydantic import Field, PositiveFloat, model_validator

from app.shared.schemas.arm import ArmInput
from app.shared.schemas.base import ApiModel
from app.shared.schemas.direct_object import DirectObjectInput
from app.shared.schemas.overhead_wire import OverheadWireInput
from app.shared.schemas.pole import PoleSegmentInput


class _PoleRequestBase(ApiModel):
    """Fields shared by every design standard. Every component except the pole is optional."""

    # Narrowed to a Literal by each subclass; declared here so it stays the first field.
    design_standard: int
    wind_speed_m_s: PositiveFloat = Field(
        description=(
            "Kecepatan angin rencana (m/s). Default-nya dari master design standard "
            "(Old JIL dan New JIL: 60) dan boleh diubah user per request."
        )
    )
    air_density_kg_m3: PositiveFloat = Field(
        description=(
            "Massa jenis udara (kg/m³). Default-nya dari master design standard "
            "(Old JIL dan New JIL: 1.23) dan boleh diubah user per request."
        )
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


class PoleStandard3Request(_PoleRequestBase):
    """Design standard 3 (Old Lighting Pole): bending only, no seismic."""

    design_standard: Literal[3] = Field(description="3 = Old Lighting Pole (Old JIL).")
    include_oblique_wind: bool = Field(
        default=False,
        description="true = hitung juga angin miring 45° (OBLIQUE) selain angin lurus 90° (STRAIGHT).",
    )


class PoleStandard7Request(_PoleRequestBase):
    """Design standard 7 (New JIL): eight wind directions, torsion and seismic.

    The seismic inputs are optional: when left out, the engine default applies.
    """

    design_standard: Literal[7] = Field(description="7 = New JIL.")
    horizontal_acceleration_m_s2: PositiveFloat | None = Field(
        default=None,
        description=(
            "Horizontal Acceleration (EQa), m/s². Opsional; bila tidak dikirim, "
            "dipakai default New JIL 4.71. Beban seismik = massa × EQa × EQr."
        ),
    )
    response_ratio: PositiveFloat | None = Field(
        default=None,
        description=(
            "Response Ratio (EQr), tanpa satuan. Opsional; bila tidak dikirim, "
            "dipakai default New JIL 1.0."
        ),
    )


PoleCalculationRequest = PoleStandard3Request | PoleStandard7Request
