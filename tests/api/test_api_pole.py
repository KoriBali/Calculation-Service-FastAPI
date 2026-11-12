"""POST /api/pole/calculate (design standard 3 and 7, schema 2.2): contract and validation."""

import copy

import pytest

from app.pole.docs import REQUEST_EXAMPLES

URL = "/api/pole/calculate"


def example(name: str) -> dict:
    return copy.deepcopy(REQUEST_EXAMPLES[name]["value"])


def calculate(client, body: dict) -> dict:
    response = client.post(URL, json=body)
    assert response.status_code == 200, response.json()
    return response.json()["data"]


def error_fields(response) -> set[str]:
    return {item["field"] for item in response.json()["errors"]}


def all_keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in all_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in all_keys(item)}
    return set()


def all_checks(data: dict) -> list[dict]:
    return [check for arm in data["arms"] for check in arm["checks"]] + [
        check
        for position in data["evaluated_positions"]
        for case in position["wind_cases"]
        for check in case["checks"]
    ]


STANDARD_NAMES = {3: "Old Lighting Pole", 7: "New JIL"}
NEW_JIL_CASES = ["N", "S", "E", "W", "NE", "SW", "NW", "SE"]
NEW_JIL_POLE_CHECKS = [
    "pole_fix_load_bending",
    "pole_wind_bending", "pole_wind_torsion", "pole_wind_combined",
    "pole_seismic_bending", "pole_seismic_torsion", "pole_seismic_combined",
]


# ===== Contract =====
@pytest.mark.parametrize("name", REQUEST_EXAMPLES)
def test_every_openapi_example_returns_200(client, name):
    body = example(name)
    data = calculate(client, body)
    code = body["design_standard"]
    assert data["schema_version"] == "2.2"
    assert data["design_standard"] == {"code": code, "name": STANDARD_NAMES[code]}


@pytest.mark.parametrize("name", REQUEST_EXAMPLES)
def test_response_keys_are_snake_case_and_statuses_are_codes(client, name):
    data = calculate(client, example(name))
    camel = {key for key in all_keys(data) if key != key.lower()}
    assert not camel, f"camelCase keys in response: {sorted(camel)}"
    assert {check["status"] for check in all_checks(data)} <= {"OK", "NG"}
    assert data["summary"]["status"] in {"OK", "NG"}


