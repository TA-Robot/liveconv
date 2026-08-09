from __future__ import annotations

import struct
from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum, IntFlag, StrEnum

from .errors import ErrorCode, ProtocolValidationError

MAGIC = 0x4C56
PROTOCOL_VERSION = 1
HEADER_LENGTH = 32
SAMPLE_WIDTH_BYTES = 4
V1_SAMPLE_RATE = 48_000
V1_CHANNELS = 1
V1_FRAME_MS = 20
V1_SAMPLES_PER_CHANNEL = 960

_UINT16_MAX = (1 << 16) - 1
_UINT32_MAX = (1 << 32) - 1
_UINT64_MAX = (1 << 64) - 1
_HEADER = struct.Struct("!HBBHHIIIHHQ")

assert _HEADER.size == HEADER_LENGTH


class FrameKind(IntEnum):
    INPUT = 1
    OUTPUT = 2


class FrameFlags(IntFlag):
    NONE = 0


class FrameOrderResult(StrEnum):
    ACCEPTED = "accepted"


def _wire_int(
    value: object,
    *,
    field: str,
    minimum: int,
    maximum: int,
    code: ErrorCode = ErrorCode.UNSUPPORTED_AUDIO,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolValidationError(code, f"{field} must be an integer", field=field)
    if not minimum <= value <= maximum:
        raise ProtocolValidationError(
            code,
            f"{field} must be between {minimum} and {maximum}",
            field=field,
        )
    return value


@dataclass(frozen=True, slots=True)
class FrameHeader:
    kind: FrameKind
    generation_id: int
    sequence: int
    source_monotonic_ns: int
    sample_rate: int = V1_SAMPLE_RATE
    channels: int = V1_CHANNELS
    samples_per_channel: int = V1_SAMPLES_PER_CHANNEL
    flags: FrameFlags = FrameFlags.NONE

    def __post_init__(self) -> None:
        if isinstance(self.kind, bool) or not isinstance(self.kind, int):
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                "kind must be INPUT or OUTPUT",
                field="kind",
            )
        try:
            kind = FrameKind(self.kind)
        except (TypeError, ValueError) as exc:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                "kind must be INPUT or OUTPUT",
                field="kind",
            ) from exc
        if isinstance(self.flags, bool) or not isinstance(self.flags, int):
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                "flags must be a valid version 1 bit set",
                field="flags",
            )
        try:
            flags = FrameFlags(self.flags)
        except (TypeError, ValueError) as exc:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                "flags must be a valid version 1 bit set",
                field="flags",
            ) from exc
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "flags", flags)

        if flags != FrameFlags.NONE:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                "version 1 does not define non-zero frame flags",
                field="flags",
            )

        _wire_int(
            self.generation_id,
            field="generation_id",
            minimum=0,
            maximum=_UINT32_MAX,
            code=ErrorCode.INVALID_STATE,
        )
        _wire_int(self.sequence, field="sequence", minimum=0, maximum=_UINT32_MAX)
        _wire_int(
            self.source_monotonic_ns,
            field="source_monotonic_ns",
            minimum=0,
            maximum=_UINT64_MAX,
        )
        _wire_int(self.sample_rate, field="sample_rate", minimum=1, maximum=_UINT32_MAX)
        _wire_int(self.channels, field="channels", minimum=1, maximum=_UINT16_MAX)
        _wire_int(
            self.samples_per_channel,
            field="samples_per_channel",
            minimum=1,
            maximum=_UINT16_MAX,
        )

        if self.sample_rate != V1_SAMPLE_RATE:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                f"version 1 requires sample_rate={V1_SAMPLE_RATE}",
                field="sample_rate",
            )
        if self.channels != V1_CHANNELS:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                f"version 1 requires channels={V1_CHANNELS}",
                field="channels",
            )
        if self.samples_per_channel != V1_SAMPLES_PER_CHANNEL:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                f"version 1 requires samples_per_channel={V1_SAMPLES_PER_CHANNEL}",
                field="samples_per_channel",
            )

    @property
    def payload_length(self) -> int:
        return self.channels * self.samples_per_channel * SAMPLE_WIDTH_BYTES

    def encode(self) -> bytes:
        return _HEADER.pack(
            MAGIC,
            PROTOCOL_VERSION,
            int(self.kind),
            int(self.flags),
            HEADER_LENGTH,
            self.generation_id,
            self.sequence,
            self.sample_rate,
            self.channels,
            self.samples_per_channel,
            self.source_monotonic_ns,
        )

    @classmethod
    def decode(cls, data: bytes | bytearray | memoryview) -> FrameHeader:
        view = memoryview(data)
        if len(view) < HEADER_LENGTH:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                f"frame header must contain {HEADER_LENGTH} bytes",
                field="header_length",
            )

        (
            magic,
            protocol_version,
            kind,
            flags,
            header_length,
            generation_id,
            sequence,
            sample_rate,
            channels,
            samples_per_channel,
            source_monotonic_ns,
        ) = _HEADER.unpack(view[:HEADER_LENGTH])

        if magic != MAGIC:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_PROTOCOL,
                "frame magic is not LV",
                field="magic",
            )
        if protocol_version != PROTOCOL_VERSION:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_PROTOCOL,
                f"unsupported frame protocol version {protocol_version}",
                field="protocol_version",
            )
        if header_length != HEADER_LENGTH:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_PROTOCOL,
                f"version 1 header_length must be {HEADER_LENGTH}",
                field="header_length",
            )

        return cls(
            kind=kind,
            flags=flags,
            generation_id=generation_id,
            sequence=sequence,
            sample_rate=sample_rate,
            channels=channels,
            samples_per_channel=samples_per_channel,
            source_monotonic_ns=source_monotonic_ns,
        )


