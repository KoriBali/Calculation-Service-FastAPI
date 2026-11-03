"""Stable calculation scenarios used by regression tests.

The geometry and loads intentionally match ``manual_check.py``.  This module
does not define new engineering rules; it records the calculation engine's
confirmed behaviour after calculation-rounding integration.
"""

from dataclasses import asdict

from app.engine.calculation.direct_object_calculator import DirectObjectCalculator
from app.engine.calculation.evaluated_position_calculator import EvaluatedPositionCalculator
from app.engine.calculation.overhead_wire_calculator import OverheadWireCalculator
from app.engine.calculation.pole_assembly import PoleAssembly
from app.engine.calculation.pole_calculator import PoleCalculator
from app.engine.calculation.rounding import CalculationValueType, rounding_profile_for
from app.engine.domain.conditions import SeismicCondition, WindCondition
from app.engine.domain.direct_object import DirectObject
from app.engine.domain.loads import OverdesignFactor
from app.engine.domain.overhead_wire import OverheadWire
from app.engine.domain.pole import PoleObject


EVALUATED_POSITIONS_M = (6.65, 1.65, 0.0)


def _poles() -> tuple[PoleObject, ...]:
    return (
        PoleObject(
            name="Pole-1",
            pole_type="Straight",
            diameter_lower_mm=75,
            diameter_upper_mm=75,
            thickness_lower_mm=4.5,
            thickness_upper_mm=4.5,
            material="STK400",
            top_elevation_m=8.15,
            quantity=1,
        ),
        PoleObject(
            name="Pole-2",
            pole_type="Taper",
            diameter_lower_mm=165.2,
            diameter_upper_mm=75,
            thickness_lower_mm=4.5,
            thickness_upper_mm=4.5,
            material="STK400",
            top_elevation_m=6.65,
            quantity=1,
        ),
        PoleObject(
            name="Pole-3",
            pole_type="Straight",
            diameter_lower_mm=165.2,
            diameter_upper_mm=165.2,
            thickness_lower_mm=4.5,
            thickness_upper_mm=4.5,
            material="STK400",
            top_elevation_m=1.65,
            quantity=1,
        ),
    )


def _direct_objects() -> tuple[DirectObject, ...]:
    return (
        DirectObject(
            name="DO1",
            object_type="Directional",
            front_area_m2=0.049,
            side_area_m2=0.041,
            mass_per_unit_kg=5.8,
            elevation_m=8.15,
            base_wind_coefficient=1.0,
            quantity=1,
            fixed_angle_deg=0,
        ),
    )


def _overhead_wires() -> tuple[OverheadWire, ...]:
    return (
        OverheadWire(
            name="OHW1",
            mass_per_length_kg_m=0.19,
            diameter_mm=11.5,
            elevation_m=5.75,
            span_length_m=15,
            sag_ratio_percent=3,
            base_wind_coefficient=1.0,
            fixed_angle_deg=180,
            vertical_angle_deg=0,
        ),
    )


def wind_condition_for(design_standard: int) -> WindCondition:
    """Return the fixed baseline wind input for one existing standard."""
    if design_standard in {1, 6}:
        return WindCondition(
            design_standard=design_standard,
            structure_height_m=8.15,
            area_density_code=2,
            basic_wind_speed_m_s=60.0,
        )
    return WindCondition(
        design_standard=design_standard,
        structure_height_m=8.15,
    )


def create_calculator(design_standard: int) -> EvaluatedPositionCalculator:
    """Build the current engine using stable manual-check inputs."""
    wind_condition = wind_condition_for(design_standard)
    seismic_condition = SeismicCondition.ground(k_value=0.5)
    pole_calculator = PoleCalculator(
        assembly=PoleAssembly(_poles(), base_elevation_m=0),
        wind_condition=wind_condition,
        seismic_condition=seismic_condition,
        overdesign_factor=OverdesignFactor(value=1.0),
    )
    direct_object_calculator = DirectObjectCalculator(
        direct_objects=_direct_objects(),
        wind_condition=wind_condition,
        seismic_condition=seismic_condition,
    )
    overhead_wire_calculator = OverheadWireCalculator(
        wires=_overhead_wires(),
        wind_condition=wind_condition,
        seismic_condition=seismic_condition,
    )
    return EvaluatedPositionCalculator(
        pole_calculator=pole_calculator,
        direct_object_calculator=direct_object_calculator,
        overhead_wire_calculator=overhead_wire_calculator,
    )


def scenario_snapshot(design_standard: int) -> dict:
    """Return JSON-compatible baseline values through EvaluatedPosition."""
    calculator = create_calculator(design_standard)
    wind_condition = calculator.pole_calculator.wind_condition
    rounding = rounding_profile_for(design_standard)
    positions = []

    for evaluated_position_m in EVALUATED_POSITIONS_M:
        result = calculator.calculate_at(evaluated_position_m)
        positions.append(
            {
                "evaluated_position_m": evaluated_position_m,
                "evaluated_pole_name": result.evaluated_pole_name,
                "material_name": result.material_name,
                "section_properties": asdict(result.section_properties),
                "total_fix_load_n": result.total_fix_load_n,
                "total_seismic_load_n": result.total_seismic_load_n,
                "total_seismic_moment_nm": result.total_seismic_moment_nm,
                "north_report_result": asdict(result.report_result),
            }
        )

    return {
        "design_standard": design_standard,
        "structure_height_m": wind_condition.structure_height_m,
        "area_density_code": wind_condition.area_density_code,
        "basic_wind_speed_m_s": wind_condition.basic_wind_speed_m_s,
        "common_parameters": wind_condition.common_parameters,
        "wind_pressure_by_pole_top_n_m2": {
            str(top): rounding.apply(
                wind_condition.wind_pressure_at(top),
                CalculationValueType.WIND_PRESSURE,
            )
            for top in (8.15, 6.65, 1.65)
        },
        "seismic_k_value": 0.5,
        "pole_overdesign_factor": 1.0,
        "evaluated_positions": positions,
    }


def all_baseline_snapshots() -> dict:
    """Return all minimum Stage 0 reference scenarios."""
    return {
        "schema_version": 1,
        "scenarios": {
            f"design_standard_{standard}": scenario_snapshot(standard)
            for standard in (1, 2, 3, 6)
        },
    }
