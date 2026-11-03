"""Immutable description of one direct-wind case.

Ported from python_calc ``calculation/wind/wind_case.py`` (commit 270d23b).
"""

from dataclasses import dataclass
from math import radians


@dataclass(frozen=True)
class WindCase:
    """Name and direct-wind angle for one calculation case.

    ``angle_deg`` is the direct-wind angle. When object calculations are
    connected in a later stage, the confirmed angle of attack is:

    ``object fixed angle - direct-wind angle``.
    """

    name: str
    angle_deg: float

    @property
    def angle_rad(self) -> float:
        """Return the direct-wind angle in radians."""
        return radians(self.angle_deg)