@dataclass(frozen=True, slots=True)
class PcmFrame:
    header: FrameHeader
    payload: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.payload, bytes):
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                "payload must be bytes",
                field="payload",
            )
        if len(self.payload) != self.header.payload_length:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                (
                    f"payload length {len(self.payload)} does not match "
                    f"expected {self.header.payload_length}"
                ),
                field="payload",
            )

    def encode(self) -> bytes:
        return self.header.encode() + self.payload

    def unpack_samples(self) -> tuple[float, ...]:
        sample_count = self.header.channels * self.header.samples_per_channel
        return struct.unpack(f"<{sample_count}f", self.payload)

    @classmethod
    def from_samples(cls, header: FrameHeader, samples: Iterable[float]) -> PcmFrame:
        values = tuple(samples)
        expected = header.channels * header.samples_per_channel
        if len(values) != expected:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                f"sample count {len(values)} does not match expected {expected}",
                field="payload",
            )
        try:
            payload = struct.pack(f"<{expected}f", *values)
        except (OverflowError, struct.error, TypeError) as exc:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                "samples must be representable as float32",
                field="payload",
            ) from exc
        return cls(header=header, payload=payload)

    @classmethod
    def decode(cls, data: bytes | bytearray | memoryview) -> PcmFrame:
        view = memoryview(data)
        header = FrameHeader.decode(view)
        expected_length = HEADER_LENGTH + header.payload_length
        if len(view) != expected_length:
            raise ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                f"frame length {len(view)} does not match expected {expected_length}",
                field="payload",
            )
        return cls(header=header, payload=bytes(view[HEADER_LENGTH:]))


@dataclass(slots=True)
class FrameOrderGuard:
    """Enforce generation monotonicity and contiguous per-generation sequences."""

    last_generation_id: int | None = None
    active_generation_id: int | None = None
    next_sequence: int = 0

    def start_generation(self, generation_id: int) -> None:
        _wire_int(
            generation_id,
            field="generation_id",
            minimum=0,
            maximum=_UINT32_MAX,
            code=ErrorCode.INVALID_STATE,
        )
        if self.active_generation_id is not None:
            raise ProtocolValidationError(
                ErrorCode.INVALID_STATE,
                "a generation is already active",
                field="generation_id",
            )
        if (
            self.last_generation_id is not None
            and generation_id <= self.last_generation_id
        ):
            raise ProtocolValidationError(
                ErrorCode.STALE_GENERATION,
                "generation_id must strictly increase",
                field="generation_id",
            )
        self.last_generation_id = generation_id
        self.active_generation_id = generation_id
        self.next_sequence = 0

    def observe(self, generation_id: int, sequence: int) -> FrameOrderResult:
        _wire_int(
            generation_id,
            field="generation_id",
            minimum=0,
            maximum=_UINT32_MAX,
            code=ErrorCode.INVALID_STATE,
        )
        _wire_int(sequence, field="sequence", minimum=0, maximum=_UINT32_MAX)

        if (
            self.last_generation_id is not None
            and generation_id < self.last_generation_id
        ):
            raise ProtocolValidationError(
                ErrorCode.STALE_GENERATION,
                "frame belongs to an older generation",
                field="generation_id",
            )
        if self.active_generation_id is None:
            code = (
                ErrorCode.STALE_GENERATION
                if self.last_generation_id is not None
                and generation_id <= self.last_generation_id
                else ErrorCode.INVALID_STATE
            )
            raise ProtocolValidationError(
                code,
                "frame has no matching active generation",
                field="generation_id",
            )
        if generation_id != self.active_generation_id:
            code = (
                ErrorCode.STALE_GENERATION
                if generation_id < self.active_generation_id
                else ErrorCode.INVALID_STATE
            )
            raise ProtocolValidationError(
                code,
                "frame generation does not match the active generation",
                field="generation_id",
            )
        if sequence != self.next_sequence:
            expected = self.next_sequence
            self.active_generation_id = None
            raise ProtocolValidationError(
                ErrorCode.SEQUENCE_GAP,
                f"expected sequence {expected}, received {sequence}",
                field="sequence",
            )

        self.next_sequence += 1
        return FrameOrderResult.ACCEPTED

    def finish_generation(self, generation_id: int) -> None:
        if self.active_generation_id != generation_id:
            code = (
                ErrorCode.STALE_GENERATION
                if self.last_generation_id is not None
                and generation_id <= self.last_generation_id
                else ErrorCode.INVALID_STATE
            )
            raise ProtocolValidationError(
                code,
                "cannot finish a generation that is not active",
                field="generation_id",
            )
        self.active_generation_id = None

    cancel_generation = finish_generation
