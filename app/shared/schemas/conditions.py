"""Wind and seismic input. The classifier field decides which fields exist."""

from typing import Annotated, Literal

from pydantic import Field, PositiveFloat

from app.shared.schemas.base import ApiModel

STRUCTURE_HEIGHT = "Tinggi struktur (m), dipakai untuk parameter angin."


class WindAtmosphericInput(ApiModel):
    """Design standard 1 or 6: atmospheric category and wind speed required."""

    design_standard: Literal[1, 6] = Field(
        description="Standar desain angin 1 atau 6 (dihitung dari kategori atmosfer dan kecepatan angin)."
    )
    structure_height_m: PositiveFloat = Field(description=STRUCTURE_HEIGHT)
    atmospheric_category: Literal[1, 2, 3, 4] = Field(
        description="Kategori atmosfer 1-4 (I-IV). Wajib untuk standar 1 dan 6."
    )
    basic_wind_speed_m_s: PositiveFloat = Field(
        description="Kecepatan angin dasar (m/s). Wajib untuk standar 1 dan 6."
    )


class WindFixedInput(ApiModel):
    """Design standard 2-5: wind pressure is a constant inside the engine."""

    design_standard: Literal[2, 3, 4, 5] = Field(
        description=(
            "Standar desain angin 2-5: tekanan angin konstan (standar 2-3 = 60 m/s, "
            "4 = 40 m/s, 5 = 50 m/s). Jangan kirim atmospheric_category atau "
            "basic_wind_speed_m_s."
        )
    )
    structure_height_m: PositiveFloat = Field(description=STRUCTURE_HEIGHT)


WindInput = Annotated[
    WindAtmosphericInput | WindFixedInput,
    Field(discriminator="design_standard"),
]


class SeismicGroundInput(ApiModel):
    position: Literal["Ground"] = Field(description="Tiang berdiri di tanah.")
    k_value: PositiveFloat = Field(description="Koefisien seismik K (> 0), misalnya 0.5.")


class SeismicRooftopInput(ApiModel):
    position: Literal["Rooftop"] = Field(description="Tiang berdiri di atap bangunan.")
    seismic_class: Literal["A", "B", "S"] = Field(
        description="Kelas seismik rooftop; nilai K diambil otomatis: A = 1.5, B = 1.0, S = 2.0."
    )


SeismicInput = Annotated[
    SeismicGroundInput | SeismicRooftopInput,
    Field(discriminator="position"),
]
