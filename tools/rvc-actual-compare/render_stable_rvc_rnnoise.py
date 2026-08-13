#!/usr/bin/env python3
"""Render raw and RNNoise-preprocessed actual input through stable RVC seed 0."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REPEAT_RUNNER = Path(__file__).with_name("render_rvc_repeat_turn.py")
PROFILE_ID = "vc.rvc-v2.amitaro-sasayaki-clean-bright-seed0.v1"
SOURCE_ID = "ACTUAL_CHATGPT_20260811_114251"
SOURCE_SHA256 = "78b15cd5e9d25ee10d8cb27084c63275221d773a04b21d11e4e3ba2be8056da6"
SOURCE_F32_SHA256 = "60e2b54bc4a013e653865bc8b80a55e9af3c994fa21ee506de1137f5816a4802"
RNNOISE_STREAM_SHA256 = (
    "e8992103e4f78610d8aaedc83c73d9c5a009b8aba5036db7bc23f141c3cac45c"
)
RNNOISE_MANIFEST_SHA256 = (
    "21772cd336fba424eeaf5cbb4e3b776b3c1a128d60c9b1dcc40336b40ebf7cce"
)


class StableRnnoiseError(RuntimeError):
    """The bounded raw-versus-RNNoise comparison cannot continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_repeat_runner() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "liveconv_stable_rnnoise_repeat", REPEAT_RUNNER
    )
    if specification is None or specification.loader is None:
        raise StableRnnoiseError("repeat runner cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def preprocess_rnnoise(frames: list[bytes], executable: Path) -> list[bytes]:
    if not frames or any(len(frame) != 960 * 4 for frame in frames):
        raise StableRnnoiseError("source must contain complete 20 ms float32 frames")
    samples = np.frombuffer(b"".join(frames), dtype="<f4").astype(np.float64)
    if not np.all(np.isfinite(samples)) or np.max(np.abs(samples)) > 1.0:
        raise StableRnnoiseError("source PCM is outside normalized finite bounds")
    pcm16 = np.rint(samples * 32767.0).clip(-32768, 32767).astype("<i2")
    completed = subprocess.run(
        [str(executable)], input=pcm16.tobytes(), capture_output=True, check=False
    )
    if completed.returncode:
        message = completed.stderr.decode(errors="replace")[-500:]
        raise StableRnnoiseError(f"RNNoise helper failed: {message}")
    if len(completed.stdout) != len(pcm16.tobytes()):
        raise StableRnnoiseError("RNNoise helper returned incomplete PCM")
    denoised = (
        (np.frombuffer(completed.stdout, dtype="<i2").astype(np.float32) / 32768.0)
        .astype("<f4")
        .tobytes()
    )
    frame_bytes = 960 * 4
    return [
        denoised[offset : offset + frame_bytes]
        for offset in range(0, len(denoised), frame_bytes)
    ]


def validate(
    arguments: argparse.Namespace,
) -> tuple[Path, ModuleType, ModuleType, ModuleType]:
    for path, expected, label in (
        (arguments.actual_source_wav, SOURCE_SHA256, "actual source"),
        (arguments.rnnoise_stream, RNNOISE_STREAM_SHA256, "RNNoise helper"),
        (arguments.rnnoise_manifest, RNNOISE_MANIFEST_SHA256, "RNNoise manifest"),
    ):
        resolved = path.resolve(strict=True)
        if resolved.is_symlink() or sha256_file(resolved) != expected:
            raise StableRnnoiseError(f"{label} identity drifted")
    if not os.access(arguments.rnnoise_stream, os.X_OK):
        raise StableRnnoiseError("RNNoise helper is not executable")
    deployment = arguments.deployment.resolve(strict=True)
    repeat = load_repeat_runner()
    session = repeat._load_session_runner()  # noqa: SLF001
    heldout = session._load_heldout_runner()  # noqa: SLF001
    manifest = json.loads((deployment / "manifest.json").read_text())
    profiles = json.loads((deployment / "profiles.json").read_text())
    heldout._selected_records(manifest, "variants", (PROFILE_ID,))  # noqa: SLF001
    heldout._selected_records(profiles, "profiles", (PROFILE_ID,))  # noqa: SLF001
    if arguments.work_dir.exists() or arguments.listener_dir.exists():
        raise StableRnnoiseError("work and listener outputs must be new")
    if not os.environ.get("LIVECONV_API_TOKEN"):
        raise StableRnnoiseError("LIVECONV_API_TOKEN is required")
    if not os.environ.get("LIVECONV_ALLOWED_ORIGINS"):
        raise StableRnnoiseError("LIVECONV_ALLOWED_ORIGINS is required")
    return deployment, session, heldout, heldout._load_renderer()  # noqa: SLF001


async def execute(
    arguments: argparse.Namespace,
    deployment: Path,
    session: ModuleType,
    heldout: ModuleType,
    renderer: ModuleType,
) -> dict[str, Any]:
    arguments.work_dir.mkdir(parents=True)
    source_f32 = arguments.work_dir / "source.f32le"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(arguments.actual_source_wav),
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ar",
            "48000",
            "-ac",
            "1",
            str(source_f32),
        ],
        check=True,
    )
    if sha256_file(source_f32) != SOURCE_F32_SHA256:
        raise StableRnnoiseError("actual source float32 identity drifted")
    frames, _, _ = renderer.source_frames(source_f32)
    denoised_frames = preprocess_rnnoise(frames, arguments.rnnoise_stream)

    manifest = renderer.read_json(deployment / "manifest.json")
    profiles = renderer.read_json(deployment / "profiles.json")
    variant = heldout._selected_records(manifest, "variants", (PROFILE_ID,))[0]  # noqa: SLF001
    sealed = heldout._selected_records(profiles, "profiles", (PROFILE_ID,))[0]  # noqa: SLF001
    profile = {
        **sealed,
        "profile_hash": variant["profile_hash"],
        "configuration_hash": variant["configuration_hash"],
    }
    token = os.environ["LIVECONV_API_TOKEN"]
    origin = next(
        value.strip()
        for value in os.environ["LIVECONV_ALLOWED_ORIGINS"].split(",")
        if value.strip()
    )
    gateway_url = arguments.gateway_url.rstrip("/")
    async with httpx.AsyncClient(follow_redirects=False) as client:
        catalog = await client.get(
            f"{gateway_url}/v1/models",
            headers={"Authorization": f"Bearer {token}"},
            timeout=arguments.timeout_seconds,
        )
        advertised = {
            item.get("profile_id"): item
            for item in catalog.json().get("profiles", [])
            if isinstance(item, dict)
        }
        current = advertised.get(PROFILE_ID)
        if not isinstance(current, dict) or any(
            current.get(field) != variant.get(field)
            for field in ("profile_hash", "configuration_hash")
        ):
            raise StableRnnoiseError("Gateway stable RVC profile identity differs")
        outputs = await session.render_profile_turns(
            client,
            renderer=renderer,
            gateway_url=gateway_url,
            token=token,
            origin=origin,
            profile=profile,
            turns=[("raw", frames), ("rnnoise", denoised_frames)],
            timeout=arguments.timeout_seconds,
            route_parity_qualification=True,
        )
    if [label for label, _, _ in outputs] != ["raw", "rnnoise"]:
        raise StableRnnoiseError("Gateway output arms differ from the bounded plan")

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    shutil.copyfile(arguments.actual_source_wav, staging / "00-source.wav")
    renderer.write_wav(staging / "10-stable-rvc-raw.wav", outputs[0][1])
    renderer.write_wav(staging / "20-rnnoise-input.wav", b"".join(denoised_frames))
    renderer.write_wav(staging / "30-stable-rvc-rnnoise.wav", outputs[1][1])
    variants = [
        {
            "variant_id": "stable-rvc-raw",
            "display_name": "Stable seed-0 RVC / raw actual input",
            "display_order": 1,
            "output_file": "10-stable-rvc-raw.wav",
            "output_sha256": "sha256:" + sha256_file(staging / "10-stable-rvc-raw.wav"),
            "profile_id": PROFILE_ID,
            "generation": outputs[0][2],
            "status": "passed",
            "operator_judgment": "unreviewed",
        },
        {
            "variant_id": "stable-rvc-rnnoise",
            "display_name": "RNNoise + stable seed-0 RVC",
            "display_order": 2,
            "output_file": "30-stable-rvc-rnnoise.wav",
            "output_sha256": "sha256:"
            + sha256_file(staging / "30-stable-rvc-rnnoise.wav"),
            "profile_id": PROFILE_ID,
            "generation": outputs[1][2],
            "status": "passed",
            "operator_judgment": "unreviewed",
        },
    ]
    index = {
        "schema_version": 1,
        "title": "Stable RVC actual input: raw vs RNNoise",
        "run_kind": "MS-3 single-variable actual-input preprocessing comparison",
        "status": "completed-listen-now-unselected",
        "source_id": SOURCE_ID,
        "source_file": "Native / actual ChatGPT-tab input (2026-08-11)",
        "source_output_file": "00-source.wav",
        "diagnostic_input_file": "20-rnnoise-input.wav",
        "comparison_scope": {
            "changed_variable": "stateful RNNoise preprocessing",
            "fixed": ["source", "stable seed-0 RVC profile", "Gateway", "session"],
            "machine_selection_allowed": False,
            "question": "Does RNNoise improve the stable RVC actual-input candidate?",
        },
        "rnnoise": {
            "stream_sha256": "sha256:" + RNNOISE_STREAM_SHA256,
            "manifest_sha256": "sha256:" + RNNOISE_MANIFEST_SHA256,
            "frame_ms": 10,
            "state_scope": "one continuous actual-input replay",
        },
        "variants": variants,
    }
    (staging / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    staging.rename(arguments.listener_dir)
    result = {
        "schema_version": 1,
        "kind": "liveconv-ms3-stable-rvc-rnnoise-result",
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "profile_id": PROFILE_ID,
        "source_id": SOURCE_ID,
        "output_sha256": {
            item["variant_id"]: item["output_sha256"] for item in variants
        },
        "claims": {"perceptual_winner": False, "product_selected": False},
    }
    (arguments.work_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return result


async def run(arguments: argparse.Namespace) -> int:
    deployment, session, heldout, renderer = validate(arguments)
    if arguments.check:
        print("ok   stable RVC RNNoise CPU admission complete")
        return 0
    await execute(arguments, deployment, session, heldout, renderer)
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    mode = value.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    value.add_argument("--deployment", type=Path, required=True)
    value.add_argument("--actual-source-wav", type=Path, required=True)
    value.add_argument("--rnnoise-stream", type=Path, required=True)
    value.add_argument("--rnnoise-manifest", type=Path, required=True)
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    value.add_argument("--gateway-url", default="http://127.0.0.1:8881")
    value.add_argument("--timeout-seconds", type=float, default=180.0)
    return value


def main() -> int:
    try:
        return asyncio.run(run(parser().parse_args()))
    except (
        OSError,
        StableRnnoiseError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        print(f"render_stable_rvc_rnnoise: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
