#!/usr/bin/env bash
# Port the whole python_calc engine and its tests into calculation_service.
#
# Usage: tools/port_engine.sh   (run from the repo root)
#
# Copies every file of BasicFunction.py, domain/, calculation/,
# application/calculation_service.py and tests/ from commit $PYTHON_CALC_REF.
# application/output/ (report mapping for the legacy PDF) is not ported: the
# API builds its own response in app/<feature>/mappers.py. Its test is skipped
# for the same reason.
set -euo pipefail

ref="${PYTHON_CALC_REF:-270d23b}"
python_calc="${PYTHON_CALC:-../python_calc_V2}"
here="$(cd "$(dirname "$0")" && pwd)"
export PYTHON_CALC_REF="$ref" PYTHON_CALC="$python_calc"

"$here/port.sh" BasicFunction.py app/engine/basic_function.py
"$here/port.sh" application/calculation_service.py app/engine/calculation_service.py

git -C "$python_calc" ls-tree -r --name-only "$ref" -- domain calculation tests \
  | grep '\.py$' \
  | grep -v -e '^tests/__init__\.py$' -e '^tests/test_standard_output\.py$' \
  | while read -r src; do
      case "$src" in
        tests/*) dst="tests/engine/${src#tests/}" ;;
        *) dst="app/engine/$src" ;;
      esac
      "$here/port.sh" "$src" "$dst"
    done
