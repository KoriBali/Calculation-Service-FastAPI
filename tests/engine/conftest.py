"""Tests ported from python_calc check python_calc behaviour, rounding included.

``tools/port.sh`` writes "Ported from python_calc" into the docstring of every
ported file. Those files run with python_calc rounding; the files written for
this service run with the VBA rounding the app uses.
"""

import pytest

from app.engine.rounding import python_calc_rounding

PORTED_MARKER = "Ported from python_calc"


@pytest.fixture(autouse=True)
def _rounding_of_the_source(request):
    if PORTED_MARKER in (request.module.__doc__ or ""):
        with python_calc_rounding():
            yield
    else:
        yield