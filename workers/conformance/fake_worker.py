from __future__ import annotations

import argparse
import base64
import contextlib
import os
import signal
import struct
import subprocess
import sys

from workers.runtime.codec import (
    WORKER_PROTOCOL_VERSION,
    decode_message,
    encode_message,
)

_CAPACITY_FRAMES = 25


def _emit(message: dict[str, object]) -> None:
    sys.stdout.buffer.write(encode_message(message))
    sys.stdout.buffer.flush()


def _control(
    message_type: str, request: dict[str, object], **fields: object
) -> dict[str, object]:
    return {
        "type": message_type,
        "worker_protocol_version": WORKER_PROTOCOL_VERSION,
        "rpc_id": request["rpc_id"],
        **fields,
    }


def _output(frame: dict[str, object], gain: float | None) -> dict[str, object]:
    encoded = str(frame["pcm_f32le_base64"])
    if gain is not None:
        raw = base64.b64decode(encoded, validate=True)
        count = len(raw) // 4
        samples = struct.unpack(f"<{count}f", raw)
        transformed = struct.pack(f"<{count}f", *(sample * gain for sample in samples))
        encoded = base64.b64encode(transformed).decode("ascii")
    return {
        **frame,
        "type": "audio.output",
        "pcm_f32le_base64": encoded,
    }


def _spawn_orphan() -> subprocess.Popen[bytes]:
    program = (
        "import signal,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "signal.signal(signal.SIGINT, signal.SIG_IGN); "
        "time.sleep(3600)"
    )
    return subprocess.Popen(  # noqa: S603 - deterministic test-only child
        [sys.executable, "-c", program],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run(mode: str, gain: float | None) -> int:
    active_generation_id: int | None = None
    queued: list[dict[str, object]] = []
    output_count = 0
    orphan: subprocess.Popen[bytes] | None = None
    canceled_once = False

    if mode == "orphan-child":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        orphan = _spawn_orphan()

    for line in sys.stdin.buffer:
        try:
            message = decode_message(line)
        except Exception:
            return 2
        message_type = message["type"]

        if message_type == "worker.hello":
            if mode == "delayed-ready":
                continue
            _emit(
                _control(
                    "worker.ready",
                    message,
                    profile_id=message["profile_id"],
                    pipeline_id=message["pipeline_id"],
                    implementation_revision="fake-worker-v1",
                    weight_revision=None,
                    configuration_hash=message["configuration_hash"],
                )
            )
        elif message_type == "generation.start":
            active_generation_id = int(message["generation_id"])
            queued.clear()
            output_count = 0
            if mode == "ignore-start":
                continue
            if mode == "sensitive-start-error":
                _emit(
                    _control(
                        "worker.error",
                        message,
                        code="WORKER_CRASH",
                        message="failed at /private/cache with credential=secret",
                        recoverable=True,
                    )
                )
                continue
            _emit(
                _control(
                    "generation.started",
                    message,
                    generation_id=active_generation_id,
                )
            )
            if mode == "blocked-input":
                while True:
                    signal.pause()
        elif message_type == "audio.push":
            if mode == "crashed":
                os._exit(17)
            if mode == "malformed-output":
                sys.stdout.buffer.write(b'{"type":malformed}\n')
                sys.stdout.buffer.flush()
                continue
            if mode == "stalled-until-cancel" and not canceled_once:
                queued.append(message)
                continue
            if mode in {"delayed", "stalled", "cancellation-race"}:
                queued.append(message)
                continue
            if mode == "reverse-order":
                queued.append(message)
                if len(queued) == 2:
                    _emit(_output(queued[1], None))
                    _emit(_output(queued[0], None))
                    queued.clear()
                continue
            if mode == "one-output-then-stall" and output_count > 0:
                queued.append(message)
                continue
            _emit(_output(message, gain if mode == "gain" else None))
            output_count += 1
        elif message_type == "generation.end":
            if mode == "ignore-end":
                continue
            if mode == "delayed":
                for frame in queued:
                    _emit(_output(frame, None))
                queued.clear()
            elif mode in {"stalled", "one-output-then-stall"} and queued:
                continue
            _emit(
                _control(
                    "generation.completed",
                    message,
                    generation_id=message["generation_id"],
                )
            )
            active_generation_id = None
        elif message_type == "generation.cancel":
            if mode == "ignore-cancel":
                continue
            canceled_once = True
            late = list(queued)
            queued.clear()
            active_generation_id = None
            _emit(
                _control(
                    "generation.canceled",
                    message,
                    generation_id=message["generation_id"],
                )
            )
            if mode == "cancellation-race":
                for frame in late:
                    _emit(_output(frame, None))
        elif message_type == "worker.health":
            _emit(
                _control(
                    "worker.health.result",
                    message,
                    ready=True,
                    active_generation_id=active_generation_id,
                    queue_depth_frames=len(queued),
                    capacity_frames=_CAPACITY_FRAMES,
                )
            )
        elif message_type == "worker.close":
            if mode == "orphan-child":
                continue
            _emit(_control("worker.closed", message))
            return 0

    if orphan is not None:
        with contextlib.suppress(ProcessLookupError):
            orphan.kill()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "passthrough",
            "gain",
            "delayed",
            "stalled",
            "crashed",
            "malformed-output",
            "cancellation-race",
            "blocked-input",
            "delayed-ready",
            "one-output-then-stall",
            "sensitive-start-error",
            "stalled-until-cancel",
            "ignore-cancel",
            "ignore-start",
            "ignore-end",
            "orphan-child",
            "reverse-order",
        ),
    )
    parser.add_argument("--gain", type=float)
    args = parser.parse_args(argv)
    return run(args.mode, args.gain)


if __name__ == "__main__":
    raise SystemExit(main())
