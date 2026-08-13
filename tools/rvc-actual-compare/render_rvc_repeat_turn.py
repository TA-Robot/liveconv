#!/usr/bin/env python3
"""Repeat one real utterance three times in one live RVC Gateway session."""

from __future__ import annotations

import argparse
import asyncio
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
SESSION_RUNNER = Path(__file__).with_name("render_vc_session_reuse.py")
PROFILE_ID = "vc.rvc-v2.amitaro-sasayaki-clean-bright.v1"
SEEDED_PROFILE_ID = "vc.rvc-v2.amitaro-sasayaki-clean-bright-seed0.v1"
SOURCE_ID = "EMOTION100_017"
REPEAT_COUNT = 3


class RepeatTurnError(RuntimeError):
    """The bounded same-input repeat diagnostic cannot continue."""


def _load_session_runner() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "liveconv_rvc_repeat_turn_session", SESSION_RUNNER
    )
    if specification is None or specification.loader is None:
        raise RepeatTurnError("session-reuse runner cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def signal_comparison(anchor_pcm: bytes, candidate_pcm: bytes) -> dict[str, float]:
    anchor = np.frombuffer(anchor_pcm, dtype="<f4").astype(np.float64)
    candidate = np.frombuffer(candidate_pcm, dtype="<f4").astype(np.float64)
    if anchor.shape != candidate.shape or not anchor.size:
        raise RepeatTurnError("repeat outputs are not shape-compatible")
    difference = anchor - candidate
    anchor_rms = float(np.sqrt(np.mean(anchor * anchor)))
    difference_rms = float(np.sqrt(np.mean(difference * difference)))
    correlation = float(np.corrcoef(anchor, candidate)[0, 1])
    snr_db = (
        float(20 * np.log10(anchor_rms / difference_rms))
        if difference_rms
        else float("inf")
    )
    return {
        "correlation_to_generation_1": correlation,
        "max_abs_difference": float(np.max(np.abs(difference))),
        "rms_difference": difference_rms,
        "snr_db_to_generation_1": snr_db,
    }


def validate_scope(profile_id: str) -> None:
    if (
        profile_id == PROFILE_ID
        and profile_id not in _load_session_runner().PROFILE_IDS
    ):
        raise RepeatTurnError("repeat profile is not a surviving live arm")
    if profile_id not in {PROFILE_ID, SEEDED_PROFILE_ID}:
        raise RepeatTurnError("repeat profile is outside the bounded diagnostic")
    if REPEAT_COUNT != 3:
        raise RepeatTurnError("repeat diagnostic must contain exactly three turns")


async def execute(
    arguments: argparse.Namespace,
    session: ModuleType,
    heldout: ModuleType,
    deployment: Path,
    renderer: ModuleType,
) -> dict[str, Any]:
    profile_id = arguments.profile_id
    source = next(item for item in heldout.SOURCES if item["source_id"] == SOURCE_ID)
    arguments.work_dir.mkdir(parents=True)
    source_f32 = arguments.work_dir / "source.f32le"
    heldout.wav_to_f32le(source["path"], source_f32)
    frames, _, _ = renderer.source_frames(source_f32)

    manifest = renderer.read_json(deployment / "manifest.json")
    profile_document = renderer.read_json(deployment / "profiles.json")
    variant = heldout._selected_records(  # noqa: SLF001
        manifest, "variants", (profile_id,)
    )[0]
    sealed_profile = heldout._selected_records(  # noqa: SLF001
        profile_document, "profiles", (profile_id,)
    )[0]
    profile = {
        **sealed_profile,
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
        current = advertised.get(profile_id)
        if not isinstance(current, dict) or any(
            current.get(field) != variant.get(field)
            for field in ("profile_hash", "configuration_hash")
        ):
            raise RepeatTurnError("Gateway RVC profile identity differs")
        outputs = await session.render_profile_turns(
            client,
            renderer=renderer,
            gateway_url=gateway_url,
            token=token,
            origin=origin,
            profile=profile,
            turns=[(f"repeat-{index}", frames) for index in range(1, 4)],
            timeout=arguments.timeout_seconds,
        )

    if len(outputs) != REPEAT_COUNT:
        raise RepeatTurnError("repeat generation count drifted")
    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    shutil.copyfile(source["path"], staging / "00-source.wav")
    anchor_pcm = outputs[0][1]
    comparisons: list[dict[str, Any]] = []
    variants = []
    for order, (_, pcm, generation) in enumerate(outputs, start=1):
        output_file = f"{order}0-generation-{order}.wav"
        output_path = staging / output_file
        renderer.write_wav(output_path, pcm)
        comparison = (
            {
                "correlation_to_generation_1": 1.0,
                "max_abs_difference": 0.0,
                "rms_difference": 0.0,
                "snr_db_to_generation_1": None,
            }
            if order == 1
            else signal_comparison(anchor_pcm, pcm)
        )
        comparisons.append(
            {
                "generation_id": order,
                "output_sha256": session.sha256_file(output_path),
                **comparison,
            }
        )
        variants.append(
            {
                "variant_id": f"rvc-repeat-generation-{order}",
                "display_name": f"RVC clean-bright / same session generation {order}",
                "display_order": order,
                "output_file": output_file,
                "output_sha256": "sha256:" + session.sha256_file(output_path),
                "status": "passed",
                "profile_id": profile_id,
                "operator_judgment": "unreviewed",
                "generation": generation,
            }
        )
    (staging / "index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "title": "RVC same-input repeat turn diagnostic",
                "run_kind": "MS-3 persistent-session RVC state diagnostic",
                "status": "completed-listen-now-unselected",
                "source_file": f"Hadou public heldout / {SOURCE_ID}",
                "source_text": source["display_text"],
                "source_id": SOURCE_ID,
                "source_output_file": "00-source.wav",
                "comparison_scope": {
                    "single_changed_variable": "generation position in one session",
                    "machine_selection_allowed": False,
                    "question": (
                        "Does RVC output drift across repeated conversation turns?"
                    ),
                },
                "variants": variants,
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
        "kind": "liveconv-ms3-rvc-repeat-turn-result",
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "profile_id": profile_id,
        "source_id": SOURCE_ID,
        "repeat_count": REPEAT_COUNT,
        "comparisons": comparisons,
        "claims": {"perceptual_winner": False, "product_selected": False},
    }
    (arguments.work_dir / "repeat-turn-result.json").write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    )
    return result


async def run(arguments: argparse.Namespace) -> int:
    validate_scope(arguments.profile_id)
    session = _load_session_runner()
    heldout = session._load_heldout_runner()  # noqa: SLF001
    if arguments.profile_id == PROFILE_ID:
        deployment, renderer = session.validate_inputs(arguments, heldout)
    else:
        deployment = arguments.deployment.resolve(strict=True)
        try:
            manifest = json.loads((deployment / "manifest.json").read_text())
            renderer_document = json.loads((deployment / "profiles.json").read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise RepeatTurnError("seeded deployment cannot be decoded") from error
        heldout._selected_records(  # noqa: SLF001
            manifest, "variants", (arguments.profile_id,)
        )
        heldout._selected_records(  # noqa: SLF001
            renderer_document, "profiles", (arguments.profile_id,)
        )
        source = next(
            item for item in heldout.SOURCES if item["source_id"] == SOURCE_ID
        )
        heldout._checked_file(  # noqa: SLF001
            source["path"], source["sha256"], SOURCE_ID
        )
        if arguments.work_dir.exists() or arguments.listener_dir.exists():
            raise RepeatTurnError("work and listener outputs must be new")
        if not os.environ.get("LIVECONV_API_TOKEN"):
            raise RepeatTurnError("LIVECONV_API_TOKEN is required")
        if not os.environ.get("LIVECONV_ALLOWED_ORIGINS"):
            raise RepeatTurnError("LIVECONV_ALLOWED_ORIGINS is required")
        renderer = heldout._load_renderer()  # noqa: SLF001
    if arguments.check:
        print("ok   RVC same-input repeat CPU admission complete")
        return 0
    result = await execute(arguments, session, heldout, deployment, renderer)
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
    value.add_argument(
        "--profile-id",
        choices=(PROFILE_ID, SEEDED_PROFILE_ID),
        default=PROFILE_ID,
    )
    value.add_argument("--timeout-seconds", type=float, default=180.0)
    return value


def main() -> int:
    try:
        return asyncio.run(run(parser().parse_args()))
    except (OSError, RepeatTurnError, ValueError) as error:
        print(f"render_rvc_repeat_turn: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
