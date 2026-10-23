from typing import Annotated

from fastapi import APIRouter, Body

from app.pole.docs import DESCRIPTION, REQUEST_EXAMPLES, RESPONSES
from app.pole.schemas import PoleCalculationRequest
from app.pole.services import calculate_pole
from app.shared.response import success_response

pole_router = APIRouter(prefix="/api/pole", tags=["pole"])


# Plain def: the engine is CPU-bound, so FastAPI runs it in its thread pool.
@pole_router.post(
    "/calculate",
    summary="Hitung tiang (pole) dan cek penampangnya",
    description=DESCRIPTION,
    responses=RESPONSES,
)
def calculate(data: Annotated[PoleCalculationRequest, Body(openapi_examples=REQUEST_EXAMPLES)]):
    # FastAPI validates the body before this runs. A body that is not a JSON
    # object becomes 400; ValidationError and CalculationInputError become 422
    # in app/shared/errors.py.
    return success_response(calculate_pole(data))
