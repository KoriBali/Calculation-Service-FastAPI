from app.engine.calculation.pole_assembly import PoleAssembly
from app.engine.calculation.standard_34_workflow import Standard34CalculationWorkflow
from app.engine.calculation_service import CalculationService
from app.engine.domain.arm import ArmAssembly
from app.engine.domain.loads import OverdesignFactor
from app.engine.domain.standards import DesignStandardFactory
from app.pole.mappers import map_standard_3
from app.pole.schemas import PoleCalculationRequest
from app.shared.adapters import (
    to_arm_part,
    to_direct_object,
    to_overhead_wire,
    to_pole_object,
)
from app.shared.errors import CalculationInputError


def calculate_pole(request: PoleCalculationRequest) -> dict:
    try:
        standard = DesignStandardFactory.create(
            request.design_standard,
            # Confirmed rule: the structure height is the top of the highest pole.
            structure_height_m=max(pole.top_elevation_m for pole in request.poles),
            include_oblique=request.include_oblique_wind,
        )
        wires = tuple(to_overhead_wire(wire) for wire in request.overhead_wires)
        arm_parts = tuple(to_arm_part(arm) for arm in request.arms)
        workflow = Standard34CalculationWorkflow(
            design_standard=standard,
            pole_assembly=PoleAssembly(
                [to_pole_object(pole) for pole in request.poles],
                base_elevation_m=request.base_elevation_m,
            ),
            direct_objects=[to_direct_object(item) for item in request.direct_objects],
            overhead_wires=wires,
            arm_assembly=ArmAssembly(arm_parts) if arm_parts else None,
            overdesign_factor=OverdesignFactor(request.overdesign_factor),
        )
        positions = CalculationService(workflow).calculate(request.evaluated_positions_m)

        # Wire tension and the arm check belong to the wire or arm, not to an
        # evaluated position. Each is calculated at its own elevation, so every
        # wire and arm in the request is reported once, even one that lies
        # below every evaluated position.
        wire_results = tuple(
            workflow.overhead_wire_calculator.calculate_one(wire, wire.elevation_m)
            for wire in wires
        )
        arm_results = (
            tuple(
                workflow.arm_assembly_calculator.part_calculator.calculate(
                    part, part.arm.installation_height_m
                )
                for part in arm_parts
            )
            if arm_parts
            else ()
        )
    except ValueError as error:
        # Engine rules beyond the schema, e.g. a position above every pole top.
        raise CalculationInputError(str(error)) from error

    return map_standard_3(
        request=request,
        standard=standard,
        positions=positions,
        wires=wires,
        wire_results=wire_results,
        arm_parts=arm_parts,
        arm_results=arm_results,
    )