def test_case_3_matches_python_calc_report_values(client):
    """The values python_calc 270d23b locks for its Case 3 report (tests/test_standard_output.py)."""
    data = calculate(client, example("arm_and_overhead_wire"))
    conditions = data["conditions"]
    assert (conditions["wind_speed_m_s"], conditions["air_density_kg_m3"]) == (60.0, 1.23)
    assert conditions["wind_pressure_n_m2"] == 2214.0
    assert conditions["wind_cases"] == [{"code": "STRAIGHT", "angle_deg": 90.0}]

    arm = data["arms"][0]
    assert arm["specification"]["section_modulus_cm3"] == 9.03
    assert arm["specification"]["unit_weight_kg_m"] == 5.31
    assert arm["totals"] == {"fix_load_n": 146.7, "fix_load_moment_nm": 25.5, "wind_moment_nm": 53.3}
    assert arm["checks"][0]["moment_nm"] == 59.1
    assert arm["checks"][0]["utilization_ratio"] == 0.028
    assert [item["object_type"] for item in arm["objects"]] == ["ArmBody", "Omni"]

    straight, taper = data["pole_sections"]
    assert (straight["name"], taper["name"]) == ("Pole-2", "Pole-1")
    assert straight == {
        "name": "Pole-2",
        "pole_type": "Straight",
        "material": "STK400",
        "diameter_mm": 175.0,
        "thickness_mm": 4.0,
        "cross_section_area_cm2": 21.49,
        "moment_of_inertia_cm4": 785.86,
        "radius_of_gyration_cm": 6.05,
        "unit_weight_kg_m": 16.87,
    }

    position = data["evaluated_positions"][0]
    assert position["section"] == {
        "material": "STK400",
        "diameter_mm": 175.0,
        "thickness_mm": 4.0,
        "section_modulus_cm3": 89.81,
    }
    assert position["vertical_fix_load_n"] == 1343.4
    (case,) = position["wind_cases"]
    assert [row["kind"] for row in case["load_rows"]] == ["ARM", "OVERHEAD_WIRE", "POLE", "POLE"]
    arm_row = case["load_rows"][0]
    assert arm_row["wind_load_n"] == 304.8
    assert (arm_row["projected_area_m2"], arm_row["wind_coefficient"]) == (None, None)
    assert case["totals"]["wind_load_n"] == 2398.4
    assert case["totals"]["arm_fix_load_moment_nm"] == 25.5
    assert case["totals"]["resultant_horizontal_load_n"] == 2623.7
    assert case["totals"]["combined_moment_nm"] == 13992.1
    check = case["checks"][0]
    assert (check["stress_n_mm2"], check["utilization_ratio"], check["status"]) == (155.8, 0.663, "OK")

    assert data["summary"] == {
        "status": "OK",
        "governing": {
            "component": "pole",
            "name": "Pole-2",
            "evaluated_position_m": 0.0,
            "wind_case": "STRAIGHT",
            "check": "pole_bending",
            "utilization_ratio": 0.663,
        },
    }


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"wind_speed_m_s": 50}, (50.0, 1.23, 1538.0)),
        ({"air_density_kg_m3": 1.2}, (60.0, 1.2, 2160.0)),
    ],
    ids=["wind-speed", "air-density"],
)
def test_wind_speed_and_air_density_come_from_the_request(client, change, expected):
    """The gateway sends the master default or the user's value; the engine must use it."""
    request = example("arm_and_overhead_wire")
    default = calculate(client, request)
    request.update(change)
    data = calculate(client, request)
    conditions = data["conditions"]
    assert (
        conditions["wind_speed_m_s"],
        conditions["air_density_kg_m3"],
        conditions["wind_pressure_n_m2"],
    ) == expected
    assert data["arms"][0]["totals"]["wind_moment_nm"] != default["arms"][0]["totals"]["wind_moment_nm"]


def test_oblique_wind_adds_a_case_everywhere(client):
    data = calculate(client, example("direct_object_oblique"))
    expected = ["STRAIGHT", "OBLIQUE"]
    assert [case["code"] for case in data["conditions"]["wind_cases"]] == expected
    for position in data["evaluated_positions"]:
        assert [case["code"] for case in position["wind_cases"]] == expected


def test_summary_is_ng_when_any_check_fails(client):
    body = example("pole_only")
    body["direct_objects"] = [{
        "name": "Heavy sign", "object_type": "Omni", "front_area_m2": 3.0,
        "mass_per_unit_kg": 50, "elevation_m": 6.0, "base_wind_coefficient": 1.2, "quantity": 1,
    }]
    data = calculate(client, body)
    ratios = [check["utilization_ratio"] for check in all_checks(data)]
    assert data["summary"]["status"] == "NG"
    assert data["summary"]["governing"]["utilization_ratio"] == max(ratios) > 1.0


def test_wire_and_arm_below_every_position_are_still_reported(client):
    body = example("arm_and_overhead_wire")
    body["arms"][0]["installation_height_m"] = 5.0
    body["overhead_wires"][0]["elevation_m"] = 5.0
    body["evaluated_positions_m"] = [8.0]
    data = calculate(client, body)
    assert [arm["name"] for arm in data["arms"]] == ["Arm-1"]
    assert [wire["name"] for wire in data["overhead_wires"]] == ["OHW-1"]
    kinds = {row["kind"] for row in data["evaluated_positions"][0]["wind_cases"][0]["load_rows"]}
    assert kinds == {"POLE"}


