from app.engine.conditions.wind import WindCondition
from app.pole.schemas import PoleCalculationRequest
from app.shared.mappers import map_result, map_wind_condition

SCHEMA_VERSION = "1.0"


def map_pole_calculation(
    request: PoleCalculationRequest,
    wind: WindCondition,
    has_seismic: bool,
    positions: list[tuple],
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "checks": ["wind", "seismic"] if has_seismic else ["wind"],
        "design_condition": {
            "wind": map_wind_condition(wind),
            "seismic": None if request.seismic is None else request.seismic.model_dump(),
            "overdesign_factor": request.overdesign_factor,
            "base_elevation_m": request.base_elevation_m,
        },
        "evaluated_positions": [
            {
                "evaluated_position_m": position,
                "pole": map_result(pole),
                "direct_object": map_result(direct_object),
                "section_check": map_result(section),
            }
            for position, pole, direct_object, section in positions
        ],
    }
