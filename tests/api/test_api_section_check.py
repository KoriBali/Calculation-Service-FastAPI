"""POST /api/section-check/calculate: contract, validation, and parity."""

import copy

import pytest

from tests.parity.parity import assert_matches, case_names, load_fixture

URL = "/api/section-check/calculate"

# Cases that the API can run before D6 (no overhead wire).
API_CASES = [
    name for name in case_names() if not load_fixture(name)["input"]["overhead_wires"]
]

# Fields the engine kwargs carry but the API refuses for that variant.
TAPER_ONLY = ("diameter_lower_mm", "diameter_upper_mm", "thickness_lower_mm", "thickness_upper_mm")
DIRECTIONAL_ONLY = ("side_area_m2", "fixed_angle_deg")


def to_request(case_input: dict, with_seismic: bool = True) -> dict:
    """Fixture input (engine kwargs) -> request body (API contract).

    Both are snake_case; only the variant-specific fields differ.
    """
    poles = []
    for pole in case_input["poles"]:
        body = dict(pole)
        if pole["pole_type"] == "Straight":
            body["diameter_mm"] = pole["diameter_lower_mm"]
            body["thickness_mm"] = pole["thickness_lower_mm"]
            for key in TAPER_ONLY:
                del body[key]
        poles.append(body)

    direct_objects = []
    for item in case_input["direct_objects"]:
        body = dict(item)
        if item["object_type"] == "Omni":
            for key in DIRECTIONAL_ONLY:
                del body[key]
        direct_objects.append(body)

    request = {
        "wind": dict(case_input["wind"]),
        "overdesign_factor": case_input["overdesign_factor"],
        "base_elevation_m": case_input["base_elevation_m"],
        "poles": poles,
        "direct_objects": direct_objects,
        "evaluated_positions_m": case_input["evaluated_positions_m"],
    }
    if with_seismic:
        request["seismic"] = dict(case_input["seismic"])
    return request


@pytest.mark.parametrize("with_seismic", [True, False], ids=["seismic", "no-seismic"])
@pytest.mark.parametrize("name", API_CASES)
def test_response_matches_python_calc(client, name, with_seismic):
    fixture = load_fixture(name)
    response = client.post(URL, json=to_request(fixture["input"], with_seismic))

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["checks"] == (["wind", "seismic"] if with_seismic else ["wind"])

    for actual, expected in zip(
        data["evaluated_positions"], fixture["expected"]["positions"], strict=True
    ):
        label = f"{name}@{expected['evaluated_position_m']}"
        assert actual["evaluated_position_m"] == expected["evaluated_position_m"]
        for key in ("pole", "direct_object", "section_check"):
            assert_matches(
                actual[key],
                expected[key],
                f"{label}.{key}",
                seismic_absent=not with_seismic,
            )


def test_camel_case_body_is_rejected(client):
    """The contract is snake_case only; camelCase is converted by the gateway."""
    body = {
        "wind": {"designStandard": 3, "structureHeightM": 8.0},
        "poles": [{
            "name": "P", "poleType": "Straight", "diameterMm": 139.8,
            "thicknessMm": 4.5, "material": "STK400", "topElevationM": 8.0,
        }],
        "evaluatedPositionsM": [0.0],
    }
    response = client.post(URL, json=body)
    assert response.status_code == 422
    assert "evaluatedPositionsM" in error_fields(response)


def all_keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in all_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in all_keys(item)}
    return set()


@pytest.mark.parametrize("name", API_CASES)
def test_response_keys_are_snake_case(client, name):
    response = client.post(URL, json=to_request(load_fixture(name)["input"]))
    camel = {key for key in all_keys(response.json()) if key != key.lower()}
    assert not camel, f"camelCase keys in response: {sorted(camel)}"


def base_request() -> dict:
    return to_request(load_fixture("case_pole_only_std2")["input"])


def error_fields(response) -> set[str]:
    return {item["field"] for item in response.json()["errors"]}


@pytest.mark.parametrize(
    ("change", "field"),
    [
        (lambda r: r["wind"].update(design_standard=1), "wind.1.atmospheric_category"),
        (lambda r: r["wind"].update(design_standard=9), "wind"),
        (lambda r: r["wind"].update(atmospheric_category=2), "wind.2.atmospheric_category"),
        (lambda r: r.update(seismic={"position": "Rooftop"}), "seismic.Rooftop.seismic_class"),
        (lambda r: r["poles"][0].update(material="SS400"), "poles.0.Straight.material"),
        (lambda r: r["poles"][0].pop("thickness_mm"), "poles.0.Straight.thickness_mm"),
        (lambda r: r.update(poles=[]), "poles"),
        (lambda r: r.update(evaluated_positions_m=[]), "evaluated_positions_m"),
        (lambda r: r.update(overhead_wires=[]), "overhead_wires"),
        (lambda r: r.update(overdesign_factor=0), "overdesign_factor"),
    ],
)
def test_schema_errors_return_422_with_field(client, change, field):
    request = copy.deepcopy(base_request())
    change(request)
    response = client.post(URL, json=request)
    assert response.status_code == 422
    assert response.json()["success"] is False
    assert field in error_fields(response)


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["poles"].append(dict(r["poles"][0], top_elevation_m=9.0)),
        lambda r: r.update(evaluated_positions_m=[1.0, 1.0]),
        lambda r: r.update(evaluated_positions_m=[0.0]),  # base is 0.5
    ],
    ids=["duplicate-pole-name", "duplicate-position", "below-base"],
)
def test_cross_field_errors_return_422(client, change):
    request = copy.deepcopy(base_request())
    change(request)
    assert client.post(URL, json=request).status_code == 422


def test_engine_rule_error_returns_422_with_message(client):
    request = base_request() | {"evaluated_positions_m": [6.0]}  # top of the only pole
    response = client.post(URL, json=request)
    assert response.status_code == 422
    assert "EvaluatedPosition must be below the top" in response.json()["message"]


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