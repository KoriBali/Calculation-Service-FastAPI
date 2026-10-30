"""Design standard 3 engine results -> response ``data`` (schema 2.0).

The engine already rounds every value (rounding profile of the design
standard). This module only selects and arranges values; the few values it
derives (wire fixed tension, per-arm wind load, arm object front area) use the
same domain methods and rounding profile the engine uses.

Report layout (numbered slots of the legacy PDF, "・・・O.K" text) is not built
here: that is the gateway report formatter's job.
"""

from math import fsum

from app.engine.calculation.gravity import gravity_for_standard
from app.engine.calculation.result import Standard34CalculationResult
from app.engine.calculation.rounding import CalculationValueType, rounding_profile_for
from app.engine.domain.arm import ArmPart
from app.engine.domain.standards import DesignStandard
from app.pole.schemas import PoleCalculationRequest

SCHEMA_VERSION = "2.0"

OK = "OK"
NG = "NG"
_STATUS = {"O.K": OK, "N.G": NG}


def _status(engine_status: str) -> str:
    """Engine "O.K"/"N.G" -> "OK"/"NG". An unknown text fails loudly."""
    return _STATUS[engine_status]


def _check(check: str, *, moment_nm, stress_n_mm2, allowable_n_mm2, ratio, status) -> dict:
    return {
        "check": check,
        "moment_nm": moment_nm,
        "stress_n_mm2": stress_n_mm2,
        "allowable_stress_n_mm2": allowable_n_mm2,
        "utilization_ratio": ratio,
        "status": _status(status),
    }


def map_standard_3(
    *,
    request: PoleCalculationRequest,
    standard: DesignStandard,
    positions: tuple[Standard34CalculationResult, ...],
    wires,
    wire_results,
    arm_parts: tuple[ArmPart, ...],
    arm_results,
) -> dict:
    rounding = rounding_profile_for(standard.code)
    pressure_policy = standard.wind_pressure_policy
    arms = [
        _arm(standard, part, result)
        for part, result in zip(arm_parts, arm_results, strict=True)
    ]
    evaluated_positions = [_evaluated_position(rounding, result) for result in positions]
    return {
        "schema_version": SCHEMA_VERSION,
        "design_standard": {"code": int(standard.code), "name": standard.name},
        "summary": _summary(arms, evaluated_positions),
        "conditions": {
            "structure_height_m": max(pole.top_elevation_m for pole in request.poles),
            "wind_speed_m_s": float(pressure_policy.wind_speed_m_s),
            "air_density_kg_m3": float(pressure_policy.air_density_kg_m3),
            # d_st 3 pressure is the same at every height.
            "wind_pressure_n_m2": rounding.apply(
                pressure_policy.wind_pressure_at(0.0), CalculationValueType.WIND_PRESSURE
            ),
            "gravity_m_s2": gravity_for_standard(standard.code),
            "overdesign_factor": request.overdesign_factor,
            "base_elevation_m": request.base_elevation_m,
            "wind_cases": [
                {"code": case.name, "angle_deg": case.angle_deg}
                for case in standard.wind_case_policy.cases()
            ],
            "seismic": None,
        },
        "overhead_wires": [
            _overhead_wire(rounding, wire, result)
            for wire, result in zip(wires, wire_results, strict=True)
        ],
        "arms": arms,
        "evaluated_positions": evaluated_positions,
    }


# ===== Overall verdict =====
def _summary(arms: list[dict], evaluated_positions: list[dict]) -> dict:
    """NG if any check is NG. Governing = highest ratio; on a tie, the first."""
    candidates = [
        ({"component": "arm", "name": arm["name"], "evaluated_position_m": None, "wind_case": None}, check)
        for arm in arms
        for check in arm["checks"]
    ] + [
        (
            {
                "component": "pole",
                "name": position["pole_name"],
                "evaluated_position_m": position["evaluated_position_m"],
                "wind_case": case["code"],
            },
            check,
        )
        for position in evaluated_positions
        for case in position["wind_cases"]
        for check in case["checks"]
    ]
    where, check = max(candidates, key=lambda item: item[1]["utilization_ratio"])
    return {
        "status": NG if any(c["status"] == NG for _, c in candidates) else OK,
        "governing": {
            **where,
            "check": check["check"],
            "utilization_ratio": check["utilization_ratio"],
        },
    }


