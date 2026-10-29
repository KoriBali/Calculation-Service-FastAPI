"""Engine DEVIATION: VBA rounding (Fkb_SF, RInt) and the per-quantity rules."""

import pytest

from app.engine import rounding
from app.engine.rounding import (
    python_calc_rounding,
    round_half_away,
    significant_figures,
)


@pytest.mark.parametrize(
    ("value", "digits", "expected"),
    [
        (1478.385, 3, 1480.0),  # normal: half away from zero
        (45.678, 3, 45.7),
        (0.0012345, 3, 0.00123),
        (38912345.6, 3, 38900000.0),
        (2214.0, 4, 2214.0),
        (1537.5, 3, 1540.0),  # std 5 wind pressure
        (553.5, 3, 554.0),  # exact half, kept digit 3 is odd -> up
        (4905.0, 3, 4900.0),  # exact half, kept digit 0 is even -> down
        (1.245, 3, 1.24),
        (-1.235, 3, -1.24),
        (-1.245, 3, -1.24),
        (0.9995, 3, 1.0),
        (1000.0, 3, 1000.0),  # Fkb_iLog10 special case
        (0.0, 3, 0.0),
    ],
)
def test_significant_figures_follows_fkb_sf(value, digits, expected):
    assert significant_figures(value, digits) == expected


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        (0.7071067811865476, 3, 0.707),
        (-0.7071067811865476, 3, -0.707),
        (0.0005, 3, 0.001),  # Python round() gives 0.0 here
        (-0.0005, 3, -0.001),
        (0.0, 3, 0.0),
    ],
)
def test_round_half_away_follows_rint(value, decimals, expected):
    assert round_half_away(value, decimals) == expected


def test_rule_uses_vba_unless_python_calc_rounding_is_active():
    assert rounding.SECTION_PROPERTY(62.6912) == 62.7
    with python_calc_rounding():
        assert rounding.SECTION_PROPERTY(62.6912) == 62.69
        assert rounding.SIG3(1478.385) == 1478.385
    assert rounding.SIG3(1478.385) == 1480.0


def test_python_calc_rounding_is_reset_after_an_error():
    with pytest.raises(RuntimeError), python_calc_rounding():
        raise RuntimeError
    assert rounding.SIG3(1478.385) == 1480.0
    
    