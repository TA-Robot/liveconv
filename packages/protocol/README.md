# liveconv protocol

This package implements protocol version 1 from
`docs/architecture/remote-protocol.md` without runtime dependencies.

```python
from liveconv_protocol import FrameHeader, FrameKind, PcmFrame

frame = PcmFrame.from_samples(
    FrameHeader(
        kind=FrameKind.INPUT,
        generation_id=1,
        sequence=0,
        source_monotonic_ns=123,
    ),
    [0.0] * 960,
)
message = frame.encode()
assert PcmFrame.decode(message) == frame
```

Control messages are parsed with `parse_control_message`. The parser rejects
unknown message types, unknown fields, duplicate JSON keys, unsupported protocol
versions, and values outside their wire ranges.

Gateway events use typed classes such as `SessionReadyEvent`,
`GenerationReadyEvent`, `ErrorEvent`, and `PongEvent`. Use
`parse_server_event`, `validate_server_event`, and `encode_server_event`; every
event type has an exact required/optional field set. A pre-attachment `error`
may omit `session_id` and `request_id`. All other events are session scoped.

The binary transport codec validates framing and payload length, but deliberately
accepts every IEEE-754 float32 payload, including NaN and infinity. The gateway
owns normalized-audio policy and must reject non-finite or out-of-range samples
with `UNSUPPORTED_AUDIO` plus `fallback.required`. Evaluation owns signal-quality
judgment. Keeping those checks out of the codec preserves a testable boundary
between valid wire bytes and valid application audio.

`FrameOrderGuard` is a per-session helper for enforcing strictly increasing
generation IDs and contiguous frame sequences. A sequence error invalidates the
active generation, matching the version 1 fallback contract.

Run focused tests from the repository root:

```bash
uv run --package liveconv-protocol --group dev pytest packages/protocol/tests
```
