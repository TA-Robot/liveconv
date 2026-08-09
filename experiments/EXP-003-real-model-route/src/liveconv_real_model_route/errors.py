class HarnessError(RuntimeError):
    """A bounded route or evidence invariant failed."""


class ConfigurationError(HarnessError):
    """Environment, registry, or command configuration is invalid."""


class TransportError(HarnessError):
    """The Gateway transport failed or timed out."""


class RouteValidationError(HarnessError):
    """The Gateway route violated an EXP-003 technical invariant."""
