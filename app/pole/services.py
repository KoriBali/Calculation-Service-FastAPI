from dataclasses import dataclass

from app.engine.calculation.pole_assembly import PoleAssembly
from app.engine.calculation.standard_34_workflow import Standard34CalculationWorkflow
from app.engine.calculation.standard_arm_workflows import Standard7CalculationWorkflow
from app.engine.calculation_service import CalculationService
from app.engine.domain.arm import ArmAssembly, ArmPart
from app.engine.domain.loads import OverdesignFactor
from app.engine.domain.overhead_wire import OverheadWire
from app.engine.domain.pole import PoleObject
from app.engine.domain.standards import DesignStandard, DesignStandardFactory
from app.pole.mappers import map_standard_3, map_standard_7
from app.pole.schemas import (
    PoleCalculationRequest,
    PoleStandard3Request,
    PoleStandard7Request,
)
from app.shared.adapters import (
    to_arm_part,
    to_direct_object,
    to_overhead_wire,
    to_pole_object,
)
from app.shared.errors import CalculationInputError


@dataclass(frozen=True)
class _Calculated:
    """Engine results every design standard reports, ready for its mapper."""

    standard: DesignStandard
    positions: tuple
    pole_sections: tuple
    wires: tuple[OverheadWire, ...]
    wire_results: tuple
    arm_parts: tuple[ArmPart, ...]
    arm_results: tuple


def calculate_pole(request: PoleCalculationRequest) -> dict:
    if isinstance(request, PoleStandard7Request):
        calculated = _calculate(
            request,
            standard_options={
                # Left out -> the engine's New JIL default.
                key: value
                for key, value in (
                    ("eqa_m_s2", request.horizontal_acceleration_m_s2),
                    ("eqr", request.response_ratio),
                )
                if value is not None
            },
            build_workflow=lambda common, arm_parts: Standard7CalculationWorkflow(
                **common,
                # d_st 7 always takes an arm assembly, even an empty one.
                arm_assembly=ArmAssembly(arm_parts),
            ),
        )
        return map_standard_7(request=request, **vars(calculated))

    if isinstance(request, PoleStandard3Request):
        calculated = _calculate(
            request,
            standard_options={"include_oblique": request.include_oblique_wind},
            build_workflow=lambda common, arm_parts: Standard34CalculationWorkflow(
                **common,
                arm_assembly=ArmAssembly(arm_parts) if arm_parts else None,
            ),
        )
        return map_standard_3(request=request, **vars(calculated))

    raise TypeError(f"Unsupported request {type(request).__name__}")


def _calculate(request, *, standard_options: dict, build_workflow) -> _Calculated:
    try:
        standard = DesignStandardFactory.create(
            request.design_standard,
            # Confirmed rule: the structure height is the top of the highest pole.
            structure_height_m=max(pole.top_elevation_m for pole in request.poles),
            basic_wind_speed_m_s=request.wind_speed_m_s,
            air_density_kg_m3=request.air_density_kg_m3,
            **standard_options,
        )
        wires = tuple(to_overhead_wire(wire) for wire in request.overhead_wires)
        arm_parts = tuple(to_arm_part(arm) for arm in request.arms)
        poles: tuple[PoleObject, ...] = tuple(to_pole_object(pole) for pole in request.poles)
        workflow = build_workflow(
            {
                "design_standard": standard,
                "pole_assembly": PoleAssembly(
                    list(poles),
                    base_elevation_m=request.base_elevation_m,
                ),
                "direct_objects": [to_direct_object(item) for item in request.direct_objects],
                "overhead_wires": wires,
                "overdesign_factor": OverdesignFactor(request.overdesign_factor),
            },
            arm_parts,
        )
        positions = CalculationService(workflow).calculate(request.evaluated_positions_m)

        # Section properties belong to the step pole, not to an evaluated
        # position: every step pole is reported once, at its lower end.
        pole_sections = tuple(
            workflow.pole_calculator.section_properties(pole, pole.diameter_lower_mm)
            for pole in poles
        )

        # Wire tension and the arm check belong to the wire or arm, not to an
        # evaluated position. Each is calculated at its own elevation, so every
        # wire and arm in the request is reported once, even one that lies
        # below every evaluated position.
        wire_results = tuple(
            workflow.overhead_wire_calculator.calculate_one(wire, wire.elevation_m)
            for wire in wires
        )
        arm_results = tuple(
            workflow.arm_assembly_calculator.part_calculator.calculate(
                part, part.arm.installation_height_m
            )
            for part in arm_parts
        )
    except ValueError as error:
        # Engine rules beyond the schema, e.g. a position above every pole top.
        raise CalculationInputError(str(error)) from error

    return _Calculated(
        standard=standard,
        positions=positions,
        pole_sections=pole_sections,
        wires=wires,
        wire_results=wire_results,
        arm_parts=arm_parts,
        arm_results=arm_results,
    )
