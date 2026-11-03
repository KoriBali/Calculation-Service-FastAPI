"""Common interface for stress calculation policies.

Ported from python_calc ``calculation/stress/base.py`` (commit 270d23b).
"""

from abc import ABC, abstractmethod
from typing import Any


class StressPolicy(ABC):
    """Interface implemented by standard-specific stress methods."""

    @abstractmethod
    def calculate(self, calculation_input: Any) -> Any:
        """Return an immutable stress result from explicit calculation data."""
