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


# A body that is a union discriminated by ``design_standard``: pydantic puts the
# tag in the loc (("body", 3, "poles", 0)), or reports a bad or missing tag at
# ("body",). Both are rewritten so the field path is the same as for a plain model.
DESIGN_STANDARD_TAG_ERRORS = {"union_tag_invalid", "union_tag_not_found"}


def _body_loc(item: dict) -> tuple:
    loc = tuple(item["loc"][1:])
    if item["type"] in DESIGN_STANDARD_TAG_ERRORS and not loc:
        return ("design_standard",)
    # The body is a JSON object, so its first key is never an int: an int is the tag.
    if loc and isinstance(loc[0], int):
        return loc[1:]
    return loc


def _field_errors(errors, loc=lambda item: item["loc"]) -> list[dict]:
    return [
        {
            "field": ".".join(str(part) for part in loc(item)),
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
        # FastAPI prefixes every loc with "body"; drop it (and the design
        # standard tag) so fields match the model_validate() paths
        # (e.g. "poles.1.diameter_upper_mm").
        return error_response("Input tidak valid", errors=_field_errors(errors, _body_loc), status_code=422)

    @app.exception_handler(ValidationError)
    async def _validation_error(request: Request, error: ValidationError):
        errors = _field_errors(error.errors(include_url=False))
        return error_response("Input tidak valid", errors=errors, status_code=422)

    @app.exception_handler(CalculationInputError)
    async def _calculation_input_error(request: Request, error: CalculationInputError):
        return error_response(str(error), status_code=422)
