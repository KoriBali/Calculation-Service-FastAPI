from typing import Annotated

from fastapi import APIRouter, Body

from app.section_check.docs import DESCRIPTION, REQUEST_EXAMPLES, RESPONSES
from app.section_check.schemas import SectionCheckRequest
from app.section_check.services import calculate_section_check
from app.shared.response import success_response

section_check_router = APIRouter(prefix="/api/section-check", tags=["section-check"])


# Plain def: the engine is CPU-bound, so FastAPI runs it in its thread pool.
@section_check_router.post(
    "/calculate",
    summary="Hitung section check tiang",
    description=DESCRIPTION,
    responses=RESPONSES,
)
def calculate(data: Annotated[SectionCheckRequest, Body(openapi_examples=REQUEST_EXAMPLES)]):
    # FastAPI validates the body before this runs. A body that is not a JSON
    # object becomes 400; ValidationError and CalculationInputError become 422
    # in app/shared/errors.py.
    return success_response(calculate_section_check(data))
