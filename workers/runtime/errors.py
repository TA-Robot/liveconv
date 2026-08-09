from __future__ import annotations


class WorkerRuntimeError(RuntimeError):
    """A bounded worker failure safe to expose to the gateway."""

    def __init__(self, code: str, message: str, *, recoverable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.recoverable = recoverable


class WorkerProtocolError(WorkerRuntimeError):
    """A strict worker-protocol validation failure."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__("WORKER_PROTOCOL", message, recoverable=False)
        self.field = field
