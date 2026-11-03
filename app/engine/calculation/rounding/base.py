"""Common interface for calculation rounding policies.

Ported from python_calc ``calculation/rounding/base.py`` (commit 270d23b).
"""

from abc import ABC, abstractmethod
from decimal import Decimal


class RoundingPolicy(ABC):
    """Interface implemented by every calculation rounding method."""

    @abstractmethod
    def apply(
        self,
        value: int | float | Decimal,
        precision: int,
    ) -> float:
        """Round ``value`` using the policy-specific meaning of precision."""

    def __call__(
        self,
        value: int | float | Decimal,
        precision: int,
    ) -> float:
        """Allow a policy object to be called like a function."""
        return self.apply(value, precision)
