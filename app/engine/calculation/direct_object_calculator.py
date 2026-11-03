"""Load calculation and aggregation for Direct Objects.

Ported from python_calc ``calculation/direct_object_calculator.py`` (commit 270d23b).
"""

from collections.abc import Iterable
from math import cos, fsum, pi, sin

from app.engine.domain.conditions import SeismicCondition, WindCondition
from app.engine.domain.direct_object import DirectObject
from .rounding import CalculationValueType, rounding_profile_for
from .seismic import SeismicPolicy, seismic_policy_for
from .gravity import gravity_for_standard

from .result import (
    DirectObjectAggregationResult,
    DirectObjectCalculationResult,
    DirectObjectDirectionalResult,
    DirectObjectDirectionalTotal,
)


class DirectObjectCalculator:
    """Calculate Direct Objects at one EvaluatedPosition."""

    def __init__(
        self,
        direct_objects: Iterable[DirectObject],
        wind_condition: WindCondition,
        seismic_condition: SeismicCondition,
        seismic_policy: SeismicPolicy | None = None,
        enable_optional_seismic: bool = False,
    ) -> None:
        self.direct_objects = tuple(direct_objects)
        if any(
            not isinstance(direct_object, DirectObject)
            for direct_object in self.direct_objects
        ):
            raise TypeError(
                "DirectObjectCalculator accepts only DirectObject instances"
            )
        self.wind_condition = wind_condition
        self.seismic_condition = seismic_condition
        self.rounding = rounding_profile_for(wind_condition.design_standard)
        self.gravity_m_s2 = gravity_for_standard(
            wind_condition.design_standard
        )
        self.seismic_policy = seismic_policy or seismic_policy_for(
            wind_condition.design_standard,
            k_value=seismic_condition.k_value,
            enable_optional_seismic=enable_optional_seismic,
        )

    def active_objects(
        self,
        evaluated_position_m: float,
    ) -> tuple[DirectObject, ...]:
        """Return objects at or above the EvaluatedPosition, per VBA."""
        return tuple(
            direct_object
            for direct_object in self.direct_objects
            if direct_object.elevation_m >= evaluated_position_m
        )

    def calculate_one(
        self,
        direct_object: DirectObject,
        evaluated_position_m: float,
    ) -> DirectObjectCalculationResult:
        if direct_object.elevation_m < evaluated_position_m:
            raise ValueError(
                f"Direct Object {direct_object.name!r} is below "
                "the EvaluatedPosition"
            )

        load_center_height = self.rounding.apply(
            direct_object.load_center_height_m(evaluated_position_m),
            CalculationValueType.LOAD_CENTER_HEIGHT,
        )
        kz = self.wind_condition.kz_at(direct_object.elevation_m)
        cf = direct_object.wind_coefficient(
            design_standard=self.wind_condition.design_standard,
            kz=kz,
        )
        wind_pressure = self.rounding.apply(
            self.wind_condition.wind_pressure_at(direct_object.elevation_m),
            CalculationValueType.WIND_PRESSURE,
        )
        fix_load = self.rounding.apply(
            direct_object.fix_load_n(self.gravity_m_s2),
            CalculationValueType.LOAD,
        )
        total_mass = direct_object.total_mass_kg()
        seismic_load = self.rounding.apply(
            self.seismic_policy.calculate_load_n(
                fix_load_n=fix_load,
                mass_kg=total_mass,
            ),
            CalculationValueType.LOAD,
        )
        seismic_moment = self.rounding.apply(
            direct_object.calculate_moment(seismic_load, load_center_height),
            CalculationValueType.MOMENT,
        )
        directional_results = tuple(
            self._directional_result(
                direct_object=direct_object,
                direction=direction.name,
                wind_angle_rad=direction.angle_rad,
                cf=cf,
                wind_pressure_n_m2=wind_pressure,
                load_center_height_m=load_center_height,
            )
            for direction in self.wind_condition.directions
        )

        return DirectObjectCalculationResult(
            object_name=direct_object.name,
            object_type=direct_object.object_type.value,
            evaluated_position_m=float(evaluated_position_m),
            elevation_m=direct_object.elevation_m,
            load_center_height_m=load_center_height,
            quantity=direct_object.quantity,
            mass_per_unit_kg=direct_object.mass_per_unit_kg,
            total_mass_kg=total_mass,
            nnc=direct_object.base_wind_coefficient,
            kz=kz,
            cf=cf,
            wind_pressure_n_m2=wind_pressure,
            fix_load_n=fix_load,
            seismic_load_n=seismic_load,
            seismic_moment_nm=seismic_moment,
            directional_results=directional_results,
        )

    def calculate_at(
        self,
        evaluated_position_m: float,
    ) -> tuple[DirectObjectCalculationResult, ...]:
        return tuple(
            self.calculate_one(direct_object, evaluated_position_m)
            for direct_object in self.active_objects(evaluated_position_m)
        )

    def aggregate_at(
        self,
        evaluated_position_m: float,
    ) -> DirectObjectAggregationResult:
        results = self.calculate_at(evaluated_position_m)
        directional_totals = tuple(
            self._aggregate_direction(
                results,
                direction.name,
                direction.angle_rad,
            )
            for direction in self.wind_condition.directions
        )
        return DirectObjectAggregationResult(
            evaluated_position_m=float(evaluated_position_m),
            direct_object_results=results,
            active_object_count=len(results),
            total_fix_load_n=self.rounding.apply(
                fsum(result.fix_load_n for result in results),
                CalculationValueType.LOAD,
            ),
            total_seismic_load_n=self.rounding.apply(
                fsum(result.seismic_load_n for result in results),
                CalculationValueType.LOAD,
            ),
            total_seismic_moment_nm=self.rounding.apply(
                fsum(result.seismic_moment_nm for result in results),
                CalculationValueType.MOMENT,
            ),
            directional_totals=directional_totals,
        )

    def _directional_result(
        self,
        direct_object: DirectObject,
        direction: str,
        wind_angle_rad: float,
        cf: float,
        wind_pressure_n_m2: float,
        load_center_height_m: float,
    ) -> DirectObjectDirectionalResult:
        angle_of_attack = direct_object.angle_of_attack_rad(wind_angle_rad)
        sine, cosine = direct_object.direction_factors(wind_angle_rad)
        projected_area = self.rounding.apply(
            direct_object.projected_area(wind_angle_rad),
            CalculationValueType.PROJECTED_AREA,
        )
        wind_load = self.rounding.apply(
            direct_object.calculate_wind_load(
                projected_area,
                cf,
                wind_pressure_n_m2,
            ),
            CalculationValueType.LOAD,
        )
        wind_x = self.rounding.apply(
            wind_load * round(cos(wind_angle_rad + pi), 3),
            CalculationValueType.LOAD,
        )
        wind_y = self.rounding.apply(
            wind_load * round(sin(wind_angle_rad), 3),
            CalculationValueType.LOAD,
        )
        return DirectObjectDirectionalResult(
            direction=direction,
            angle_rad=wind_angle_rad,
            angle_of_attack_rad=angle_of_attack,
            sin_angle_of_attack=sine,
            cos_angle_of_attack=cosine,
            projected_area_m2=projected_area,
            wind_load_n=wind_load,
            wind_load_x_n=wind_x,
            wind_load_y_n=wind_y,
            wind_moment_nm=self.rounding.apply(
                wind_load * load_center_height_m,
                CalculationValueType.MOMENT,
            ),
            wind_moment_x_nm=self.rounding.apply(
                wind_y * load_center_height_m,
                CalculationValueType.MOMENT,
            ),
            wind_moment_y_nm=self.rounding.apply(
                wind_x * load_center_height_m,
                CalculationValueType.MOMENT,
            ),
        )

    def _aggregate_direction(
        self,
        results: tuple[DirectObjectCalculationResult, ...],
        direction: str,
        angle_rad: float,
    ) -> DirectObjectDirectionalTotal:
        direction_results = tuple(
            directional
            for result in results
            for directional in result.directional_results
            if directional.direction == direction
        )
        return DirectObjectDirectionalTotal(
            direction=direction,
            angle_rad=angle_rad,
            total_wind_load_n=self.rounding.apply(
                fsum(result.wind_load_n for result in direction_results),
                CalculationValueType.LOAD,
            ),
            total_wind_load_x_n=self.rounding.apply(
                fsum(result.wind_load_x_n for result in direction_results),
                CalculationValueType.LOAD,
            ),
            total_wind_load_y_n=self.rounding.apply(
                fsum(result.wind_load_y_n for result in direction_results),
                CalculationValueType.LOAD,
            ),
            total_wind_moment_nm=self.rounding.apply(
                fsum(result.wind_moment_nm for result in direction_results),
                CalculationValueType.MOMENT,
            ),
            total_wind_moment_x_nm=self.rounding.apply(
                fsum(result.wind_moment_x_nm for result in direction_results),
                CalculationValueType.MOMENT,
            ),
            total_wind_moment_y_nm=self.rounding.apply(
                fsum(result.wind_moment_y_nm for result in direction_results),
                CalculationValueType.MOMENT,
            ),
        )
