class NameComClientError(Exception):
    """Base exception for all name.com client failures."""
    pass


class NameComTimeoutError(NameComClientError):
    """Raised when name.com does not respond within the configured timeout."""
    pass


class NameComAPIError(NameComClientError):
    """
    Raised when name.com responds with an error or malformed payload.

    status_code / detail are optional and only populated when the failure
    came from an actual HTTP response (a real 4xx/5xx from name.com) rather
    than e.g. a malformed-JSON parse failure. status_code lets callers
    distinguish "name.com rejected this specific request" (4xx — a real,
    actionable reason worth showing the user) from "name.com itself is
    having problems" (5xx, or no response at all — genuinely a "try again
    later" situation). detail is name.com's own error message extracted
    from the response body, when available, for surfacing to the user
    instead of always falling back to a generic string.
    """
    def __init__(self, message: str, status_code: int | None = None, detail: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class NameComSandboxGuardError(NameComClientError):
    """
    Raised when a sandbox-only operation is configured against a base URL
    that does not resolve to the sandbox host. Never caught and reinterpreted
    as a routine provider failure — this indicates a configuration state
    that could otherwise let a "sandbox" call hit production.
    """
    pass