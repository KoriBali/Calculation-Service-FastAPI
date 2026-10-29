"""Engine DEVIATION: results are rounded where VBA rounds.

One small case, checked by hand against the VBA steps in Pole_each.cls,
DO_each.cls, and Section_each.cls (python_calc 3571622).
"""

import pytest

from app.engine.calculators.direct_object import DirectObjectCalculator
from app.engine.calculators.pole import PoleCalculator
from app.engine.calculators.section_check import EvaluatedPositionCalculator
from app.engine.conditions.seismic import SeismicCondition
from app.engine.conditions.wind import WindCondition
from app.engine.geometry.pole_assembly import PoleAssembly
from app.engine.loads.direct_object import DirectObject
from app.engine.loads.pole import PoleObject

WIND = WindCondition(3, 8.0)
SEISMIC = SeismicCondition.ground(0.3)


def calculators():
    pole = PoleObject("P1", "Straight", 139.8, 139.8, 4.5, 4.5, "STK400", 8.0)
    lamp = DirectObject("LAMP", "Omni", 0.123, 0.0, 12.5, 7.5, 1.2, 2, 0.0)
    pole_calculator = PoleCalculator(PoleAssembly([pole]), WIND, SEISMIC)
    direct_calculator = DirectObjectCalculator([lamp], WIND, SEISMIC)
    return pole_calculator, direct_calculator


def test_pole_values_are_rounded_like_pole_each():
    pole_calculator, _ = calculators()
    result = pole_calculator.aggregate_at(0.0).pole_results[0]

    assert result.section_properties.section_modulus_cm3 == 62.7  # 62.69 before
    assert result.projected_area_m2 == 1.12  # 1.1184
    assert result.mass_kg == 120.0  # 120.12
    assert result.weight_n == 1180.0  # 1177.97...
    assert result.fix_load_n == 1180.0
    assert result.wind_load_n == 1740.0  # 2214 * 0.7 * 1.12 = 1735.776
    assert result.wind_moment_nm == 6960.0  # 4.0 * 1740
    assert result.seismic_load_n == 354.0
    assert result.seismic_moment_nm == 1420.0  # 4.0 * 354 = 1416


def test_direct_object_values_are_rounded_like_do_each():
    _, direct_calculator = calculators()
    result = direct_calculator.aggregate_at(0.0).direct_object_results[0]
    north = result.directional_results[0]

    assert result.weight_per_unit_n == 123.0  # 12.5 * 9.80665 = 122.58
    assert result.fix_load_n == 246.0  # 123 * 2, not 245.17
    assert result.seismic_load_n == 73.8
    assert result.seismic_moment_nm == 554.0  # 553.5: odd kept digit -> up
    assert north.wind_load_n == 654.0  # 653.57
    assert north.wind_moment_nm == 4900.0  # 4905: even kept digit -> down


def test_section_check_values_are_rounded_like_section_each():
    result = EvaluatedPositionCalculator(*calculators()).calculate_at(0.0)
    north = result.directional_results[0]

    assert result.total_fix_load_n == 1430.0  # 1180 + 246 = 1426
    assert north.total_wind_load_n == 2390.0  # 1740 + 654 = 2394
    assert north.combined_wind_moment_nm == 11900.0  # 6960 + 4900 = 11860
    assert north.wind_strength.calculated_stress_n_mm2 == 190.0  # 11900 / 62.7
    assert north.wind_strength.utilization_ratio == 0.809  # 190 / 235
    assert north.seismic_strength.utilization_ratio == 0.134


@pytest.mark.parametrize(
    ("bending_moment_nm", "status"),
    [(234.9, "N.G"), (234.4, "O.K")],
)
def test_status_compares_the_rounded_ratio(bending_moment_nm, status):
    """Section_each.Calc_Safety_Mwl: Fkb_SF(ratio, 3) < 1."""
    result = EvaluatedPositionCalculator._strength_result(bending_moment_nm, 1.0, 235.0)

    assert result.status == status
    if status == "N.G":
        # 234.9 / 235 = 0.99957 was O.K at full precision.
        assert result.utilization_ratio == 1.0
