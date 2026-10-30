"""DesignStandard-object workflow for d_st 1, 2, and 6.

Ported from python_calc ``calculation/standard_126_workflow.py`` (commit 270d23b).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from math import radians

from app.engine.domain.conditions import SeismicCondition, WindDirection
from app.engine.domain.direct_object import DirectObject
from app.engine.domain.loads import OverdesignFactor
from app.engine.domain.overhead_wire import OverheadWire
from app.engine.domain.standards import DesignStandard, DesignStandardCode

from .direct_object_calculator import DirectObjectCalculator
from .evaluated_position_calculator import EvaluatedPositionCalculator
from .overhead_wire_calculator import OverheadWireCalculator
from .pole_assembly import PoleAssembly
from .pole_calculator import PoleCalculator
from .result import Standard126CalculationResult
from .seismic import NoSeismicPolicy
from .stress import (
    CompressionBendingStressInput,
    CompressionBendingStressPolicy,
)


@dataclass(frozen=True)
class _StandardWindCondition:
    """Compatibility surface backed only by a DesignStandard object."""

    standard: DesignStandard

    @property
    def design_standard(self) -> int:
        return int(self.standard.code)

    @property
    def directions(self) -> tuple[WindDirection, ...]:
        cases = self.standard.wind_case_policy.cases()
        return tuple(
            WindDirection(case.name, radians(case.angle_deg)) for case in cases
        )

    @property
    def common_parameters(self):
        common = self.standard.wind_pressure_policy.common_parameters
        return None if common is None else dict(common)

    def kz_at(self, top_elevation_m: float) -> float:
        return self.standard.wind_pressure_policy.kz_at(top_elevation_m)

    def wind_pressure_at(self, top_elevation_m: float) -> float:
        return self.standard.wind_pressure_policy.wind_pressure_at(
            top_elevation_m
        )


class Standard126CalculationWorkflow:
    """Run Pole, Direct Object, OHW, aggregation, and stress for an omni case."""

    _SUPPORTED_CODES = {
        DesignStandardCode.ACT_DISASTER_PREVENTION,
        DesignStandardCode.FIXED_WIND_DISASTER,
        DesignStandardCode.ACT_TOWER,
    }

    def __init__(
        self,
        *,
        design_standard: DesignStandard,
        pole_assembly: PoleAssembly,
        seismic_condition: SeismicCondition,
        direct_objects: Iterable[DirectObject] = (),
        overhead_wires: Iterable[OverheadWire] = (),
        overdesign_factor: OverdesignFactor | None = None,
    ) -> None:
        if not isinstance(design_standard, DesignStandard):
            raise TypeError("design_standard must be a DesignStandard")
        if design_standard.code not in self._SUPPORTED_CODES:
            raise ValueError("This workflow supports only d_st 1, 2, and 6")
        if not isinstance(
            design_standard.stress_policy,
            CompressionBendingStressPolicy,
        ):
            raise TypeError(
                "d_st 1, 2, and 6 require CompressionBendingStressPolicy"
            )

        self.design_standard = design_standard
        self.wind_condition = _StandardWindCondition(design_standard)
        self.seismic_condition = seismic_condition
        self.pole_calculator = PoleCalculator(
            assembly=pole_assembly,
            wind_condition=self.wind_condition,
            seismic_condition=seismic_condition,
            overdesign_factor=overdesign_factor,
            seismic_policy=design_standard.seismic_policy,
        )
        self.direct_object_calculator = DirectObjectCalculator(
            direct_objects=direct_objects,
            wind_condition=self.wind_condition,
            seismic_condition=seismic_condition,
            seismic_policy=design_standard.seismic_policy,
        )
        # Confirmed rule: d_st 1, 2, and 6 calculate neither OHW seismic
        # load nor OHW seismic tension.
        self.overhead_wire_calculator = OverheadWireCalculator(
            wires=overhead_wires,
            wind_condition=self.wind_condition,
            seismic_condition=seismic_condition,
            seismic_policy=NoSeismicPolicy(),
            calculate_seismic_tension=False,
        )
        self.evaluated_position_calculator = EvaluatedPositionCalculator(
            pole_calculator=self.pole_calculator,
            direct_object_calculator=self.direct_object_calculator,
            overhead_wire_calculator=self.overhead_wire_calculator,
        )

    def calculate_at(
        self,
        evaluated_position_m: float,
    ) -> Standard126CalculationResult:
        pole = self.pole_calculator.aggregate_at(evaluated_position_m)
        direct = self.direct_object_calculator.aggregate_at(
            evaluated_position_m
        )
        wire = self.overhead_wire_calculator.aggregate_at(
            evaluated_position_m
        )
        evaluated = self.evaluated_position_calculator.calculate_at(
            evaluated_position_m
        )
        omni = evaluated.directional_results[0]

        stress = self.design_standard.stress_policy.calculate(
            CompressionBendingStressInput(
                total_fix_load_n=evaluated.total_fix_load_n,
                total_seismic_load_n=evaluated.total_seismic_load_n,
                total_wind_moment_nm=omni.combined_wind_moment_nm,
                total_seismic_moment_nm=omni.combined_seismic_moment_nm,
                active_pole_segment_lengths_m=tuple(
                    item.geometry.active_length_m for item in pole.pole_results
                ),
                cross_section_area_cm2=(
                    evaluated.section_properties.cross_section_area_cm2
                ),
                section_modulus_cm3=(
                    evaluated.section_properties.section_modulus_cm3
                ),
                radius_of_gyration_cm=(
                    evaluated.section_properties.radius_of_gyration_cm
                ),
                short_term_allowable_bending_n_mm2=(
                    self.pole_calculator.assembly.poles[
                        self._evaluated_pole_index(evaluated.evaluated_pole_name)
                    ].material.short_term_allowable_bending
                ),
            )
        )

        return Standard126CalculationResult(
            design_standard=self.design_standard,
            pole_aggregation=pole,
            direct_object_aggregation=direct,
            overhead_wire_aggregation=wire,
            evaluated_position_result=evaluated,
            stress_result=stress,
        )

    def _evaluated_pole_index(self, pole_name: str) -> int:
        return next(
            index
            for index, pole in enumerate(self.pole_calculator.assembly.poles)
            if pole.name == pole_name
        )