def test_every_step_pole_has_a_section_at_its_lower_end(client):
    body = example("direct_object_oblique")
    body["evaluated_positions_m"] = [0.0]  # only Pole-3 holds a check position
    data = calculate(client, body)
    sections = {item["name"]: item for item in data["pole_sections"]}
    assert list(sections) == ["Pole-1", "Pole-2", "Pole-3"]
    assert sections["Pole-1"]["diameter_mm"] == 75.0
    assert (sections["Pole-1"]["cross_section_area_cm2"], sections["Pole-1"]["unit_weight_kg_m"]) == (9.97, 7.82)
    # The taper is taken at its lower diameter, the same as Pole-3 below it.
    assert {**sections["Pole-2"], "name": None, "pole_type": None} == {
        **sections["Pole-3"],
        "name": None,
        "pole_type": None,
    }


# ===== Design standard 7 (New JIL) =====
def test_new_jil_matches_python_calc_values(client):
    """LA10B, the same values python_calc_V2 manual_check_taper_pole_l_dst7.py prints."""
    data = calculate(client, example("new_jil_arm"))
    conditions = data["conditions"]
    assert conditions["gravity_m_s2"] == 9.81
    assert conditions["wind_pressure_n_m2"] == 2214.0
    assert [case["code"] for case in conditions["wind_cases"]] == NEW_JIL_CASES
    assert conditions["seismic"] == {"horizontal_acceleration_m_s2": 4.71, "response_ratio": 1.0}

    arm = data["arms"][0]
    assert [check["check"] for check in arm["checks"]] == [
        "arm_fix_load_bending", "arm_wind_bending", "arm_seismic_bending",
    ]
    assert [check["utilization_ratio"] for check in arm["checks"]] == [0.0181, 0.0229, 0.0133]
    assert arm["totals"] == {
        "fix_load_n": 146.0, "fix_load_moment_nm": 25.5, "wind_moment_nm": 41.3,
        "seismic_load_n": 70.4, "seismic_moment_nm": 12.3,
    }
    lamp = arm["objects"][1]
    assert (lamp["front_wind_load_n"], lamp["side_wind_load_n"], lamp["seismic_load_n"]) == (221.0, 221.0, 65.9)

    base = next(p for p in data["evaluated_positions"] if p["evaluated_position_m"] == 0.0)
    assert base["section"] == {
        "material": "STK400", "diameter_mm": 175.0, "thickness_mm": 4.0, "section_modulus_cm3": 89.8,
        "moment_of_inertia_cm4": 786.0, "polar_moment_of_inertia_cm4": 1572.0,
    }
    assert (base["vertical_fix_load_n"], base["seismic_load_n"], base["seismic_moment_nm"]) == (1290.0, 616.0, 2950.0)
    cases = {case["code"]: case for case in base["wind_cases"]}
    assert list(cases) == NEW_JIL_CASES
    north, north_east = cases["N"], cases["NE"]
    assert north["totals"]["combined_moment_nm"] == 10200.0
    assert north["totals"]["fix_load_moment_nm"] == 25.5
    assert north["totals"]["combined_seismic_moment_nm"] == 2950.0
    assert (north["totals"]["wind_torsional_moment_nm"], north_east["totals"]["wind_torsional_moment_nm"]) == (-41.3, -40.6)
    checks = {check["check"]: check for check in north["checks"]}
    assert list(checks) == NEW_JIL_POLE_CHECKS
    assert (checks["pole_wind_bending"]["stress_n_mm2"], checks["pole_wind_bending"]["utilization_ratio"]) == (114.0, 0.485)
    assert checks["pole_wind_torsion"]["allowable_stress_n_mm2"] == 136  # STK400 short-term shear
    assert checks["pole_fix_load_bending"]["allowable_stress_n_mm2"] == 156
    assert "maximum_shear_stress_n_mm2" in checks["pole_wind_combined"]
    arm_row = north["load_rows"][0]
    assert (arm_row["kind"], arm_row["wind_torque_nm"], arm_row["seismic_torque_nm"]) == ("ARM", -41.3, -12.3)
    assert {row["kind"]: row["wind_torque_nm"] for row in north["load_rows"]}["POLE"] is None

    assert data["summary"] == {
        "status": "OK",
        "governing": {
            "component": "pole",
            "name": "Pole-3",
            "evaluated_position_m": 0.0,
            "wind_case": "N",
            "check": "pole_wind_bending",
            "utilization_ratio": 0.485,
        },
    }


