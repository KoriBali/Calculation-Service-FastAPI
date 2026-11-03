"""OOP calculations corresponding to Arm_Spec, AO_Each, Arm_Part and Arm_Kmpl.

Ported from python_calc ``calculation/arm_calculator.py`` (commit 270d23b).
"""

from collections.abc import Iterable
from math import cos, fsum, hypot, pi, sin, sqrt

from app.engine import basic_function as BasicFunction
from app.engine.domain.arm import Arm, ArmAssembly, ArmLoadObject, ArmObjectType, ArmPart
from app.engine.domain.loads import LoadObject
from app.engine.domain.standards import DesignStandard, DesignStandardCode

from .result import (
    ArmAggregationResult,
    ArmDirectionalTotal,
    ArmObjectCalculationResult,
    ArmObjectDirectionalResult,
    ArmPartCalculationResult,
    ArmSafetyResult,
    ArmSpecificationResult,
)
from .rounding import CalculationValueType, rounding_profile_for
from .gravity import gravity_for_standard


_ARM_STANDARD_CODES = {
    DesignStandardCode.OLD_LIGHTING_POLE,
    DesignStandardCode.LARGE_SIGN_BOARD,
    DesignStandardCode.NEW_JIL,
    DesignStandardCode.OLD_TRAFFIC_SIGNAL,
}


class ArmSpecificationCalculator:
    """Calculate the specification and self-load of an Arm."""

    def __init__(self, design_standard: DesignStandard) -> None:
        self._validate_standard(design_standard)
        self.design_standard = design_standard
        self.rounding = rounding_profile_for(design_standard.code)
        self.gravity_m_s2 = gravity_for_standard(design_standard.code)

    def calculate(self, arm: Arm) -> ArmSpecificationResult:
        if not isinstance(arm, Arm):
            raise TypeError("arm must be an Arm")

        diameter = arm.diameter_mm
        thickness = arm.thickness_mm
        inner_diameter = diameter - 2 * thickness
        raw_area = BasicFunction.PI / 4 * (
            diameter**2 - inner_diameter**2
        ) / 100
        raw_inertia = BasicFunction.PI / 64 * (
            diameter**4 - inner_diameter**4
        ) / 10000
        raw_section_modulus = BasicFunction.PI * (
            diameter**4 - inner_diameter**4
        ) / (32 * diameter) / 1000
        raw_radius = sqrt(
            (diameter**2 + inner_diameter**2) / 1600
        )
        raw_mass_per_meter = (
            BasicFunction.PI
            / 4
            * (diameter**2 - inner_diameter**2)
            / 1_000_000
            * BasicFunction.DENSITY
        )

        area = self.rounding.apply(
            raw_area, CalculationValueType.CROSS_SECTION_AREA
        )
        inertia = self.rounding.apply(
            raw_inertia, CalculationValueType.MOMENT_OF_INERTIA
        )
        section_modulus = self.rounding.apply(
            raw_section_modulus, CalculationValueType.SECTION_MODULUS
        )
        radius = self.rounding.apply(
            raw_radius, CalculationValueType.RADIUS_OF_GYRATION
        )
        mass_per_meter = self.rounding.apply(
            raw_mass_per_meter, CalculationValueType.WEIGHT_PER_METER
        )
        mass = self.rounding.apply(
            raw_mass_per_meter * arm.total_length_m,
            CalculationValueType.WEIGHT_PER_METER,
        )
        fix_load_per_meter = self.rounding.apply(
            mass_per_meter * self.gravity_m_s2,
            CalculationValueType.LOAD,
        )
        fix_load = self.rounding.apply(
            mass * self.gravity_m_s2, CalculationValueType.LOAD
        )
        front_area = self.rounding.apply(
            diameter / 1000 * arm.exposed_length_m,
            CalculationValueType.PROJECTED_AREA,
        )

        return ArmSpecificationResult(
            arm_name=arm.name,
            section_area_cm2=area,
            section_modulus_cm3=section_modulus,
            moment_of_inertia_cm4=inertia,
            polar_moment_of_inertia_cm4=self.rounding.apply(
                inertia * 2, CalculationValueType.MOMENT_OF_INERTIA
            ),
            radius_of_gyration_cm=radius,
            mass_per_meter_kg_m=mass_per_meter,
            mass_kg=mass,
            fix_load_per_meter_n_m=fix_load_per_meter,
            fix_load_n=fix_load,
            front_projected_area_m2=front_area,
            side_projected_area_m2=0.0,
            center_length_m=self.rounding.apply(
                arm.total_length_m / 2,
                CalculationValueType.LOAD_CENTER_HEIGHT,
            ),
            allowable_bending_n_mm2=arm.material.allowable_bending,
            short_term_allowable_bending_n_mm2=(
                arm.material.short_term_allowable_bending
            ),
            short_term_allowable_shear_n_mm2=(
                arm.material.short_term_allowable_shear
            ),
            short_term_allowable_compression_n_mm2=(
                arm.material.short_term_allowable_compression
            ),
        )

    @staticmethod
    def _validate_standard(design_standard: DesignStandard) -> None:
        if not isinstance(design_standard, DesignStandard):
            raise TypeError("design_standard must be a DesignStandard")
        if design_standard.code not in _ARM_STANDARD_CODES:
            raise ValueError(
                f"d_st = {int(design_standard.code)} does not use Arm calculation"
            )


