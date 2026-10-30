"""Stress policy confirmed for design standards 1, 2, and 6.

Ported from python_calc ``calculation/stress/stress_policies.py`` (commit 270d23b).
"""

from dataclasses import dataclass
from math import pi, sqrt

from app.engine.calculation.rounding import (
    DecimalRoundingPolicy,
    SignificantFigureRoundingPolicy,
)
from app.engine.calculation.wind import EightDirectionWindCasePolicy

from .base import StressPolicy


@dataclass(frozen=True)
class CompressionBendingStressInput:
    """Explicit inputs for the non-concrete d_st 1, 2, and 6 method.

    Net/jaring-jaring and Arm are intentionally outside this input. Totals are
    supplied by the current Pole, Direct Object, and OHW calculation paths.
    """

    total_fix_load_n: float
    total_seismic_load_n: float
    total_wind_moment_nm: float
    total_seismic_moment_nm: float
    active_pole_segment_lengths_m: tuple[float, ...]
    cross_section_area_cm2: float
    section_modulus_cm3: float
    radius_of_gyration_cm: float
    short_term_allowable_bending_n_mm2: float


@dataclass(frozen=True)
class CompressionBendingStressResult:
    """Complete non-concrete stress result for d_st 1, 2, and 6."""

    absolute_total_wind_moment_nm: float
    absolute_total_seismic_moment_nm: float
    max_total_moment_nm: float
    controlling_load_case: str
    vertical_load_n: float
    buckling_length_cm: float
    slenderness_ratio_lambda: float
    limit_slenderness_ratio_lambda: float
    safety_factor_nu: float
    allowable_compressive_stress_n_mm2: float
    compressive_stress_n_mm2: float
    bending_stress_n_mm2: float
    compression_utilization_ratio: float
    bending_utilization_ratio: float
    total_utilization_ratio: float
    status: str


