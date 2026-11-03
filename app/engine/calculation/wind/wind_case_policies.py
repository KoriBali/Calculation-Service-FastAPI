"""Wind-case policies without load or stress calculations.

Ported from python_calc ``calculation/wind/wind_case_policies.py`` (commit 270d23b).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.engine.domain.standards.codes import DesignStandardCode

from .wind_case import WindCase


class WindCasePolicy(ABC):
    """Interface for policies that only select direct-wind cases."""

    @abstractmethod
    def cases(self) -> tuple[WindCase, ...]:
        """Return ordered wind cases without performing calculations."""


@dataclass(frozen=True)
class OmniWindCasePolicy(WindCasePolicy):
    """Represent an omni calculation by the confirmed 90-degree case."""

    def cases(self) -> tuple[WindCase, ...]:
        return (WindCase(name="OMNI", angle_deg=90.0),)


@dataclass(frozen=True)
class StraightWindCasePolicy(WindCasePolicy):
    """Return the confirmed straight direct-wind case at 90 degrees."""

    def cases(self) -> tuple[WindCase, ...]:
        return (WindCase(name="STRAIGHT", angle_deg=90.0),)


@dataclass(frozen=True)
class StraightObliqueWindCasePolicy(WindCasePolicy):
    """Return straight 90-degree and oblique 45-degree cases."""

    def cases(self) -> tuple[WindCase, ...]:
        return (
            WindCase(name="STRAIGHT", angle_deg=90.0),
            WindCase(name="OBLIQUE", angle_deg=45.0),
        )


@dataclass(frozen=True)
class EightDirectionWindCasePolicy(WindCasePolicy):
    """Return the confirmed VBA direction order and angles."""

    def cases(self) -> tuple[WindCase, ...]:
        return (
            WindCase(name="N", angle_deg=90.0),
            WindCase(name="S", angle_deg=270.0),
            WindCase(name="E", angle_deg=0.0),
            WindCase(name="W", angle_deg=180.0),
            WindCase(name="NE", angle_deg=45.0),
            WindCase(name="SW", angle_deg=225.0),
            WindCase(name="NW", angle_deg=135.0),
            WindCase(name="SE", angle_deg=315.0),
        )


def wind_case_policy_for(
    design_standard: int | DesignStandardCode,
    *,
    include_oblique: bool = False,
) -> WindCasePolicy:
    """Select a wind-case policy using only confirmed standard rules.

    Standards 3 and 4 add the 45-degree oblique case only when explicitly
    requested. Standard 5 always contains straight and oblique cases.
    """
    standard = DesignStandardCode(design_standard)
    standard.ensure_calculation_is_available()

    if standard in {
        DesignStandardCode.ACT_DISASTER_PREVENTION,
        DesignStandardCode.FIXED_WIND_DISASTER,
        DesignStandardCode.ACT_TOWER,
    }:
        return OmniWindCasePolicy()

    if standard in {
        DesignStandardCode.OLD_LIGHTING_POLE,
        DesignStandardCode.SMALL_SIGN_BOARD,
    }:
        if include_oblique:
            return StraightObliqueWindCasePolicy()
        return StraightWindCasePolicy()

    if standard is DesignStandardCode.LARGE_SIGN_BOARD:
        return StraightObliqueWindCasePolicy()

    if standard in {
        DesignStandardCode.NEW_JIL,
        DesignStandardCode.OLD_TRAFFIC_SIGNAL,
    }:
        return EightDirectionWindCasePolicy()

    raise AssertionError(f"Unhandled design standard: {standard!r}")


def wind_cases_for(
    design_standard: int | DesignStandardCode,
    *,
    include_oblique: bool = False,
) -> tuple[WindCase, ...]:
    """Return the ordered wind cases for a design standard."""
    return wind_case_policy_for(
        design_standard,
        include_oblique=include_oblique,
    ).cases()
