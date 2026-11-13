from dataclasses import dataclass

from app.engine.calculation.pole_assembly import PoleAssembly
from app.engine.calculation.standard_34_workflow import Standard34CalculationWorkflow
from app.engine.calculation.standard_arm_workflows import Standard7CalculationWorkflow
from app.engine.calculation_service import CalculationService
from app.engine.domain.arm import ArmAssembly, ArmPart
from app.engine.domain.direct_object import DirectObject
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
    """Engine results ready for the mapper of a design standard."""

    standard: DesignStandard
    positions: tuple
    pole_sections: tuple
    wires: tuple[OverheadWire, ...]
    wire_results: tuple
    arm_parts: tuple[ArmPart, ...]
    arm_results: tuple
    # Design standard 7 only: each step pole and direct object on its own,
    # calculated at its own lower end or elevation.
    poles: tuple[PoleObject, ...]
    pole_results: tuple
    direct_objects: tuple[DirectObject, ...]
    direct_object_results: tuple

    def shared(self) -> dict:
        """The results every design standard reports."""
        return {
            "standard": self.standard,
            "positions": self.positions,
            "pole_sections": self.pole_sections,
            "wires": self.wires,
            "wire_results": self.wire_results,
            "arm_parts": self.arm_parts,
            "arm_results": self.arm_results,
        }


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
        return map_standard_3(request=request, **calculated.shared())

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
        direct_objects = tuple(to_direct_object(item) for item in request.direct_objects)
        assembly = PoleAssembly(list(poles), base_elevation_m=request.base_elevation_m)
        workflow = build_workflow(
            {
                "design_standard": standard,
                "pole_assembly": assembly,
                "direct_objects": list(direct_objects),
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
        # The whole step pole, from its lower end, and each direct object at its
        # own elevation: the values of the item itself, not of a position.
        pole_results = tuple(
            workflow.pole_calculator.calculate_one(pole, assembly.segment_bounds(pole)[0])
            for pole in poles
        )
        direct_object_results = tuple(
            workflow.direct_object_calculator.calculate_one(item, item.elevation_m)
            for item in direct_objects
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
        poles=poles,
        pole_results=pole_results,
        direct_objects=direct_objects,
        direct_object_results=direct_object_results,
    )
