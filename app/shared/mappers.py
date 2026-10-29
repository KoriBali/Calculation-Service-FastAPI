"""Engine results -> JSON-ready dicts. Values are already rounded by the engine (VBA rules)."""

from dataclasses import asdict

from app.engine.conditions.seismic import SeismicCondition
from app.engine.conditions.wind import WindCondition


def map_result(result) -> dict | None:
    """Any engine result dataclass -> snake_case dict (None stays None)."""
    return None if result is None else asdict(result)


def map_pole_aggregate(result) -> dict:
    """PoleAggregationResult + the engine ADDITION ``weight_n`` per segment."""
    data = asdict(result)
    for item, mapped in zip(result.pole_results, data["pole_results"], strict=True):
        mapped["weight_n"] = item.weight_n
    return data


def map_direct_object_aggregate(result) -> dict | None:
    """DirectObjectAggregationResult + the engine ADDITION per-unit values."""
    if result is None:
        return None
    data = asdict(result)
    for item, mapped in zip(
        result.direct_object_results, data["direct_object_results"], strict=True
    ):
        mapped["weight_per_unit_n"] = item.weight_per_unit_n
        for unit, directional in zip(
            item.per_unit_directional_results, mapped["directional_results"], strict=True
        ):
            directional["projected_area_per_unit_m2"] = unit.projected_area_per_unit_m2
            directional["wind_load_per_unit_n"] = unit.wind_load_per_unit_n
    return data


def map_wind_condition(wind: WindCondition) -> dict:
    common = wind.common_parameters
    return {
        "design_standard": wind.design_standard,
        "structure_height_m": wind.structure_height_m,
        "atmospheric_category": wind.atmospheric_category,
        "basic_wind_speed_m_s": wind.basic_wind_speed_m_s,
        "design_wind_speed_m_s": wind.design_wind_speed_m_s,
        # Keys follow std_act_common() in app/engine/conditions/wind.py.
        "common_parameters": None if common is None else {
            "hstr": common["Hstr"],
            "zb": common["zb"],
            "zg": common["zg"],
            "alpha": common["alpha"],
            "gf": common["Gf"],
            "er": common["Er"],
            "ds_air": common["Ds_air"],
            "adc_symbol": common["ADC_symbol"],
        },
    }


def map_seismic_condition(seismic: SeismicCondition | None) -> dict | None:
    """The K value the engine used; for Rooftop it comes from seismic_class."""
    if seismic is None:
        return None
    return {
        "position": seismic.position,
        "seismic_class": seismic.seismic_class,
        "k_value": seismic.k_value,
    }
