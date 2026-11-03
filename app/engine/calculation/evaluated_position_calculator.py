"""Calculations performed at an EvaluatedPosition.

This is the OOP replacement for the applicable parts of ``Section_each.cls``.
Arm-dependent eccentric FixLoad moments and torsion are deliberately deferred;
they are not represented by artificial zero-valued strength checks here.
"""

from math import fsum, hypot

from .direct_object_calculator import DirectObjectCalculator
from .overhead_wire_calculator import OverheadWireCalculator
from .pole_calculator import PoleCalculator
from .rounding import CalculationValueType, rounding_profile_for
from .result import (
    BendingStrengthResult,
    EvaluatedPositionDirectionalResult,
    EvaluatedPositionResult,
)


class EvaluatedPositionCalculator:
    """Combine Pole, Direct Object, and OHW results at one position.

    The directions supplied by the wind condition are calculated. The legacy
    condition supplies eight directions; standard-object workflows may supply
    a single ``OMNI`` direction.
    """

    def __init__(
        self,
        pole_calculator: PoleCalculator,
        direct_object_calculator: DirectObjectCalculator | None = None,
        overhead_wire_calculator: OverheadWireCalculator | None = None,
    ) -> None:
        if not isinstance(pole_calculator, PoleCalculator):
            raise TypeError("pole_calculator must be a PoleCalculator")
        if (
            direct_object_calculator is not None
            and not isinstance(direct_object_calculator, DirectObjectCalculator)
        ):
            raise TypeError(
                "direct_object_calculator must be a DirectObjectCalculator"
            )
        if (
            overhead_wire_calculator is not None
            and not isinstance(overhead_wire_calculator, OverheadWireCalculator)
        ):
            raise TypeError(
                "overhead_wire_calculator must be an OverheadWireCalculator"
            )

        self.pole_calculator = pole_calculator
        self.direct_object_calculator = direct_object_calculator
        self.overhead_wire_calculator = overhead_wire_calculator
        self.rounding = rounding_profile_for(
            pole_calculator.wind_condition.design_standard
        )

    def calculate_at(self, evaluated_position_m: float) -> EvaluatedPositionResult:
        """Return load totals and bending checks for all eight directions."""
        pole = self.pole_calculator.aggregate_at(evaluated_position_m)
        if not pole.pole_results:
            raise ValueError(
                "EvaluatedPosition must be below the top of at least one Pole"
            )

        direct = (
            self.direct_object_calculator.aggregate_at(evaluated_position_m)
            if self.direct_object_calculator is not None
            else None
        )
        wire = (
            self.overhead_wire_calculator.aggregate_at(evaluated_position_m)
            if self.overhead_wire_calculator is not None
            else None
        )

        evaluated_pole_result = pole.pole_results[0]
        evaluated_pole = self._pole_by_name(
            evaluated_pole_result.geometry.pole_name
        )
        section_properties = evaluated_pole_result.section_properties
        allowable_stress = evaluated_pole.material.short_term_allowable_bending

        total_fix_load = self.rounding.apply(
            fsum((
                pole.total_fix_load_n,
                0.0 if direct is None else direct.total_fix_load_n,
                0.0 if wire is None else wire.total_fix_load_n,
            )),
            CalculationValueType.LOAD,
        )
        total_seismic_load = self.rounding.apply(
            fsum((
                pole.total_seismic_load_n,
                0.0 if direct is None else direct.total_seismic_load_n,
                0.0 if wire is None else wire.total_seismic_load_n,
            )),
            CalculationValueType.LOAD,
        )
        total_seismic_moment = self.rounding.apply(
            fsum((
                pole.total_seismic_moment_nm,
                0.0 if direct is None else direct.total_seismic_moment_nm,
                0.0 if wire is None else wire.total_seismic_moment_nm,
            )),
            CalculationValueType.MOMENT,
        )

        pole_by_direction = {
            item.direction: item for item in pole.directional_totals
        }
        direct_by_direction = (
            {}
            if direct is None
            else {item.direction: item for item in direct.directional_totals}
        )
        wire_by_direction = (
            {}
            if wire is None
            else {item.direction: item for item in wire.directional_totals}
        )

        directional_results = tuple(
            self._directional_result(
                direction=direction.name,
                angle_rad=direction.angle_rad,
                pole=pole_by_direction[direction.name],
                direct=direct_by_direction.get(direction.name),
                wire=wire_by_direction.get(direction.name),
                total_seismic_load_n=total_seismic_load,
                total_seismic_moment_nm=total_seismic_moment,
                total_seismic_tension_n=(
                    0.0 if wire is None else wire.total_seismic_tension_n
                ),
                section_modulus_cm3=section_properties.section_modulus_cm3,
                allowable_stress_n_mm2=allowable_stress,
            )
            for direction in self.pole_calculator.wind_condition.directions
        )

        return EvaluatedPositionResult(
            evaluated_position_m=float(evaluated_position_m),
            evaluated_pole_name=evaluated_pole.name,
            material_name=evaluated_pole.material.name,
            section_properties=section_properties,
            total_fix_load_n=total_fix_load,
            total_seismic_load_n=total_seismic_load,
            total_seismic_moment_nm=total_seismic_moment,
            directional_results=directional_results,
            report_direction=(
                self.pole_calculator.wind_condition.directions[0].name
            ),
        )

    def _pole_by_name(self, pole_name: str):
        return next(
            pole
            for pole in self.pole_calculator.assembly.poles
            if pole.name == pole_name
        )

    def _directional_result(
        self,
        *,
        direction,
        angle_rad,
        pole,
        direct,
        wire,
        total_seismic_load_n,
        total_seismic_moment_nm,
        total_seismic_tension_n,
        section_modulus_cm3,
        allowable_stress_n_mm2,
    ) -> EvaluatedPositionDirectionalResult:
        wind_load = self.rounding.apply(
            fsum((
                pole.total_wind_load_n,
                0.0 if direct is None else direct.total_wind_load_n,
                0.0 if wire is None else wire.total_wind_load_n,
            )),
            CalculationValueType.LOAD,
        )
        wind_x = self.rounding.apply(
            fsum((
                pole.total_wind_load_x_n,
                0.0 if direct is None else direct.total_wind_load_x_n,
                0.0 if wire is None else wire.total_wind_load_x_n,
            )),
            CalculationValueType.LOAD,
        )
        wind_y = self.rounding.apply(
            fsum((
                pole.total_wind_load_y_n,
                0.0 if direct is None else direct.total_wind_load_y_n,
                0.0 if wire is None else wire.total_wind_load_y_n,
            )),
            CalculationValueType.LOAD,
        )
        tension_x = 0.0 if wire is None else wire.total_wind_tension_x_n
        tension_y = 0.0 if wire is None else wire.total_wind_tension_y_n
        resultant_x = self.rounding.apply(
            wind_x + tension_x,
            CalculationValueType.LOAD,
        )
        resultant_y = self.rounding.apply(
            wind_y + tension_y,
            CalculationValueType.LOAD,
        )

        wind_moment_x = self.rounding.apply(
            fsum((
                pole.total_wind_moment_x_nm,
                0.0 if direct is None else direct.total_wind_moment_x_nm,
                0.0 if wire is None else wire.total_wind_moment_x_nm,
            )),
            CalculationValueType.MOMENT,
        )
        wind_moment_y = self.rounding.apply(
            fsum((
                pole.total_wind_moment_y_nm,
                0.0 if direct is None else direct.total_wind_moment_y_nm,
                0.0 if wire is None else wire.total_wind_moment_y_nm,
            )),
            CalculationValueType.MOMENT,
        )
        tension_moment_x = (
            0.0 if wire is None else wire.total_wind_tension_moment_x_nm
        )
        tension_moment_y = (
            0.0 if wire is None else wire.total_wind_tension_moment_y_nm
        )
        combined_moment_x = self.rounding.apply(
            wind_moment_x + tension_moment_x,
            CalculationValueType.MOMENT,
        )
        combined_moment_y = self.rounding.apply(
            wind_moment_y + tension_moment_y,
            CalculationValueType.MOMENT,
        )
        combined_wind_moment = self.rounding.apply(
            hypot(combined_moment_x, combined_moment_y),
            CalculationValueType.MOMENT,
        )

        seismic_tension_moment = (
            0.0 if wire is None else abs(wire.total_seismic_tension_moment_nm)
        )
        seismic_tension_load = abs(total_seismic_tension_n)
        combined_seismic_moment = self.rounding.apply(
            total_seismic_moment_nm + seismic_tension_moment,
            CalculationValueType.MOMENT,
        )

        return EvaluatedPositionDirectionalResult(
            direction=direction,
            angle_rad=angle_rad,
            total_wind_load_n=wind_load,
            total_wind_load_x_n=wind_x,
            total_wind_load_y_n=wind_y,
            total_wind_tension_n=0.0 if wire is None else wire.total_wind_tension_n,
            resultant_wind_load_x_n=resultant_x,
            resultant_wind_load_y_n=resultant_y,
            resultant_wind_load_n=self.rounding.apply(
                hypot(resultant_x, resultant_y),
                CalculationValueType.LOAD,
            ),
            total_wind_moment_x_nm=wind_moment_x,
            total_wind_moment_y_nm=wind_moment_y,
            total_wind_tension_moment_x_nm=tension_moment_x,
            total_wind_tension_moment_y_nm=tension_moment_y,
            combined_wind_moment_x_nm=combined_moment_x,
            combined_wind_moment_y_nm=combined_moment_y,
            combined_wind_moment_nm=combined_wind_moment,
            wind_strength=self._strength_result(
                combined_wind_moment,
                section_modulus_cm3,
                allowable_stress_n_mm2,
            ),
            resultant_seismic_load_n=self.rounding.apply(
                total_seismic_load_n + seismic_tension_load,
                CalculationValueType.LOAD,
            ),
            combined_seismic_moment_nm=combined_seismic_moment,
            seismic_strength=self._strength_result(
                combined_seismic_moment,
                section_modulus_cm3,
                allowable_stress_n_mm2,
            ),
        )

    def _strength_result(
        self,
        bending_moment_nm: float,
        section_modulus_cm3: float,
        allowable_stress_n_mm2: float,
    ) -> BendingStrengthResult:
        if section_modulus_cm3 <= 0:
            raise ValueError("Section modulus must be greater than zero")
        if allowable_stress_n_mm2 <= 0:
            raise ValueError("Allowable bending stress must be greater than zero")

        # Nm / cm3 is numerically equal to N/mm2 after both x1000
        # conversions used by Section_each.cls.
        stress = self.rounding.apply(
            bending_moment_nm / section_modulus_cm3,
            CalculationValueType.STRESS,
        )
        utilization = self.rounding.apply(
            stress / allowable_stress_n_mm2,
            CalculationValueType.SAFETY_FACTOR,
        )
        return BendingStrengthResult(
            bending_moment_nm=bending_moment_nm,
            section_modulus_cm3=section_modulus_cm3,
            calculated_stress_n_mm2=stress,
            allowable_stress_n_mm2=allowable_stress_n_mm2,
            utilization_ratio=utilization,
            status="O.K" if utilization < 1.0 else "N.G",
        )

