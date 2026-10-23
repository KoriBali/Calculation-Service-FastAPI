"""Wind condition for design standards 1-6.

Ported from python_calc ``domain/conditions.py`` (commit 41cca03). Formulas,
constants, and rounding are unchanged.

ADDITION: ``WindCondition.design_wind_speed_m_s`` exposes the speed each
standard uses. It is not in python_calc and no formula reads it.
"""

from app.engine.conditions.directions import WIND_DIRECTIONS, WindDirection


def std_act_common(adc: int, hstr: float) -> dict[str, float | str]:
    """Return atmospheric parameters used by design standards 1 and 6."""
    atmospheric_parameters = {
        1: (5.0, 250.0, 0.1, "I"),
        2: (5.0, 350.0, 0.15, "II"),
        3: (5.0, 450.0, 0.2, "III"),
        4: (10.0, 550.0, 0.27, "IV"),
    }
    try:
        zb, zg, alpha, adc_symbol = atmospheric_parameters[int(adc)]
        adc = int(adc)
    except (KeyError, TypeError, ValueError):
        raise ValueError("ADC is not recognized") from None

    hstr = float(hstr)
    if hstr <= 0:
        raise ValueError("Structure height must be greater than zero")

    if adc == 1:
        gf = 2.0 if hstr <= 10 else (
            (-0.2 / 30) * (hstr - 10) + 2.0 if hstr < 40 else 1.8
        )
    elif adc == 2:
        gf = 2.2 if hstr <= 10 else (
            (-0.2 / 30) * (hstr - 10) + 2.2 if hstr < 40 else 2.0
        )
    elif adc == 3:
        gf = 2.5 if hstr <= 10 else (
            (-0.4 / 30) * (hstr - 10) + 2.5 if hstr < 40 else 2.1
        )
    else:
        gf = 3.1 if hstr <= 10 else (
            (-0.8 / 30) * (hstr - 10) + 3.1 if hstr < 40 else 2.3
        )

    gf = round(gf, 3)
    er_reference_height = zb if hstr <= zb else hstr
    er = round(1.7 * (er_reference_height / zg) ** alpha, 3)
    air_density_factor = round(er**2 * gf, 3)

    return {
        "Hstr": hstr,
        "zb": zb,
        "zg": zg,
        "alpha": alpha,
        "Gf": gf,
        "Er": er,
        "Ds_air": air_density_factor,
        "ADC_symbol": adc_symbol,
    }


def calc_kz(
    z_height: float,
    hstr: float,
    zb: float,
    alpha: float,
) -> float:
    """Return the height correction factor Kz using metre-based heights."""
    try:
        z_height = float(z_height)
        hstr = float(hstr)
        zb = float(zb)
        alpha = float(alpha)
    except (TypeError, ValueError):
        raise ValueError("Kz parameters must be numbers") from None

    if z_height < 0:
        raise ValueError("Object height (z_height) cannot be negative")
    if hstr <= 0:
        raise ValueError("Structure height (hstr) must be greater than zero")
    if zb <= 0:
        raise ValueError("zb must be greater than zero")
    if alpha < 0:
        raise ValueError("alpha cannot be negative")

    if hstr <= zb:
        kz = 1.0
    elif z_height <= zb:
        kz = (zb / hstr) ** (2 * alpha)
    else:
        kz = (z_height / hstr) ** (2 * alpha)
    return round(kz, 3)


class WindCondition:
    """Wind condition implementing the confirmed rules for standards 1-6."""

    # ADDITION (not in python_calc): the speeds hardcoded in wind_pressure_at()
    # for standards 2-5. tests/engine/test_report_additions.py keeps them equal.
    FIXED_WIND_SPEED_M_S = {2: 60.0, 3: 60.0, 4: 40.0, 5: 50.0}

    def __init__(
        self,
        design_standard: int,
        structure_height_m: float,
        atmospheric_category: int | None = None,
        basic_wind_speed_m_s: float | None = None,
    ) -> None:
        self.design_standard = int(design_standard)
        self.structure_height_m = float(structure_height_m)
        self.atmospheric_category = atmospheric_category
        self.basic_wind_speed_m_s = basic_wind_speed_m_s
        self._validate()

        self._common = None
        if self.design_standard in (1, 6):
            self._common = std_act_common(
                adc=self.atmospheric_category,
                hstr=self.structure_height_m,
            )

    def _validate(self) -> None:
        if self.design_standard not in {1, 2, 3, 4, 5, 6}:
            raise ValueError("Wind design standard must be between 1 and 6")
        if self.structure_height_m <= 0:
            raise ValueError("Structure height must be greater than zero")
        if self.design_standard in (1, 6):
            if self.atmospheric_category not in {1, 2, 3, 4}:
                raise ValueError(
                    "Atmospheric category 1-4 is required for standard 1 or 6"
                )
            if (
                self.basic_wind_speed_m_s is None
                or self.basic_wind_speed_m_s <= 0
            ):
                raise ValueError(
                    "Basic wind speed is required for standard 1 or 6"
                )

    @property
    def directions(self) -> tuple[WindDirection, ...]:
        return WIND_DIRECTIONS

    # ADDITION (not in python_calc): report item "design wind speed V".
    @property
    def design_wind_speed_m_s(self) -> float:
        """Speed behind the wind pressure: fixed for 2-5, given for 1 and 6."""
        return self.FIXED_WIND_SPEED_M_S.get(
            self.design_standard,
            self.basic_wind_speed_m_s,
        )

    @property
    def common_parameters(self) -> dict | None:
        return None if self._common is None else dict(self._common)

    def kz_at(self, top_elevation_m: float) -> float:
        """Return Kz at the top elevation of an individual pole segment."""
        if self.design_standard not in (1, 6):
            return 1.0
        return calc_kz(
            z_height=top_elevation_m,
            hstr=self.structure_height_m,
            zb=self._common["zb"],
            alpha=self._common["alpha"],
        )

    def wind_pressure_at(self, top_elevation_m: float) -> float:
        """Return pole wind pressure in N/m2 according to the VBA rules."""
        standard = self.design_standard
        if standard == 1:
            return round(
                0.6 * self._common["Ds_air"] * self.basic_wind_speed_m_s**2,
                3,
            )
        if standard in (2, 3):
            return round(0.5 * 1.23 * 60**2, 4)
        if standard == 4:
            return round(0.5 * 1.23 * 40**2, 3)
        if standard == 5:
            return round(0.5 * 1.23 * 50**2, 3)

        kz = self.kz_at(top_elevation_m)
        base_pressure = round(
            0.6 * self._common["Ds_air"] * self.basic_wind_speed_m_s**2,
            3,
        )
        pressure_with_kz = base_pressure * 1.42 * kz
        return round(pressure_with_kz, 3) if pressure_with_kz > 2350 else 2350.0
