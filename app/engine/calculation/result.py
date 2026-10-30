"""Immutable result objects returned by the calculation engine.

Ported from python_calc ``calculation/result.py`` (commit 270d23b).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.engine.domain.pole import PoleSectionProperties

if TYPE_CHECKING:
    from app.engine.calculation.stress import CompressionBendingStressResult
    from app.engine.calculation.stress import LargeSignPoleStressResult
    from app.engine.calculation.stress import NewJILPoleStressResult
    from app.engine.calculation.stress import OldTrafficSignalPoleStressResult
    from app.engine.calculation.stress import SimpleBendingStressResult
    from app.engine.domain.standards import DesignStandard


@dataclass(frozen=True)
class ArmSpecificationResult:
    """Calculated properties of one single, round, straight Arm."""

    arm_name: str
    section_area_cm2: float
    section_modulus_cm3: float
    moment_of_inertia_cm4: float
    polar_moment_of_inertia_cm4: float
    radius_of_gyration_cm: float
    mass_per_meter_kg_m: float
    mass_kg: float
    fix_load_per_meter_n_m: float
    fix_load_n: float
    front_projected_area_m2: float
    side_projected_area_m2: float
    center_length_m: float
    allowable_bending_n_mm2: float
    short_term_allowable_bending_n_mm2: float
    short_term_allowable_shear_n_mm2: float | None
    short_term_allowable_compression_n_mm2: float | None


@dataclass(frozen=True)
class ArmSafetyResult:
    """One local Arm bending-safety check."""

    load_case: str
    moment_nm: float
    bending_stress_n_mm2: float
    allowable_stress_n_mm2: float
    utilization_ratio: float
    status: str


@dataclass(frozen=True)
class ArmObjectDirectionalResult:
    """Directional response of one Arm Object."""

    direction: str
    angle_rad: float
    angle_of_attack_rad: float
    sin_angle_of_attack: float
    cos_angle_of_attack: float
    directional_projected_area_m2: float
    wind_load_n: float
    wind_load_x_n: float
    wind_load_y_n: float
    wind_moment_at_pole_x_nm: float
    wind_moment_at_pole_y_nm: float
    fix_load_moment_x_nm: float
    fix_load_moment_y_nm: float
    wind_torque_nm: float
    seismic_torque_nm: float


@dataclass(frozen=True)
class ArmObjectCalculationResult:
    """Local and Pole-level results for one Arm Object."""

    object_index: int
    object_name: str
    object_type: str
    load_center_height_m: float
    horizontal_load_distance_m: float
    mass_kg: float
    fix_load_n: float
    seismic_load_n: float
    front_wind_load_n: float
    side_wind_load_n: float
    fix_load_moment_at_arm_support_nm: float
    wind_moment_at_arm_support_nm: float
    seismic_moment_at_arm_support_nm: float
    seismic_moment_at_pole_nm: float
    directional_results: tuple[ArmObjectDirectionalResult, ...]


@dataclass(frozen=True)
class ArmPartCalculationResult:
    """Complete local calculation and safety result for one Arm."""

    arm_name: str
    installation_height_m: float
    specification: ArmSpecificationResult
    object_results: tuple[ArmObjectCalculationResult, ...]
    total_fix_load_n: float
    total_seismic_load_n: float
    total_fix_load_moment_at_arm_support_nm: float
    total_wind_moment_at_arm_support_nm: float
    total_seismic_moment_at_arm_support_nm: float
    fix_load_safety: ArmSafetyResult | None
    wind_combination_safety: ArmSafetyResult
    seismic_combination_safety: ArmSafetyResult | None


@dataclass(frozen=True)
class ArmDirectionalTotal:
    """Aggregated contribution of all active Arms for one wind direction."""

    direction: str
    angle_rad: float
    total_wind_load_n: float
    total_wind_load_x_n: float
    total_wind_load_y_n: float
    total_wind_moment_x_nm: float
    total_wind_moment_y_nm: float
    total_fix_load_moment_x_nm: float
    total_fix_load_moment_y_nm: float
    total_wind_torque_nm: float
    total_seismic_torque_nm: float


@dataclass(frozen=True)
class ArmAggregationResult:
    """Arm contribution above one Pole EvaluatedPosition."""

    evaluated_position_m: float
    arm_results: tuple[ArmPartCalculationResult, ...]
    active_arm_count: int
    total_fix_load_n: float
    total_seismic_load_n: float
    total_seismic_moment_nm: float
    directional_totals: tuple[ArmDirectionalTotal, ...]


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
    seismic_load_n: float
    wind_moment_nm: float
    seismic_moment_nm: float
    directional_results: tuple["PoleDirectionalResult", ...] = ()


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
    total_seismic_load_n: float
    total_seismic_moment_nm: float
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
    seismic_load_n: float
    seismic_moment_nm: float
    directional_results: tuple[DirectObjectDirectionalResult, ...]


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
    total_seismic_load_n: float
    total_seismic_moment_nm: float
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
    seismic_tension_moment_nm: float


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
    seismic_load_n: float
    seismic_moment_nm: float
    seismic_tension_n: float
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
    total_seismic_tension_moment_nm: float


@dataclass(frozen=True)
class OverheadWireAggregationResult:
    """Aggregated OHW response at one EvaluatedPosition."""

    evaluated_position_m: float
    wire_results: tuple[OverheadWireCalculationResult, ...]
    active_wire_count: int
    total_fix_load_n: float
    total_seismic_load_n: float
    total_seismic_moment_nm: float
    total_seismic_tension_n: float
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
    resultant_seismic_load_n: float
    combined_seismic_moment_nm: float
    seismic_strength: BendingStrengthResult


@dataclass(frozen=True)
class EvaluatedPositionResult:
    """Section_each-equivalent result without the deferred Arm contribution."""

    evaluated_position_m: float
    evaluated_pole_name: str
    material_name: str
    section_properties: PoleSectionProperties
    total_fix_load_n: float
    total_seismic_load_n: float
    total_seismic_moment_nm: float
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


@dataclass(frozen=True)
class CalculationResult:
    """Top-level engine result; details will grow with later object phases."""

    evaluated_position_m: float
    pole_results: tuple[PoleCalculationResult, ...] = ()


@dataclass(frozen=True)
class Standard126CalculationResult:
    """Complete Stage 8 result for the d_st 1, 2, and 6 workflow."""

    design_standard: "DesignStandard"
    pole_aggregation: PoleAggregationResult
    direct_object_aggregation: DirectObjectAggregationResult | None
    overhead_wire_aggregation: OverheadWireAggregationResult | None
    evaluated_position_result: EvaluatedPositionResult
    stress_result: "CompressionBendingStressResult"


@dataclass(frozen=True)
class Standard34DirectionResult:
    """One straight or oblique wind result for d_st 3 and 4."""

    wind_case_name: str
    wind_direction_deg: float
    total_wind_load_n: float
    total_wind_load_x_n: float
    total_wind_load_y_n: float
    total_wind_tension_n: float
    resultant_wind_load_x_n: float
    resultant_wind_load_y_n: float
    resultant_wind_load_n: float
    combined_wind_moment_x_nm: float
    combined_wind_moment_y_nm: float
    combined_wind_moment_nm: float
    bending_stress: "SimpleBendingStressResult"


@dataclass(frozen=True)
class Standard34CalculationResult:
    """Stage 9 output without compression, torque, or seismic result fields."""

    design_standard: "DesignStandard"
    evaluated_position_m: float
    evaluated_pole_name: str
    material_name: str
    section_properties: PoleSectionProperties
    total_fix_load_n: float
    pole_aggregation: PoleAggregationResult
    direct_object_aggregation: DirectObjectAggregationResult
    overhead_wire_aggregation: OverheadWireAggregationResult
    direction_results: tuple[Standard34DirectionResult, ...]
    arm_aggregation: ArmAggregationResult | None = None


@dataclass(frozen=True)
class StandardDirectionalLoadResult:
    """Combined Pole, DO, OHW and Arm response for one wind case."""

    wind_case_name: str
    wind_direction_deg: float
    total_wind_load_n: float
    total_wind_load_x_n: float
    total_wind_load_y_n: float
    resultant_wind_load_x_n: float
    resultant_wind_load_y_n: float
    resultant_wind_load_n: float
    moment_due_to_fix_load_x_nm: float
    moment_due_to_fix_load_y_nm: float
    moment_due_to_fix_load_nm: float
    combined_wind_moment_x_nm: float
    combined_wind_moment_y_nm: float
    combined_wind_moment_nm: float
    wind_torsional_moment_nm: float
    combined_seismic_moment_nm: float
    seismic_torsional_moment_nm: float


@dataclass(frozen=True)
class Standard5CalculationResult:
    """Complete d_st 5 result including Arm contribution."""

    design_standard: "DesignStandard"
    evaluated_position_m: float
    evaluated_pole_name: str
    material_name: str
    section_properties: PoleSectionProperties
    total_fix_load_n: float
    pole_aggregation: PoleAggregationResult
    direct_object_aggregation: DirectObjectAggregationResult
    overhead_wire_aggregation: OverheadWireAggregationResult
    arm_aggregation: ArmAggregationResult
    direction_results: tuple[StandardDirectionalLoadResult, ...]
    stress_result: "LargeSignPoleStressResult"


@dataclass(frozen=True)
class Standard7CalculationResult:
    """Complete New JIL result including eight-direction Arm response."""

    design_standard: "DesignStandard"
    evaluated_position_m: float
    evaluated_pole_name: str
    material_name: str
    section_properties: PoleSectionProperties
    total_fix_load_n: float
    total_seismic_load_n: float
    total_seismic_moment_nm: float
    pole_aggregation: PoleAggregationResult
    direct_object_aggregation: DirectObjectAggregationResult
    overhead_wire_aggregation: OverheadWireAggregationResult
    arm_aggregation: ArmAggregationResult
    direction_results: tuple[StandardDirectionalLoadResult, ...]
    stress_result: "NewJILPoleStressResult"


@dataclass(frozen=True)
class Standard9CalculationResult:
    """Complete old-traffic-signal result including Arm response."""

    design_standard: "DesignStandard"
    evaluated_position_m: float
    evaluated_pole_name: str
    material_name: str
    section_properties: PoleSectionProperties
    total_fix_load_n: float
    pole_aggregation: PoleAggregationResult
    direct_object_aggregation: DirectObjectAggregationResult
    overhead_wire_aggregation: OverheadWireAggregationResult
    arm_aggregation: ArmAggregationResult
    direction_results: tuple[StandardDirectionalLoadResult, ...]
    stress_result: "OldTrafficSignalPoleStressResult"

