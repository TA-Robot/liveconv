#!/usr/bin/env python3
"""Compare fresh sessions with three real generations in one Gateway session."""

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
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[2]
HELDOUT_RUNNER = Path(__file__).with_name("render_sasayaki_heldout.py")
PROFILE_IDS = (
    "vc.rvc-v2.amitaro-sasayaki-clean-bright.v1",
    "vc.x-vc.amitaro-yofukashi-q34.v1",
)
FRESH = {
    "vc.rvc-v2.amitaro-sasayaki-clean-bright.v1": {
        "collection": "exp020-sasayaki-heldout-generalization-v1",
        "file": "20-vc.rvc-v2.amitaro-sasayaki-clean-bright.v1.wav",
        "hashes": {
            "EMOTION100_002": (
                "1009a84fefaf359cc2bb4c295d7f0b63794f2e53c1bba210b962cd14eaf05a92"
            ),
            "EMOTION100_004": (
                "7e1558ba108a3a366a6d258fd4e6212ab08ed6535ad3c79c901244797e64cb19"
            ),
            "EMOTION100_017": (
                "62c4c53134ee3d5a65ad4a10847485d61798b83216ec065a6f9afaf1389bbf8d"
            ),
        },
    },
    "vc.x-vc.amitaro-yofukashi-q34.v1": {
        "collection": "exp026-xvc-yofukashi-q34-heldout-route-v1",
        "file": "10-vc.x-vc.amitaro-yofukashi-q34.v1.wav",
        "hashes": {
            "EMOTION100_002": (
                "71ea2e43f7219ba40dbe3dae660534d9a93b12b368a085c910f33879a7304b04"
            ),
            "EMOTION100_004": (
                "cfd74bd0e47a8b25136c1ff8f20f223e4d992d912fcc316fd105c8b755d446bc"
            ),
            "EMOTION100_017": (
                "8f050600f59bd02165b62b538866f3eedb7382486df49c6ea994461a0875eec3"
            ),
        },
    },
}


