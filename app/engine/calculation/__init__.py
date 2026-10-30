"""Calculation services for the structural calculation engine.

Ported from python_calc ``calculation/__init__.py`` (commit 270d23b).
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .standard_126_workflow import Standard126CalculationWorkflow
    from .standard_34_workflow import Standard34CalculationWorkflow
    from .standard_arm_workflows import (
        Standard5CalculationWorkflow,
        Standard7CalculationWorkflow,
        Standard9CalculationWorkflow,
    )


def __getattr__(name: str) -> Any:
    """Load complete workflows only when explicitly requested."""
    if name == "Standard126CalculationWorkflow":
        from .standard_126_workflow import Standard126CalculationWorkflow

        return Standard126CalculationWorkflow
    if name == "Standard34CalculationWorkflow":
        from .standard_34_workflow import Standard34CalculationWorkflow

        return Standard34CalculationWorkflow
    if name in {
        "Standard5CalculationWorkflow",
        "Standard7CalculationWorkflow",
        "Standard9CalculationWorkflow",
    }:
        from .standard_arm_workflows import (
            Standard5CalculationWorkflow,
            Standard7CalculationWorkflow,
            Standard9CalculationWorkflow,
        )

        return {
            "Standard5CalculationWorkflow": Standard5CalculationWorkflow,
            "Standard7CalculationWorkflow": Standard7CalculationWorkflow,
            "Standard9CalculationWorkflow": Standard9CalculationWorkflow,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "Standard126CalculationWorkflow",
    "Standard34CalculationWorkflow",
    "Standard5CalculationWorkflow",
    "Standard7CalculationWorkflow",
    "Standard9CalculationWorkflow",
]

