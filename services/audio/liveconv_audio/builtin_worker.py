from __future__ import annotations

import argparse
import base64
import struct
import sys

from workers.runtime.codec import (
    WORKER_PROTOCOL_VERSION,
    decode_message,
    encode_message,
)


def _emit(message: dict[str, object]) -> None:
    sys.stdout.buffer.write(encode_message(message))
    sys.stdout.buffer.flush()


def _response(
    message_type: str,
    request: dict[str, object],
    **fields: object,
) -> dict[str, object]:
    return {
        "type": message_type,
        "worker_protocol_version": WORKER_PROTOCOL_VERSION,
        "rpc_id": request["rpc_id"],
        **fields,
    }


def _output(message: dict[str, object], gain: float | None) -> dict[str, object]:
    encoded = str(message["pcm_f32le_base64"])
    if gain is not None:
        raw = base64.b64decode(encoded, validate=True)
        count = len(raw) // 4
        samples = struct.unpack(f"<{count}f", raw)
        raw = struct.pack(f"<{count}f", *(sample * gain for sample in samples))
        encoded = base64.b64encode(raw).decode("ascii")
    return {
        **message,
        "type": "audio.output",
        "pcm_f32le_base64": encoded,
    }


def run(
    *,
    mode: str,
    gain: float | None,
    implementation_revision: str,
    weight_revision: str | None,
    capacity_frames: int,
) -> int:
    active_generation_id: int | None = None
    for line in sys.stdin.buffer:
        try:
            message = decode_message(line)
        except Exception:
            return 2
        message_type = message["type"]

        if message_type == "worker.hello":
            _emit(
                _response(
                    "worker.ready",
                    message,
                    profile_id=message["profile_id"],
                    pipeline_id=message["pipeline_id"],
                    implementation_revision=implementation_revision,
                    weight_revision=weight_revision,
                    configuration_hash=message["configuration_hash"],
                )
            )
        elif message_type == "generation.start":
            active_generation_id = int(message["generation_id"])
            _emit(
                _response(
                    "generation.started",
                    message,
                    generation_id=active_generation_id,
                )
            )
        elif message_type == "audio.push":
            _emit(_output(message, gain if mode == "gain" else None))
        elif message_type == "generation.end":
            _emit(
                _response(
                    "generation.completed",
                    message,
                    generation_id=message["generation_id"],
                )
            )
            active_generation_id = None
        elif message_type == "generation.cancel":
            active_generation_id = None
            _emit(
                _response(
                    "generation.canceled",
                    message,
                    generation_id=message["generation_id"],
                )
            )
        elif message_type == "worker.health":
            _emit(
                _response(
                    "worker.health.result",
                    message,
                    ready=True,
                    active_generation_id=active_generation_id,
                    queue_depth_frames=0,
                    capacity_frames=capacity_frames,
                )
            )
        elif message_type == "worker.close":
            _emit(_response("worker.closed", message))
            return 0
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("passthrough", "gain"), required=True)
    parser.add_argument("--gain", type=float)
    parser.add_argument("--implementation-revision", required=True)
    parser.add_argument("--weight-revision")
    parser.add_argument("--capacity-frames", type=int, required=True)
    args = parser.parse_args(argv)
    if args.mode == "gain" and args.gain is None:
        parser.error("--gain is required for gain mode")
    return run(
        mode=args.mode,
        gain=args.gain,
        implementation_revision=args.implementation_revision,
        weight_revision=args.weight_revision,
        capacity_frames=args.capacity_frames,
    )


if __name__ == "__main__":
    raise SystemExit(main())
