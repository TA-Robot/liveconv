#!/usr/bin/env python3
"""Render the current exclusive hard fallback on stable actual-input audio."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
INPUT_ROOT = ROOT / "artifacts/ms3/listening/ms3-stable-vc-actual-shortlist-v1"
SOURCE_FILE = "00-source.wav"
SOURCE_SHA256 = "78b15cd5e9d25ee10d8cb27084c63275221d773a04b21d11e4e3ba2be8056da6"
SAMPLE_RATE = 48_000
CHANNELS = 1
SAMPLE_WIDTH = 3
SWITCH_SECONDS = 2.0
SWITCH_FRAME = int(SAMPLE_RATE * SWITCH_SECONDS)
WINDOW_FRAMES = 960
PROFILES = (
    {
        "slug": "rvc-seed0",
        "label": "Stable seed-0 RVC",
        "profile_id": "vc.rvc-v2.amitaro-sasayaki-clean-bright-seed0.v1",
        "remote_file": "10-stable-rvc-seed0.wav",
        "remote_sha256": (
            "e00b7f6ec53e838ee3b7cd77d1c6af3035ff3a8e49b724c674631f53cc56e13f"
        ),
    },
    {
        "slug": "xvc-q34",
        "label": "Stable X-VC Yofukashi Q034",
        "profile_id": "vc.x-vc.amitaro-yofukashi-q34.v1",
        "remote_file": "20-stable-xvc-q34.wav",
        "remote_sha256": (
            "bbcc638cd330940a79d8b009653e7d1cd930dc452de0252ca7b01d9c97c31442"
        ),
    },
)


class NativeFallbackError(RuntimeError):
    """The bounded native-fallback listening render cannot continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_wav(path: Path, expected_sha256: str) -> tuple[wave._wave_params, bytes]:
    if sha256_file(path) != expected_sha256:
        raise NativeFallbackError(f"input identity drifted: {path.name}")
    with wave.open(str(path), "rb") as stream:
        parameters = stream.getparams()
        payload = stream.readframes(stream.getnframes())
    if (
        parameters.nchannels != CHANNELS
        or parameters.sampwidth != SAMPLE_WIDTH
        or parameters.framerate != SAMPLE_RATE
        or parameters.comptype != "NONE"
    ):
        raise NativeFallbackError(f"unsupported WAV contract: {path.name}")
    return parameters, payload


def splice_pcm24(remote: bytes, native: bytes, switch_frame: int) -> bytes:
    if switch_frame <= 0:
        raise NativeFallbackError("fallback switch must follow remote playout")
    boundary = switch_frame * SAMPLE_WIDTH * CHANNELS
    if boundary >= len(native) or boundary > len(remote):
        raise NativeFallbackError("fallback switch is outside retained audio")
    return remote[:boundary] + native[boundary:]


def sample_pcm24(payload: bytes, frame: int) -> float:
    offset = frame * SAMPLE_WIDTH
    value = int.from_bytes(
        payload[offset : offset + SAMPLE_WIDTH], "little", signed=True
    )
    return value / 8_388_608.0


def rms_window(payload: bytes, end_frame: int) -> float:
    start = max(0, end_frame - WINDOW_FRAMES)
    samples = [sample_pcm24(payload, frame) for frame in range(start, end_frame)]
    return math.sqrt(sum(value * value for value in samples) / len(samples))


def write_wav(path: Path, parameters: wave._wave_params, payload: bytes) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setparams(parameters)
        stream.writeframes(payload)


def staging_path(listener_dir: Path) -> Path:
    return listener_dir.with_name(f".{listener_dir.name}.staging")


def validate(arguments: argparse.Namespace) -> dict[str, Any]:
    source_parameters, source_payload = checked_wav(
        INPUT_ROOT / SOURCE_FILE, SOURCE_SHA256
    )
    remotes: dict[str, tuple[wave._wave_params, bytes]] = {}
    for profile in PROFILES:
        parameters, payload = checked_wav(
            INPUT_ROOT / profile["remote_file"], profile["remote_sha256"]
        )
        if (
            parameters.nchannels != source_parameters.nchannels
            or parameters.sampwidth != source_parameters.sampwidth
            or parameters.framerate != source_parameters.framerate
            or parameters.comptype != source_parameters.comptype
        ):
            raise NativeFallbackError("source and remote WAV contracts differ")
        splice_pcm24(payload, source_payload, SWITCH_FRAME)
        remotes[profile["slug"]] = (parameters, payload)
    if (
        arguments.work_dir.exists()
        or arguments.listener_dir.exists()
        or staging_path(arguments.listener_dir).exists()
    ):
        raise NativeFallbackError("work and listener outputs must be new")
    return {
        "source_parameters": source_parameters,
        "source_payload": source_payload,
        "remotes": remotes,
    }


