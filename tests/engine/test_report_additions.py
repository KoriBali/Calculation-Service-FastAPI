"""Engine ADDITION: read-only report values that python_calc does not have."""

from dataclasses import asdict

import pytest

from app.engine.calculators.direct_object import DirectObjectCalculator
from app.engine.calculators.pole import PoleCalculator
from app.engine.conditions.wind import WindCondition
from app.engine.geometry.pole_assembly import PoleAssembly
from app.engine.loads.base import LoadObject, OverdesignFactor
from app.engine.loads.direct_object import DirectObject
from app.engine.loads.pole import PoleObject

WIND = WindCondition(3, 8.0)
QUANTITY = 3


def pole_result():
    pole = PoleObject("P", "Straight", 139.8, 139.8, 4.5, 4.5, "STK400", 8.0)
    calculator = PoleCalculator(PoleAssembly([pole]), WIND, None, OverdesignFactor(1.2))
    return calculator.aggregate_at(0.0).pole_results[0]


def sign_result():
    sign = DirectObject("Sign", "Directional", 0.5, 0.1, 15, 6.0, 1.2, QUANTITY, 30)
    calculator = DirectObjectCalculator([sign], WIND, None)
    return calculator.aggregate_at(0.0).direct_object_results[0]


def test_pole_weight_is_before_overdesign_factor():
    result = pole_result()

    assert result.weight_n == pytest.approx(result.mass_kg * LoadObject.GRAVITY, abs=1e-9)
    assert result.fix_load_n == pytest.approx(result.weight_n * 1.2, abs=1e-9)


def test_direct_object_per_unit_values_times_quantity_give_totals():
    result = sign_result()

    assert result.weight_per_unit_n * QUANTITY == pytest.approx(result.fix_load_n, abs=1e-9)
    for unit, total in zip(
        result.per_unit_directional_results, result.directional_results, strict=True
    ):
        assert unit.direction == total.direction
        assert unit.projected_area_per_unit_m2 * QUANTITY == pytest.approx(
            total.projected_area_m2, abs=1e-9
        )
        assert unit.wind_load_per_unit_n * QUANTITY == pytest.approx(
            total.wind_load_n, abs=1e-9
        )


def test_properties_stay_out_of_asdict():
    """Parity compares asdict() key for key, so additions must not appear there."""
    assert "weight_n" not in asdict(pole_result())
    data = asdict(sign_result())
    assert "weight_per_unit_n" not in data
    assert "per_unit_directional_results" not in data


@pytest.mark.parametrize("standard", [2, 3, 4, 5])
def test_fixed_design_wind_speed_matches_wind_pressure(standard):
    """Guards the copy of 60/40/50 m/s against wind_pressure_at()."""
    condition = WindCondition(standard, 8.0)
    digits = 4 if standard in (2, 3) else 3

    assert condition.wind_pressure_at(8.0) == round(
        0.5 * 1.23 * condition.design_wind_speed_m_s**2, digits
    )


@pytest.mark.parametrize("standard", [1, 6])
def test_design_wind_speed_is_the_given_speed_for_1_and_6(standard):
    condition = WindCondition(standard, 8.0, atmospheric_category=3, basic_wind_speed_m_s=34)
    assert condition.design_wind_speed_m_s == 34