def test_new_jil_every_position_has_eight_cases_and_seven_checks(client):
    data = calculate(client, example("new_jil_wire_and_seismic"))
    for position in data["evaluated_positions"]:
        assert [case["code"] for case in position["wind_cases"]] == NEW_JIL_CASES
        for case in position["wind_cases"]:
            assert [check["check"] for check in case["checks"]] == NEW_JIL_POLE_CHECKS
            assert all("seismic_load_n" in row for row in case["load_rows"])
    (wire,) = data["overhead_wires"]
    assert wire["seismic_tension_n"] > 0


def test_new_jil_seismic_inputs_default_and_come_from_the_request(client):
    """Left out -> the engine default; sent -> the engine uses the request's value."""
    default = calculate(client, example("new_jil_arm"))
    explicit = example("new_jil_arm")
    explicit.update(horizontal_acceleration_m_s2=4.71, response_ratio=1.0)
    assert calculate(client, explicit) == default

    changed = example("new_jil_arm")
    changed.update(horizontal_acceleration_m_s2=5.0, response_ratio=1.2)
    data = calculate(client, changed)
    assert data["conditions"]["seismic"] == {"horizontal_acceleration_m_s2": 5.0, "response_ratio": 1.2}
    seismic = data["arms"][0]["totals"]["seismic_load_n"]
    assert seismic > default["arms"][0]["totals"]["seismic_load_n"]
    assert data["evaluated_positions"][1]["seismic_load_n"] > default["evaluated_positions"][1]["seismic_load_n"]


def test_omni_arm_side_area_drives_new_jil_torque(client):
    """As VBA/python_calc: Omni wind load uses the front area, torque also the side area."""
    without_side = example("new_jil_arm")
    del without_side["arms"][0]["objects"][0]["side_area_m2"]
    with_side = calculate(client, example("new_jil_arm"))
    plain = calculate(client, without_side)

    def torque(data, code):
        case = next(c for c in data["evaluated_positions"][1]["wind_cases"] if c["code"] == code)
        return case["totals"]["wind_torsional_moment_nm"]

    assert (torque(with_side, "NE"), torque(plain, "NE")) == (-40.6, -20.7)
    assert torque(with_side, "N") == torque(plain, "N")
    assert plain["arms"][0]["objects"][1]["side_wind_load_n"] == 0.0


# ===== Upper/lower and Omni: ignored values do not change any result =====
def test_straight_pole_ignores_upper_values(client):
    plain = example("direct_object_oblique")
    with_upper = example("direct_object_oblique")
    for pole in with_upper["poles"]:
        if pole["pole_type"] == "Straight":
            pole.update(diameter_upper_mm=999, thickness_upper_mm=99)
    assert calculate(client, with_upper) == calculate(client, plain)


def test_omni_objects_ignore_side_area_and_angle(client):
    """Design standard 3 has no torque, so an Omni side area changes no value."""
    plain = example("arm_and_overhead_wire")
    plain["direct_objects"] = [{
        "name": "Lamp", "object_type": "Omni", "front_area_m2": 0.2,
        "mass_per_unit_kg": 10, "elevation_m": 10.1, "base_wind_coefficient": 1.0, "quantity": 2,
    }]
    with_side = copy.deepcopy(plain)
    with_side["direct_objects"][0].update(side_area_m2=5.0, fixed_angle_deg=30)
    with_side["arms"][0]["objects"][0]["side_area_m2"] = 5.0
    assert calculate(client, with_side) == calculate(client, plain)