# ===== Overhead wires (independent of the evaluated position) =====
def _overhead_wire(rounding, wire, result) -> dict:
    return {
        "name": result.wire_name,
        "wind_coefficient": result.cf,
        "fix_load_per_length_n_m": result.fix_load_per_length_n_m,
        "fixed_tension_n": rounding.apply(
            wire.tension_from_line_load(result.fix_load_per_length_n_m),
            CalculationValueType.LOAD,
        ),
        "wind_cases": [
            {
                "code": item.direction,
                "combined_wind_line_load_n_m": item.combined_wind_line_load_n_m,
                "wind_tension_n": item.wind_tension_n,
            }
            for item in result.directional_results
        ],
    }


# ===== Arms (local check, independent of the evaluated position) =====
def _arm(standard: DesignStandard, part: ArmPart, result) -> dict:
    spec = result.specification
    safety = result.wind_combination_safety
    return {
        "name": result.arm_name,
        "specification": {
            "section_area_cm2": spec.section_area_cm2,
            "section_modulus_cm3": spec.section_modulus_cm3,
            "moment_of_inertia_cm4": spec.moment_of_inertia_cm4,
            "radius_of_gyration_cm": spec.radius_of_gyration_cm,
            "mass_kg": spec.mass_kg,
            "fix_load_n": spec.fix_load_n,
            "front_projected_area_m2": spec.front_projected_area_m2,
            "center_length_m": spec.center_length_m,
        },
        # objects[0] is the arm body; mounted objects follow, farthest first.
        "objects": [
            _arm_object(standard, part, spec, item) for item in result.object_results
        ],
        "totals": {
            "fix_load_n": result.total_fix_load_n,
            "fix_load_moment_nm": result.total_fix_load_moment_at_arm_support_nm,
            "wind_moment_nm": result.total_wind_moment_at_arm_support_nm,
        },
        "checks": [
            _check(
                "arm_bending",
                moment_nm=safety.moment_nm,
                stress_n_mm2=safety.bending_stress_n_mm2,
                allowable_n_mm2=safety.allowable_stress_n_mm2,
                ratio=safety.utilization_ratio,
                status=safety.status,
            )
        ],
    }


def _arm_object(standard: DesignStandard, part: ArmPart, spec, result) -> dict:
    if result.object_index == 0:
        quantity = 1
        front_area = spec.front_projected_area_m2
        coefficient = part.arm.shape_factor
    else:
        mounted = part.mounted_objects[result.object_index - 1]
        quantity = mounted.quantity
        front_area = mounted.front_area_m2 * mounted.quantity
        coefficient = mounted.base_wind_coefficient
    return {
        "index": result.object_index,
        "name": result.object_name,
        "object_type": result.object_type,
        "quantity": quantity,
        "fix_load_n": result.fix_load_n,
        "front_projected_area_m2": front_area,
        # The engine rounds the coefficient to 3 places before using it.
        "wind_coefficient": standard.rounding_policy.apply(coefficient, 3),
        "front_wind_load_n": result.front_wind_load_n,
        "horizontal_load_distance_m": result.horizontal_load_distance_m,
        "fix_load_moment_nm": result.fix_load_moment_at_arm_support_nm,
        "wind_moment_nm": result.wind_moment_at_arm_support_nm,
    }


