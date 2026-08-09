class SmokeError(Exception):
    """Expected EXP-004 configuration, protocol, or transport failure."""


class ConfigurationError(SmokeError):
    """The opt-in run was not configured safely enough to start."""


class RouteValidationError(SmokeError):
    """The Gateway route violated the narrow technical smoke contract."""


class TransportError(SmokeError):
    """The disposable Gateway transport failed without safe route evidence."""
