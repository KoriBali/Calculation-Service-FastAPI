"""Material definitions used by structural domain objects.

Ported from python_calc ``domain/materials.py`` (commit 270d23b).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PoleMaterial:
    """Allowable stresses for one pole material.

    Stress values use N/mm². A value can be ``None`` when the source data does
    not provide that particular allowable stress.
    """

    name: str
    allowable_bending: float
    short_term_allowable_bending: float
    short_term_allowable_shear: float | None = None
    short_term_allowable_compression: float | None = None

    def __post_init__(self) -> None:
        normalized_name = self.name.strip().upper()
        if not normalized_name:
            raise ValueError("Material name cannot be empty")
        if self.allowable_bending <= 0:
            raise ValueError("Allowable bending stress must be greater than zero")
        if self.short_term_allowable_bending <= 0:
            raise ValueError(
                "Short-term allowable bending stress must be greater than zero"
            )

        object.__setattr__(self, "name", normalized_name)

    def require_shear(self) -> float:
        """Return allowable shear stress or fail when it is unavailable."""
        if self.short_term_allowable_shear is None:
            raise ValueError(
                f"Short-term allowable shear stress is not provided for {self.name}"
            )
        return self.short_term_allowable_shear

    def require_compression(self) -> float:
        """Return allowable compression stress or fail when unavailable."""
        if self.short_term_allowable_compression is None:
            raise ValueError(
                "Short-term allowable compression stress is not provided "
                f"for {self.name}"
            )
        return self.short_term_allowable_compression


MATERIALS: dict[str, PoleMaterial] = {
    "SGP": PoleMaterial("SGP", 113, 170),
    "STK400": PoleMaterial("STK400", 156, 235, 136, 235),
    "STK490": PoleMaterial("STK490", 217, 325),
    "STK500": PoleMaterial("STK500", 234, 350, 202, 350),
    "STK540": PoleMaterial("STK540", 250, 375, 216, 375),
    "STKR400": PoleMaterial("STKR400", 156, 235, 135, 235),
}


def get_pole_material(name: str) -> PoleMaterial:
    """Return a validated pole material by its case-insensitive name."""
    if not isinstance(name, str):
        raise ValueError("Material name must be text")

    normalized_name = name.strip().upper()
    try:
        return MATERIALS[normalized_name]
    except KeyError:
        raise ValueError(f"Pole material is not recognized: {name}") from None

