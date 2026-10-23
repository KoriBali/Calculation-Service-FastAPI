"""Immutable result objects returned by the calculation engine.

Ported from python_calc ``calculation/result.py``.

DEVIATION: every seismic field is ``float | None``. None means no seismic
condition was given, so nothing seismic was calculated. It is never
replaced by 0.0, because 0.0 would read as "calculated and zero".

ADDITION: read-only ``@property`` values for the report (weight and per-unit
values). They are not in python_calc. ``asdict()`` skips properties, so the
parity output of every dataclass is unchanged.
"""

from dataclasses import dataclass

from app.engine.loads.base import LoadObject
from app.engine.loads.pole import PoleSectionProperties


@dataclass(frozen=True)
class PoleActiveGeometry:
    """Geometry of one pole segment above an evaluated position."""

    pole_name: str
    evaluated_position_m: float
    segment_bottom_m: float
    segment_top_m: float
    active_bottom_m: float
    active_top_m: float
    full_length_m: float
    active_length_m: float
    diameter_at_active_bottom_mm: float
    diameter_at_active_top_mm: float
    local_load_center_m: float
    load_center_height_m: float


@dataclass(frozen=True)
class PoleCalculationResult:
    """Calculated response of one pole segment at an evaluated position."""

    geometry: PoleActiveGeometry
    section_properties: PoleSectionProperties
    nnc: float
    kz: float
    cf: float
    wind_pressure_n_m2: float
    projected_area_m2: float
    mass_kg: float
    overdesign_factor: float
    fix_load_n: float
    wind_load_n: float
    seismic_load_n: float | None
    wind_moment_nm: float
    seismic_moment_nm: float | None
    directional_results: tuple["PoleDirectionalResult", ...] = ()

    # ADDITION (not in python_calc): report column "unit weight W (N)".
    @property
    def weight_n(self) -> float:
        """Gravity force of this segment before the OverdesignFactor."""
        return LoadObject.force_from_mass(self.mass_kg)


@dataclass(frozen=True)
class PoleDirectionalResult:
    """Signed pole force and moment components for one wind direction."""

    direction: str
    angle_rad: float
    wind_load_x_n: float
    wind_load_y_n: float
    wind_moment_x_nm: float
    wind_moment_y_nm: float


@dataclass(frozen=True)
class PoleDirectionalTotal:
    """Aggregated signed wind response for one direction."""

    direction: str
    angle_rad: float
    total_wind_load_n: float
    total_wind_load_x_n: float
    total_wind_load_y_n: float
    total_wind_moment_x_nm: float
    total_wind_moment_y_nm: float


@dataclass(frozen=True)
class PoleAggregationResult:
    """Aggregated pole response at one EvaluatedPosition."""

    evaluated_position_m: float
    pole_results: tuple[PoleCalculationResult, ...]
    total_fix_load_n: float
    total_seismic_load_n: float | None
    total_seismic_moment_nm: float | None
    directional_totals: tuple[PoleDirectionalTotal, ...]


@dataclass(frozen=True)
class DirectObjectDirectionalResult:
    """Wind response of one Direct Object for one wind direction."""

    direction: str
    angle_rad: float
    angle_of_attack_rad: float
    sin_angle_of_attack: float
    cos_angle_of_attack: float
    projected_area_m2: float
    wind_load_n: float
    wind_load_x_n: float
    wind_load_y_n: float
    wind_moment_nm: float
    wind_moment_x_nm: float
    wind_moment_y_nm: float


@dataclass(frozen=True)
class DirectObjectCalculationResult:
    """Calculated response of one Direct Object at an EvaluatedPosition."""

    object_name: str
    object_type: str
    evaluated_position_m: float
    elevation_m: float
    load_center_height_m: float
    quantity: int
    mass_per_unit_kg: float
    total_mass_kg: float
    nnc: float
    kz: float
    cf: float
    wind_pressure_n_m2: float
    fix_load_n: float
    seismic_load_n: float | None
    seismic_moment_nm: float | None
    directional_results: tuple[DirectObjectDirectionalResult, ...]

    # ADDITION (not in python_calc): report columns for one unit.
    @property
    def weight_per_unit_n(self) -> float:
        """Gravity force of one unit."""
        return LoadObject.force_from_mass(self.mass_per_unit_kg)

    @property
    def per_unit_directional_results(
        self,
    ) -> tuple["DirectObjectPerUnitDirectionalResult", ...]:
        """``directional_results`` divided back to one unit, same order."""
        return tuple(
            DirectObjectPerUnitDirectionalResult(
                direction=item.direction,
                projected_area_per_unit_m2=item.projected_area_m2 / self.quantity,
                wind_load_per_unit_n=item.wind_load_n / self.quantity,
            )
            for item in self.directional_results
        )


# ADDITION (not in python_calc): built only by the property above.
@dataclass(frozen=True)
class DirectObjectPerUnitDirectionalResult:
    """Wind values of one Direct Object unit for one direction."""

    direction: str
    projected_area_per_unit_m2: float
    wind_load_per_unit_n: float


