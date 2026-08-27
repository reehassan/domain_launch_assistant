class NameComClientError(Exception):
    """Base exception for all name.com client failures."""
    pass


class NameComTimeoutError(NameComClientError):
    """Raised when name.com does not respond within the configured timeout."""
    pass


class NameComAPIError(NameComClientError):
    """Raised when name.com responds with an error or malformed payload."""
    pass


class NameComSandboxGuardError(NameComClientError):
    """
    Raised when a sandbox-only operation is configured against a base URL
    that does not resolve to the sandbox host. Never caught and reinterpreted
    as a routine provider failure — this indicates a configuration state
    that could otherwise let a "sandbox" call hit production.
    """
    pass