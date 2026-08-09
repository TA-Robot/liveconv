"""Public, redacted errors raised by the STT evidence runner."""


class SttError(Exception):
    """Base class for expected STT runner failures."""


class AudioValidationError(SttError):
    """The input is not an accepted bounded mono PCM WAV artifact."""


class ConfigurationError(SttError):
    """Provenance or decoding configuration is invalid."""


class ArtifactVerificationError(SttError):
    """A local model artifact cannot be verified."""


class BackendExecutionError(SttError):
    """The backend failed without exposing its potentially sensitive detail."""
