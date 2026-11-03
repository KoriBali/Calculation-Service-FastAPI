"""Standard-specific seismic load policies.

Ported from python_calc ``calculation/seismic/__init__.py`` (commit 270d23b).
"""

from .base import SeismicPolicy
from .seismic_policies import (
    FixLoadCoefficientSeismicPolicy,
    NewJILSeismicPolicy,
    NoSeismicPolicy,
    seismic_policy_for,
)

__all__ = [
    "FixLoadCoefficientSeismicPolicy",
    "NewJILSeismicPolicy",
    "NoSeismicPolicy",
    "SeismicPolicy",
    "seismic_policy_for",
]