@dataclass(frozen=True)
class DirectObjectDirectionalTotal:
    """Aggregated Direct Object wind response for one direction."""

    direction: str
    angle_rad: float
    total_wind_load_n: float
    total_wind_load_x_n: float
    total_wind_load_y_n: float
    total_wind_moment_nm: float
    total_wind_moment_x_nm: float
    total_wind_moment_y_nm: float


@dataclass(frozen=True)
class DirectObjectAggregationResult:
    """Aggregated Direct Object response at one EvaluatedPosition."""

    evaluated_position_m: float
    direct_object_results: tuple[DirectObjectCalculationResult, ...]
    active_object_count: int
    total_fix_load_n: float
    total_seismic_load_n: float | None
    total_seismic_moment_nm: float | None
    directional_totals: tuple[DirectObjectDirectionalTotal, ...]


@dataclass(frozen=True)
class OverheadWireDirectionalResult:
    """OHW wind and directional tension response for one wind direction."""

    direction: str
    angle_rad: float
    angle_of_attack_rad: float
    sin_angle_of_attack: float
    cos_angle_of_attack: float
    directional_projected_area_m2: float
    wind_load_n: float
    wind_load_x_n: float
    wind_load_y_n: float
    wind_moment_nm: float
    wind_moment_x_nm: float
    wind_moment_y_nm: float
    combined_wind_line_load_n_m: float
    wind_tension_n: float
    wind_tension_x_n: float
    wind_tension_y_n: float
    wind_tension_moment_nm: float
    wind_tension_moment_x_nm: float
    wind_tension_moment_y_nm: float
    seismic_tension_moment_nm: float | None


@dataclass(frozen=True)
class OverheadWireCalculationResult:
    """Calculated response of one OHW at an EvaluatedPosition."""

    wire_name: str
    evaluated_position_m: float
    elevation_m: float
    load_center_height_m: float
    tributary_wire_length_m: float
    total_mass_kg: float
    nnc: float
    kz: float
    cf: float
    wind_pressure_n_m2: float
    projected_area_m2: float
    fix_load_per_length_n_m: float
    fix_load_n: float
    seismic_load_n: float | None
    seismic_moment_nm: float | None
    seismic_tension_n: float | None
    directional_results: tuple[OverheadWireDirectionalResult, ...]


@dataclass(frozen=True)
class OverheadWireDirectionalTotal:
    """Aggregated OHW response for one wind direction."""

    direction: str
    angle_rad: float
    total_wind_load_n: float
    total_wind_load_x_n: float
    total_wind_load_y_n: float
    total_wind_moment_nm: float
    total_wind_moment_x_nm: float
    total_wind_moment_y_nm: float
    total_wind_tension_n: float
    total_wind_tension_x_n: float
    total_wind_tension_y_n: float
    total_wind_tension_moment_nm: float
    total_wind_tension_moment_x_nm: float
    total_wind_tension_moment_y_nm: float
    total_seismic_tension_moment_nm: float | None


@dataclass(frozen=True)
class OverheadWireAggregationResult:
    """Aggregated OHW response at one EvaluatedPosition."""

    evaluated_position_m: float
    wire_results: tuple[OverheadWireCalculationResult, ...]
    active_wire_count: int
    total_fix_load_n: float
    total_seismic_load_n: float | None
    total_seismic_moment_nm: float | None
    total_seismic_tension_n: float | None
    directional_totals: tuple[OverheadWireDirectionalTotal, ...]


@dataclass(frozen=True)
class BendingStrengthResult:
    """Bending-stress verification for one load case and direction."""

    bending_moment_nm: float
    section_modulus_cm3: float
    calculated_stress_n_mm2: float
    allowable_stress_n_mm2: float
    utilization_ratio: float
    status: str


@dataclass(frozen=True)
class EvaluatedPositionDirectionalResult:
    """Complete response at an EvaluatedPosition for one direction."""

    direction: str
    angle_rad: float
    total_wind_load_n: float
    total_wind_load_x_n: float
    total_wind_load_y_n: float
    total_wind_tension_n: float
    resultant_wind_load_x_n: float
    resultant_wind_load_y_n: float
    resultant_wind_load_n: float
    total_wind_moment_x_nm: float
    total_wind_moment_y_nm: float
    total_wind_tension_moment_x_nm: float
    total_wind_tension_moment_y_nm: float
    combined_wind_moment_x_nm: float
    combined_wind_moment_y_nm: float
    combined_wind_moment_nm: float
    wind_strength: BendingStrengthResult
    resultant_seismic_load_n: float | None
    combined_seismic_moment_nm: float | None
    seismic_strength: BendingStrengthResult | None


@dataclass(frozen=True)
class EvaluatedPositionResult:
    """Section_each-equivalent result without the deferred Arm contribution."""

    evaluated_position_m: float
    evaluated_pole_name: str
    material_name: str
    section_properties: PoleSectionProperties
    total_fix_load_n: float
    total_seismic_load_n: float | None
    total_seismic_moment_nm: float | None
    directional_results: tuple[EvaluatedPositionDirectionalResult, ...]
    report_direction: str = "N"

    @property
    def report_result(self) -> EvaluatedPositionDirectionalResult:
        """Return the positive-N (90 degree) result used by an omni report."""
        return next(
            item
            for item in self.directional_results
            if item.direction == self.report_direction
        )

