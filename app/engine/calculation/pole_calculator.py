"""Complete load calculation for assembled pole segments.

Ported from python_calc ``calculation/pole_calculator.py`` (commit 270d23b).
"""

from dataclasses import replace
from math import cos, pi, sin
from math import fsum
from decimal import Decimal, ROUND_HALF_UP

from .pole_assembly import PoleAssembly
from .result import (
    PoleAggregationResult,
    PoleCalculationResult,
    PoleDirectionalResult,
    PoleDirectionalTotal,
)
from app.engine.domain.conditions import SeismicCondition, WindCondition
from app.engine.domain.loads import OverdesignFactor
from app.engine.domain.pole import PoleObject
from .rounding import CalculationValueType, rounding_profile_for
from .seismic import SeismicPolicy, seismic_policy_for
from .gravity import gravity_for_standard
from app.engine.domain.standards import DesignStandardCode


class PoleCalculator:
    """Calculate pole loads at one EvaluatedPosition."""

    def __init__(
        self,
        assembly: PoleAssembly,
        wind_condition: WindCondition,
        seismic_condition: SeismicCondition,
        overdesign_factor: OverdesignFactor | None = None,
        seismic_policy: SeismicPolicy | None = None,
        enable_optional_seismic: bool = False,
    ) -> None:
        self.assembly = assembly
        self.wind_condition = wind_condition
        self.seismic_condition = seismic_condition
        self.overdesign_factor = overdesign_factor or OverdesignFactor()
        self.rounding = rounding_profile_for(wind_condition.design_standard)
        self.gravity_m_s2 = gravity_for_standard(
            wind_condition.design_standard
        )
        self.seismic_policy = seismic_policy or seismic_policy_for(
            wind_condition.design_standard,
            k_value=seismic_condition.k_value,
            enable_optional_seismic=enable_optional_seismic,
        )

    def calculate_one(
        self,
        pole: PoleObject,
        evaluated_position_m: float,
    ) -> PoleCalculationResult:
        geometry = self.assembly.active_geometry(pole, evaluated_position_m)
        if geometry.active_length_m <= 0:
            raise ValueError(
                f"Pole {pole.name!r} is not active above the evaluated position"
            )

        diameter_bottom = self.rounding.apply(
            geometry.diameter_at_active_bottom_mm,
            CalculationValueType.CALCULATED_POLE_DIAMETER,
        )
        diameter_top = self.rounding.apply(
            geometry.diameter_at_active_top_mm,
            CalculationValueType.CALCULATED_POLE_DIAMETER,
        )
        geometry = replace(
            geometry,
            diameter_at_active_bottom_mm=diameter_bottom,
            diameter_at_active_top_mm=diameter_top,
            local_load_center_m=self.rounding.apply(
                geometry.local_load_center_m,
                CalculationValueType.LOAD_CENTER_HEIGHT,
            ),
            load_center_height_m=self.rounding.apply(
                geometry.load_center_height_m,
                CalculationValueType.LOAD_CENTER_HEIGHT,
            ),
        )
        nnc = pole.base_wind_coefficient(
            geometry.active_length_m,
            diameter_bottom,
            self.wind_condition.design_standard,
        )
        kz = self.wind_condition.kz_at(pole.top_elevation_m)
        cf = pole.wind_coefficient(
            geometry.active_length_m,
            diameter_bottom,
            self.wind_condition.design_standard,
            kz,
        )
        wind_pressure = self.rounding.apply(
            self.wind_condition.wind_pressure_at(pole.top_elevation_m),
            CalculationValueType.WIND_PRESSURE,
        )
        projected_area = self.rounding.apply(
            pole.projected_area(
                geometry.active_length_m,
                diameter_bottom,
                diameter_top,
            ),
            CalculationValueType.PROJECTED_AREA,
        )
        mass, fix_load = self._mass_and_fix_load(
            pole,
            geometry.active_length_m,
            diameter_bottom,
            diameter_top,
        )
        wind_load = self.rounding.apply(
            pole.calculate_wind_load(projected_area, cf, wind_pressure),
            CalculationValueType.LOAD,
        )
        seismic_load = self.rounding.apply(
            self.seismic_policy.calculate_load_n(
                fix_load_n=fix_load,
                mass_kg=mass * self.overdesign_factor.value,
            ),
            CalculationValueType.LOAD,
        )
        wind_moment = self.rounding.apply(
            pole.calculate_moment(wind_load, geometry.load_center_height_m),
            CalculationValueType.MOMENT,
        )
        seismic_moment = self.rounding.apply(
            pole.calculate_moment(seismic_load, geometry.load_center_height_m),
            CalculationValueType.MOMENT,
        )
        directional_results = tuple(
            self._directional_result(
                wind_load,
                geometry.load_center_height_m,
                direction.name,
                direction.angle_rad,
            )
            for direction in self.wind_condition.directions
        )

        section_properties = pole.section_properties(diameter_bottom)
        section_properties = replace(
            section_properties,
            cross_section_area_cm2=self.rounding.apply(
                section_properties.cross_section_area_cm2,
                CalculationValueType.CROSS_SECTION_AREA,
            ),
            section_modulus_cm3=self.rounding.apply(
                section_properties.section_modulus_cm3,
                CalculationValueType.SECTION_MODULUS,
            ),
            moment_of_inertia_cm4=self.rounding.apply(
                section_properties.moment_of_inertia_cm4,
                CalculationValueType.MOMENT_OF_INERTIA,
            ),
            second_moment_pair_cm4=self.rounding.apply(
                section_properties.second_moment_pair_cm4,
                CalculationValueType.MOMENT_OF_INERTIA,
            ),
            radius_of_gyration_cm=self.rounding.apply(
                section_properties.radius_of_gyration_cm,
                CalculationValueType.RADIUS_OF_GYRATION,
            ),
        )

        return PoleCalculationResult(
            geometry=geometry,
            section_properties=section_properties,
            nnc=nnc,
            kz=kz,
            cf=cf,
            wind_pressure_n_m2=wind_pressure,
            projected_area_m2=projected_area,
            mass_kg=mass,
            overdesign_factor=self.overdesign_factor.value,
            fix_load_n=fix_load,
            wind_load_n=wind_load,
            seismic_load_n=seismic_load,
            wind_moment_nm=wind_moment,
            seismic_moment_nm=seismic_moment,
            directional_results=directional_results,
        )

    def _mass_and_fix_load(
        self,
        pole: PoleObject,
        active_length_m: float,
        diameter_bottom_mm: float,
        diameter_top_mm: float,
    ) -> tuple[float, float]:
        """Apply the confirmed standard-specific pole self-weight sequence."""
        standard = DesignStandardCode(self.wind_condition.design_standard)

        if standard is DesignStandardCode.NEW_JIL:
            # VBA Pole_each: mass = Fkb_SF(fL_*, 3), then
            # fld = Fkb_SF(mass * 9.81, 3).
            mass = self.rounding.apply(
                pole.mass_kg(
                    active_length_m,
                    diameter_bottom_mm,
                    diameter_top_mm,
                ),
                CalculationValueType.WEIGHT_PER_METER,
            )
            fix_load = self.rounding.apply(
                mass * self.gravity_m_s2 * self.overdesign_factor.value,
                CalculationValueType.LOAD,
            )
            return mass, fix_load

        if pole.is_tapered:
            # Decimal standards: taper mass [kg] is rounded first to 1 decimal.
            mass = float(
                Decimal(
                    str(
                        pole.raw_mass_kg(
                            active_length_m,
                            diameter_bottom_mm,
                            diameter_top_mm,
                        )
                    )
                ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            )
            fix_load = self.rounding.apply(
                mass * self.gravity_m_s2 * self.overdesign_factor.value,
                CalculationValueType.LOAD,
            )
            return mass, fix_load

        # Decimal standards, straight pole: weight per metre [N/m] is rounded
        # to 2 decimals before multiplication by length and overdesign factor.
        mass_per_meter = pole.raw_mass_per_meter_kg(
            diameter_bottom_mm,
            diameter_top_mm,
        )
        fix_load_per_meter = self.rounding.apply(
            mass_per_meter * self.gravity_m_s2,
            CalculationValueType.WEIGHT_PER_METER,
        )
        fix_load = self.rounding.apply(
            fix_load_per_meter
            * active_length_m
            * self.overdesign_factor.value,
            CalculationValueType.LOAD,
        )
        return mass_per_meter * active_length_m, fix_load

    def calculate_at(
        self,
        evaluated_position_m: float,
    ) -> tuple[PoleCalculationResult, ...]:
        """Calculate all active pole segments, ordered bottom-up."""
        return tuple(
            self.calculate_one(pole, evaluated_position_m)
            for pole in self.assembly.active_poles(evaluated_position_m)
        )

    def aggregate_at(
        self,
        evaluated_position_m: float,
    ) -> PoleAggregationResult:
        """Aggregate all active pole results at one EvaluatedPosition."""
        pole_results = self.calculate_at(evaluated_position_m)
        directional_totals = tuple(
            self._aggregate_direction(
                pole_results=pole_results,
                direction=direction.name,
                angle_rad=direction.angle_rad,
            )
            for direction in self.wind_condition.directions
        )

        return PoleAggregationResult(
            evaluated_position_m=float(evaluated_position_m),
            pole_results=pole_results,
            total_fix_load_n=self.rounding.apply(
                fsum(result.fix_load_n for result in pole_results),
                CalculationValueType.LOAD,
            ),
            total_seismic_load_n=self.rounding.apply(
                fsum(result.seismic_load_n for result in pole_results),
                CalculationValueType.LOAD,
            ),
            total_seismic_moment_nm=self.rounding.apply(
                fsum(result.seismic_moment_nm for result in pole_results),
                CalculationValueType.MOMENT,
            ),
            directional_totals=directional_totals,
        )

    def _aggregate_direction(
        self,
        pole_results: tuple[PoleCalculationResult, ...],
        direction: str,
        angle_rad: float,
    ) -> PoleDirectionalTotal:
        matching_results = tuple(
            directional
            for pole_result in pole_results
            for directional in pole_result.directional_results
            if directional.direction == direction
        )
        return PoleDirectionalTotal(
            direction=direction,
            angle_rad=angle_rad,
            total_wind_load_n=self.rounding.apply(
                fsum(result.wind_load_n for result in pole_results),
                CalculationValueType.LOAD,
            ),
            total_wind_load_x_n=self.rounding.apply(
                fsum(result.wind_load_x_n for result in matching_results),
                CalculationValueType.LOAD,
            ),
            total_wind_load_y_n=self.rounding.apply(
                fsum(result.wind_load_y_n for result in matching_results),
                CalculationValueType.LOAD,
            ),
            total_wind_moment_x_nm=self.rounding.apply(
                fsum(result.wind_moment_x_nm for result in matching_results),
                CalculationValueType.MOMENT,
            ),
            total_wind_moment_y_nm=self.rounding.apply(
                fsum(result.wind_moment_y_nm for result in matching_results),
                CalculationValueType.MOMENT,
            ),
        )

    def _directional_result(
        self,
        wind_load_n: float,
        load_center_height_m: float,
        direction: str,
        angle_rad: float,
    ) -> PoleDirectionalResult:
        direction_cosine = round(cos(angle_rad + pi), 3)
        direction_sine = round(sin(angle_rad), 3)
        wind_x = self.rounding.apply(
            wind_load_n * direction_cosine,
            CalculationValueType.LOAD,
        )
        wind_y = self.rounding.apply(
            wind_load_n * direction_sine,
            CalculationValueType.LOAD,
        )
        return PoleDirectionalResult(
            direction=direction,
            angle_rad=angle_rad,
            wind_load_x_n=wind_x,
            wind_load_y_n=wind_y,
            wind_moment_x_nm=self.rounding.apply(
                load_center_height_m * wind_y,
                CalculationValueType.MOMENT,
            ),
            wind_moment_y_nm=self.rounding.apply(
                load_center_height_m * wind_x,
                CalculationValueType.MOMENT,
            ),
        )
