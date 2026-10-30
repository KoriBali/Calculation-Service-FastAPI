"""Design-standard identities used by the calculation engine.

Ported from python_calc ``domain/standards/__init__.py`` (commit 270d23b).
"""

from typing import TYPE_CHECKING, Any

from .codes import DesignStandardCode
from .features import (
    CalculationFeatures,
    WindCaseMode,
    calculation_features_for,
)

if TYPE_CHECKING:
    from .design_standard import DesignStandard
    from .factory import DesignStandardFactory


def __getattr__(name: str) -> Any:
    """Load policy aggregates lazily to avoid calculation/domain cycles."""
    if name == "DesignStandard":
        from .design_standard import DesignStandard

        return DesignStandard
    if name == "DesignStandardFactory":
        from .factory import DesignStandardFactory

        return DesignStandardFactory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "CalculationFeatures",
    "DesignStandardCode",
    "DesignStandard",
    "DesignStandardFactory",
    "WindCaseMode",
    "calculation_features_for",
]