# ===== Validation =====
@pytest.mark.parametrize(
    ("change", "field"),
    [
        (lambda r: r.update(design_standard=2), "design_standard"),
        (lambda r: r.update(seismic={"position": "Ground", "k_value": 0.5}), "seismic"),
        (lambda r: r.update(wind={"design_standard": 3}), "wind"),
        (lambda r: r["poles"][1].pop("diameter_upper_mm"), "poles.1"),
        (lambda r: r["poles"][0].pop("thickness_lower_mm"), "poles.0.thickness_lower_mm"),
        (lambda r: r["poles"][0].update(material="SS400"), "poles.0.material"),
        (lambda r: r["poles"][0].update(diameter_mm=175), "poles.0.diameter_mm"),
        (lambda r: r.update(poles=[]), "poles"),
        (lambda r: r.update(evaluated_positions_m=[]), "evaluated_positions_m"),
        (lambda r: r.update(overdesign_factor=0), "overdesign_factor"),
        (lambda r: r["arms"][0]["objects"][0].update(object_type="Directional"), "arms.0.objects.0"),
        (lambda r: r["arms"][0]["objects"][0].update(object_type="ArmBody"), "arms.0.objects.0.object_type"),
        (lambda r: r["overhead_wires"][0].pop("span_length_m"), "overhead_wires.0.span_length_m"),
        (lambda r: r.pop("wind_speed_m_s"), "wind_speed_m_s"),
        (lambda r: r.pop("air_density_kg_m3"), "air_density_kg_m3"),
        (lambda r: r.update(wind_speed_m_s=0), "wind_speed_m_s"),
        (lambda r: r.update(air_density_kg_m3=-1.23), "air_density_kg_m3"),
    ],
    ids=[
        "other-standard", "seismic-not-allowed", "old-wind-object", "taper-without-upper",
        "missing-lower", "unknown-material", "old-straight-field", "no-poles", "no-positions",
        "zero-overdesign", "directional-arm-object-without-side", "arm-body-is-generated",
        "wire-without-span", "no-wind-speed", "no-air-density", "zero-wind-speed",
        "negative-air-density",
    ],
)
def test_schema_errors_return_422_with_field(client, change, field):
    request = example("arm_and_overhead_wire")
    change(request)
    response = client.post(URL, json=request)
    assert response.status_code == 422
    assert response.json()["success"] is False
    assert field in error_fields(response)


@pytest.mark.parametrize(
    ("name", "change", "field"),
    [
        ("arm_and_overhead_wire", lambda r: r.pop("design_standard"), "design_standard"),
        ("arm_and_overhead_wire", lambda r: r.update(design_standard="3"), "design_standard"),
        ("arm_and_overhead_wire", lambda r: r.update(horizontal_acceleration_m_s2=4.71), "horizontal_acceleration_m_s2"),
        ("arm_and_overhead_wire", lambda r: r.update(response_ratio=1.0), "response_ratio"),
        ("new_jil_arm", lambda r: r.update(include_oblique_wind=True), "include_oblique_wind"),
        ("new_jil_arm", lambda r: r.update(horizontal_acceleration_m_s2=0), "horizontal_acceleration_m_s2"),
        ("new_jil_arm", lambda r: r.update(response_ratio=-1), "response_ratio"),
        ("new_jil_arm", lambda r: r.pop("wind_speed_m_s"), "wind_speed_m_s"),
        ("new_jil_arm", lambda r: r["poles"][1].pop("diameter_upper_mm"), "poles.1"),
        ("new_jil_arm", lambda r: r["arms"][0]["objects"][0].update(object_type="Directional", side_area_m2=None), "arms.0.objects.0"),
    ],
    ids=[
        "no-standard", "standard-as-string", "seismic-on-standard-3", "response-ratio-on-standard-3",
        "oblique-on-standard-7", "zero-acceleration", "negative-response-ratio",
        "standard-7-no-wind-speed", "standard-7-taper-without-upper", "standard-7-directional-arm-object",
    ],
)
def test_field_path_has_no_design_standard_tag(client, name, change, field):
    """The body is a union on design_standard; error paths stay the plain field path."""
    request = example(name)
    change(request)
    response = client.post(URL, json=request)
    assert response.status_code == 422
    assert field in error_fields(response)


