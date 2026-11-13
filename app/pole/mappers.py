"""Design standard 3 and 7 engine results -> response ``data`` (schema 2.2).

Both standards share one response skeleton (summary, conditions, overhead
wires, arms, pole sections, evaluated positions with ``checks[]``); d_st 7
adds seismic values, torsion and more checks to the same places.

The engine already rounds every value (rounding profile of the design
standard). This module only selects and arranges values; the few values it
derives (wire fixed tension, per-arm wind load, arm object front area) use the
same domain methods and rounding profile the engine uses.

Report layout (numbered slots of the legacy PDF, "・・・O.K" text) is not built
here: that is the gateway report formatter's job.
"""

from math import fsum, pi

from app.engine.calculation.gravity import gravity_for_standard
from app.engine.calculation.result import (
    DirectObjectCalculationResult,
    OverheadWireCalculationResult,
    PoleCalculationResult,
    Standard7CalculationResult,
    Standard34CalculationResult,
)
from app.engine.calculation.rounding import CalculationValueType, rounding_profile_for
from app.engine.domain.arm import ArmPart
from app.engine.domain.direct_object import DirectObject, DirectObjectType
from app.engine.domain.materials import get_pole_material
from app.engine.domain.overhead_wire import OverheadWire
from app.engine.domain.pole import PoleObject, PoleSectionProperties
from app.engine.domain.standards import DesignStandard
from app.pole.schemas import PoleStandard3Request, PoleStandard7Request

SCHEMA_VERSION = "2.2"

OK = "OK"
NG = "NG"
_STATUS = {"O.K": OK, "N.G": NG}


def _status(engine_status: str) -> str:
    """Engine "O.K"/"N.G" -> "OK"/"NG". An unknown text fails loudly."""
    return _STATUS[engine_status]


def _check(check: str, *, moment_nm, stress_n_mm2, allowable_n_mm2, ratio, status, **extra) -> dict:
    return {
        "check": check,
        "moment_nm": moment_nm,
        "stress_n_mm2": stress_n_mm2,
        "allowable_stress_n_mm2": allowable_n_mm2,
        "utilization_ratio": ratio,
        "status": _status(status),
        **extra,
    }


def map_standard_3(
    *,
    request: PoleStandard3Request,
    standard: DesignStandard,
    positions: tuple[Standard34CalculationResult, ...],
    pole_sections: tuple[PoleSectionProperties, ...],
    wires,
    wire_results,
    arm_parts: tuple[ArmPart, ...],
    arm_results,
) -> dict:
    rounding = rounding_profile_for(standard.code)
    arms = [
        _arm(standard, part, result)
        for part, result in zip(arm_parts, arm_results, strict=True)
    ]
    evaluated_positions = [_evaluated_position(rounding, result) for result in positions]
    return {
        "schema_version": SCHEMA_VERSION,
        "design_standard": {"code": int(standard.code), "name": standard.name},
        "summary": _summary(arms, evaluated_positions),
        "conditions": _conditions(request, standard, rounding, seismic=None),
        "overhead_wires": [
            _overhead_wire(rounding, wire, result)
            for wire, result in zip(wires, wire_results, strict=True)
        ],
        "arms": arms,
        "pole_sections": [
            _pole_section(pole, section)
            for pole, section in zip(request.poles, pole_sections, strict=True)
        ],
        "evaluated_positions": evaluated_positions,
    }


