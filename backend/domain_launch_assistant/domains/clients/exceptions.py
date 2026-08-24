# domain_launch_assistant/domains/clients/exceptions.py

class NameComClientError(Exception):
    """Base exception for all name.com client failures."""
    pass


class NameComTimeoutError(NameComClientError):
    """Raised when name.com does not respond within the configured timeout."""
    pass


class NameComAPIError(NameComClientError):
    """Raised when name.com responds with an error or malformed payload."""
    pass