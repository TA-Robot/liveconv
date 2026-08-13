#!/usr/bin/env python3
"""Compare one versus two generation boundaries on exact actual-input RVC."""

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
RVC_PROFILE_ID = "vc.rvc-v2.amitaro-sasayaki-clean-bright-seed0.v1"
SOURCE_ID = "ACTUAL_CHATGPT_20260811_114251"
SOURCE_WAV_SHA256 = "78b15cd5e9d25ee10d8cb27084c63275221d773a04b21d11e4e3ba2be8056da6"
SOURCE_F32_SHA256 = "b114aed49c79291b10caf30f9828e6efb0e191773aa2fe8ab77d786f7a83b5f2"
BASELINE_RVC_SHA256 = "e00b7f6ec53e838ee3b7cd77d1c6af3035ff3a8e49b724c674631f53cc56e13f"
EXPECTED_FRAMES = 409
SPLIT_FRAME = 212
QUIET_START_FRAME = 198
QUIET_END_FRAME = 226
MAX_QUIET_RMS = 10.0 ** (-50.0 / 20.0)


class StableTurnSplitError(RuntimeError):
    """The bounded stable-RVC generation-boundary comparison cannot continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_file(path: Path, expected: str, label: str) -> Path:
    resolved = path.resolve(strict=True)
    if resolved.is_symlink() or sha256_file(resolved) != expected:
        raise StableTurnSplitError(f"{label} identity drifted")
    return resolved


def listener_staging_path(listener_dir: Path) -> Path:
    return listener_dir.with_name(f".{listener_dir.name}.staging")


def load_repeat_runner() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "liveconv_stable_turn_split_repeat", REPEAT_RUNNER
    )
    if specification is None or specification.loader is None:
        raise StableTurnSplitError("repeat runner cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def split_turns(frames: list[bytes]) -> tuple[list[bytes], list[bytes], float]:
    if len(frames) != EXPECTED_FRAMES or any(len(frame) != 960 * 4 for frame in frames):
        raise StableTurnSplitError("source does not match the fixed 409-frame input")
    quiet = np.frombuffer(
        b"".join(frames[QUIET_START_FRAME:QUIET_END_FRAME]), dtype="<f4"
    ).astype(np.float64)
    quiet_rms = float(np.sqrt(np.mean(quiet**2)))
    if not np.isfinite(quiet_rms) or quiet_rms >= MAX_QUIET_RMS:
        raise StableTurnSplitError("fixed generation boundary is no longer quiet")
    return frames[:SPLIT_FRAME], frames[SPLIT_FRAME:], quiet_rms


def validate(
    arguments: argparse.Namespace,
) -> tuple[Path, ModuleType, ModuleType, ModuleType]:
    checked_file(arguments.source_wav, SOURCE_WAV_SHA256, "listening source")
    checked_file(arguments.source_f32, SOURCE_F32_SHA256, "original float PCM")
    checked_file(arguments.baseline_rvc_wav, BASELINE_RVC_SHA256, "baseline RVC")
    deployment = arguments.deployment.resolve(strict=True)
    repeat = load_repeat_runner()
    session = repeat._load_session_runner()  # noqa: SLF001
    heldout = session._load_heldout_runner()  # noqa: SLF001
    manifest = json.loads((deployment / "manifest.json").read_text())
    profiles = json.loads((deployment / "profiles.json").read_text())
    heldout._selected_records(manifest, "variants", (RVC_PROFILE_ID,))  # noqa: SLF001
    heldout._selected_records(profiles, "profiles", (RVC_PROFILE_ID,))  # noqa: SLF001
    if (
        arguments.work_dir.exists()
        or arguments.listener_dir.exists()
        or listener_staging_path(arguments.listener_dir).exists()
    ):
        raise StableTurnSplitError("work and listener outputs must be new")
    if not os.environ.get("LIVECONV_API_TOKEN"):
        raise StableTurnSplitError("LIVECONV_API_TOKEN is required")
    if not os.environ.get("LIVECONV_ALLOWED_ORIGINS"):
        raise StableTurnSplitError("LIVECONV_ALLOWED_ORIGINS is required")
    return deployment, session, heldout, heldout._load_renderer()  # noqa: SLF001


async def execute(
    arguments: argparse.Namespace,
    deployment: Path,
    session: ModuleType,
    heldout: ModuleType,
    renderer: ModuleType,
) -> dict[str, Any]:
    arguments.work_dir.mkdir(parents=True)
    frames, source_samples, source_levels = renderer.source_frames(arguments.source_f32)
    turn_one, turn_two, quiet_rms = split_turns(frames)

    manifest = renderer.read_json(deployment / "manifest.json")
    profiles = renderer.read_json(deployment / "profiles.json")
    variant = heldout._selected_records(  # noqa: SLF001
        manifest, "variants", (RVC_PROFILE_ID,)
    )[0]
    sealed = heldout._selected_records(  # noqa: SLF001
        profiles, "profiles", (RVC_PROFILE_ID,)
    )[0]
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
        current = advertised.get(RVC_PROFILE_ID)
        if not isinstance(current, dict) or any(
            current.get(field) != variant.get(field)
            for field in ("profile_hash", "configuration_hash")
        ):
            raise StableTurnSplitError("Gateway stable RVC profile identity differs")
        outputs = await session.render_profile_turns(
            client,
            renderer=renderer,
            gateway_url=gateway_url,
            token=token,
            origin=origin,
            profile=profile,
            turns=[("turn-1", turn_one), ("turn-2", turn_two)],
            timeout=arguments.timeout_seconds,
            route_parity_qualification=True,
        )
    if [label for label, _, _ in outputs] != ["turn-1", "turn-2"]:
        raise StableTurnSplitError("Gateway output turns differ from the bounded plan")
    split_output = outputs[0][1] + outputs[1][1]
    if len(split_output) != EXPECTED_FRAMES * 960 * 4:
        raise StableTurnSplitError("two-turn output length differs from the baseline")

    staging = listener_staging_path(arguments.listener_dir)
    staging.mkdir()
    shutil.copyfile(arguments.source_wav, staging / "00-source.wav")
    shutil.copyfile(arguments.baseline_rvc_wav, staging / "10-stable-rvc-one-turn.wav")
    renderer.write_wav(staging / "20-stable-rvc-two-turn.wav", split_output)
    variants = [
        {
            "variant_id": "stable-rvc-one-generation",
            "display_name": "Stable seed-0 RVC / one 8.17 s generation",
            "display_order": 1,
            "output_file": "10-stable-rvc-one-turn.wav",
            "output_sha256": "sha256:" + BASELINE_RVC_SHA256,
            "profile_id": RVC_PROFILE_ID,
            "status": "passed",
            "operator_judgment": "unreviewed",
            "reused_by_exact_hash": True,
        },
        {
            "variant_id": "stable-rvc-two-generations",
            "display_name": "Stable seed-0 RVC / split into two generations",
            "display_order": 2,
            "output_file": "20-stable-rvc-two-turn.wav",
            "output_sha256": "sha256:"
            + sha256_file(staging / "20-stable-rvc-two-turn.wav"),
            "profile_id": RVC_PROFILE_ID,
            "generations": [item[2] for item in outputs],
            "status": "passed",
            "operator_judgment": "unreviewed",
        },
    ]
    index = {
        "schema_version": 1,
        "title": "Stable RVC actual input: one vs two generations",
        "run_kind": "MS-3 generation-boundary actual-input comparison",
        "status": "completed-listen-now-unselected",
        "source_id": SOURCE_ID,
        "source_file": "Native / actual ChatGPT-tab input (2026-08-11)",
        "source_output_file": "00-source.wav",
        "source_raw_f32_sha256": "sha256:" + SOURCE_F32_SHA256,
        "source_samples": source_samples,
        "source_levels": source_levels,
        "comparison_scope": {
            "changed_variable": "one generation versus two generations",
            "fixed": ["source bytes", "source order", RVC_PROFILE_ID, "Gateway"],
            "machine_selection_allowed": False,
            "question": "Does a natural turn boundary degrade stable RVC output?",
        },
        "turn_boundary": {
            "split_frame": SPLIT_FRAME,
            "split_seconds": SPLIT_FRAME * 0.02,
            "quiet_window_frames": [QUIET_START_FRAME, QUIET_END_FRAME],
            "quiet_window_seconds": [
                QUIET_START_FRAME * 0.02,
                QUIET_END_FRAME * 0.02,
            ],
            "quiet_window_rms": quiet_rms,
        },
        "variants": variants,
    }
    (staging / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    staging.rename(arguments.listener_dir)
    result = {
        "schema_version": 1,
        "kind": "liveconv-ms3-stable-rvc-turn-split-result",
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "profile_id": RVC_PROFILE_ID,
        "source_id": SOURCE_ID,
        "split_seconds": SPLIT_FRAME * 0.02,
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
        frames, _, _ = renderer.source_frames(arguments.source_f32)
        split_turns(frames)
        print("ok   stable RVC natural turn-split CPU admission complete")
        return 0
    await execute(arguments, deployment, session, heldout, renderer)
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    mode = value.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    value.add_argument("--deployment", type=Path, required=True)
    value.add_argument("--source-wav", type=Path, required=True)
    value.add_argument("--source-f32", type=Path, required=True)
    value.add_argument("--baseline-rvc-wav", type=Path, required=True)
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    value.add_argument("--gateway-url", default="http://127.0.0.1:8881")
    value.add_argument("--timeout-seconds", type=float, default=300.0)
    return value


def main() -> int:
    try:
        return asyncio.run(run(parser().parse_args()))
    except (
        OSError,
        StableTurnSplitError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        print(f"render_stable_rvc_turn_split: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
