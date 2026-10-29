"""VBA rounding functions and the rounding rule of every engine quantity.

``significant_figures`` is ported from ``Fkb_iLog10``, ``Fkb_DigiNo``, and
``Fkb_SF`` in ``Module_Init_Data.bas`` of multiple_JIL_14f.xlsm.
``round_half_away`` is ported from ``RInt0``..``RInt4`` in ``M_Func_Basic.bas``.
Both keep the VBA floating-point steps, including their quirks.

DEVIATION from python_calc: the engine rounds where VBA rounds, with the VBA
function and digit count. python_calc used ``round(x, n)`` in a few places
and kept the rest at full precision. Each rule below carries both, so the
parity tests can still compare formulas against python_calc
(``python_calc_rounding()``). The app always runs with the VBA rules.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from math import floor, log, trunc

# Fkb_iLog10 answers these exactly because Log(x) / Log(10) misses them.
_EXACT_LOG10 = {1000: 3, 100000: 5, 1000000: 6, 10000000: 7, 100000000: 8}


def _vba_str(value: float) -> str:
    """VBA ``Str()``: at most 15 significant digits, a space before positives."""
    text = f"{value:.15g}"
    return text if value < 0 else f" {text}"


def _ilog10(value: float) -> int:
    """VBA ``Fkb_iLog10``."""
    if value == 0:
        return 0
    if value in _EXACT_LOG10:
        return _EXACT_LOG10[value]
    return floor(log(abs(value)) / log(10))


def _digit_count(value: float) -> int:
    """VBA ``Fkb_DigiNo``: significant digits written by ``Str()``."""
    length = len(_vba_str(value * (10 ** (_ilog10(value) * -1)))) - 1
    return 1 if length == 1 else length - 1


def significant_figures(value: float, digits: int) -> float:
    """VBA ``Fkb_SF``: round ``value`` to ``digits`` significant figures.

    An exact half (one digit more than ``digits`` and that digit is 5) goes to
    the even neighbour. Anything else is rounded half away from zero.
    """
    if value == 0:
        return 0.0
    shift = (digits - 1) - _ilog10(value)
    scale = 10**shift
    text = _vba_str(value * (10 ** (_ilog10(value) * -1)))

    if _digit_count(value) == digits + 1 and text[-1] == "5":
        kept_digit = int(text[digits + 1])  # VBA Mid(text, dSF + 2, 1)
        toward_zero = trunc(value * scale)  # Int for > 0, Fix for < 0
        if kept_digit % 2 == 0:
            return toward_zero / scale
        return (toward_zero + (1 if value > 0 else -1)) / scale

    if value > 0:
        return floor(value * scale + 0.5) / scale
    return trunc(value * scale - 0.5) / scale


def round_half_away(value: float, decimals: int) -> float:
    """VBA ``RInt<decimals>``: round half away from zero."""
    scale = 10**decimals
    if value > 0:
        return floor(value * scale + 0.5) / scale
    return trunc(value * scale - 0.5) / scale


def _sig(digits: int) -> Callable[[float], float]:
    return lambda value: significant_figures(value, digits)


def _rint(decimals: int) -> Callable[[float], float]:
    return lambda value: round_half_away(value, decimals)


def _python_round(decimals: int) -> Callable[[float], float]:
    return lambda value: round(value, decimals)


def _keep(value: float) -> float:
    return value


_USE_PYTHON_CALC: ContextVar[bool] = ContextVar("use_python_calc", default=False)


@contextmanager
def python_calc_rounding() -> Iterator[None]:
    """Use python_calc rounding inside the block. For parity tests only."""
    token = _USE_PYTHON_CALC.set(True)
    try:
        yield
    finally:
        _USE_PYTHON_CALC.reset(token)


@dataclass(frozen=True)
class RoundingRule:
    """How one quantity is rounded: per VBA (app) and per python_calc (parity)."""

    vba_source: str
    vba: Callable[[float], float]
    python_calc: Callable[[float], float]

    def __call__(self, value: float) -> float:
        rule = self.python_calc if _USE_PYTHON_CALC.get() else self.vba
        return rule(value)


# --- Wind condition (Module_Init_Data, Pole_each.q_wp, DO_each.q_wp) -------
COMMON_FACTOR = RoundingRule("Gf/Er_act/Ds_air = RInt3", _rint(3), _python_round(3))
KZ = RoundingRule("f_kz = RInt3", _rint(3), _python_round(3))
PRESSURE_3 = RoundingRule("q_wpr = Fkb_SF(.., 3)", _sig(3), _python_round(3))
PRESSURE_4 = RoundingRule("q_wpr = Fkb_SF(.., 4) (std 2/3)", _sig(4), _python_round(4))
PRESSURE_WITH_KZ = RoundingRule("q_wpr = Fkb_SF(q_b_kz, 3) (std 6)", _sig(3), _python_round(3))

# --- Direction factors (Calc_Windload_XY, Calc_Angle_of_Atack) -------------
DIRECTION_FACTOR = RoundingRule("RInt3(Sin/Cos)", _rint(3), _python_round(3))

# --- Pole section and mass (Pole_each.Po_Spec, Calc_Fixload) ---------------
TAPER_DIAMETER = RoundingRule("Dia_sec = Fkb_SF(.., 4)", _sig(4), _keep)
SECTION_PROPERTY = RoundingRule("Sec_A/sec_mod/M_Ine/Rad_G = Fkb_SF(.., 3)", _sig(3), _python_round(2))
SECOND_MOMENT_PAIR = RoundingRule("Ip = Fkb_SF(M_Ine * 2, 3)", _sig(3), _python_round(3))
POLE_MASS = RoundingRule(
    "mass = Fkb_SF(fL_s(..), 3), fL_s uses RInt2",
    lambda value: significant_figures(round_half_away(value, 2), 3),
    _python_round(2),
)

# --- Coefficients (Pole_each.Calc_Cf, DO_each.Calc_Cf) ---------------------
NNC = RoundingRule("nc shown as Fkb_SF(nc, 3)", _sig(3), _python_round(3))
NNC_INTO_CF = RoundingRule("cf reads the unrounded nc", _keep, _python_round(3))
CF = RoundingRule("cf = Fkb_SF(nc [* kz], 3)", _sig(3), _python_round(3))

# --- Values python_calc keeps at full precision ----------------------------
SIG3 = RoundingRule("Fkb_SF(.., 3)", _sig(3), _keep)