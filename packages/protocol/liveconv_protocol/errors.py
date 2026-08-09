from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable protocol version 1 error codes."""

    AUTH_FAILED = "AUTH_FAILED"
    UNSUPPORTED_PROTOCOL = "UNSUPPORTED_PROTOCOL"
    INVALID_STATE = "INVALID_STATE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    QUEUE_OVERFLOW = "QUEUE_OVERFLOW"
    SEQUENCE_GAP = "SEQUENCE_GAP"
    STALE_GENERATION = "STALE_GENERATION"
    UNSUPPORTED_AUDIO = "UNSUPPORTED_AUDIO"
    WORKER_CRASH = "WORKER_CRASH"


class RequiredAction(StrEnum):
    NONE = "none"
    RETRY = "retry"
    FALLBACK = "fallback"
    CLOSE_SESSION = "close_session"


class ProtocolValidationError(ValueError):
    """A wire value violates the accepted protocol contract."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