# ===== Evaluated positions =====
def _evaluated_position(rounding, result: Standard34CalculationResult) -> dict:
    section = result.section_properties
    arm_results = () if result.arm_aggregation is None else result.arm_aggregation.arm_results
    return {
        "evaluated_position_m": result.evaluated_position_m,
        "pole_name": result.evaluated_pole_name,
        "section": {
            "material": result.material_name,
            "diameter_mm": section.diameter_mm,
            "thickness_mm": section.thickness_mm,
            "cross_section_area_cm2": section.cross_section_area_cm2,
            "section_modulus_cm3": section.section_modulus_cm3,
            "moment_of_inertia_cm4": section.moment_of_inertia_cm4,
            "radius_of_gyration_cm": section.radius_of_gyration_cm,
        },
        "vertical_fix_load_n": result.total_fix_load_n,
        "wind_cases": [
            {
                "code": case.wind_case_name,
                "angle_deg": case.wind_direction_deg,
                "load_rows": _load_rows(rounding, result, case.wind_case_name),
                "totals": {
                    "wind_load_n": case.total_wind_load_n,
                    "wind_tension_n": case.total_wind_tension_n,
                    "resultant_horizontal_load_n": case.resultant_wind_load_n,
                    "arm_fix_load_moment_nm": rounding.apply(
                        fsum(arm.total_fix_load_moment_at_arm_support_nm for arm in arm_results),
                        CalculationValueType.MOMENT,
                    ),
                    "combined_moment_x_nm": case.combined_wind_moment_x_nm,
                    "combined_moment_y_nm": case.combined_wind_moment_y_nm,
                    "combined_moment_nm": case.combined_wind_moment_nm,
                },
                "checks": [
                    _check(
                        "pole_bending",
                        moment_nm=case.bending_stress.absolute_total_moment_nm,
                        stress_n_mm2=case.bending_stress.bending_stress_n_mm2,
                        allowable_n_mm2=case.bending_stress.short_term_allowable_bending_n_mm2,
                        ratio=case.bending_stress.safety_factor,
                        status=case.bending_stress.status,
                    )
                ],
            }
            for case in result.direction_results
        ],
    }


def _row(kind, name, *, quantity, fix_load_n, projected_area_m2, wind_coefficient,
         wind_load_n, load_center_height_m, wind_moment_nm, wind_tension_n=None) -> dict:
    return {
        "kind": kind,
        "name": name,
        "quantity": quantity,
        "fix_load_n": fix_load_n,
        "projected_area_m2": projected_area_m2,
        "wind_coefficient": wind_coefficient,
        "wind_load_n": wind_load_n,
        "load_center_height_m": load_center_height_m,
        "wind_moment_nm": wind_moment_nm,
        "wind_tension_n": wind_tension_n,
    }


def _in_case(directional_results, case_name: str):
    return next(item for item in directional_results if item.direction == case_name)


def _load_rows(rounding, result: Standard34CalculationResult, case_name: str) -> list[dict]:
    """Report order: arms, direct objects, overhead wires, poles from the top."""
    rows = []
    if result.arm_aggregation is not None:
        for arm in result.arm_aggregation.arm_results:
            # One arm part is one row: area and Cf live per object in arms[].
            rows.append(_row(
                "ARM", arm.arm_name,
                quantity=1,
                fix_load_n=arm.total_fix_load_n,
                projected_area_m2=None,
                wind_coefficient=None,
                wind_load_n=rounding.apply(
                    fsum(_in_case(obj.directional_results, case_name).wind_load_n
                         for obj in arm.object_results),
                    CalculationValueType.LOAD,
                ),
                load_center_height_m=arm.object_results[0].load_center_height_m,
                wind_moment_nm=None,
            ))
    for item in result.direct_object_aggregation.direct_object_results:
        wind = _in_case(item.directional_results, case_name)
        rows.append(_row(
            "DIRECT_OBJECT", item.object_name,
            quantity=item.quantity,
            fix_load_n=item.fix_load_n,
            projected_area_m2=wind.projected_area_m2,
            wind_coefficient=item.cf,
            wind_load_n=wind.wind_load_n,
            load_center_height_m=item.load_center_height_m,
            wind_moment_nm=wind.wind_moment_nm,
        ))
    for item in result.overhead_wire_aggregation.wire_results:
        wind = _in_case(item.directional_results, case_name)
        rows.append(_row(
            "OVERHEAD_WIRE", item.wire_name,
            quantity=1,
            fix_load_n=item.fix_load_n,
            projected_area_m2=wind.directional_projected_area_m2,
            wind_coefficient=item.cf,
            wind_load_n=wind.wind_load_n,
            load_center_height_m=item.load_center_height_m,
            wind_moment_nm=wind.wind_moment_nm,
            wind_tension_n=wind.wind_tension_n,
        ))
    # pole_results starts at the evaluated (lowest active) segment.
    for item in reversed(result.pole_aggregation.pole_results):
        rows.append(_row(
            "POLE", item.geometry.pole_name,
            quantity=1,
            fix_load_n=item.fix_load_n,
            projected_area_m2=item.projected_area_m2,
            wind_coefficient=item.cf,
            wind_load_n=item.wind_load_n,
            load_center_height_m=item.geometry.load_center_height_m,
            wind_moment_nm=item.wind_moment_nm,
        ))
    return rows