class ArmPartCalculator:
    """Calculate one Arm locally and relative to an EvaluatedPosition."""

    def __init__(self, design_standard: DesignStandard) -> None:
        ArmSpecificationCalculator._validate_standard(design_standard)
        self.design_standard = design_standard
        self.rounding = rounding_profile_for(design_standard.code)
        self.gravity_m_s2 = gravity_for_standard(design_standard.code)
        self.specification_calculator = ArmSpecificationCalculator(
            design_standard
        )

    def calculate(
        self,
        arm_part: ArmPart,
        evaluated_position_m: float,
    ) -> ArmPartCalculationResult:
        if not isinstance(arm_part, ArmPart):
            raise TypeError("arm_part must be an ArmPart")
        evaluated_position = float(evaluated_position_m)
        if arm_part.arm.installation_height_m < evaluated_position:
            raise ValueError("Arm is below the EvaluatedPosition")

        specification = self.specification_calculator.calculate(arm_part.arm)
        arm_body = self._arm_as_load_object(arm_part.arm, specification)
        objects = (arm_body, *arm_part.mounted_objects)
        object_results = tuple(
            self._calculate_object(
                object_index=index,
                arm=arm_part.arm,
                arm_object=arm_object,
                evaluated_position_m=evaluated_position,
            )
            for index, arm_object in enumerate(objects)
        )

        total_fix_load = self._sum(
            (item.fix_load_n for item in object_results),
            CalculationValueType.LOAD,
        )
        total_seismic_load = self._sum(
            (item.seismic_load_n for item in object_results),
            CalculationValueType.LOAD,
        )
        fix_moment = self._sum(
            (
                item.fix_load_moment_at_arm_support_nm
                for item in object_results
            ),
            CalculationValueType.MOMENT,
        )
        wind_moment = self._sum(
            (
                item.wind_moment_at_arm_support_nm
                for item in object_results
            ),
            CalculationValueType.MOMENT,
        )
        seismic_moment = self._sum(
            (
                item.seismic_moment_at_arm_support_nm
                for item in object_results
            ),
            CalculationValueType.MOMENT,
        )
        wind_combined_moment = self.rounding.apply(
            hypot(fix_moment, wind_moment), CalculationValueType.MOMENT
        )
        wind_safety = self._safety(
            "FIX_LOAD_AND_WIND",
            wind_combined_moment,
            specification.section_modulus_cm3,
            specification.short_term_allowable_bending_n_mm2,
        )

        if self.design_standard.code is DesignStandardCode.NEW_JIL:
            fix_safety = self._safety(
                "FIX_LOAD",
                fix_moment,
                specification.section_modulus_cm3,
                specification.allowable_bending_n_mm2,
            )
            seismic_safety = self._safety(
                "FIX_LOAD_AND_SEISMIC",
                self.rounding.apply(
                    hypot(fix_moment, seismic_moment),
                    CalculationValueType.MOMENT,
                ),
                specification.section_modulus_cm3,
                specification.short_term_allowable_bending_n_mm2,
            )
        else:
            fix_safety = None
            seismic_safety = None

        return ArmPartCalculationResult(
            arm_name=arm_part.arm.name,
            installation_height_m=arm_part.arm.installation_height_m,
            specification=specification,
            object_results=object_results,
            total_fix_load_n=total_fix_load,
            total_seismic_load_n=total_seismic_load,
            total_fix_load_moment_at_arm_support_nm=fix_moment,
            total_wind_moment_at_arm_support_nm=wind_moment,
            total_seismic_moment_at_arm_support_nm=seismic_moment,
            fix_load_safety=fix_safety,
            wind_combination_safety=wind_safety,
            seismic_combination_safety=seismic_safety,
        )

    def _arm_as_load_object(
        self,
        arm: Arm,
        specification: ArmSpecificationResult,
    ) -> ArmLoadObject:
        return ArmLoadObject(
            name=arm.name,
            object_type=ArmObjectType.ARM_BODY,
            front_area_m2=specification.front_projected_area_m2,
            side_area_m2=0.0,
            mass_per_unit_kg=specification.mass_kg,
            horizontal_load_distance_m=specification.center_length_m,
            base_wind_coefficient=arm.shape_factor,
            quantity=1,
        )

    def _calculate_object(
        self,
        *,
        object_index: int,
        arm: Arm,
        arm_object: ArmLoadObject,
        evaluated_position_m: float,
    ) -> ArmObjectCalculationResult:
        load_center_height = self.rounding.apply(
            arm.installation_height_m - evaluated_position_m,
            CalculationValueType.LOAD_CENTER_HEIGHT,
        )
        coefficient = self.design_standard.rounding_policy.apply(
            arm_object.base_wind_coefficient, 3
        )
        wind_pressure = self.rounding.apply(
            self.design_standard.wind_pressure_policy.wind_pressure_at(
                arm.installation_height_m
            ),
            CalculationValueType.WIND_PRESSURE,
        )
        fix_load = self.rounding.apply(
            arm_object.fix_load_n(self.gravity_m_s2), CalculationValueType.LOAD
        )
        # Confirmed Arm rule: complete seismic response belongs only to New
        # JIL. Standards 3, 5 and 9 keep Arm seismic at zero even though the
        # general standard factory can expose an optional seismic policy for
        # other object types.
        if self.design_standard.code is DesignStandardCode.NEW_JIL:
            seismic_load = self.rounding.apply(
                self.design_standard.seismic_policy.calculate_load_n(
                    fix_load_n=fix_load,
                    mass_kg=arm_object.total_mass_kg(),
                ),
                CalculationValueType.LOAD,
            )
        else:
            seismic_load = 0.0
        front_wind_load = self.rounding.apply(
            arm_object.front_area_m2
            * coefficient
            * wind_pressure
            * arm_object.quantity,
            CalculationValueType.LOAD,
        )
        side_wind_load = self.rounding.apply(
            arm_object.side_area_m2
            * coefficient
            * wind_pressure
            * arm_object.quantity,
            CalculationValueType.LOAD,
        )
        distance = arm_object.horizontal_load_distance_m
        fix_moment = self.rounding.apply(
            fix_load * distance, CalculationValueType.MOMENT
        )
        wind_moment = self.rounding.apply(
            front_wind_load * distance, CalculationValueType.MOMENT
        )
        seismic_moment = self.rounding.apply(
            seismic_load * distance, CalculationValueType.MOMENT
        )
        seismic_pole_moment = self.rounding.apply(
            seismic_load * load_center_height, CalculationValueType.MOMENT
        )
        directional = tuple(
            self._directional_result(
                direction=case.name,
                wind_angle_rad=case.angle_deg / 180 * pi,
                arm_object=arm_object,
                arm_fixed_angle_deg=arm.fixed_angle_deg,
                front_wind_load_n=front_wind_load,
                side_wind_load_n=side_wind_load,
                fix_load_n=fix_load,
                seismic_load_n=seismic_load,
                load_center_height_m=load_center_height,
            )
            for case in self.design_standard.wind_case_policy.cases()
        )
        return ArmObjectCalculationResult(
            object_index=object_index,
            object_name=arm_object.name,
            object_type=arm_object.object_type.value,
            load_center_height_m=load_center_height,
            horizontal_load_distance_m=distance,
            mass_kg=arm_object.total_mass_kg(),
            fix_load_n=fix_load,
            seismic_load_n=seismic_load,
            front_wind_load_n=front_wind_load,
            side_wind_load_n=side_wind_load,
            fix_load_moment_at_arm_support_nm=fix_moment,
            wind_moment_at_arm_support_nm=wind_moment,
            seismic_moment_at_arm_support_nm=seismic_moment,
            seismic_moment_at_pole_nm=seismic_pole_moment,
            directional_results=directional,
        )

    def _directional_result(
        self,
        *,
        direction: str,
        wind_angle_rad: float,
        arm_object: ArmLoadObject,
        arm_fixed_angle_deg: float,
        front_wind_load_n: float,
        side_wind_load_n: float,
        fix_load_n: float,
        seismic_load_n: float,
        load_center_height_m: float,
    ) -> ArmObjectDirectionalResult:
        angle_of_attack = arm_object.angle_of_attack_rad(
            arm_fixed_angle_deg,
            wind_angle_rad,
        )
        sine = round(sin(angle_of_attack), 3)
        cosine = round(cos(angle_of_attack), 3)
        if arm_object.is_omni:
            directional_area = arm_object.front_area_m2 * arm_object.quantity
            wind_load = front_wind_load_n
        else:
            directional_area = self.rounding.apply(
                (
                    arm_object.front_area_m2 * abs(sine)
                    + arm_object.side_area_m2 * abs(cosine)
                )
                * arm_object.quantity,
                CalculationValueType.PROJECTED_AREA,
            )
            wind_load = self.rounding.apply(
                front_wind_load_n * abs(sine)
                + side_wind_load_n * abs(cosine),
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
        fixed_angle_rad = arm_fixed_angle_deg / 180 * pi
        fix_moment_x = self.rounding.apply(
            fix_load_n
            * arm_object.horizontal_load_distance_m
            * round(sin(-fixed_angle_rad), 3),
            CalculationValueType.MOMENT,
        )
        fix_moment_y = self.rounding.apply(
            fix_load_n
            * arm_object.horizontal_load_distance_m
            * round(cos(fixed_angle_rad), 3),
            CalculationValueType.MOMENT,
        )
        if self.design_standard.features.calculates_torque:
            torque = self.rounding.apply(
                (
                    abs(front_wind_load_n * sine)
                    * arm_object.horizontal_load_distance_m
                    * sine
                    + abs(side_wind_load_n * cosine)
                    * arm_object.horizontal_load_distance_m
                    * sine
                ),
                CalculationValueType.MOMENT,
            )
            seismic_torque = self.rounding.apply(
                seismic_load_n
                * arm_object.horizontal_load_distance_m
                * sine,
                CalculationValueType.MOMENT,
            )
        else:
            torque = 0.0
            seismic_torque = 0.0
        return ArmObjectDirectionalResult(
            direction=direction,
            angle_rad=wind_angle_rad,
            angle_of_attack_rad=angle_of_attack,
            sin_angle_of_attack=sine,
            cos_angle_of_attack=cosine,
            directional_projected_area_m2=directional_area,
            wind_load_n=wind_load,
            wind_load_x_n=wind_x,
            wind_load_y_n=wind_y,
            wind_moment_at_pole_x_nm=self.rounding.apply(
                load_center_height_m * wind_y, CalculationValueType.MOMENT
            ),
            wind_moment_at_pole_y_nm=self.rounding.apply(
                load_center_height_m * wind_x, CalculationValueType.MOMENT
            ),
            fix_load_moment_x_nm=fix_moment_x,
            fix_load_moment_y_nm=fix_moment_y,
            wind_torque_nm=torque,
            seismic_torque_nm=seismic_torque,
        )

    def _safety(
        self,
        load_case: str,
        moment_nm: float,
        section_modulus_cm3: float,
        allowable_n_mm2: float,
    ) -> ArmSafetyResult:
        stress = self.rounding.apply(
            moment_nm / section_modulus_cm3,
            CalculationValueType.STRESS,
        )
        utilization = self.rounding.apply(
            stress / allowable_n_mm2,
            CalculationValueType.SAFETY_FACTOR,
        )
        return ArmSafetyResult(
            load_case=load_case,
            moment_nm=moment_nm,
            bending_stress_n_mm2=stress,
            allowable_stress_n_mm2=allowable_n_mm2,
            utilization_ratio=utilization,
            status="O.K" if utilization <= 1 else "N.G",
        )

    def _sum(
        self,
        values: Iterable[float],
        value_type: CalculationValueType,
    ) -> float:
        return self.rounding.apply(fsum(values), value_type)


class ArmAssemblyCalculator:
    """Aggregate all Arms above each Pole EvaluatedPosition."""

    def __init__(
        self,
        arm_assembly: ArmAssembly,
        design_standard: DesignStandard,
    ) -> None:
        if not isinstance(arm_assembly, ArmAssembly):
            raise TypeError("arm_assembly must be an ArmAssembly")
        ArmSpecificationCalculator._validate_standard(design_standard)
        self.arm_assembly = arm_assembly
        self.design_standard = design_standard
        self.rounding = rounding_profile_for(design_standard.code)
        self.part_calculator = ArmPartCalculator(design_standard)

    def active_arm_parts(self, evaluated_position_m: float) -> tuple[ArmPart, ...]:
        return tuple(
            part
            for part in self.arm_assembly.arm_parts
            if part.arm.installation_height_m >= evaluated_position_m
        )

    def calculate_at(
        self, evaluated_position_m: float
    ) -> tuple[ArmPartCalculationResult, ...]:
        return tuple(
            self.part_calculator.calculate(part, evaluated_position_m)
            for part in self.active_arm_parts(evaluated_position_m)
        )

    def aggregate_at(self, evaluated_position_m: float) -> ArmAggregationResult:
        results = self.calculate_at(evaluated_position_m)
        direction_totals = tuple(
            self._aggregate_direction(results, case.name, case.angle_deg / 180 * pi)
            for case in self.design_standard.wind_case_policy.cases()
        )
        return ArmAggregationResult(
            evaluated_position_m=float(evaluated_position_m),
            arm_results=results,
            active_arm_count=len(results),
            total_fix_load_n=self._sum(
                (item.total_fix_load_n for item in results),
                CalculationValueType.LOAD,
            ),
            total_seismic_load_n=self._sum(
                (item.total_seismic_load_n for item in results),
                CalculationValueType.LOAD,
            ),
            total_seismic_moment_nm=self._sum(
                (
                    obj.seismic_moment_at_pole_nm
                    for item in results
                    for obj in item.object_results
                ),
                CalculationValueType.MOMENT,
            ),
            directional_totals=direction_totals,
        )

    def _aggregate_direction(
        self,
        results: tuple[ArmPartCalculationResult, ...],
        direction: str,
        angle_rad: float,
    ) -> ArmDirectionalTotal:
        directional = tuple(
            value
            for part in results
            for obj in part.object_results
            for value in obj.directional_results
            if value.direction == direction
        )
        return ArmDirectionalTotal(
            direction=direction,
            angle_rad=angle_rad,
            total_wind_load_n=self._sum(
                (item.wind_load_n for item in directional),
                CalculationValueType.LOAD,
            ),
            total_wind_load_x_n=self._sum(
                (item.wind_load_x_n for item in directional),
                CalculationValueType.LOAD,
            ),
            total_wind_load_y_n=self._sum(
                (item.wind_load_y_n for item in directional),
                CalculationValueType.LOAD,
            ),
            total_wind_moment_x_nm=self._sum(
                (item.wind_moment_at_pole_x_nm for item in directional),
                CalculationValueType.MOMENT,
            ),
            total_wind_moment_y_nm=self._sum(
                (item.wind_moment_at_pole_y_nm for item in directional),
                CalculationValueType.MOMENT,
            ),
            total_fix_load_moment_x_nm=self._sum(
                (item.fix_load_moment_x_nm for item in directional),
                CalculationValueType.MOMENT,
            ),
            total_fix_load_moment_y_nm=self._sum(
                (item.fix_load_moment_y_nm for item in directional),
                CalculationValueType.MOMENT,
            ),
            total_wind_torque_nm=self._sum(
                (item.wind_torque_nm for item in directional),
                CalculationValueType.MOMENT,
            ),
            total_seismic_torque_nm=self._sum(
                (item.seismic_torque_nm for item in directional),
                CalculationValueType.MOMENT,
            ),
        )

    def _sum(
        self,
        values: Iterable[float],
        value_type: CalculationValueType,
    ) -> float:
        return self.rounding.apply(fsum(values), value_type)
