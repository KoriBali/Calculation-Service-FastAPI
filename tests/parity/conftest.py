"""Parity tests compare formulas with python_calc, so they use its rounding."""

import pytest

from app.engine.rounding import python_calc_rounding


@pytest.fixture(autouse=True)
def _python_calc_rounding():
    with python_calc_rounding():
        yield