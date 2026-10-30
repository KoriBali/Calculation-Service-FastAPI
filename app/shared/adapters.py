"""Validated request schemas -> engine objects. No formulas here."""

from app.engine.domain.arm import Arm, ArmLoadObject, ArmPart
from app.engine.domain.direct_object import DirectObject
from app.engine.domain.overhead_wire import OverheadWire
from app.engine.domain.pole import PoleObject
from app.shared.schemas.arm import ArmInput, ArmObjectInput
from app.shared.schemas.direct_object import DirectObjectInput
from app.shared.schemas.overhead_wire import OverheadWireInput
from app.shared.schemas.pole import PoleSegmentInput


def to_pole_object(pole: PoleSegmentInput) -> PoleObject:
    if pole.pole_type == "Straight":
        # The engine reads only the lower values of a Straight segment, but
        # PoleObject still validates the upper ones, so they get the lower ones.
        diameter_upper, thickness_upper = pole.diameter_lower_mm, pole.thickness_lower_mm
    else:
        diameter_upper, thickness_upper = pole.diameter_upper_mm, pole.thickness_upper_mm
    return PoleObject(
        name=pole.name,
        pole_type=pole.pole_type,
        diameter_lower_mm=pole.diameter_lower_mm,
        diameter_upper_mm=diameter_upper,
        thickness_lower_mm=pole.thickness_lower_mm,
        thickness_upper_mm=thickness_upper,
        material=pole.material,
        top_elevation_m=pole.top_elevation_m,
    )


def to_direct_object(item: DirectObjectInput) -> DirectObject:
    if item.object_type == "Omni":
        # Omni uses the front area for every direction; side area and angle
        # do not change any load.
        side_area, fixed_angle = 0.0, 0.0
    else:
        side_area, fixed_angle = item.side_area_m2, item.fixed_angle_deg
    return DirectObject(
        name=item.name,
        object_type=item.object_type,
        front_area_m2=item.front_area_m2,
        side_area_m2=side_area,
        mass_per_unit_kg=item.mass_per_unit_kg,
        elevation_m=item.elevation_m,
        base_wind_coefficient=item.base_wind_coefficient,
        quantity=item.quantity,
        fixed_angle_deg=fixed_angle,
    )


def to_overhead_wire(wire: OverheadWireInput) -> OverheadWire:
    return OverheadWire(
        name=wire.name,
        mass_per_length_kg_m=wire.mass_per_length_kg_m,
        diameter_mm=wire.diameter_mm,
        elevation_m=wire.elevation_m,
        span_length_m=wire.span_length_m,
        sag_ratio_percent=wire.sag_ratio_percent,
        base_wind_coefficient=wire.base_wind_coefficient,
        fixed_angle_deg=wire.fixed_angle_deg,
        vertical_angle_deg=wire.vertical_angle_deg,
    )


def _to_arm_load_object(item: ArmObjectInput) -> ArmLoadObject:
    # Omni uses the front area for every direction; side area is not read.
    side_area = 0.0 if item.object_type == "Omni" else item.side_area_m2
    return ArmLoadObject(
        name=item.name,
        object_type=item.object_type,
        front_area_m2=item.front_area_m2,
        side_area_m2=side_area,
        mass_per_unit_kg=item.mass_per_unit_kg,
        horizontal_load_distance_m=item.horizontal_load_distance_m,
        base_wind_coefficient=item.base_wind_coefficient,
        quantity=item.quantity,
    )


def to_arm_part(arm: ArmInput) -> ArmPart:
    return ArmPart(
        arm=Arm(
            name=arm.name,
            diameter_mm=arm.diameter_mm,
            thickness_mm=arm.thickness_mm,
            total_length_m=arm.total_length_m,
            exposed_length_m=arm.exposed_length_m,
            installation_height_m=arm.installation_height_m,
            material=arm.material,
            fixed_angle_deg=arm.fixed_angle_deg,
        ),
        mounted_objects=tuple(_to_arm_load_object(item) for item in arm.objects),
    )
