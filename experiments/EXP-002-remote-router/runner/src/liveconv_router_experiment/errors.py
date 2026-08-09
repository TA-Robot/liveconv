class ExperimentFailure(RuntimeError):
    """A protocol observation did not satisfy the experiment contract."""


class TransportFailure(ExperimentFailure):
    """The real gateway transport could not complete an operation."""


class WebSocketClosed(TransportFailure):
    """The gateway WebSocket closed before another message was available."""