class SessionReuseError(RuntimeError):
    """The bounded persistent-session comparison cannot continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_heldout_runner() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "liveconv_vc_session_reuse_heldout", HELDOUT_RUNNER
    )
    if specification is None or specification.loader is None:
        raise SessionReuseError("heldout runner cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def validate_turn_capacity(frame_count: int, maximum: int, budget_ms: int) -> int:
    credit = min(maximum, budget_ms // 20)
    if frame_count <= 0 or credit < frame_count:
        raise SessionReuseError("one bounded turn exceeds advertised ingress credit")
    return credit


def comparison_status(fresh_sha256: str, reused_sha256: str) -> str:
    return "exact" if fresh_sha256 == reused_sha256 else "different"


def validate_inputs(
    arguments: argparse.Namespace, heldout: ModuleType
) -> tuple[Path, ModuleType]:
    deployment = arguments.deployment.resolve(strict=True)
    heldout._checked_file(  # noqa: SLF001
        deployment / "manifest.json",
        heldout.EXPECTED_MANIFEST_SHA256,
        "deployment manifest",
    )
    heldout._checked_file(  # noqa: SLF001
        deployment / "profiles.json",
        heldout.EXPECTED_PROFILES_SHA256,
        "deployment profiles",
    )
    manifest = json.loads((deployment / "manifest.json").read_text())
    profiles = json.loads((deployment / "profiles.json").read_text())
    heldout._selected_records(manifest, "variants", PROFILE_IDS)  # noqa: SLF001
    heldout._selected_records(profiles, "profiles", PROFILE_IDS)  # noqa: SLF001
    for source in heldout.SOURCES:
        heldout._checked_file(  # noqa: SLF001
            source["path"], source["sha256"], source["source_id"]
        )
        for profile_id in PROFILE_IDS:
            fresh = FRESH[profile_id]
            row = next(
                index
                for index, item in enumerate(heldout.SOURCES, start=1)
                if item["source_id"] == source["source_id"]
            )
            path = (
                ROOT
                / "artifacts/ms3/listening"
                / fresh["collection"]
                / f"{row:02d}-{source['source_id']}"
                / fresh["file"]
            )
            heldout._checked_file(  # noqa: SLF001
                path, fresh["hashes"][source["source_id"]], "fresh session control"
            )
    if arguments.work_dir.exists() or arguments.listener_dir.exists():
        raise SessionReuseError("work and listener outputs must be new")
    if not os.environ.get("LIVECONV_API_TOKEN"):
        raise SessionReuseError("LIVECONV_API_TOKEN is required")
    if not os.environ.get("LIVECONV_ALLOWED_ORIGINS"):
        raise SessionReuseError("LIVECONV_ALLOWED_ORIGINS is required")
    return deployment, heldout._load_renderer()  # noqa: SLF001


async def receive_control(websocket: Any, renderer: ModuleType, timeout: float) -> Any:
    try:
        message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
    except TimeoutError as error:
        raise SessionReuseError("Gateway control receive timed out") from error
    if not isinstance(message, str):
        raise SessionReuseError("Gateway returned PCM while control was required")
    event = renderer.parse_server_event(message)
    if isinstance(event, renderer.ErrorEvent):
        raise SessionReuseError(f"Gateway error: {event.code}")
    if isinstance(event, renderer.FallbackRequiredEvent):
        raise SessionReuseError(f"Gateway fallback: {event.reason_code}")
    return event


async def render_profile_turns(
    client: httpx.AsyncClient,
    *,
    renderer: ModuleType,
    gateway_url: str,
    token: str,
    origin: str,
    profile: dict[str, Any],
    turns: list[tuple[str, list[bytes]]],
    timeout: float,
    route_parity_qualification: bool = False,
) -> list[tuple[str, bytes, dict[str, Any]]]:
    profile_id = renderer.require_text(profile, "profile_id")
    headers = {"Authorization": f"Bearer {token}"}
    session_path = (
        "/v1/route-parity-sessions"
        if route_parity_qualification
        else "/v1/sessions"
    )
    response = await client.post(
        f"{gateway_url}{session_path}",
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
        timeout=timeout,
    )
    if response.status_code != 201:
        detail = response.json().get("detail", "unknown response")
        raise SessionReuseError(
            f"session creation returned {response.status_code}: {detail}"
        )
    descriptor = response.json()
    session_id = renderer.require_text(descriptor, "session_id")
    ticket = renderer.require_text(descriptor, "ticket")
    pipeline_id = renderer.require_text(descriptor, "pipeline_id")
    if any(
        descriptor.get(field) != profile[field]
        for field in ("profile_id", "profile_hash", "configuration_hash")
    ):
        raise SessionReuseError("session identity differs from sealed profile")

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
    results: list[tuple[str, bytes, dict[str, Any]]] = []
    try:
        websocket = await connect(
            websocket_url,
            origin=origin,
            compression=None,
            max_size=16_384,
            max_queue=None,
            open_timeout=timeout,
            close_timeout=timeout,
        )
        attach_id = "ms3.session-reuse.attach"
        await websocket.send(
            renderer.encode_control_message(
                renderer.SessionAttach(
                    protocol_version=1,
                    request_id=attach_id,
                    session_id=session_id,
                    ticket=ticket,
                )
            )
        )
        ready = await receive_control(websocket, renderer, timeout)
        if not isinstance(ready, renderer.SessionReadyEvent):
            raise SessionReuseError("Gateway did not return session.ready")
        if (
            ready.session_id != session_id
            or ready.profile_id != profile_id
            or ready.profile_hash != profile["profile_hash"]
            or ready.configuration_hash != profile["configuration_hash"]
            or ready.pipeline_id != pipeline_id
        ):
            raise SessionReuseError("session.ready identity is invalid")

        for generation_id, (source_id, input_frames) in enumerate(turns, start=1):
            credit = validate_turn_capacity(
                len(input_frames),
                ready.limits.max_ingress_frames,
                ready.limits.ingress_budget_ms,
            )
            request_prefix = f"ms3.session-reuse.{generation_id}"
            await websocket.send(
                renderer.encode_control_message(
                    renderer.GenerationStart(
                        protocol_version=1,
                        request_id=request_prefix + ".start",
                        session_id=session_id,
                        generation_id=generation_id,
                    )
                )
            )
            generation_ready = await receive_control(websocket, renderer, timeout)
            if not isinstance(generation_ready, renderer.GenerationReadyEvent):
                raise SessionReuseError("Gateway did not return generation.ready")
            if (
                generation_ready.generation_id != generation_id
                or generation_ready.profile_id != profile_id
                or generation_ready.pipeline_id != pipeline_id
            ):
                raise SessionReuseError("generation.ready identity is invalid")

            started = time.monotonic()
            epoch_ns = time.monotonic_ns()
            inputs: dict[int, tuple[int, bytes]] = {}
            maximum_lateness_ns = 0
            for sequence, payload in enumerate(input_frames):
                target_ns = epoch_ns + sequence * renderer.FRAME_NS
                delay = (target_ns - time.monotonic_ns()) / 1_000_000_000
                if delay > 0:
                    await asyncio.sleep(delay)
                sent_ns = time.monotonic_ns()
                maximum_lateness_ns = max(
                    maximum_lateness_ns, max(0, sent_ns - target_ns)
                )
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
            await websocket.send(
                renderer.encode_control_message(
                    renderer.GenerationEnd(
                        protocol_version=1,
                        request_id=request_prefix + ".end",
                        session_id=session_id,
                        generation_id=generation_id,
                    )
                )
            )

            output_payloads: list[bytes] = []
            changed_samples = 0
            finite_samples = 0
            absolute_peak = 0.0
            completed = False
            while not completed:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                except TimeoutError as error:
                    raise SessionReuseError("generation drain timed out") from error
                if isinstance(message, str):
                    event = renderer.parse_server_event(message)
                    if isinstance(event, renderer.ErrorEvent):
                        raise SessionReuseError(f"Gateway error: {event.code}")
                    if isinstance(event, renderer.FallbackRequiredEvent):
                        raise SessionReuseError(
                            f"Gateway fallback: {event.reason_code}"
                        )
                    if isinstance(event, renderer.GenerationCompletedEvent):
                        if (
                            event.generation_id != generation_id
                            or event.pipeline_id != pipeline_id
                        ):
                            raise SessionReuseError("completion identity is invalid")
                        completed = True
                        continue
                    raise SessionReuseError("unexpected event during generation drain")
                frame = renderer.PcmFrame.decode(message)
                header = frame.header
                sequence = len(output_payloads)
                if (
                    header.kind is not renderer.FrameKind.OUTPUT
                    or header.generation_id != generation_id
                    or header.sequence != sequence
                ):
                    raise SessionReuseError("output generation or sequence drifted")
                expected = inputs.pop(sequence, None)
                if expected is None or header.source_monotonic_ns != expected[0]:
                    raise SessionReuseError("output timestamp or input binding drifted")
                output_samples = struct.unpack(
                    f"<{renderer.SAMPLES_PER_FRAME}f", frame.payload
                )
                source_samples = struct.unpack(
                    f"<{renderer.SAMPLES_PER_FRAME}f", expected[1]
                )
                if any(not math.isfinite(value) for value in output_samples):
                    raise SessionReuseError("output PCM is non-finite")
                peak = max(abs(value) for value in output_samples)
                if peak > 1.0:
                    raise SessionReuseError("output PCM is outside normalized bounds")
                changed_samples += sum(
                    abs(output - source) > 1e-7
                    for output, source in zip(
                        output_samples, source_samples, strict=True
                    )
                )
                finite_samples += len(output_samples)
                absolute_peak = max(absolute_peak, peak)
                output_payloads.append(frame.payload)
            if inputs or len(output_payloads) != len(input_frames):
                raise SessionReuseError("generation completed before audio drained")
            if changed_samples <= 0:
                raise SessionReuseError("generation output did not change")
            results.append(
                (
                    source_id,
                    b"".join(output_payloads),
                    {
                        "generation_id": generation_id,
                        "frames": len(output_payloads),
                        "credit_limit": credit,
                        "finite_samples": finite_samples,
                        "changed_samples": changed_samples,
                        "absolute_peak": absolute_peak,
                        "maximum_send_lateness_ms": round(
                            maximum_lateness_ns / 1_000_000, 3
                        ),
                        "wall_seconds": round(time.monotonic() - started, 3),
                        "sequence_contiguous": True,
                        "timestamps_echoed": True,
                    },
                )
            )

        await websocket.send(
            renderer.encode_control_message(
                renderer.SessionClose(
                    protocol_version=1,
                    request_id="ms3.session-reuse.close",
                    session_id=session_id,
                )
            )
        )
        closed = await receive_control(websocket, renderer, timeout)
        if not isinstance(closed, renderer.SessionClosedEvent):
            raise SessionReuseError("Gateway did not acknowledge session close")
        invalidated = True
    finally:
        if websocket is not None:
            with contextlib.suppress(Exception):
                await websocket.close()
        with contextlib.suppress(httpx.HTTPError):
            cleanup = await client.delete(
                f"{gateway_url}/v1/sessions/{session_id}",
                headers=headers,
                timeout=timeout,
            )
            if invalidated and cleanup.status_code != 404:
                raise SessionReuseError("closed session remained addressable")
    return results


async def execute(
    arguments: argparse.Namespace,
    deployment: Path,
    renderer: ModuleType,
    heldout: ModuleType,
) -> dict[str, Any]:
    arguments.work_dir.mkdir(parents=True)
    persistent = arguments.work_dir / "persistent"
    persistent.mkdir()
    source_f32 = arguments.work_dir / "source-f32"
    source_f32.mkdir()
    turns = []
    for source in heldout.SOURCES:
        path = source_f32 / f"{source['source_id']}.f32le"
        heldout.wav_to_f32le(source["path"], path)
        frames, _, _ = renderer.source_frames(path)
        turns.append((source["source_id"], frames))

    manifest = renderer.read_json(deployment / "manifest.json")
    profiles_document = renderer.read_json(deployment / "profiles.json")
    variants = heldout._selected_records(  # noqa: SLF001
        manifest, "variants", PROFILE_IDS
    )
    profiles = heldout._selected_records(  # noqa: SLF001
        profiles_document, "profiles", PROFILE_IDS
    )
    variants_by_id = {item["profile_id"]: item for item in variants}
    profiles_by_id = {item["profile_id"]: item for item in profiles}
    token = os.environ["LIVECONV_API_TOKEN"]
    origin = next(
        value.strip()
        for value in os.environ["LIVECONV_ALLOWED_ORIGINS"].split(",")
        if value.strip()
    )
    gateway_url = arguments.gateway_url.rstrip("/")
    comparisons: list[dict[str, Any]] = []
    async with httpx.AsyncClient(follow_redirects=False) as client:
        catalog = await client.get(
            f"{gateway_url}/v1/models",
            headers={"Authorization": f"Bearer {token}"},
            timeout=arguments.timeout_seconds,
        )
        if catalog.status_code != 200:
            raise SessionReuseError("Gateway catalog is unavailable")
        advertised = {
            item["profile_id"]: item
            for item in catalog.json().get("profiles", [])
            if isinstance(item, dict) and "profile_id" in item
        }
        for profile_id in PROFILE_IDS:
            variant = variants_by_id[profile_id]
            current = advertised.get(profile_id)
            if not isinstance(current, dict) or any(
                current.get(field) != variant.get(field)
                for field in ("profile_hash", "configuration_hash")
            ):
                raise SessionReuseError("Gateway profile identity differs")
            profile = {
                **profiles_by_id[profile_id],
                "profile_hash": variant["profile_hash"],
                "configuration_hash": variant["configuration_hash"],
            }
            print(f"rendering persistent session / {profile_id}", flush=True)
            outputs = await render_profile_turns(
                client,
                renderer=renderer,
                gateway_url=gateway_url,
                token=token,
                origin=origin,
                profile=profile,
                turns=turns,
                timeout=arguments.timeout_seconds,
            )
            profile_dir = persistent / profile_id.replace(".", "-")
            profile_dir.mkdir()
            for source_id, pcm, generation in outputs:
                output = profile_dir / f"{source_id}.wav"
                renderer.write_wav(output, pcm)
                reused_sha256 = sha256_file(output)
                fresh_sha256 = FRESH[profile_id]["hashes"][source_id]
                comparisons.append(
                    {
                        "profile_id": profile_id,
                        "source_id": source_id,
                        "fresh_sha256": fresh_sha256,
                        "reused_sha256": reused_sha256,
                        "comparison": comparison_status(fresh_sha256, reused_sha256),
                        "generation": generation,
                    }
                )

    different = [item for item in comparisons if item["comparison"] == "different"]
    listener_published = bool(different)
    if listener_published:
        staging = arguments.work_dir / "listener-staging"
        staging.mkdir()
        for order, source in enumerate(heldout.SOURCES, start=1):
            source_id = source["source_id"]
            row = staging / f"{order:02d}-{source_id}"
            row.mkdir()
            shutil.copyfile(source["path"], row / "00-source.wav")
            variants_out = []
            display_order = 0
            for profile_id in PROFILE_IDS:
                display_order += 1
                fresh = FRESH[profile_id]
                fresh_path = (
                    ROOT
                    / "artifacts/ms3/listening"
                    / fresh["collection"]
                    / f"{order:02d}-{source_id}"
                    / fresh["file"]
                )
                family = "RVC" if profile_id.startswith("vc.rvc-v2") else "X-VC"
                fresh_name = f"{display_order}0-{family.lower()}-fresh.wav"
                shutil.copyfile(fresh_path, row / fresh_name)
                variants_out.append(
                    {
                        "variant_id": f"{family.lower()}-fresh",
                        "display_name": f"{family} / fresh Gateway session",
                        "display_order": display_order,
                        "output_file": fresh_name,
                        "status": "passed",
                        "profile_id": profile_id,
                        "operator_judgment": "unreviewed",
                    }
                )
                display_order += 1
                reused_name = f"{display_order}0-{family.lower()}-reused.wav"
                reused_path = (
                    persistent / profile_id.replace(".", "-") / f"{source_id}.wav"
                )
                shutil.copyfile(reused_path, row / reused_name)
                variants_out.append(
                    {
                        "variant_id": f"{family.lower()}-reused",
                        "display_name": f"{family} / generation {order} in one session",
                        "display_order": display_order,
                        "output_file": reused_name,
                        "status": "passed",
                        "profile_id": profile_id,
                        "operator_judgment": "unreviewed",
                    }
                )
            (row / "index.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "title": f"VC session reuse / {source_id}",
                        "run_kind": "MS-3 persistent-session state comparison",
                        "status": "completed-listen-now-unselected",
                        "source_file": f"Hadou public heldout / {source_id}",
                        "source_text": source["display_text"],
                        "source_id": source_id,
                        "source_output_file": "00-source.wav",
                        "variants": variants_out,
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        staging.rename(arguments.listener_dir)

    result = {
        "schema_version": 1,
        "kind": "liveconv-ms3-vc-session-reuse-result",
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "profiles": list(PROFILE_IDS),
        "turns_per_session": len(turns),
        "comparisons": comparisons,
        "different_count": len(different),
        "listener_published": listener_published,
        "claims": {"perceptual_winner": False, "product_selected": False},
    }
    (arguments.work_dir / "session-reuse-result.json").write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    )
    return result


async def run(arguments: argparse.Namespace) -> int:
    heldout = _load_heldout_runner()
    deployment, renderer = validate_inputs(arguments, heldout)
    if arguments.check:
        print("ok   persistent-session CPU admission complete")
        return 0
    result = await execute(arguments, deployment, renderer, heldout)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    mode = value.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    value.add_argument("--deployment", type=Path, required=True)
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    value.add_argument("--gateway-url", default="http://127.0.0.1:8877")
    value.add_argument("--timeout-seconds", type=float, default=180.0)
    return value


def main() -> int:
    try:
        return asyncio.run(run(parser().parse_args()))
    except (OSError, SessionReuseError, ValueError) as error:
        print(f"render_vc_session_reuse: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
