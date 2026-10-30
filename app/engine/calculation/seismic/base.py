"""Interface for seismic load policies.

Ported from python_calc ``calculation/seismic/base.py`` (commit 270d23b).
"""

from abc import ABC, abstractmethod


class SeismicPolicy(ABC):
    """Calculate seismic load from explicitly named physical quantities."""

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Return whether seismic calculation is active."""

    @abstractmethod
    def calculate_load_n(
        self,
        *,
        fix_load_n: float,
        mass_kg: float,
    ) -> float:
        """Return seismic load in N using the policy's confirmed source."""