@dataclass(frozen=True)
class CompressionBendingStressPolicy(StressPolicy):
    """Steel-pole stress method confirmed for d_st 1, 2, and 6."""

    elastic_modulus_n_mm2: float = 205000.0

    def __post_init__(self) -> None:
        if self.elastic_modulus_n_mm2 <= 0:
            raise ValueError("Elastic modulus must be greater than zero")

    def calculate(
        self,
        calculation_input: CompressionBendingStressInput,
    ) -> CompressionBendingStressResult:
        if not isinstance(calculation_input, CompressionBendingStressInput):
            raise TypeError(
                "calculation_input must be CompressionBendingStressInput"
            )
        self._validate(calculation_input)
        rounding = DecimalRoundingPolicy()

        wind_moment = abs(float(calculation_input.total_wind_moment_nm))
        seismic_moment = abs(float(calculation_input.total_seismic_moment_nm))

        if wind_moment > seismic_moment:
            max_total_moment = wind_moment
            vertical_load = float(calculation_input.total_fix_load_n)
            controlling_case = "wind"
        else:
            max_total_moment = seismic_moment
            vertical_load = (
                float(calculation_input.total_fix_load_n)
                + 0.5 * float(calculation_input.total_seismic_load_n)
            )
            controlling_case = "seismic"

        buckling_length_cm = (
            sum(calculation_input.active_pole_segment_lengths_m)
            * 2
            * 100
        )
        slenderness_ratio = rounding.apply(
            buckling_length_cm
            / calculation_input.radius_of_gyration_cm,
            1,
        )
        limit_slenderness_ratio = rounding.apply(
            sqrt(
                (pi**2 * self.elastic_modulus_n_mm2)
                / (
                    0.6
                    * calculation_input.short_term_allowable_bending_n_mm2
                )
            ),
            0,
        )
        safety_factor_nu = rounding.apply(
            3 / 2
            + 2 / 3
            * (slenderness_ratio / limit_slenderness_ratio) ** 2,
            2,
        )

        slenderness_fraction = (
            slenderness_ratio / limit_slenderness_ratio
        )
        if slenderness_ratio <= limit_slenderness_ratio:
            allowable_compressive_stress = rounding.apply(
                (
                    (1 - 0.4 * slenderness_fraction**2)
                    * calculation_input.short_term_allowable_bending_n_mm2
                    / safety_factor_nu
                ),
                1,
            )
        else:
            allowable_compressive_stress = rounding.apply(
                0.277
                * calculation_input.short_term_allowable_bending_n_mm2
                / slenderness_fraction**2,
                1,
            )

        compressive_stress = rounding.apply(
            vertical_load
            / (calculation_input.cross_section_area_cm2 * 100),
            3,
        )
        bending_stress = rounding.apply(
            max_total_moment / calculation_input.section_modulus_cm3,
            1,
        )
        compression_utilization = rounding.apply(
            compressive_stress / (1.5 * allowable_compressive_stress),
            3,
        )
        bending_utilization = rounding.apply(
            bending_stress
            / calculation_input.short_term_allowable_bending_n_mm2,
            3,
        )
        total_utilization = rounding.apply(
            compression_utilization + bending_utilization,
            3,
        )

        return CompressionBendingStressResult(
            absolute_total_wind_moment_nm=wind_moment,
            absolute_total_seismic_moment_nm=seismic_moment,
            max_total_moment_nm=max_total_moment,
            controlling_load_case=controlling_case,
            vertical_load_n=vertical_load,
            buckling_length_cm=buckling_length_cm,
            slenderness_ratio_lambda=slenderness_ratio,
            limit_slenderness_ratio_lambda=limit_slenderness_ratio,
            safety_factor_nu=safety_factor_nu,
            allowable_compressive_stress_n_mm2=(
                allowable_compressive_stress
            ),
            compressive_stress_n_mm2=compressive_stress,
            bending_stress_n_mm2=bending_stress,
            compression_utilization_ratio=compression_utilization,
            bending_utilization_ratio=bending_utilization,
            total_utilization_ratio=total_utilization,
            status="O.K" if total_utilization < 1.0 else "N.G",
        )

    @staticmethod
    def _validate(calculation_input: CompressionBendingStressInput) -> None:
        non_negative = {
            "total_fix_load_n": calculation_input.total_fix_load_n,
            "total_seismic_load_n": calculation_input.total_seismic_load_n,
        }
        for name, value in non_negative.items():
            if value < 0:
                raise ValueError(f"{name} cannot be negative")

        if not calculation_input.active_pole_segment_lengths_m:
            raise ValueError("At least one active pole segment is required")
        if any(
            length <= 0
            for length in calculation_input.active_pole_segment_lengths_m
        ):
            raise ValueError(
                "Active pole segment lengths must be greater than zero"
            )

        positive = {
            "cross_section_area_cm2": calculation_input.cross_section_area_cm2,
            "section_modulus_cm3": calculation_input.section_modulus_cm3,
            "radius_of_gyration_cm": (
                calculation_input.radius_of_gyration_cm
            ),
            "short_term_allowable_bending_n_mm2": (
                calculation_input.short_term_allowable_bending_n_mm2
            ),
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")


@dataclass(frozen=True)
class SimpleBendingStressInput:
    """Final directional moment and pole properties for d_st 3 and 4."""

    total_moment_nm: float
    section_modulus_cm3: float
    short_term_allowable_bending_n_mm2: float


@dataclass(frozen=True)
class SimpleBendingStressResult:
    """Bending-only safety result for d_st 3 and 4."""

    absolute_total_moment_nm: float
    section_modulus_cm3: float
    bending_stress_n_mm2: float
    short_term_allowable_bending_n_mm2: float
    safety_factor: float
    status: str


@dataclass(frozen=True)
class SimpleBendingStressPolicy(StressPolicy):
    """Bending-only method confirmed for d_st 3 and 4.

    The caller supplies the final moment for the selected wind direction. The
    normal report path supplies direction N at 90 degrees. Directional moment
    generation and OHW moment combination remain outside this stress policy.
    """

    def calculate(
        self,
        calculation_input: SimpleBendingStressInput,
    ) -> SimpleBendingStressResult:
        if not isinstance(calculation_input, SimpleBendingStressInput):
            raise TypeError(
                "calculation_input must be SimpleBendingStressInput"
            )
        if calculation_input.section_modulus_cm3 <= 0:
            raise ValueError("Section modulus must be greater than zero")
        if calculation_input.short_term_allowable_bending_n_mm2 <= 0:
            raise ValueError(
                "Short-term allowable bending stress must be greater than zero"
            )

        rounding = DecimalRoundingPolicy()
        absolute_total_moment = abs(float(calculation_input.total_moment_nm))
        bending_stress = rounding.apply(
            absolute_total_moment / calculation_input.section_modulus_cm3,
            1,
        )
        safety_factor = rounding.apply(
            bending_stress
            / calculation_input.short_term_allowable_bending_n_mm2,
            3,
        )

        return SimpleBendingStressResult(
            absolute_total_moment_nm=absolute_total_moment,
            section_modulus_cm3=calculation_input.section_modulus_cm3,
            bending_stress_n_mm2=bending_stress,
            short_term_allowable_bending_n_mm2=(
                calculation_input.short_term_allowable_bending_n_mm2
            ),
            safety_factor=safety_factor,
            status="O.K" if safety_factor <= 1.0 else "N.G",
        )


@dataclass(frozen=True)
class LargeSignPoleStressInput:
    """Round-pole stress inputs for the d_st 5 large-sign method.

    Loads and moments are final values calculated upstream. Arm-member stress
    and rectangular-pole equations are intentionally outside this first
    implementation.
    """

    total_fix_load_n: float
    straight_total_bending_moment_nm: float
    straight_total_torsional_moment_nm: float
    oblique_total_bending_moment_nm: float
    oblique_total_torsional_moment_nm: float
    arm_height_m: float
    evaluated_position_m: float
    pole_diameter_mm: float
    cross_section_area_cm2: float
    moment_of_inertia_cm4: float
    section_modulus_cm3: float
    radius_of_gyration_cm: float
    short_term_allowable_bending_n_mm2: float
    short_term_allowable_shear_n_mm2: float


@dataclass(frozen=True)
class LargeSignPoleDirectionStressResult:
    """Stress result for one d_st 5 wind direction."""

    wind_case_name: str
    wind_direction_deg: float
    absolute_total_bending_moment_nm: float
    absolute_total_torsional_moment_nm: float
    bending_stress_n_mm2: float
    compressive_stress_n_mm2: float
    combined_compression_bending_stress_n_mm2: float
    compression_utilization_ratio: float
    bending_utilization_ratio: float
    compression_bending_utilization_ratio: float
    compression_bending_status: str
    torsional_shear_stress_n_mm2: float
    maximum_shear_stress_n_mm2: float
    shear_utilization_ratio: float
    shear_status: str
    maximum_combined_stress_n_mm2: float
    combined_utilization_ratio: float
    combined_status: str


@dataclass(frozen=True)
class LargeSignPoleStressResult:
    """Complete round-pole result for d_st 5 straight and oblique wind."""

    distance_to_arm_height_m: float
    buckling_length_cm: float
    slenderness_ratio_lambda: float
    limit_slenderness_ratio_lambda: float
    safety_factor_nu: float
    allowable_compressive_stress_n_mm2: float
    polar_moment_of_inertia_cm4: float
    straight: LargeSignPoleDirectionStressResult
    oblique: LargeSignPoleDirectionStressResult


@dataclass(frozen=True)
class LargeSignPoleStressPolicy(StressPolicy):
    """Confirmed d_st 5 stress method for a round pole only."""

    elastic_modulus_n_mm2: float = 205000.0

    def __post_init__(self) -> None:
        if self.elastic_modulus_n_mm2 <= 0:
            raise ValueError("Elastic modulus must be greater than zero")

    def calculate(
        self,
        calculation_input: LargeSignPoleStressInput,
    ) -> LargeSignPoleStressResult:
        if not isinstance(calculation_input, LargeSignPoleStressInput):
            raise TypeError("calculation_input must be LargeSignPoleStressInput")
        self._validate(calculation_input)
        rounding = DecimalRoundingPolicy()

        distance_to_arm_height_m = (
            calculation_input.arm_height_m
            - calculation_input.evaluated_position_m
        )
        buckling_length_cm = 2 * distance_to_arm_height_m * 100
        slenderness_ratio = rounding.apply(
            buckling_length_cm / calculation_input.radius_of_gyration_cm,
            1,
        )
        limit_slenderness_ratio = rounding.apply(
            sqrt(
                (pi**2 * self.elastic_modulus_n_mm2)
                / (0.6 * calculation_input.short_term_allowable_bending_n_mm2)
            ),
            0,
        )
        slenderness_fraction = slenderness_ratio / limit_slenderness_ratio
        safety_factor_nu = rounding.apply(
            3 / 2 + 2 / 3 * slenderness_fraction**2,
            2,
        )
        if slenderness_ratio <= limit_slenderness_ratio:
            allowable_compressive_stress = rounding.apply(
                (
                    (1 - 0.4 * slenderness_fraction**2)
                    * calculation_input.short_term_allowable_bending_n_mm2
                    / safety_factor_nu
                ),
                1,
            )
        else:
            allowable_compressive_stress = rounding.apply(
                0.277
                * calculation_input.short_term_allowable_bending_n_mm2
                / slenderness_fraction**2,
                1,
            )

        compressive_stress = rounding.apply(
            calculation_input.total_fix_load_n
            / (calculation_input.cross_section_area_cm2 * 100),
            2,
        )
        polar_moment_of_inertia = 2 * calculation_input.moment_of_inertia_cm4

        def direction_result(
            name: str,
            angle_deg: float,
            bending_moment_nm: float,
            torsional_moment_nm: float,
        ) -> LargeSignPoleDirectionStressResult:
            absolute_bending_moment = abs(float(bending_moment_nm))
            absolute_torsional_moment = abs(float(torsional_moment_nm))
            bending_stress = rounding.apply(
                absolute_bending_moment / calculation_input.section_modulus_cm3,
                1,
            )
            compression_bending_stress = rounding.apply(
                compressive_stress + bending_stress,
                1,
            )
            compression_utilization = compressive_stress / (
                allowable_compressive_stress * 1.5
            )
            bending_utilization = (
                bending_stress
                / calculation_input.short_term_allowable_bending_n_mm2
            )
            compression_bending_utilization = rounding.apply(
                compression_utilization + bending_utilization,
                3,
            )

            # Round-pole VBA equation:
            # tau = Mt * (diameter_cm) / (I_cm4 * 2 * 2)
            torsional_shear_stress = rounding.apply(
                absolute_torsional_moment
                * (calculation_input.pole_diameter_mm / 10)
                / (calculation_input.moment_of_inertia_cm4 * 2 * 2),
                1,
            )
            maximum_shear_stress = rounding.apply(
                sqrt(
                    compression_bending_stress**2
                    + 4 * torsional_shear_stress**2
                )
                / 2,
                1,
            )
            shear_utilization = rounding.apply(
                maximum_shear_stress
                / calculation_input.short_term_allowable_shear_n_mm2,
                3,
            )
            maximum_combined_stress = rounding.apply(
                compression_bending_stress / 2 + maximum_shear_stress,
                1,
            )
            combined_utilization = rounding.apply(
                maximum_combined_stress
                / calculation_input.short_term_allowable_bending_n_mm2,
                3,
            )

            return LargeSignPoleDirectionStressResult(
                wind_case_name=name,
                wind_direction_deg=angle_deg,
                absolute_total_bending_moment_nm=absolute_bending_moment,
                absolute_total_torsional_moment_nm=absolute_torsional_moment,
                bending_stress_n_mm2=bending_stress,
                compressive_stress_n_mm2=compressive_stress,
                combined_compression_bending_stress_n_mm2=(
                    compression_bending_stress
                ),
                compression_utilization_ratio=compression_utilization,
                bending_utilization_ratio=bending_utilization,
                compression_bending_utilization_ratio=(
                    compression_bending_utilization
                ),
                compression_bending_status=(
                    "O.K"
                    if compression_bending_utilization < 1.0
                    else "N.G"
                ),
                torsional_shear_stress_n_mm2=torsional_shear_stress,
                maximum_shear_stress_n_mm2=maximum_shear_stress,
                shear_utilization_ratio=shear_utilization,
                shear_status="O.K" if shear_utilization < 1.0 else "N.G",
                maximum_combined_stress_n_mm2=maximum_combined_stress,
                combined_utilization_ratio=combined_utilization,
                combined_status=(
                    "O.K" if combined_utilization < 1.0 else "N.G"
                ),
            )

        return LargeSignPoleStressResult(
            distance_to_arm_height_m=distance_to_arm_height_m,
            buckling_length_cm=buckling_length_cm,
            slenderness_ratio_lambda=slenderness_ratio,
            limit_slenderness_ratio_lambda=limit_slenderness_ratio,
            safety_factor_nu=safety_factor_nu,
            allowable_compressive_stress_n_mm2=allowable_compressive_stress,
            polar_moment_of_inertia_cm4=polar_moment_of_inertia,
            straight=direction_result(
                "STRAIGHT",
                90.0,
                calculation_input.straight_total_bending_moment_nm,
                calculation_input.straight_total_torsional_moment_nm,
            ),
            oblique=direction_result(
                "OBLIQUE",
                45.0,
                calculation_input.oblique_total_bending_moment_nm,
                calculation_input.oblique_total_torsional_moment_nm,
            ),
        )

    @staticmethod
    def _validate(calculation_input: LargeSignPoleStressInput) -> None:
        if calculation_input.total_fix_load_n < 0:
            raise ValueError("total_fix_load_n cannot be negative")
        if calculation_input.evaluated_position_m < 0:
            raise ValueError("evaluated_position_m cannot be negative")
        if calculation_input.arm_height_m <= calculation_input.evaluated_position_m:
            raise ValueError(
                "arm_height_m must be greater than evaluated_position_m"
            )

        positive = {
            "pole_diameter_mm": calculation_input.pole_diameter_mm,
            "cross_section_area_cm2": calculation_input.cross_section_area_cm2,
            "moment_of_inertia_cm4": calculation_input.moment_of_inertia_cm4,
            "section_modulus_cm3": calculation_input.section_modulus_cm3,
            "radius_of_gyration_cm": calculation_input.radius_of_gyration_cm,
            "short_term_allowable_bending_n_mm2": (
                calculation_input.short_term_allowable_bending_n_mm2
            ),
            "short_term_allowable_shear_n_mm2": (
                calculation_input.short_term_allowable_shear_n_mm2
            ),
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")


@dataclass(frozen=True)
class OldTrafficSignalPoleStressInput:
    """Round-pole inputs for the eight-direction d_st 9 stress method.

    Both moment tuples must follow the confirmed order:
    N, S, E, W, NE, SW, NW, SE.
    """

    total_bending_moments_nm: tuple[float, ...]
    total_torsional_moments_nm: tuple[float, ...]
    pole_diameter_mm: float
    moment_of_inertia_cm4: float
    section_modulus_cm3: float
    short_term_allowable_bending_n_mm2: float
    short_term_allowable_shear_n_mm2: float


@dataclass(frozen=True)
class OldTrafficSignalPoleDirectionStressResult:
    """Stress result for one of the eight d_st 9 wind directions."""

    wind_case_name: str
    wind_direction_deg: float
    absolute_total_bending_moment_nm: float
    absolute_total_torsional_moment_nm: float
    bending_stress_n_mm2: float
    bending_utilization_ratio: float
    bending_status: str
    torsional_shear_stress_n_mm2: float
    maximum_shear_stress_n_mm2: float
    shear_utilization_ratio: float
    shear_status: str
    maximum_combined_stress_n_mm2: float
    combined_utilization_ratio: float
    combined_status: str


@dataclass(frozen=True)
class OldTrafficSignalPoleStressResult:
    """Complete eight-direction stress result for d_st 9."""

    polar_moment_of_inertia_cm4: float
    direction_results: tuple[OldTrafficSignalPoleDirectionStressResult, ...]


@dataclass(frozen=True)
class OldTrafficSignalPoleStressPolicy(StressPolicy):
    """Confirmed bending-and-torsion stress method for round-pole d_st 9."""

    def calculate(
        self,
        calculation_input: OldTrafficSignalPoleStressInput,
    ) -> OldTrafficSignalPoleStressResult:
        if not isinstance(calculation_input, OldTrafficSignalPoleStressInput):
            raise TypeError(
                "calculation_input must be OldTrafficSignalPoleStressInput"
            )
        self._validate(calculation_input)
        rounding = DecimalRoundingPolicy()
        wind_cases = EightDirectionWindCasePolicy().cases()
        direction_results = []

        for wind_case, bending_moment, torsional_moment in zip(
            wind_cases,
            calculation_input.total_bending_moments_nm,
            calculation_input.total_torsional_moments_nm,
        ):
            absolute_bending_moment = abs(float(bending_moment))
            absolute_torsional_moment = abs(float(torsional_moment))
            bending_stress = rounding.apply(
                absolute_bending_moment / calculation_input.section_modulus_cm3,
                1,
            )
            bending_utilization = rounding.apply(
                bending_stress
                / calculation_input.short_term_allowable_bending_n_mm2,
                3,
            )
            torsional_shear_stress = rounding.apply(
                absolute_torsional_moment
                * (calculation_input.pole_diameter_mm / 10)
                / (calculation_input.moment_of_inertia_cm4 * 2 * 2),
                1,
            )
            maximum_shear_stress = rounding.apply(
                sqrt(
                    bending_stress**2
                    + 4 * torsional_shear_stress**2
                )
                / 2,
                1,
            )
            shear_utilization = rounding.apply(
                maximum_shear_stress
                / calculation_input.short_term_allowable_shear_n_mm2,
                3,
            )
            maximum_combined_stress = rounding.apply(
                bending_stress / 2 + maximum_shear_stress,
                1,
            )
            combined_utilization = rounding.apply(
                maximum_combined_stress
                / calculation_input.short_term_allowable_bending_n_mm2,
                3,
            )

            direction_results.append(
                OldTrafficSignalPoleDirectionStressResult(
                    wind_case_name=wind_case.name,
                    wind_direction_deg=wind_case.angle_deg,
                    absolute_total_bending_moment_nm=absolute_bending_moment,
                    absolute_total_torsional_moment_nm=absolute_torsional_moment,
                    bending_stress_n_mm2=bending_stress,
                    bending_utilization_ratio=bending_utilization,
                    bending_status=(
                        "O.K"
                        if bending_stress
                        < calculation_input.short_term_allowable_bending_n_mm2
                        else "N.G"
                    ),
                    torsional_shear_stress_n_mm2=torsional_shear_stress,
                    maximum_shear_stress_n_mm2=maximum_shear_stress,
                    shear_utilization_ratio=shear_utilization,
                    shear_status=(
                        "O.K"
                        if maximum_shear_stress
                        < calculation_input.short_term_allowable_shear_n_mm2
                        else "N.G"
                    ),
                    maximum_combined_stress_n_mm2=maximum_combined_stress,
                    combined_utilization_ratio=combined_utilization,
                    combined_status=(
                        "O.K"
                        if maximum_combined_stress
                        < calculation_input.short_term_allowable_bending_n_mm2
                        else "N.G"
                    ),
                )
            )

        return OldTrafficSignalPoleStressResult(
            polar_moment_of_inertia_cm4=(
                2 * calculation_input.moment_of_inertia_cm4
            ),
            direction_results=tuple(direction_results),
        )

    @staticmethod
    def _validate(calculation_input: OldTrafficSignalPoleStressInput) -> None:
        expected_direction_count = 8
        if len(calculation_input.total_bending_moments_nm) != expected_direction_count:
            raise ValueError(
                "total_bending_moments_nm must contain exactly eight values"
            )
        if len(calculation_input.total_torsional_moments_nm) != expected_direction_count:
            raise ValueError(
                "total_torsional_moments_nm must contain exactly eight values"
            )

        positive = {
            "pole_diameter_mm": calculation_input.pole_diameter_mm,
            "moment_of_inertia_cm4": calculation_input.moment_of_inertia_cm4,
            "section_modulus_cm3": calculation_input.section_modulus_cm3,
            "short_term_allowable_bending_n_mm2": (
                calculation_input.short_term_allowable_bending_n_mm2
            ),
            "short_term_allowable_shear_n_mm2": (
                calculation_input.short_term_allowable_shear_n_mm2
            ),
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")


@dataclass(frozen=True)
class NewJILPoleStressInput:
    """Round-pole inputs for the eight-direction New JIL stress method.

    Every moment tuple follows the confirmed order N, S, E, W, NE, SW, NW,
    SE. ``moments_due_to_fixload_nm`` contains moments caused by objects on
    an arm, not their vertical FixLoad values in newtons.
    """

    moments_due_to_fixload_nm: tuple[float, ...]
    combined_wind_moments_nm: tuple[float, ...]
    wind_torsional_moments_nm: tuple[float, ...]
    combined_seismic_moments_nm: tuple[float, ...]
    seismic_torsional_moments_nm: tuple[float, ...]
    pole_diameter_mm: float
    moment_of_inertia_cm4: float
    section_modulus_cm3: float
    allowable_bending_n_mm2: float
    short_term_allowable_bending_n_mm2: float
    short_term_allowable_shear_n_mm2: float


@dataclass(frozen=True)
class NewJILPoleDirectionStressResult:
    """FixLoad, wind, and seismic stress results for one direction."""

    wind_case_name: str
    wind_direction_deg: float
    absolute_moment_due_to_fixload_nm: float
    fixload_bending_stress_n_mm2: float
    fixload_bending_utilization_ratio: float
    fixload_bending_status: str
    absolute_combined_wind_moment_nm: float
    absolute_wind_torsional_moment_nm: float
    wind_bending_stress_n_mm2: float
    wind_bending_utilization_ratio: float
    wind_bending_status: str
    wind_torsional_shear_stress_n_mm2: float
    wind_torsional_utilization_ratio: float
    wind_torsional_status: str
    wind_maximum_shear_stress_n_mm2: float
    wind_maximum_combined_stress_n_mm2: float
    wind_combined_utilization_ratio: float
    wind_combined_status: str
    absolute_combined_seismic_moment_nm: float
    absolute_seismic_torsional_moment_nm: float
    seismic_bending_stress_n_mm2: float
    seismic_bending_utilization_ratio: float
    seismic_bending_status: str
    seismic_torsional_shear_stress_n_mm2: float
    seismic_torsional_utilization_ratio: float
    seismic_torsional_status: str
    seismic_maximum_shear_stress_n_mm2: float
    seismic_maximum_combined_stress_n_mm2: float
    seismic_combined_utilization_ratio: float
    seismic_combined_status: str


@dataclass(frozen=True)
class NewJILPoleStressResult:
    """Complete New JIL stress result without report-case selection."""

    polar_moment_of_inertia_cm4: float
    direction_results: tuple[NewJILPoleDirectionStressResult, ...]


@dataclass(frozen=True)
class NewJILPoleStressPolicy(StressPolicy):
    """Confirmed d_st 7 stress method for a round pole."""

    def calculate(
        self,
        calculation_input: NewJILPoleStressInput,
    ) -> NewJILPoleStressResult:
        if not isinstance(calculation_input, NewJILPoleStressInput):
            raise TypeError("calculation_input must be NewJILPoleStressInput")
        self._validate(calculation_input)
        rounding = SignificantFigureRoundingPolicy()
        wind_cases = EightDirectionWindCasePolicy().cases()
        direction_results = []

        def sf(value: float) -> float:
            return rounding.apply(value, 3)

        def status(utilization: float) -> str:
            return "O.K" if utilization < 1.0 else "N.G"

        def short_term_case(
            combined_moment_nm: float,
            torsional_moment_nm: float,
        ) -> tuple[float | str, ...]:
            absolute_combined_moment = abs(float(combined_moment_nm))
            absolute_torsional_moment = abs(float(torsional_moment_nm))
            bending_stress = sf(
                absolute_combined_moment
                / calculation_input.section_modulus_cm3
            )
            bending_utilization = sf(
                bending_stress
                / calculation_input.short_term_allowable_bending_n_mm2
            )
            torsional_stress = sf(
                absolute_torsional_moment
                * (calculation_input.pole_diameter_mm / 10)
                / (calculation_input.moment_of_inertia_cm4 * 2 * 2)
            )
            torsional_utilization = sf(
                torsional_stress
                / calculation_input.short_term_allowable_shear_n_mm2
            )
            maximum_shear_stress = sf(
                sqrt(bending_stress**2 + 4 * torsional_stress**2) / 2
            )
            maximum_combined_stress = sf(
                (
                    absolute_combined_moment
                    / calculation_input.section_modulus_cm3
                )
                / 2
                + maximum_shear_stress
            )
            combined_utilization = sf(
                maximum_combined_stress
                / calculation_input.short_term_allowable_bending_n_mm2
            )
            return (
                absolute_combined_moment,
                absolute_torsional_moment,
                bending_stress,
                bending_utilization,
                status(bending_utilization),
                torsional_stress,
                torsional_utilization,
                status(torsional_utilization),
                maximum_shear_stress,
                maximum_combined_stress,
                combined_utilization,
                status(combined_utilization),
            )

        for index, wind_case in enumerate(wind_cases):
            absolute_fixload_moment = abs(
                float(calculation_input.moments_due_to_fixload_nm[index])
            )
            fixload_bending_stress = sf(
                absolute_fixload_moment
                / calculation_input.section_modulus_cm3
            )
            fixload_utilization = sf(
                fixload_bending_stress
                / calculation_input.allowable_bending_n_mm2
            )
            wind = short_term_case(
                calculation_input.combined_wind_moments_nm[index],
                calculation_input.wind_torsional_moments_nm[index],
            )
            seismic = short_term_case(
                calculation_input.combined_seismic_moments_nm[index],
                calculation_input.seismic_torsional_moments_nm[index],
            )

            direction_results.append(
                NewJILPoleDirectionStressResult(
                    wind_case_name=wind_case.name,
                    wind_direction_deg=wind_case.angle_deg,
                    absolute_moment_due_to_fixload_nm=absolute_fixload_moment,
                    fixload_bending_stress_n_mm2=fixload_bending_stress,
                    fixload_bending_utilization_ratio=fixload_utilization,
                    fixload_bending_status=status(fixload_utilization),
                    absolute_combined_wind_moment_nm=wind[0],
                    absolute_wind_torsional_moment_nm=wind[1],
                    wind_bending_stress_n_mm2=wind[2],
                    wind_bending_utilization_ratio=wind[3],
                    wind_bending_status=wind[4],
                    wind_torsional_shear_stress_n_mm2=wind[5],
                    wind_torsional_utilization_ratio=wind[6],
                    wind_torsional_status=wind[7],
                    wind_maximum_shear_stress_n_mm2=wind[8],
                    wind_maximum_combined_stress_n_mm2=wind[9],
                    wind_combined_utilization_ratio=wind[10],
                    wind_combined_status=wind[11],
                    absolute_combined_seismic_moment_nm=seismic[0],
                    absolute_seismic_torsional_moment_nm=seismic[1],
                    seismic_bending_stress_n_mm2=seismic[2],
                    seismic_bending_utilization_ratio=seismic[3],
                    seismic_bending_status=seismic[4],
                    seismic_torsional_shear_stress_n_mm2=seismic[5],
                    seismic_torsional_utilization_ratio=seismic[6],
                    seismic_torsional_status=seismic[7],
                    seismic_maximum_shear_stress_n_mm2=seismic[8],
                    seismic_maximum_combined_stress_n_mm2=seismic[9],
                    seismic_combined_utilization_ratio=seismic[10],
                    seismic_combined_status=seismic[11],
                )
            )

        return NewJILPoleStressResult(
            polar_moment_of_inertia_cm4=(
                2 * calculation_input.moment_of_inertia_cm4
            ),
            direction_results=tuple(direction_results),
        )

    @staticmethod
    def _validate(calculation_input: NewJILPoleStressInput) -> None:
        directional_fields = {
            "moments_due_to_fixload_nm": (
                calculation_input.moments_due_to_fixload_nm
            ),
            "combined_wind_moments_nm": (
                calculation_input.combined_wind_moments_nm
            ),
            "wind_torsional_moments_nm": (
                calculation_input.wind_torsional_moments_nm
            ),
            "combined_seismic_moments_nm": (
                calculation_input.combined_seismic_moments_nm
            ),
            "seismic_torsional_moments_nm": (
                calculation_input.seismic_torsional_moments_nm
            ),
        }
        for name, values in directional_fields.items():
            if len(values) != 8:
                raise ValueError(f"{name} must contain exactly eight values")

        positive = {
            "pole_diameter_mm": calculation_input.pole_diameter_mm,
            "moment_of_inertia_cm4": calculation_input.moment_of_inertia_cm4,
            "section_modulus_cm3": calculation_input.section_modulus_cm3,
            "allowable_bending_n_mm2": (
                calculation_input.allowable_bending_n_mm2
            ),
            "short_term_allowable_bending_n_mm2": (
                calculation_input.short_term_allowable_bending_n_mm2
            ),
            "short_term_allowable_shear_n_mm2": (
                calculation_input.short_term_allowable_shear_n_mm2
            ),
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
