from app.engine.calculators.direct_object import DirectObjectCalculator
from app.engine.calculators.pole import PoleCalculator
from app.engine.calculators.section_check import EvaluatedPositionCalculator
from app.engine.geometry.pole_assembly import PoleAssembly
from app.engine.loads.base import OverdesignFactor
from app.pole.mappers import map_pole_calculation
from app.pole.schemas import PoleCalculationRequest
from app.shared.adapters import (
    to_direct_object,
    to_pole_object,
    to_seismic_condition,
    to_wind_condition,
)
from app.shared.errors import CalculationInputError


def calculate_pole(request: PoleCalculationRequest) -> dict:
    wind = to_wind_condition(request.wind)
    seismic = to_seismic_condition(request.seismic)

    try:
        pole_calculator = PoleCalculator(
            assembly=PoleAssembly(
                [to_pole_object(pole) for pole in request.poles],
                base_elevation_m=request.base_elevation_m,
            ),
            wind_condition=wind,
            seismic_condition=seismic,
            overdesign_factor=OverdesignFactor(request.overdesign_factor),
        )
        direct_object_calculator = (
            DirectObjectCalculator(
                [to_direct_object(item) for item in request.direct_objects],
                wind,
                seismic,
            )
            if request.direct_objects
            else None
        )
        section_check = EvaluatedPositionCalculator(
            pole_calculator,
            direct_object_calculator,
        )
        positions = [
            (
                position,
                pole_calculator.aggregate_at(position),
                (
                    None
                    if direct_object_calculator is None
                    else direct_object_calculator.aggregate_at(position)
                ),
                section_check.calculate_at(position),
            )
            for position in request.evaluated_positions_m
        ]
    except ValueError as error:
        # Engine rules beyond the schema, e.g. a position above every pole top.
        raise CalculationInputError(str(error)) from error

    return map_pole_calculation(request, wind, seismic is not None, positions)
