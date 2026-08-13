#!/usr/bin/env python3
"""Compare fresh stable VC with the same utterance after cancellation."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import importlib.util
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from liveconv_protocol import GenerationCancel, GenerationCanceledEvent
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[2]
GENERALIZATION_RUNNER = Path(__file__).with_name(
    "render_stable_vc_generalization.py"
)
RVC_PROFILE_ID = "vc.rvc-v2.amitaro-sasayaki-clean-bright-seed0.v1"
XVC_PROFILE_ID = "vc.x-vc.amitaro-yofukashi-q34.v1"
CANCELED_SOURCE_ID = "EMOTION100_027"
RECOVERY_SOURCE_ID = "RECITATION324_049"
CANCEL_AFTER_FRAMES = 100
PROFILE_SPECS = {
    RVC_PROFILE_ID: {
        "label": "Stable seed-0 RVC",
        "slug": "rvc-seed0",
        "baseline_file": "10-stable-rvc-seed0.wav",
        "baseline_sha256": (
            "fe59f8e9e34f8019d6325fc0a0750e741094fc8ee3732de4219edf54268e7a62"
        ),
        "result_kind": "liveconv-ms3-rvc-cancel-recovery-result",
    },
    XVC_PROFILE_ID: {
        "label": "Stable X-VC Yofukashi Q034",
        "slug": "xvc-q34",
        "baseline_file": "20-stable-xvc-q34.wav",
        "baseline_sha256": (
            "a9e98fa89ef41766549853e7b1fcf5d12307e8171a55d519f9412e27938fcdf5"
        ),
        "result_kind": "liveconv-ms3-xvc-cancel-recovery-result",
    },
}
BASELINE_ROOT = (
    ROOT
    / "artifacts/ms3/listening/ms3-stable-vc-generalization-v1"
    / "01-RECITATION324_049"
)


class CancelRecoveryError(RuntimeError):
    """The bounded stable-VC cancellation comparison cannot continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_generalization() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "liveconv_xvc_cancel_generalization", GENERALIZATION_RUNNER
    )
    if specification is None or specification.loader is None:
        raise CancelRecoveryError("generalization runner cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def source_by_id(generalization: ModuleType, source_id: str) -> dict[str, Any]:
    matches = [
        source
        for source in generalization.SOURCES
        if source["source_id"] == source_id
    ]
    if len(matches) != 1:
        raise CancelRecoveryError(f"source {source_id} drifted")
    return matches[0]


def profile_spec(profile_id: str) -> dict[str, str]:
    try:
        return PROFILE_SPECS[profile_id]
    except KeyError:
        raise CancelRecoveryError("profile is outside the bounded comparison") from None


def staging_path(listener_dir: Path) -> Path:
    return listener_dir.with_name(f".{listener_dir.name}.staging")


def validate(
    arguments: argparse.Namespace,
) -> tuple[Path, ModuleType, ModuleType, ModuleType]:
    generalization = load_generalization()
    generalization.validate_source_manifest()
    spec = profile_spec(arguments.profile_id)
    baseline_wav = BASELINE_ROOT / spec["baseline_file"]
    generalization.checked_file(
        baseline_wav, spec["baseline_sha256"], "fresh baseline"
    )
    repeat = generalization.load_repeat_runner()
    session = repeat._load_session_runner()  # noqa: SLF001
    heldout = session._load_heldout_runner()  # noqa: SLF001
    renderer = heldout._load_renderer()  # noqa: SLF001
    deployment = arguments.deployment.resolve(strict=True)
    generalization.selected_profile(
        heldout, renderer, deployment, arguments.profile_id
    )
    if (
        arguments.work_dir.exists()
        or arguments.listener_dir.exists()
        or staging_path(arguments.listener_dir).exists()
    ):
        raise CancelRecoveryError("work and listener outputs must be new")
    if not os.environ.get("LIVECONV_API_TOKEN"):
        raise CancelRecoveryError("LIVECONV_API_TOKEN is required")
    if not os.environ.get("LIVECONV_ALLOWED_ORIGINS"):
        raise CancelRecoveryError("LIVECONV_ALLOWED_ORIGINS is required")
    return deployment, generalization, heldout, renderer


async def receive(
    websocket: Any, renderer: ModuleType, timeout: float
) -> str | bytes:
    try:
        return await asyncio.wait_for(websocket.recv(), timeout=timeout)
    except TimeoutError as error:
        raise CancelRecoveryError("Gateway receive timed out") from error


def parse_event(renderer: ModuleType, message: str) -> Any:
    event = renderer.parse_server_event(message)
    if isinstance(event, renderer.ErrorEvent):
        raise CancelRecoveryError(f"Gateway error: {event.code}")
    if isinstance(event, renderer.FallbackRequiredEvent):
        raise CancelRecoveryError(f"Gateway fallback: {event.reason_code}")
    return event


async def receive_control(
    websocket: Any, renderer: ModuleType, timeout: float, expected: type[Any]
) -> Any:
    message = await receive(websocket, renderer, timeout)
    if not isinstance(message, str):
        raise CancelRecoveryError("Gateway returned PCM while control was required")
    event = parse_event(renderer, message)
    if not isinstance(event, expected):
        raise CancelRecoveryError(
            f"expected {expected.message_type}, received {event.message_type}"
        )
    return event


async def send_paced_frames(
    websocket: Any,
    *,
    renderer: ModuleType,
    generation_id: int,
    frames: list[bytes],
) -> dict[int, tuple[int, bytes]]:
    epoch_ns = time.monotonic_ns()
    inputs: dict[int, tuple[int, bytes]] = {}
    for sequence, payload in enumerate(frames):
        target_ns = epoch_ns + sequence * renderer.FRAME_NS
        delay = (target_ns - time.monotonic_ns()) / 1_000_000_000
        if delay > 0:
            await asyncio.sleep(delay)
        inputs[sequence] = (target_ns, payload)
        await websocket.send(
            renderer.PcmFrame(
                renderer.FrameHeader(
                    kind=renderer.FrameKind.INPUT,
                    generation_id=generation_id,
                    sequence=sequence,
                    source_monotonic_ns=target_ns,
                ),
                payload,
            ).encode()
        )
    return inputs


async def execute(
    arguments: argparse.Namespace,
    *,
    deployment: Path,
    generalization: ModuleType,
    heldout: ModuleType,
    renderer: ModuleType,
) -> dict[str, Any]:
    arguments.work_dir.mkdir(parents=True)
    source_f32 = arguments.work_dir / "source-f32"
    source_f32.mkdir()
    frames_by_id: dict[str, list[bytes]] = {}
    profile_id = arguments.profile_id
    spec = profile_spec(profile_id)
    for source_id in (CANCELED_SOURCE_ID, RECOVERY_SOURCE_ID):
        source = source_by_id(generalization, source_id)
        wav = generalization.SOURCE_ROOT / source["relative_path"]
        f32 = source_f32 / f"{source_id}.f32le"
        heldout.wav_to_f32le(wav, f32)
        frames_by_id[source_id] = renderer.source_frames(f32)[0]
    if len(frames_by_id[CANCELED_SOURCE_ID]) <= CANCEL_AFTER_FRAMES:
        raise CancelRecoveryError("canceled source is too short")

    variant, profile = generalization.selected_profile(
        heldout, renderer, deployment, profile_id
    )
    token = os.environ["LIVECONV_API_TOKEN"]
    origin = next(
        item.strip()
        for item in os.environ["LIVECONV_ALLOWED_ORIGINS"].split(",")
        if item.strip()
    )
    gateway_url = arguments.gateway_url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(follow_redirects=False) as client:
        catalog = await client.get(
            f"{gateway_url}/v1/models",
            headers=headers,
            timeout=arguments.timeout_seconds,
        )
        current = {
            item.get("profile_id"): item
            for item in catalog.json().get("profiles", [])
            if isinstance(item, dict)
        }.get(profile_id)
        if catalog.status_code != 200 or not isinstance(current, dict) or any(
            current.get(field) != variant.get(field)
            for field in ("profile_hash", "configuration_hash")
        ):
            raise CancelRecoveryError("Gateway stable VC identity differs")
        response = await client.post(
            f"{gateway_url}/v1/route-parity-sessions",
            headers=headers,
            json={
                "protocol_version": 1,
                "profile_id": profile_id,
                "input": {
                    "sample_rate": renderer.SAMPLE_RATE,
                    "channels": 1,
                    "sample_format": "f32le",
                    "frame_ms": renderer.FRAME_MS,
                },
                "voice_id": None,
            },
            timeout=arguments.timeout_seconds,
        )
        if response.status_code != 201:
            raise CancelRecoveryError(
                f"session creation returned HTTP {response.status_code}"
            )
        descriptor = response.json()
        session_id = renderer.require_text(descriptor, "session_id")
        pipeline_id = renderer.require_text(descriptor, "pipeline_id")
        ticket = renderer.require_text(descriptor, "ticket")
        parsed = urlsplit(gateway_url)
        websocket_url = urlunsplit(
            (
                "wss" if parsed.scheme == "https" else "ws",
                parsed.netloc,
                renderer.require_text(descriptor, "websocket_path"),
                "",
                "",
            )
        )
        websocket = None
        invalidated = False
        try:
            websocket = await connect(
                websocket_url,
                origin=origin,
                compression=None,
                max_size=16_384,
                max_queue=None,
                open_timeout=arguments.timeout_seconds,
                close_timeout=arguments.timeout_seconds,
            )
            await websocket.send(
                renderer.encode_control_message(
                    renderer.SessionAttach(
                        protocol_version=1,
                        request_id="ms3.cancel-recovery.attach",
                        session_id=session_id,
                        ticket=ticket,
                    )
                )
            )
            ready = await receive_control(
                websocket,
                renderer,
                arguments.timeout_seconds,
                renderer.SessionReadyEvent,
            )
            if ready.pipeline_id != pipeline_id or ready.profile_id != profile_id:
                raise CancelRecoveryError("session.ready identity differs")
            credit = min(
                ready.limits.max_ingress_frames,
                ready.limits.ingress_budget_ms // renderer.FRAME_MS,
            )
            recovery_frames = frames_by_id[RECOVERY_SOURCE_ID]
            if credit < max(CANCEL_AFTER_FRAMES, len(recovery_frames)):
                raise CancelRecoveryError("turns exceed advertised ingress credit")

            await websocket.send(
                renderer.encode_control_message(
                    renderer.GenerationStart(
                        protocol_version=1,
                        request_id="ms3.cancel-recovery.start-1",
                        session_id=session_id,
                        generation_id=1,
                    )
                )
            )
            generation_one_ready = await receive_control(
                websocket,
                renderer,
                arguments.timeout_seconds,
                renderer.GenerationReadyEvent,
            )
            if generation_one_ready.generation_id != 1:
                raise CancelRecoveryError("generation 1 did not start")
            await send_paced_frames(
                websocket,
                renderer=renderer,
                generation_id=1,
                frames=frames_by_id[CANCELED_SOURCE_ID][:CANCEL_AFTER_FRAMES],
            )
            cancel_sent_ns = time.monotonic_ns()
            await websocket.send(
                renderer.encode_control_message(
                    GenerationCancel(
                        protocol_version=1,
                        request_id="ms3.cancel-recovery.cancel-1",
                        session_id=session_id,
                        generation_id=1,
                    )
                )
            )
            excluded_before_ack = 0
            while True:
                message = await receive(
                    websocket, renderer, arguments.timeout_seconds
                )
                if isinstance(message, bytes):
                    frame = renderer.PcmFrame.decode(message)
                    if frame.header.generation_id != 1:
                        raise CancelRecoveryError("unexpected output before cancel ack")
                    excluded_before_ack += 1
                    continue
                event = parse_event(renderer, message)
                if isinstance(event, GenerationCanceledEvent):
                    if event.generation_id != 1 or event.pipeline_id != pipeline_id:
                        raise CancelRecoveryError("cancel acknowledgment differs")
                    break
                raise CancelRecoveryError("unexpected event while canceling")
            cancel_ack_ms = (time.monotonic_ns() - cancel_sent_ns) / 1_000_000

            await websocket.send(
                renderer.encode_control_message(
                    renderer.GenerationStart(
                        protocol_version=1,
                        request_id="ms3.cancel-recovery.start-2",
                        session_id=session_id,
                        generation_id=2,
                    )
                )
            )
            stale_after_ack = 0
            while True:
                message = await receive(
                    websocket, renderer, arguments.timeout_seconds
                )
                if isinstance(message, bytes):
                    frame = renderer.PcmFrame.decode(message)
                    if frame.header.generation_id != 1:
                        raise CancelRecoveryError(
                            "unexpected PCM before recovery ready"
                        )
                    stale_after_ack += 1
                    continue
                event = parse_event(renderer, message)
                if isinstance(event, renderer.GenerationReadyEvent):
                    if event.generation_id != 2 or event.pipeline_id != pipeline_id:
                        raise CancelRecoveryError("recovery generation differs")
                    break
                raise CancelRecoveryError("unexpected event before recovery ready")

            recovery_inputs = await send_paced_frames(
                websocket,
                renderer=renderer,
                generation_id=2,
                frames=recovery_frames,
            )
            await websocket.send(
                renderer.encode_control_message(
                    renderer.GenerationEnd(
                        protocol_version=1,
                        request_id="ms3.cancel-recovery.end-2",
                        session_id=session_id,
                        generation_id=2,
                    )
                )
            )
            output_payloads: list[bytes] = []
            changed_samples = 0
            absolute_peak = 0.0
            while True:
                message = await receive(
                    websocket, renderer, arguments.timeout_seconds
                )
                if isinstance(message, str):
                    event = parse_event(renderer, message)
                    if isinstance(event, renderer.GenerationCompletedEvent):
                        if event.generation_id != 2 or event.pipeline_id != pipeline_id:
                            raise CancelRecoveryError("recovery completion differs")
                        break
                    raise CancelRecoveryError("unexpected recovery event")
                frame = renderer.PcmFrame.decode(message)
                if frame.header.generation_id == 1:
                    stale_after_ack += 1
                    continue
                sequence = len(output_payloads)
                expected = recovery_inputs.pop(sequence, None)
                if (
                    frame.header.kind is not renderer.FrameKind.OUTPUT
                    or frame.header.generation_id != 2
                    or frame.header.sequence != sequence
                    or expected is None
                    or frame.header.source_monotonic_ns != expected[0]
                ):
                    raise CancelRecoveryError("recovery output ordering differs")
                output_samples = struct.unpack(
                    f"<{renderer.SAMPLES_PER_FRAME}f", frame.payload
                )
                source_samples = struct.unpack(
                    f"<{renderer.SAMPLES_PER_FRAME}f", expected[1]
                )
                if any(not math.isfinite(value) for value in output_samples):
                    raise CancelRecoveryError("recovery output is non-finite")
                absolute_peak = max(
                    absolute_peak, max(abs(value) for value in output_samples)
                )
                changed_samples += sum(
                    abs(output - source) > 1e-7
                    for output, source in zip(
                        output_samples, source_samples, strict=True
                    )
                )
                output_payloads.append(frame.payload)
            if recovery_inputs or len(output_payloads) != len(recovery_frames):
                raise CancelRecoveryError("recovery output did not fully drain")
            if not 0 < absolute_peak <= 1.0 or changed_samples <= 0:
                raise CancelRecoveryError("recovery output failed signal checks")

            await websocket.send(
                renderer.encode_control_message(
                    renderer.SessionClose(
                        protocol_version=1,
                        request_id="ms3.cancel-recovery.close",
                        session_id=session_id,
                    )
                )
            )
            closed = await receive_control(
                websocket,
                renderer,
                arguments.timeout_seconds,
                renderer.SessionClosedEvent,
            )
            if closed.session_id != session_id:
                raise CancelRecoveryError("session.close identity differs")
            invalidated = True
        finally:
            if websocket is not None:
                with contextlib.suppress(Exception):
                    await websocket.close()
            with contextlib.suppress(httpx.HTTPError):
                cleanup = await client.delete(
                    f"{gateway_url}/v1/sessions/{session_id}",
                    headers=headers,
                    timeout=arguments.timeout_seconds,
                )
                if invalidated and cleanup.status_code != 404:
                    raise CancelRecoveryError("closed session remained addressable")

    output_pcm = b"".join(output_payloads)
    staging = staging_path(arguments.listener_dir)
    staging.mkdir()
    recovery_source = source_by_id(generalization, RECOVERY_SOURCE_ID)
    source_wav = generalization.SOURCE_ROOT / recovery_source["relative_path"]
    shutil.copyfile(source_wav, staging / "00-source.wav")
    baseline_wav = BASELINE_ROOT / spec["baseline_file"]
    baseline_output = f"10-{spec['slug']}-fresh-session.wav"
    recovery_output = f"20-{spec['slug']}-after-cancel.wav"
    shutil.copyfile(baseline_wav, staging / baseline_output)
    recovery_wav = staging / recovery_output
    renderer.write_wav(recovery_wav, output_pcm)
    recovery_sha256 = sha256_file(recovery_wav)
    variants = [
        {
            "variant_id": f"{spec['slug']}-fresh-session",
            "display_name": f"{spec['label']} / fresh session",
            "display_order": 1,
            "output_file": baseline_output,
            "output_sha256": "sha256:" + spec["baseline_sha256"],
            "profile_id": profile_id,
            "status": "passed",
            "operator_judgment": "unreviewed",
        },
        {
            "variant_id": f"{spec['slug']}-after-cancel",
            "display_name": (
                f"{spec['label']} / after canceling prior generation"
            ),
            "display_order": 2,
            "output_file": recovery_wav.name,
            "output_sha256": "sha256:" + recovery_sha256,
            "profile_id": profile_id,
            "status": "passed",
            "operator_judgment": "unreviewed",
        },
    ]
    index = {
        "schema_version": 1,
        "title": f"{spec['label']} cancellation recovery",
        "run_kind": "MS-3 realtime interruption recovery comparison",
        "status": "completed-listen-now-unselected",
        "source_file": f"Hadou public validation / {RECOVERY_SOURCE_ID}",
        "source_text": recovery_source["display_text"],
        "source_id": RECOVERY_SOURCE_ID,
        "source_output_file": "00-source.wav",
        "comparison_scope": {
            "changed_variable": "fresh session versus immediately after cancel",
            "machine_selection_allowed": False,
            "question": (
                "Does canceling an older generation contaminate the next output?"
            ),
        },
        "cancel_evidence": {
            "canceled_source_id": CANCELED_SOURCE_ID,
            "sent_frames_before_cancel": CANCEL_AFTER_FRAMES,
            "sent_audio_seconds": CANCEL_AFTER_FRAMES * renderer.FRAME_MS / 1000,
            "local_output_gate_closed_before_cancel": True,
            "excluded_output_frames_before_ack": excluded_before_ack,
            "stale_output_frames_after_ack": stale_after_ack,
            "cancel_ack_ms": round(cancel_ack_ms, 3),
            "recovery_frames": len(output_payloads),
            "recovery_absolute_peak": absolute_peak,
        },
        "variants": variants,
    }
    (staging / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    staging.rename(arguments.listener_dir)
    result = {
        "schema_version": 1,
        "kind": spec["result_kind"],
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "profile_id": profile_id,
        "baseline_sha256": "sha256:" + spec["baseline_sha256"],
        "recovery_sha256": "sha256:" + recovery_sha256,
        "cancel_evidence": index["cancel_evidence"],
        "claims": {"perceptual_winner": False, "product_selected": False},
    }
    (arguments.work_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return result


async def run(arguments: argparse.Namespace) -> int:
    deployment, generalization, heldout, renderer = validate(arguments)
    if arguments.check:
        print(
            f"ok   {arguments.profile_id} cancellation-recovery CPU admission complete"
        )
        return 0
    await execute(
        arguments,
        deployment=deployment,
        generalization=generalization,
        heldout=heldout,
        renderer=renderer,
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    mode = value.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    value.add_argument("--deployment", type=Path, required=True)
    value.add_argument(
        "--profile-id", choices=tuple(PROFILE_SPECS), default=XVC_PROFILE_ID
    )
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    value.add_argument("--gateway-url", default="http://127.0.0.1:8882")
    value.add_argument("--timeout-seconds", type=float, default=300.0)
    return value


def main() -> int:
    try:
        return asyncio.run(run(parser().parse_args()))
    except (
        json.JSONDecodeError,
        OSError,
        CancelRecoveryError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        print(f"render_xvc_cancel_recovery: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