def execute(arguments: argparse.Namespace, inputs: dict[str, Any]) -> None:
    arguments.work_dir.mkdir(parents=True)
    staging = staging_path(arguments.listener_dir)
    staging.mkdir(parents=True)
    summaries = []
    for order, profile in enumerate(PROFILES, start=1):
        run_dir = staging / f"{order:02d}-{profile['slug']}"
        run_dir.mkdir()
        source_output = "00-native-continuous.wav"
        remote_output = f"10-{profile['slug']}-remote-continuous.wav"
        fallback_output = f"20-{profile['slug']}-native-fallback-at-2s.wav"
        shutil.copyfile(INPUT_ROOT / SOURCE_FILE, run_dir / source_output)
        shutil.copyfile(INPUT_ROOT / profile["remote_file"], run_dir / remote_output)
        _, remote_payload = inputs["remotes"][profile["slug"]]
        fallback_payload = splice_pcm24(
            remote_payload, inputs["source_payload"], SWITCH_FRAME
        )
        fallback_wav = run_dir / fallback_output
        write_wav(fallback_wav, inputs["source_parameters"], fallback_payload)
        fallback_sha256 = sha256_file(fallback_wav)
        boundary_jump = abs(
            sample_pcm24(inputs["source_payload"], SWITCH_FRAME)
            - sample_pcm24(remote_payload, SWITCH_FRAME - 1)
        )
        boundary_evidence = {
            "switch_seconds": SWITCH_SECONDS,
            "switch_frame": SWITCH_FRAME,
            "switch_behavior": "remote muted before native becomes audible",
            "simultaneous_routes": False,
            "remote_pre_switch_rms_20ms": rms_window(
                remote_payload, SWITCH_FRAME
            ),
            "native_pre_switch_rms_20ms": rms_window(
                inputs["source_payload"], SWITCH_FRAME
            ),
            "hard_switch_sample_jump": boundary_jump,
        }
        index = {
            "schema_version": 1,
            "title": f"{profile['label']} native fallback at 2.0 seconds",
            "run_kind": "MS-3 audible exclusive native-fallback comparison",
            "status": "completed-listen-now-unselected",
            "source_file": "Native / actual ChatGPT-tab input (2026-08-11)",
            "source_id": "ACTUAL_CHATGPT_20260811_114251",
            "source_output_file": source_output,
            "comparison_scope": {
                "changed_variable": (
                    "remote continues versus exclusive native fallback at 2.0 seconds"
                ),
                "machine_selection_allowed": False,
                "question": (
                    "Is the current immediate native fallback audibly disruptive?"
                ),
            },
            "boundary_evidence": boundary_evidence,
            "variants": [
                {
                    "variant_id": f"{profile['slug']}-remote-continuous",
                    "display_name": f"{profile['label']} / remote continues",
                    "display_order": 1,
                    "output_file": remote_output,
                    "output_sha256": "sha256:" + profile["remote_sha256"],
                    "profile_id": profile["profile_id"],
                    "status": "passed",
                    "operator_judgment": "unreviewed",
                },
                {
                    "variant_id": f"{profile['slug']}-native-fallback-at-2s",
                    "display_name": f"{profile['label']} / native fallback at 2.0 s",
                    "display_order": 2,
                    "output_file": fallback_output,
                    "output_sha256": "sha256:" + fallback_sha256,
                    "profile_id": profile["profile_id"],
                    "status": "passed",
                    "operator_judgment": "unreviewed",
                },
            ],
        }
        (run_dir / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        summaries.append(
            {
                "profile_id": profile["profile_id"],
                "fallback_sha256": "sha256:" + fallback_sha256,
                "boundary_evidence": boundary_evidence,
            }
        )
    staging.rename(arguments.listener_dir)
    result = {
        "schema_version": 1,
        "kind": "liveconv-ms3-stable-vc-native-fallback-result",
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "source_sha256": "sha256:" + SOURCE_SHA256,
        "profiles": summaries,
        "claims": {"perceptual_winner": False, "product_selected": False},
    }
    (arguments.work_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    mode = value.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    return value


def main() -> int:
    try:
        arguments = parser().parse_args()
        inputs = validate(arguments)
        if arguments.check:
            print("ok   stable VC native-fallback CPU admission complete")
            return 0
        execute(arguments, inputs)
        return 0
    except (NativeFallbackError, OSError, subprocess.CalledProcessError) as error:
        print(f"render_stable_vc_native_fallback: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