def _conditions(request, standard: DesignStandard, rounding, *, seismic: dict | None) -> dict:
    pressure_policy = standard.wind_pressure_policy
    return {
        "structure_height_m": max(pole.top_elevation_m for pole in request.poles),
        "wind_speed_m_s": float(pressure_policy.wind_speed_m_s),
        "air_density_kg_m3": float(pressure_policy.air_density_kg_m3),
        # d_st 3 and 7 pressure is the same at every height.
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
        "seismic": seismic,
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
            "unit_weight_kg_m": spec.mass_per_meter_kg_m,
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


# ===== Step pole sections (independent of the evaluated position) =====
def _pole_section(pole, section: PoleSectionProperties) -> dict:
    # Taken at the lower end: the lower diameter and thickness of the step pole.
    return {
        "name": pole.name,
        "pole_type": pole.pole_type,
        "material": pole.material,
        "diameter_mm": section.diameter_mm,
        "thickness_mm": section.thickness_mm,
        "cross_section_area_cm2": section.cross_section_area_cm2,
        "moment_of_inertia_cm4": section.moment_of_inertia_cm4,
        "radius_of_gyration_cm": section.radius_of_gyration_cm,
        "unit_weight_kg_m": section.mass_per_meter_kg_m,
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
            "section_modulus_cm3": section.section_modulus_cm3,
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


def _seismic_row(row: dict, *, seismic_load_n, seismic_moment_nm,
                 wind_torque_nm=None, seismic_torque_nm=None) -> dict:
    """d_st 7 row: the d_st 3 row plus seismic values; torque only on ARM rows."""
    return {
        **row,
        "seismic_load_n": seismic_load_n,
        "seismic_moment_nm": seismic_moment_nm,
        "wind_torque_nm": wind_torque_nm,
        "seismic_torque_nm": seismic_torque_nm,
    }


def _in_case(directional_results, case_name: str):
    return next(item for item in directional_results if item.direction == case_name)


def _load_rows(rounding, result, case_name: str, *, seismic: bool = False) -> list[dict]:
    """Report order: arms, direct objects, overhead wires, poles from the top.

    ``seismic`` (d_st 7) adds seismic load and moment to every row, and the
    wind and seismic torque of each arm to the ARM rows.
    """
    def add(row: dict, item) -> None:
        if seismic:
            row = _seismic_row(
                row,
                seismic_load_n=item.seismic_load_n,
                seismic_moment_nm=item.seismic_moment_nm,
            )
        rows.append(row)

    def moment_sum(values):
        return rounding.apply(fsum(values), CalculationValueType.MOMENT)

    rows = []
    if result.arm_aggregation is not None:
        for arm in result.arm_aggregation.arm_results:
            in_case = [_in_case(obj.directional_results, case_name) for obj in arm.object_results]
            # One arm part is one row: area and Cf live per object in arms[].
            row = _row(
                "ARM", arm.arm_name,
                quantity=1,
                fix_load_n=arm.total_fix_load_n,
                projected_area_m2=None,
                wind_coefficient=None,
                wind_load_n=rounding.apply(
                    fsum(item.wind_load_n for item in in_case),
                    CalculationValueType.LOAD,
                ),
                load_center_height_m=arm.object_results[0].load_center_height_m,
                wind_moment_nm=None,
            )
            if seismic:
                row = _seismic_row(
                    row,
                    seismic_load_n=arm.total_seismic_load_n,
                    seismic_moment_nm=moment_sum(
                        obj.seismic_moment_at_pole_nm for obj in arm.object_results
                    ),
                    wind_torque_nm=moment_sum(item.wind_torque_nm for item in in_case),
                    seismic_torque_nm=moment_sum(item.seismic_torque_nm for item in in_case),
                )
            rows.append(row)
    for item in result.direct_object_aggregation.direct_object_results:
        wind = _in_case(item.directional_results, case_name)
        add(_row(
            "DIRECT_OBJECT", item.object_name,
            quantity=item.quantity,
            fix_load_n=item.fix_load_n,
            projected_area_m2=wind.projected_area_m2,
            wind_coefficient=item.cf,
            wind_load_n=wind.wind_load_n,
            load_center_height_m=item.load_center_height_m,
            wind_moment_nm=wind.wind_moment_nm,
        ), item)
    for item in result.overhead_wire_aggregation.wire_results:
        wind = _in_case(item.directional_results, case_name)
        add(_row(
            "OVERHEAD_WIRE", item.wire_name,
            quantity=1,
            fix_load_n=item.fix_load_n,
            projected_area_m2=wind.directional_projected_area_m2,
            wind_coefficient=item.cf,
            wind_load_n=wind.wind_load_n,
            load_center_height_m=item.load_center_height_m,
            wind_moment_nm=wind.wind_moment_nm,
            wind_tension_n=wind.wind_tension_n,
        ), item)
    # pole_results starts at the evaluated (lowest active) segment.
    for item in reversed(result.pole_aggregation.pole_results):
        add(_row(
            "POLE", item.geometry.pole_name,
            quantity=1,
            fix_load_n=item.fix_load_n,
            projected_area_m2=item.projected_area_m2,
            wind_coefficient=item.cf,
            wind_load_n=item.wind_load_n,
            load_center_height_m=item.geometry.load_center_height_m,
            wind_moment_nm=item.wind_moment_nm,
        ), item)
    return rows


# =============================================================================
# Design standard 7 (New JIL)
# =============================================================================
# Arm checks in the order the engine reports them; d_st 3 has only the wind one.
_ARM_CHECKS_7 = (
    ("arm_fix_load_bending", "fix_load_safety"),
    ("arm_wind_bending", "wind_combination_safety"),
    ("arm_seismic_bending", "seismic_combination_safety"),
)


def map_standard_7(
    *,
    request: PoleStandard7Request,
    standard: DesignStandard,
    positions: tuple[Standard7CalculationResult, ...],
    pole_sections: tuple[PoleSectionProperties, ...],
    wires,
    wire_results,
    arm_parts: tuple[ArmPart, ...],
    arm_results,
    poles: tuple[PoleObject, ...],
    pole_results: tuple[PoleCalculationResult, ...],
    direct_objects: tuple[DirectObject, ...],
    direct_object_results: tuple[DirectObjectCalculationResult, ...],
) -> dict:
    rounding = rounding_profile_for(standard.code)
    gravity = gravity_for_standard(standard.code)
    seismic_policy = standard.seismic_policy
    arms = [
        _arm_7(standard, rounding, part, result)
        for part, result in zip(arm_parts, arm_results, strict=True)
    ]
    evaluated_positions = [_evaluated_position_7(rounding, result) for result in positions]
    return {
        "schema_version": SCHEMA_VERSION,
        "design_standard": {"code": int(standard.code), "name": standard.name},
        "summary": _summary(arms, evaluated_positions),
        "conditions": _conditions(
            request,
            standard,
            rounding,
            # The values the engine used: the request's, or the New JIL default.
            seismic={
                "horizontal_acceleration_m_s2": seismic_policy.eqa_m_s2,
                "response_ratio": seismic_policy.eqr,
            },
        ),
        "overhead_wires": [
            _overhead_wire_7(rounding, wire, result)
            for wire, result in zip(wires, wire_results, strict=True)
        ],
        "arms": arms,
        "pole_sections": [
            _pole_section_7(rounding, gravity, sent, pole, section, result)
            for sent, pole, section, result in zip(
                request.poles, poles, pole_sections, pole_results, strict=True
            )
        ],
        "direct_objects": [
            _direct_object_7(rounding, item, result)
            for item, result in zip(direct_objects, direct_object_results, strict=True)
        ],
        "evaluated_positions": evaluated_positions,
    }


def _arm_7(standard: DesignStandard, rounding, part: ArmPart, result) -> dict:
    arm = _arm(standard, part, result)
    arm["specification"]["fix_load_per_meter_n_m"] = result.specification.fix_load_per_meter_n_m
    for item, engine_item in zip(arm["objects"], result.object_results, strict=True):
        item.update(
            mass_kg=engine_item.mass_kg,
            side_wind_load_n=engine_item.side_wind_load_n,
            seismic_load_n=engine_item.seismic_load_n,
            seismic_moment_nm=engine_item.seismic_moment_at_arm_support_nm,
        )
    arm["totals"].update(
        # Arm body and objects, each at its front.
        front_wind_load_n=rounding.apply(
            fsum(item.front_wind_load_n for item in result.object_results),
            CalculationValueType.LOAD,
        ),
        seismic_load_n=result.total_seismic_load_n,
        seismic_moment_nm=result.total_seismic_moment_at_arm_support_nm,
    )
    arm["checks"] = [
        _check(
            check,
            moment_nm=safety.moment_nm,
            stress_n_mm2=safety.bending_stress_n_mm2,
            allowable_n_mm2=safety.allowable_stress_n_mm2,
            ratio=safety.utilization_ratio,
            status=safety.status,
        )
        for check, attribute in _ARM_CHECKS_7
        for safety in (getattr(result, attribute),)
    ]
    return arm


def _evaluated_position_7(rounding, result: Standard7CalculationResult) -> dict:
    section = result.section_properties
    material = get_pole_material(result.material_name)
    stress_by_case = {
        item.wind_case_name: item for item in result.stress_result.direction_results
    }
    wire_by_case = {
        item.direction: item for item in result.overhead_wire_aggregation.directional_totals
    }
    wire = result.overhead_wire_aggregation
    return {
        "evaluated_position_m": result.evaluated_position_m,
        "pole_name": result.evaluated_pole_name,
        "section": {
            "material": result.material_name,
            "diameter_mm": section.diameter_mm,
            "thickness_mm": section.thickness_mm,
            "section_modulus_cm3": section.section_modulus_cm3,
            # Torsion uses the moment of inertia; Ip = 2I.
            "moment_of_inertia_cm4": section.moment_of_inertia_cm4,
            "polar_moment_of_inertia_cm4": result.stress_result.polar_moment_of_inertia_cm4,
        },
        "vertical_fix_load_n": result.total_fix_load_n,
        "seismic_load_n": result.total_seismic_load_n,
        "seismic_moment_nm": result.total_seismic_moment_nm,
        "seismic_tension_n": wire.total_seismic_tension_n,
        # Seismic load plus the wire seismic tension; the same in every direction.
        "resultant_seismic_load_n": rounding.apply(
            result.total_seismic_load_n + abs(wire.total_seismic_tension_n),
            CalculationValueType.LOAD,
        ),
        "component_totals": {
            name: {
                "fix_load_n": aggregation.total_fix_load_n,
                "seismic_load_n": aggregation.total_seismic_load_n,
                "seismic_moment_nm": aggregation.total_seismic_moment_nm,
            }
            for name, aggregation in _components(result).items()
        },
        "wind_cases": [
            {
                "code": case.wind_case_name,
                "angle_deg": case.wind_direction_deg,
                "load_rows": _load_rows(rounding, result, case.wind_case_name, seismic=True),
                "totals": {
                    "wind_load_n": case.total_wind_load_n,
                    "wind_load_x_n": case.total_wind_load_x_n,
                    "wind_load_y_n": case.total_wind_load_y_n,
                    "wind_tension_n": wire_by_case[case.wind_case_name].total_wind_tension_n,
                    "wind_tension_x_n": wire_by_case[case.wind_case_name].total_wind_tension_x_n,
                    "wind_tension_y_n": wire_by_case[case.wind_case_name].total_wind_tension_y_n,
                    "resultant_horizontal_load_n": case.resultant_wind_load_n,
                    "resultant_horizontal_load_x_n": case.resultant_wind_load_x_n,
                    "resultant_horizontal_load_y_n": case.resultant_wind_load_y_n,
                    "fix_load_moment_x_nm": case.moment_due_to_fix_load_x_nm,
                    "fix_load_moment_y_nm": case.moment_due_to_fix_load_y_nm,
                    "fix_load_moment_nm": case.moment_due_to_fix_load_nm,
                    # Wind only: no fix load and no wire tension.
                    "wind_moment_nm": _wind_moment_total(rounding, result, case.wind_case_name),
                    "wind_moment_x_nm": _wind_moment(rounding, result, case.wind_case_name, "x"),
                    "wind_moment_y_nm": _wind_moment(rounding, result, case.wind_case_name, "y"),
                    "wind_tension_moment_x_nm": (
                        wire_by_case[case.wind_case_name].total_wind_tension_moment_x_nm
                    ),
                    "wind_tension_moment_y_nm": (
                        wire_by_case[case.wind_case_name].total_wind_tension_moment_y_nm
                    ),
                    "combined_moment_x_nm": case.combined_wind_moment_x_nm,
                    "combined_moment_y_nm": case.combined_wind_moment_y_nm,
                    "combined_moment_nm": case.combined_wind_moment_nm,
                    "wind_torsional_moment_nm": case.wind_torsional_moment_nm,
                    "seismic_tension_moment_nm": (
                        wire_by_case[case.wind_case_name].total_seismic_tension_moment_nm
                    ),
                    "combined_seismic_moment_nm": case.combined_seismic_moment_nm,
                    "seismic_torsional_moment_nm": case.seismic_torsional_moment_nm,
                },
                "component_totals": _wind_components(rounding, result, case.wind_case_name),
                "checks": _pole_checks_7(material, stress_by_case[case.wind_case_name]),
            }
            for case in result.direction_results
        ],
    }


def _pole_checks_7(material, stress) -> list[dict]:
    """FixLoad (long-term), then wind and seismic (short-term): bending, torsion, combined."""
    bending = material.short_term_allowable_bending
    shear = material.require_shear()
    checks = [
        _check(
            "pole_fix_load_bending",
            moment_nm=stress.absolute_moment_due_to_fixload_nm,
            stress_n_mm2=stress.fixload_bending_stress_n_mm2,
            allowable_n_mm2=material.allowable_bending,
            ratio=stress.fixload_bending_utilization_ratio,
            status=stress.fixload_bending_status,
        )
    ]
    for case in ("wind", "seismic"):
        def value(name, case=case):
            return getattr(stress, name.format(case=case))

        checks += [
            _check(
                f"pole_{case}_bending",
                moment_nm=value("absolute_combined_{case}_moment_nm"),
                stress_n_mm2=value("{case}_bending_stress_n_mm2"),
                allowable_n_mm2=bending,
                ratio=value("{case}_bending_utilization_ratio"),
                status=value("{case}_bending_status"),
            ),
            _check(
                f"pole_{case}_torsion",
                moment_nm=value("absolute_{case}_torsional_moment_nm"),
                stress_n_mm2=value("{case}_torsional_shear_stress_n_mm2"),
                allowable_n_mm2=shear,
                ratio=value("{case}_torsional_utilization_ratio"),
                status=value("{case}_torsional_status"),
            ),
            _check(
                f"pole_{case}_combined",
                moment_nm=value("absolute_combined_{case}_moment_nm"),
                stress_n_mm2=value("{case}_maximum_combined_stress_n_mm2"),
                allowable_n_mm2=bending,
                ratio=value("{case}_combined_utilization_ratio"),
                status=value("{case}_combined_status"),
                maximum_shear_stress_n_mm2=value("{case}_maximum_shear_stress_n_mm2"),
            ),
        ]
    return checks


# ===== Design standard 7: values of each component =====
def _components(result: Standard7CalculationResult) -> dict:
    return {
        "pole": result.pole_aggregation,
        "direct_object": result.direct_object_aggregation,
        "arm": result.arm_aggregation,
        "overhead_wire": result.overhead_wire_aggregation,
    }


def _in_direction(aggregation, case_name: str):
    return next(item for item in aggregation.directional_totals if item.direction == case_name)


def _wind_moment(rounding, result: Standard7CalculationResult, case_name: str, axis: str) -> float:
    """Wind moment about one axis: pole, direct objects, arms and wires, without tension."""
    return rounding.apply(
        fsum(
            getattr(_in_direction(aggregation, case_name), f"total_wind_moment_{axis}_nm")
            for aggregation in _components(result).values()
        ),
        CalculationValueType.MOMENT,
    )


def _wind_moment_total(rounding, result: Standard7CalculationResult, case_name: str) -> float:
    """Sum of the wind moment of the four components in one direction."""
    return rounding.apply(
        fsum(
            item["wind_moment_nm"]
            for item in _wind_components(rounding, result, case_name).values()
        ),
        CalculationValueType.MOMENT,
    )


def _wind_components(rounding, result: Standard7CalculationResult, case_name: str) -> dict:
    """Wind load and wind moment of each component in one direction.

    The pole moment is the sum of every step pole above the position. The arm
    moment is the sum, over every arm object, of load centre height x wind load
    in this direction, each product rounded first.
    """
    pole = _in_direction(result.pole_aggregation, case_name)
    direct = _in_direction(result.direct_object_aggregation, case_name)
    arm = _in_direction(result.arm_aggregation, case_name)
    wire = _in_direction(result.overhead_wire_aggregation, case_name)

    def moment_sum(values):
        return rounding.apply(fsum(values), CalculationValueType.MOMENT)

    arm_moments = [
        rounding.apply(
            item.load_center_height_m * _in_case(item.directional_results, case_name).wind_load_n,
            CalculationValueType.MOMENT,
        )
        for part in result.arm_aggregation.arm_results
        for item in part.object_results
    ]
    return {
        "pole": {
            "wind_load_n": pole.total_wind_load_n,
            "wind_moment_nm": moment_sum(
                item.wind_moment_nm for item in result.pole_aggregation.pole_results
            ),
        },
        "direct_object": {
            "wind_load_n": direct.total_wind_load_n,
            "wind_moment_nm": direct.total_wind_moment_nm,
        },
        "arm": {"wind_load_n": arm.total_wind_load_n, "wind_moment_nm": moment_sum(arm_moments)},
        "overhead_wire": {
            "wind_load_n": wire.total_wind_load_n,
            "wind_moment_nm": wire.total_wind_moment_nm,
        },
    }


def _pole_section_7(rounding, gravity: float, sent, pole: PoleObject,
                    section: PoleSectionProperties, result: PoleCalculationResult) -> dict:
    """The d_st 3 section plus the whole step pole, from its lower end.

    The fix load per metre follows the New JIL sequence: mass per metre at the
    average of the lower and upper size, then x gravity, each rounded.
    """
    mass_per_meter = rounding.apply(
        pole.mass_kg(1.0, pole.diameter_lower_mm, pole.diameter_upper_mm),
        CalculationValueType.WEIGHT_PER_METER,
    )
    return {
        **_pole_section(sent, section),
        "section_modulus_cm3": section.section_modulus_cm3,
        "length_m": result.geometry.full_length_m,
        "mass_kg": result.mass_kg,
        "fix_load_n": result.fix_load_n,
        "fix_load_per_meter_n_m": rounding.apply(
            mass_per_meter * gravity, CalculationValueType.WEIGHT_PER_METER
        ),
        "projected_area_m2": result.projected_area_m2,
    }


def _direct_object_7(rounding, item: DirectObject, result: DirectObjectCalculationResult) -> dict:
    """Wind load on the front and on the side, independent of the wind direction.
    An Omni object takes the front load from every side."""

    def wind_load(area_m2: float) -> float:
        return rounding.apply(
            area_m2 * result.quantity * result.cf * result.wind_pressure_n_m2,
            CalculationValueType.LOAD,
        )

    return {
        "name": result.object_name,
        "quantity": result.quantity,
        "mass_kg": result.total_mass_kg,
        "front_wind_load_n": wind_load(item.front_area_m2),
        "side_wind_load_n": wind_load(
            item.front_area_m2 if item.object_type is DirectObjectType.OMNI else item.side_area_m2
        ),
    }


def _overhead_wire_7(rounding, wire: OverheadWire, result: OverheadWireCalculationResult) -> dict:
    """The d_st 3 wire plus seismic values, mass, front wind load, and the line
    load and tension with the wind straight (90 degrees) and oblique (45 degrees)
    to the wire."""

    def at_angle_of_attack(angle_rad: float) -> dict:
        # Angle of attack = fixed angle - wind angle.
        wind_angle_rad = wire.fixed_angle_rad - angle_rad
        line_load = rounding.apply(
            wire.combined_wind_line_load_n_m(result.wind_pressure_n_m2, result.cf, wind_angle_rad),
            CalculationValueType.WIRE_LOAD_COMBINATION,
        )
        return {
            "combined_wind_line_load_n_m": line_load,
            "wind_tension_n": rounding.apply(
                wire.tension_from_line_load(line_load), CalculationValueType.LOAD
            ),
        }

    return {
        **_overhead_wire(rounding, wire, result),
        "mass_kg": result.total_mass_kg,
        "front_wind_load_n": rounding.apply(
            result.projected_area_m2 * result.cf * result.wind_pressure_n_m2,
            CalculationValueType.LOAD,
        ),
        "straight_wind": at_angle_of_attack(pi / 2),
        "oblique_wind": at_angle_of_attack(pi / 4),
        "seismic_load_n": result.seismic_load_n,
        "seismic_tension_n": result.seismic_tension_n,
    }
