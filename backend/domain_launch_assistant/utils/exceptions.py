from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler

from rest_framework.response import Response


class AIGenerationFailed(APIException):
    """
    Raised by brand/domain generation services when the AI provider fails
    outright, returns malformed structured output, or returns an empty
    result. Maps to api-contract.md section 26 (AI Failure Contract).
    """

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Brand generation could not be completed. Please try again."
    default_code = "ai_generation_failed"


# Maps DRF's built-in exception default_code values (and our own custom
# ones) onto the contract's documented error codes (api-contract.md
# section 3). DRF's own naming ("not_authenticated", "permission_denied",
# "not_found") is close but not identical to the contract's — this table
# is the one place that reconciles the two, instead of every exception
# silently reporting "VALIDATION_ERROR" the way it did before.
_CODE_MAP = {
    "not_authenticated": "AUTHENTICATION_REQUIRED",
    "authentication_failed": "AUTHENTICATION_REQUIRED",
    "permission_denied": "PERMISSION_DENIED",
    "not_found": "NOT_FOUND",
    "invalid": "VALIDATION_ERROR",
    "parse_error": "VALIDATION_ERROR",
    "throttled": "VALIDATION_ERROR",
    "ai_generation_failed": "AI_GENERATION_FAILED",
    "token_not_valid": "TOKEN_INVALID",
}


def custom_exception_handler(exc, context):
    from django.core.exceptions import PermissionDenied
    from django.http import Http404
    from rest_framework.exceptions import NotFound
    from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied

    # DRF's exception_handler() converts these internally but doesn't
    # give us back the converted exception — so without this, exc here
    # stays a plain Http404/PermissionDenied with no default_code,
    # and every 404/403 falls through to VALIDATION_ERROR below.
    if isinstance(exc, Http404):
        exc = NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = DRFPermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        # Not a DRF/Django exception the default handler recognizes
        # (e.g. an unhandled Python exception) — let it propagate as a
        # 500 rather than pretending we have a clean error shape for it.
        return None

    default_code = getattr(exc, "default_code", "invalid")
    code = _CODE_MAP.get(default_code, "VALIDATION_ERROR")

    # response.data is either:
    #  - a dict of field errors (serializer ValidationError, e.g.
    #    {"business_description": ["This field is required."]})
    #  - {"detail": "..."} for simple APIExceptions (401/403/404/AIGenerationFailed/etc.)
    # Only the second case has a clean top-level message worth surfacing;
    # the first is genuinely a multi-field error and should stay generic.
    if isinstance(response.data, dict) and set(response.data.keys()) == {"detail"}:
        message = str(response.data["detail"])
    else:
        message = "The request contains invalid data."

    response.data = {
        "error": {
            "code": code,
            "message": message,
            "details": response.data,
        }
    }
    return response


def api_error(code: str, message: str, status_code: int, details: dict | None = None) -> Response:
    """
    Build a DRF Response using the project's standard error envelope.
    """
    payload = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details is not None:
        payload["error"]["details"] = details
 
    return Response(payload, status=status_code)
