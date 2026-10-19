"""Turn validation and engine input errors into the error envelope."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.shared.response import error_response

# Error types FastAPI reports when the body itself is not a JSON object
# (invalid JSON, empty body, a list, or a non-JSON content type).
NOT_A_JSON_OBJECT = {"json_invalid", "missing", "model_type", "model_attributes_type"}


class CalculationInputError(Exception):
    """Input passed schema validation but the engine rejected it."""


def _field_errors(errors, skip: int = 0) -> list[dict]:
    return [
        {
            "field": ".".join(str(part) for part in item["loc"][skip:]),
            "message": item["msg"],
            "type": item["type"],
        }
        for item in errors
    ]


def _is_not_a_json_object(item: dict) -> bool:
    loc = tuple(item["loc"])
    return item["type"] == "json_invalid" or (
        loc == ("body",) and item["type"] in NOT_A_JSON_OBJECT
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _request_validation_error(request: Request, error: RequestValidationError):
        errors = error.errors()
        if any(_is_not_a_json_object(item) for item in errors):
            return error_response("Request body harus berupa JSON object", status_code=400)
        # FastAPI prefixes every loc with "body"; drop it so fields match the
        # model_validate() paths (e.g. "wind.1.atmospheric_category").
        return error_response("Input tidak valid", errors=_field_errors(errors, skip=1), status_code=422)

    @app.exception_handler(ValidationError)
    async def _validation_error(request: Request, error: ValidationError):
        errors = _field_errors(error.errors(include_url=False))
        return error_response("Input tidak valid", errors=errors, status_code=422)

    @app.exception_handler(CalculationInputError)
    async def _calculation_input_error(request: Request, error: CalculationInputError):
        return error_response(str(error), status_code=422)
