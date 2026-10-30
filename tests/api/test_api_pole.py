"""POST /api/pole/calculate (design standard 3, schema 2.0): contract and validation."""

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


# ===== Contract =====
@pytest.mark.parametrize("name", REQUEST_EXAMPLES)
def test_every_openapi_example_returns_200(client, name):
    data = calculate(client, example(name))
    assert data["schema_version"] == "2.0"
    assert data["design_standard"] == {"code": 3, "name": "Old Lighting Pole"}


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
    assert arm["totals"] == {"fix_load_n": 146.7, "fix_load_moment_nm": 25.5, "wind_moment_nm": 53.3}
    assert arm["checks"][0]["moment_nm"] == 59.1
    assert arm["checks"][0]["utilization_ratio"] == 0.028
    assert [item["object_type"] for item in arm["objects"]] == ["ArmBody", "Omni"]

    position = data["evaluated_positions"][0]
    assert position["section"]["section_modulus_cm3"] == 89.81
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


# ===== Upper/lower and Omni: ignored values do not change any result =====
def test_straight_pole_ignores_upper_values(client):
    plain = example("direct_object_oblique")
    with_upper = example("direct_object_oblique")
    for pole in with_upper["poles"]:
        if pole["pole_type"] == "Straight":
            pole.update(diameter_upper_mm=999, thickness_upper_mm=99)
    assert calculate(client, with_upper) == calculate(client, plain)


def test_omni_objects_ignore_side_area_and_angle(client):
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
    ],
    ids=[
        "other-standard", "seismic-not-allowed", "old-wind-object", "taper-without-upper",
        "missing-lower", "unknown-material", "old-straight-field", "no-poles", "no-positions",
        "zero-overdesign", "directional-arm-object-without-side", "arm-body-is-generated",
        "wire-without-span",
    ],
)
def test_schema_errors_return_422_with_field(client, change, field):
    request = example("arm_and_overhead_wire")
    change(request)
    response = client.post(URL, json=request)
    assert response.status_code == 422
    assert response.json()["success"] is False
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


def test_camel_case_body_is_rejected(client):
    """The contract is snake_case only; camelCase is converted by the gateway."""
    body = {
        "designStandard": 3,
        "poles": [{
            "name": "P", "poleType": "Straight", "diameterLowerMm": 139.8,
            "thicknessLowerMm": 4.5, "material": "STK400", "topElevationM": 8.0,
        }],
        "evaluatedPositionsM": [0.0],
    }
    response = client.post(URL, json=body)
    assert response.status_code == 422
    assert "evaluatedPositionsM" in error_fields(response)


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
