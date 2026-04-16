"""Request validation helpers for the wrapped `{"data": {...}}` envelope."""

from typing import Any
from typing import TypeVar

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from pydantic import ValidationError

SchemaType = TypeVar("SchemaType", bound=BaseModel)


def _build_missing_data_error(payload: dict[str, Any]) -> RequestValidationError:
    return RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", "data"),
                "msg": "Field required",
                "input": payload,
            }
        ]
    )


def _build_nested_validation_error(exc: ValidationError) -> RequestValidationError:
    errors = []
    for error in exc.errors():
        scoped_error = dict(error)
        scoped_error["loc"] = ("body", "data", *error.get("loc", ()))
        errors.append(scoped_error)
    return RequestValidationError(errors)


def validate_data_payload(
    payload: dict[str, Any],
    schema_cls: type[SchemaType],
) -> SchemaType:
    """Validate a wrapped payload and return the typed inner data."""
    if "data" not in payload:
        raise _build_missing_data_error(payload)

    try:
        return schema_cls.model_validate(payload["data"])
    except ValidationError as exc:
        raise _build_nested_validation_error(exc) from exc
