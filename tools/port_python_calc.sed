# Rewrites python_calc imports to app.engine. Names and code stay as they are.
# Usage: git -C ../python_calc_V2 show 270d23b:<file> | sed -f tools/port_python_calc.sed > <target>
#
# Layout: python_calc <dir>/<file> -> app/engine/<dir>/<file>, with three
# renames: BasicFunction.py -> basic_function.py, application/calculation_service.py
# -> calculation_service.py, tests/<file> -> tests/engine/<file>.

s/^import BasicFunction$/from app.engine import basic_function as BasicFunction/
s/^\([[:space:]]*\)from domain\([. ]\)/\1from app.engine.domain\2/
s/^\([[:space:]]*\)from calculation\([. ]\)/\1from app.engine.calculation\2/
s/^\([[:space:]]*\)from application\.calculation_service import /\1from app.engine.calculation_service import /
s/^\([[:space:]]*\)from tests\.regression_scenarios import /\1from tests.engine.regression_scenarios import /
