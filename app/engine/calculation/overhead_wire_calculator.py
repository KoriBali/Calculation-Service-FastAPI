"""Load and tension calculation for overhead wires.

Ported from python_calc ``calculation/overhead_wire_calculator.py`` (commit 270d23b).
"""

from collections.abc import Iterable
from math import cos, fsum, pi, sin

from app.engine.domain.conditions import SeismicCondition, WindCondition
from app.engine.domain.overhead_wire import OverheadWire
from .rounding import CalculationValueType, rounding_profile_for
from .seismic import SeismicPolicy, seismic_policy_for
from .gravity import gravity_for_standard

from .result import (
    OverheadWireAggregationResult,
    OverheadWireCalculationResult,
    OverheadWireDirectionalResult,
    OverheadWireDirectionalTotal,
)


class OverheadWireCalculator:
    """Calculate OHW loads at one EvaluatedPosition."""

    def __init__(
        self,
        wires: Iterable[OverheadWire],
        wind_condition: WindCondition,
        seismic_condition: SeismicCondition,
        seismic_policy: SeismicPolicy | None = None,
        enable_optional_seismic: bool = False,
        calculate_seismic_tension: bool = True,
    ) -> None:
        self.wires = tuple(wires)
        if any(not isinstance(wire, OverheadWire) for wire in self.wires):
            raise TypeError(
                "OverheadWireCalculator accepts only OverheadWire instances"
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
        self.calculate_seismic_tension = bool(calculate_seismic_tension)

    def active_wires(
        self,
        evaluated_position_m: float,
    ) -> tuple[OverheadWire, ...]:
        return tuple(
            wire
            for wire in self.wires
            if wire.elevation_m >= evaluated_position_m
        )

    def calculate_one(
        self,
        wire: OverheadWire,
        evaluated_position_m: float,
    ) -> OverheadWireCalculationResult:
        if wire.elevation_m < evaluated_position_m:
            raise ValueError(
                f"OHW {wire.name!r} is below the EvaluatedPosition"
            )

        load_center_height = self.rounding.apply(
            wire.load_center_height_m(evaluated_position_m),
            CalculationValueType.LOAD_CENTER_HEIGHT,
        )
        kz = self.wind_condition.kz_at(wire.elevation_m)
        cf = wire.wind_coefficient(
            self.wind_condition.design_standard,
            kz,
        )
        wind_pressure = self.rounding.apply(
            self.wind_condition.wind_pressure_at(wire.elevation_m),
            CalculationValueType.WIND_PRESSURE,
        )
        fix_load_per_length = self.rounding.apply(
            wire.fix_load_per_length_n_m(self.gravity_m_s2),
            CalculationValueType.WEIGHT_PER_METER,
        )
        fix_load = self.rounding.apply(
            wire.fix_load_n(self.gravity_m_s2),
            CalculationValueType.LOAD,
        )
        total_mass = wire.total_mass_kg()
        seismic_load = self.rounding.apply(
            self.seismic_policy.calculate_load_n(
                fix_load_n=fix_load,
                mass_kg=total_mass,
            ),
            CalculationValueType.LOAD,
        )
        seismic_moment = self.rounding.apply(
            wire.calculate_moment(seismic_load, load_center_height),
            CalculationValueType.MOMENT,
        )
        seismic_tension = 0.0
        if self.seismic_policy.enabled and self.calculate_seismic_tension:
            seismic_tension = self.rounding.apply(
                wire.tension_from_line_load(
                    fix_load_per_length / wire.vertical_angle_cosine
                ),
                CalculationValueType.LOAD,
            )
        projected_area = self.rounding.apply(
            wire.projected_area(),
            CalculationValueType.PROJECTED_AREA,
        )
        directional_results = tuple(
            self._directional_result(
                wire,
                direction.name,
                direction.angle_rad,
                cf,
                wind_pressure,
                load_center_height,
                seismic_tension,
            )
            for direction in self.wind_condition.directions
        )

        return OverheadWireCalculationResult(
            wire_name=wire.name,
            evaluated_position_m=float(evaluated_position_m),
            elevation_m=wire.elevation_m,
            load_center_height_m=load_center_height,
            tributary_wire_length_m=wire.tributary_wire_length_m(),
            total_mass_kg=total_mass,
            nnc=wire.base_wind_coefficient,
            kz=kz,
            cf=cf,
            wind_pressure_n_m2=wind_pressure,
            projected_area_m2=projected_area,
            fix_load_per_length_n_m=fix_load_per_length,
            fix_load_n=fix_load,
            seismic_load_n=seismic_load,
            seismic_moment_nm=seismic_moment,
            seismic_tension_n=seismic_tension,
            directional_results=directional_results,
        )

    def calculate_at(
        self,
        evaluated_position_m: float,
    ) -> tuple[OverheadWireCalculationResult, ...]:
        return tuple(
            self.calculate_one(wire, evaluated_position_m)
            for wire in self.active_wires(evaluated_position_m)
        )

    def aggregate_at(
        self,
        evaluated_position_m: float,
    ) -> OverheadWireAggregationResult:
        results = self.calculate_at(evaluated_position_m)
        return OverheadWireAggregationResult(
            evaluated_position_m=float(evaluated_position_m),
            wire_results=results,
            active_wire_count=len(results),
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
            total_seismic_tension_n=self.rounding.apply(
                fsum(result.seismic_tension_n for result in results),
                CalculationValueType.LOAD,
            ),
            directional_totals=tuple(
                self._aggregate_direction(
                    results,
                    direction.name,
                    direction.angle_rad,
                )
                for direction in self.wind_condition.directions
            ),
        )

    def _directional_result(
        self,
        wire: OverheadWire,
        direction: str,
        wind_angle_rad: float,
        cf: float,
        wind_pressure_n_m2: float,
        load_center_height_m: float,
        seismic_tension_n: float,
    ) -> OverheadWireDirectionalResult:
        angle_of_attack = wire.angle_of_attack_rad(wind_angle_rad)
        sine, cosine = wire.direction_factors(wind_angle_rad)
        directional_area = self.rounding.apply(
            wire.projected_area(wind_angle_rad),
            CalculationValueType.PROJECTED_AREA,
        )
        wind_load = self.rounding.apply(
            wire.calculate_wind_load(
                directional_area,
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
        combined_line_load = self.rounding.apply(
            wire.combined_wind_line_load_n_m(
                wind_pressure_n_m2,
                cf,
                wind_angle_rad,
            ),
            CalculationValueType.WIRE_LOAD_COMBINATION,
        )
        wind_tension = self.rounding.apply(
            wire.tension_from_line_load(combined_line_load),
            CalculationValueType.LOAD,
        )
        raw_tension_x, raw_tension_y = wire.wind_tension_components_n(
            wind_tension
        )
        tension_x = self.rounding.apply(
            raw_tension_x,
            CalculationValueType.LOAD,
        )
        tension_y = self.rounding.apply(
            raw_tension_y,
            CalculationValueType.LOAD,
        )

        return OverheadWireDirectionalResult(
            direction=direction,
            angle_rad=wind_angle_rad,
            angle_of_attack_rad=angle_of_attack,
            sin_angle_of_attack=sine,
            cos_angle_of_attack=cosine,
            directional_projected_area_m2=directional_area,
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
            combined_wind_line_load_n_m=combined_line_load,
            wind_tension_n=wind_tension,
            wind_tension_x_n=tension_x,
            wind_tension_y_n=tension_y,
            wind_tension_moment_nm=self.rounding.apply(
                wind_tension * load_center_height_m * cosine,
                CalculationValueType.MOMENT,
            ),
            wind_tension_moment_x_nm=self.rounding.apply(
                tension_y * load_center_height_m,
                CalculationValueType.MOMENT,
            ),
            wind_tension_moment_y_nm=self.rounding.apply(
                tension_x * load_center_height_m,
                CalculationValueType.MOMENT,
            ),
            seismic_tension_moment_nm=self.rounding.apply(
                seismic_tension_n * load_center_height_m * cosine,
                CalculationValueType.MOMENT,
            ),
        )

    def _aggregate_direction(
        self,
        results: tuple[OverheadWireCalculationResult, ...],
        direction: str,
        angle_rad: float,
    ) -> OverheadWireDirectionalTotal:
        items = tuple(
            directional
            for result in results
            for directional in result.directional_results
            if directional.direction == direction
        )
        return OverheadWireDirectionalTotal(
            direction=direction,
            angle_rad=angle_rad,
            total_wind_load_n=self.rounding.apply(
                fsum(item.wind_load_n for item in items),
                CalculationValueType.LOAD,
            ),
            total_wind_load_x_n=self.rounding.apply(
                fsum(item.wind_load_x_n for item in items),
                CalculationValueType.LOAD,
            ),
            total_wind_load_y_n=self.rounding.apply(
                fsum(item.wind_load_y_n for item in items),
                CalculationValueType.LOAD,
            ),
            total_wind_moment_nm=self.rounding.apply(
                fsum(item.wind_moment_nm for item in items),
                CalculationValueType.MOMENT,
            ),
            total_wind_moment_x_nm=self.rounding.apply(
                fsum(item.wind_moment_x_nm for item in items),
                CalculationValueType.MOMENT,
            ),
            total_wind_moment_y_nm=self.rounding.apply(
                fsum(item.wind_moment_y_nm for item in items),
                CalculationValueType.MOMENT,
            ),
            total_wind_tension_n=self.rounding.apply(
                fsum(item.wind_tension_n for item in items),
                CalculationValueType.LOAD,
            ),
            total_wind_tension_x_n=self.rounding.apply(
                fsum(item.wind_tension_x_n for item in items),
                CalculationValueType.LOAD,
            ),
            total_wind_tension_y_n=self.rounding.apply(
                fsum(item.wind_tension_y_n for item in items),
                CalculationValueType.LOAD,
            ),
            total_wind_tension_moment_nm=self.rounding.apply(
                fsum(item.wind_tension_moment_nm for item in items),
                CalculationValueType.MOMENT,
            ),
            total_wind_tension_moment_x_nm=self.rounding.apply(
                fsum(item.wind_tension_moment_x_nm for item in items),
                CalculationValueType.MOMENT,
            ),
            total_wind_tension_moment_y_nm=self.rounding.apply(
                fsum(item.wind_tension_moment_y_nm for item in items),
                CalculationValueType.MOMENT,
            ),
            total_seismic_tension_moment_nm=self.rounding.apply(
                fsum(item.seismic_tension_moment_nm for item in items),
                CalculationValueType.MOMENT,
            ),
        )