def test_directional_direct_object_needs_side_area_and_angle(client):
    request = example("direct_object_oblique")
    del request["direct_objects"][0]["fixed_angle_deg"]
    response = client.post(URL, json=request)
    assert response.status_code == 422
    assert "direct_objects.0" in error_fields(response)


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["poles"].append(dict(r["poles"][0], top_elevation_m=9.0)),
        lambda r: r["poles"].append(dict(r["poles"][0], name="Pole-9")),
        lambda r: r["arms"][0]["objects"].append(dict(r["arms"][0]["objects"][0])),
        lambda r: r["overhead_wires"].append(dict(r["overhead_wires"][0])),
        lambda r: r.update(evaluated_positions_m=[1.0, 1.0]),
        lambda r: r.update(base_elevation_m=-0.5, evaluated_positions_m=[-1.0]),
    ],
    ids=[
        "duplicate-pole-name", "duplicate-top-elevation", "duplicate-arm-object-name",
        "duplicate-wire-name", "duplicate-position", "below-base",
    ],
)
def test_cross_field_errors_return_422(client, change):
    request = example("arm_and_overhead_wire")
    change(request)
    assert client.post(URL, json=request).status_code == 422


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r.update(evaluated_positions_m=[10.1]), "EvaluatedPosition must be below the top"),
        (lambda r: r["arms"][0].update(exposed_length_m=1.0), "exposed_length_m cannot exceed total_length_m"),
        (lambda r: r["arms"][0].update(thickness_mm=40), "thickness_mm must be less than half the diameter"),
    ],
    ids=["position-at-top", "arm-exposed-too-long", "arm-too-thick"],
)
def test_engine_rule_error_returns_422_with_message(client, change, message):
    request = example("arm_and_overhead_wire")
    change(request)
    response = client.post(URL, json=request)
    assert response.status_code == 422
    assert message in response.json()["message"]


@pytest.mark.parametrize(
    ("standard_key", "field"),
    [("designStandard", "design_standard"), ("design_standard", "evaluatedPositionsM")],
    ids=["camel-standard", "camel-fields"],
)
def test_camel_case_body_is_rejected(client, standard_key, field):
    """The contract is snake_case only; camelCase is converted by the gateway.

    The body is a union on design_standard: without that snake_case key the
    standard is unknown, so only design_standard is reported.
    """
    body = {
        standard_key: 3,
        "windSpeedMS": 60,
        "poles": [{
            "name": "P", "poleType": "Straight", "diameterLowerMm": 139.8,
            "thicknessLowerMm": 4.5, "material": "STK400", "topElevationM": 8.0,
        }],
        "evaluatedPositionsM": [0.0],
    }
    response = client.post(URL, json=body)
    assert response.status_code == 422
    assert field in error_fields(response)


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        ("not json", "text/plain"),
        ("not json", "application/json"),
        ("", "application/json"),
        ("[]", "application/json"),
        ('"text"', "application/json"),
    ],
    ids=["text-plain", "invalid-json", "empty", "json-list", "json-string"],
)
def test_non_json_object_body_returns_400(client, content, content_type):
    response = client.post(URL, content=content, headers={"Content-Type": content_type})
    assert response.status_code == 400
    assert response.json() == {
        "success": False,
        "message": "Request body harus berupa JSON object",
    }
