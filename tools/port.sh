#!/usr/bin/env bash
# Port one python_calc file into calculation_service.
#
# Usage: tools/port.sh <path inside python_calc> <target path>
#
# Reads the file from python_calc commit $PYTHON_CALC_REF (default 270d23b),
# never from the working tree, rewrites imports with port_python_calc.sed, and
# notes the source in a single-line module docstring.
set -euo pipefail

src="$1"
dst="$2"
ref="${PYTHON_CALC_REF:-270d23b}"
python_calc="${PYTHON_CALC:-../python_calc_V2}"
here="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$(dirname "$dst")"
git -C "$python_calc" show "$ref:$src" \
  | sed -f "$here/port_python_calc.sed" \
  | sed "1s|^\(\"\"\".*\)\"\"\"\$|\1\n\nPorted from python_calc \`\`$src\`\` (commit $ref).\n\"\"\"|" \
  > "$dst"
echo "ported $src -> $dst"
