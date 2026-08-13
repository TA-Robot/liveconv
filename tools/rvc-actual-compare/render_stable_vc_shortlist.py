#!/usr/bin/env python3
"""Render the missing stable RVC rows and publish a deployable VC shortlist."""

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

ROOT = Path(__file__).resolve().parents[2]
REPEAT_RUNNER = Path(__file__).with_name("render_rvc_repeat_turn.py")
COMPOSE_RUNNER = Path(__file__).with_name("compose_vc_heldout_shortlist.py")
PROFILE_ID = "vc.rvc-v2.amitaro-sasayaki-clean-bright-seed0.v1"
GENERATED_SOURCE_IDS = ("EMOTION100_002", "EMOTION100_004")
REUSED_SOURCE_ID = "EMOTION100_017"
REUSED_RVC_WAV = (
    ROOT
    / "artifacts/ms3/listening/ms3-rvc-seed0-gateway-repeat-v2"
    / "10-generation-1.wav"
)
REUSED_RVC_SHA256 = (
    "7f2d1aa5465392a01d3bc5d8edb0df69484b46dbcdaede8ef7bf03483b2f3451"
)


class StableShortlistError(RuntimeError):
    """The bounded stable-profile shortlist cannot continue."""


def _load_module(name: str, path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise StableShortlistError(f"{path.name} cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _xvc_arm(compose: ModuleType) -> dict[str, Any]:
    arms = [arm for arm in compose.ARMS if arm["family_id"] == "x-vc"]
    if len(arms) != 1:
        raise StableShortlistError("the surviving X-VC arm drifted")
    return arms[0]


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[ModuleType, ModuleType, ModuleType, ModuleType, Path]:
    repeat = _load_module("liveconv_stable_shortlist_repeat", REPEAT_RUNNER)
    session = repeat._load_session_runner()  # noqa: SLF001
    heldout = session._load_heldout_runner()  # noqa: SLF001
    compose = _load_module("liveconv_stable_shortlist_compose", COMPOSE_RUNNER)
    deployment = arguments.deployment.resolve(strict=True)
    try:
        manifest = json.loads((deployment / "manifest.json").read_text())
        profiles = json.loads((deployment / "profiles.json").read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise StableShortlistError("seeded deployment cannot be decoded") from error
    heldout._selected_records(manifest, "variants", (PROFILE_ID,))  # noqa: SLF001
    heldout._selected_records(profiles, "profiles", (PROFILE_ID,))  # noqa: SLF001

    source_by_id = {item["source_id"]: item for item in heldout.SOURCES}
    if set(source_by_id) != {
        *GENERATED_SOURCE_IDS,
        REUSED_SOURCE_ID,
    }:
        raise StableShortlistError("heldout source set drifted")
    for source_id, source in source_by_id.items():
        heldout._checked_file(  # noqa: SLF001
            source["path"], source["sha256"], source_id
        )
    compose.checked_file(
        REUSED_RVC_WAV, REUSED_RVC_SHA256, "reused stable RVC row"
    )
    xvc = _xvc_arm(compose)
    listening = ROOT / "artifacts/ms3/listening"
    for row in compose.ROWS:
        source_id = row["source_id"]
        xvc_path = (
            listening
            / xvc["collection"]
            / row["directory"]
            / xvc["input_file"]
        )
        compose.checked_file(
            xvc_path, xvc["hashes"][source_id], f"{source_id} X-VC control"
        )
    if arguments.work_dir.exists() or arguments.listener_dir.exists():
        raise StableShortlistError("work and listener outputs must be new")
    return repeat, session, heldout, compose, deployment


async def execute(
    arguments: argparse.Namespace,
    *,
    session: ModuleType,
    heldout: ModuleType,
    compose: ModuleType,
    deployment: Path,
) -> dict[str, Any]:
    token = os.environ.get("LIVECONV_API_TOKEN", "")
    origins = [
        value.strip()
        for value in os.environ.get("LIVECONV_ALLOWED_ORIGINS", "").split(",")
        if value.strip()
    ]
    if not token or not origins:
        raise StableShortlistError("Gateway token and origin are required")
    renderer = heldout._load_renderer()  # noqa: SLF001
    arguments.work_dir.mkdir(parents=True)
    source_f32_dir = arguments.work_dir / "source-f32"
    source_f32_dir.mkdir()
    source_by_id = {item["source_id"]: item for item in heldout.SOURCES}
    turns: list[tuple[str, list[bytes]]] = []
    for source_id in GENERATED_SOURCE_IDS:
        source_f32 = source_f32_dir / f"{source_id}.f32le"
        heldout.wav_to_f32le(source_by_id[source_id]["path"], source_f32)
        frames, _, _ = renderer.source_frames(source_f32)
        turns.append((source_id, frames))

    manifest = renderer.read_json(deployment / "manifest.json")
    profile_document = renderer.read_json(deployment / "profiles.json")
    variant = heldout._selected_records(  # noqa: SLF001
        manifest, "variants", (PROFILE_ID,)
    )[0]
    sealed_profile = heldout._selected_records(  # noqa: SLF001
        profile_document, "profiles", (PROFILE_ID,)
    )[0]
    profile = {
        **sealed_profile,
        "profile_hash": variant["profile_hash"],
        "configuration_hash": variant["configuration_hash"],
    }
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
            raise StableShortlistError("Gateway stable RVC identity differs")
        outputs = await session.render_profile_turns(
            client,
            renderer=renderer,
            gateway_url=gateway_url,
            token=token,
            origin=origins[0],
            profile=profile,
            turns=turns,
            timeout=arguments.timeout_seconds,
            route_parity_qualification=True,
        )
    output_by_id = {
        source_id: (pcm, generation)
        for source_id, pcm, generation in outputs
    }
    if set(output_by_id) != set(GENERATED_SOURCE_IDS):
        raise StableShortlistError("stable RVC output set drifted")

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    xvc = _xvc_arm(compose)
    listening = ROOT / "artifacts/ms3/listening"
    rvc_hashes: dict[str, str] = {}
    generations: dict[str, dict[str, Any]] = {}
    try:
        for row in compose.ROWS:
            source_id = row["source_id"]
            destination = staging / row["directory"]
            destination.mkdir()
            shutil.copyfile(
                source_by_id[source_id]["path"], destination / "00-source.wav"
            )
            rvc_output = destination / "10-rvc-seed0-clean-bright.wav"
            if source_id == REUSED_SOURCE_ID:
                shutil.copyfile(REUSED_RVC_WAV, rvc_output)
            else:
                pcm, generation = output_by_id[source_id]
                renderer.write_wav(rvc_output, pcm)
                generations[source_id] = generation
            rvc_sha256 = session.sha256_file(rvc_output)
            rvc_hashes[source_id] = rvc_sha256

            xvc_source = (
                listening
                / xvc["collection"]
                / row["directory"]
                / xvc["input_file"]
            )
            xvc_output = destination / "20-xvc-yofukashi-q34.wav"
            shutil.copyfile(xvc_source, xvc_output)
            index = {
                "schema_version": 1,
                "title": f"Stable VC heldout shortlist / {source_id}",
                "run_kind": "MS-3 deployable-profile two-family hearing shortlist",
                "status": "completed-listen-now-unselected",
                "source_file": f"Hadou public heldout / {source_id}",
                "source_text": row["text"],
                "source_id": source_id,
                "source_output_file": "00-source.wav",
                "source_sha256": "sha256:" + row["source_sha256"],
                "comparison_scope": {
                    "human_hearing_pending": True,
                    "machine_selection_allowed": False,
                    "question": (
                        "Which stable live route sounds clearer and more natural?"
                    ),
                    "note": (
                        "The RVC arm fixes generation RNG at seed 0; auxiliary "
                        "content screening cannot rank perceptual quality."
                    ),
                },
                "variants": [
                    {
                        "variant_id": "rvc-seed0-sasayaki-clean-bright",
                        "profile_id": PROFILE_ID,
                        "family_id": "rvc-v2",
                        "display_name": "Stable RVC seed 0 / live Gateway",
                        "display_order": 1,
                        "output_file": rvc_output.name,
                        "output_sha256": "sha256:" + rvc_sha256,
                        "status": "passed",
                        "operator_judgment": "unreviewed",
                    },
                    {
                        "variant_id": xvc["arm_id"],
                        "profile_id": xvc["profile_id"],
                        "family_id": xvc["family_id"],
                        "display_name": xvc["display_name"],
                        "display_order": 2,
                        "output_file": xvc_output.name,
                        "output_sha256": "sha256:" + xvc["hashes"][source_id],
                        "status": "passed",
                        "operator_judgment": "unreviewed",
                    },
                ],
            }
            (destination / "index.json").write_text(
                json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
        result = {
            "schema_version": 1,
            "kind": "liveconv-ms3-stable-vc-heldout-shortlist-result",
            "status": "completed-listen-now-unselected",
            "git_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "source_ids": [row["source_id"] for row in compose.ROWS],
            "generated_source_ids": list(GENERATED_SOURCE_IDS),
            "reused_source_ids": [REUSED_SOURCE_ID],
            "rvc_output_sha256": rvc_hashes,
            "generated_rvc_generations": generations,
            "claims": {"perceptual_winner": False, "product_selected": False},
        }
        (staging / "shortlist-result.json").write_text(
            json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        )
        staging.rename(arguments.listener_dir)
        return result
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


async def run(arguments: argparse.Namespace) -> int:
    _repeat, session, heldout, compose, deployment = validate_inputs(arguments)
    if arguments.check:
        print("ok   stable RVC plus retained X-VC shortlist inputs")
        return 0
    result = await execute(
        arguments,
        session=session,
        heldout=heldout,
        compose=compose,
        deployment=deployment,
    )
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
    value.add_argument("--gateway-url", default="http://127.0.0.1:8881")
    value.add_argument("--timeout-seconds", type=float, default=180.0)
    return value


def main() -> int:
    try:
        return asyncio.run(run(parser().parse_args()))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"render_stable_vc_shortlist: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
