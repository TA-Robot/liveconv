#!/usr/bin/env python3
"""Render two deployed Sasayaki presets on three public heldout utterances."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
ROUTE_RENDERER = (
    ROOT
    / "artifacts/ms3/listening/20260811-044500-rvc-sasayaki-stage1-strict/render.py"
)
EXPECTED_RENDERER_SHA256 = (
    "febb93a2c32b46ea77532297bd954dfeb14973963a7fa8c3907a3a4280e2e4c2"
)
EXPECTED_MANIFEST_SHA256 = (
    "15ec4003e6bd0d04b77dc0758dea0cc178ad8c7a1d17956c87116f73eea79073"
)
EXPECTED_PROFILES_SHA256 = (
    "7b956a554ea39369b5cecd4e5886575e6a1032561197042ad0716ad7f2cfc83d"
)
PROFILE_IDS = (
    "vc.rvc-v2.amitaro-sasayaki.v1",
    "vc.rvc-v2.amitaro-sasayaki-clean-bright.v1",
)
XVC_PROFILE_IDS = ("vc.x-vc.amitaro-yofukashi-q34.v1",)
PROFILE_SETS = {
    "sasayaki": {
        "profile_ids": PROFILE_IDS,
        "title": "RVC Sasayaki heldout",
        "run_kind": "EXP-020 Sasayaki preset heldout generalization",
        "question": "Does clean-bright generalize beyond one actual input?",
        "single_changed_variable": "deployed Sasayaki preset",
        "result_kind": "liveconv-exp020-rvc-sasayaki-heldout-result",
    },
    "xvc-yofukashi-q34": {
        "profile_ids": XVC_PROFILE_IDS,
        "title": "X-VC Yofukashi Q034 heldout system route",
        "run_kind": "EXP-026 X-VC deployed heldout route control",
        "question": (
            "Does the surviving deployed X-VC profile preserve heldout content "
            "through the live Gateway route?"
        ),
        "single_changed_variable": "VC family and deployed route profile",
        "result_kind": "liveconv-exp026-xvc-heldout-route-result",
    },
}
SOURCES = (
    {
        "source_id": "EMOTION100_002",
        "display_text": "シュヴァイツァーは見習うべき人間です。",
        "path": ROOT
        / "artifacts/ms3/listening/exp026-human87-horizon-v1/01-EMOTION100_002"
        / "00-source-reference.wav",
        "sha256": "8f27065d5b2f66baeafea5e96653f87c57ce866ea42f4e19df82886078c5e536",
    },
    {
        "source_id": "EMOTION100_004",
        "display_text": "スティーヴはジェーンから手紙をもらった。",
        "path": ROOT
        / "artifacts/ms3/listening/exp026-human87-horizon-v1/02-EMOTION100_004"
        / "00-source-reference.wav",
        "sha256": "0a3828c54f83fb28f885d0d452beab029a38030f6429a32e6720e5bb4f4c9ab5",
    },
    {
        "source_id": "EMOTION100_017",
        "display_text": "あっベルが鳴ってる。",
        "path": ROOT
        / "artifacts/ms3/listening/exp026-human87-horizon-v1/03-EMOTION100_017"
        / "00-source-reference.wav",
        "sha256": "9fad53ec17379745bc7e56d9306a1ffa1fda1ee0dfdf077826792e6e8199d455",
    },
)


class HeldoutRenderError(RuntimeError):
    """The bounded heldout comparison cannot continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_renderer() -> ModuleType:
    if (
        ROUTE_RENDERER.is_symlink()
        or not ROUTE_RENDERER.is_file()
        or sha256_file(ROUTE_RENDERER) != EXPECTED_RENDERER_SHA256
    ):
        raise HeldoutRenderError("established Gateway route renderer drifted")
    specification = importlib.util.spec_from_file_location(
        "liveconv_rvc_heldout_route_renderer", ROUTE_RENDERER
    )
    if specification is None or specification.loader is None:
        raise HeldoutRenderError("established Gateway route renderer cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _checked_file(path: Path, expected: str, label: str) -> Path:
    if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
        raise HeldoutRenderError(f"{label} identity drifted")
    return path


def _selected_records(
    document: dict[str, Any],
    field: str,
    profile_ids: tuple[str, ...] = PROFILE_IDS,
) -> list[dict[str, Any]]:
    values = document.get(field)
    if not isinstance(values, list):
        raise HeldoutRenderError(f"deployment has no {field}")
    selected = [
        item
        for item in values
        if isinstance(item, dict) and item.get("profile_id") in profile_ids
    ]
    if {item.get("profile_id") for item in selected} != set(profile_ids):
        raise HeldoutRenderError(f"deployment {field} profile set drifted")
    return selected


def wav_to_f32le(source: Path, destination: Path) -> int:
    try:
        with wave.open(str(source), "rb") as stream:
            if (
                stream.getframerate(),
                stream.getnchannels(),
                stream.getsampwidth(),
                stream.getcomptype(),
            ) != (48_000, 1, 2, "NONE"):
                raise HeldoutRenderError("heldout source must be mono PCM16 at 48 kHz")
            frames = stream.getnframes()
            pcm = stream.readframes(frames)
            if stream.readframes(1):
                raise HeldoutRenderError("heldout source contains trailing PCM")
    except (OSError, wave.Error) as error:
        raise HeldoutRenderError("heldout source WAV cannot be decoded") from error
    if frames <= 0 or len(pcm) != frames * 2:
        raise HeldoutRenderError("heldout source WAV is empty or truncated")
    destination.write_bytes(
        b"".join(
            struct.pack("<f", sample / 32768.0)
            for (sample,) in struct.iter_unpack("<h", pcm)
        )
    )
    return frames


def validate_inputs(arguments: argparse.Namespace) -> tuple[Path, ModuleType]:
    profile_ids = PROFILE_SETS[arguments.profile_set]["profile_ids"]
    if not isinstance(profile_ids, tuple):
        raise HeldoutRenderError("profile set is malformed")
    deployment = arguments.deployment.resolve(strict=True)
    _checked_file(
        deployment / "manifest.json", EXPECTED_MANIFEST_SHA256, "deployment manifest"
    )
    _checked_file(
        deployment / "profiles.json", EXPECTED_PROFILES_SHA256, "deployment profiles"
    )
    manifest = json.loads((deployment / "manifest.json").read_text(encoding="utf-8"))
    profiles = json.loads((deployment / "profiles.json").read_text(encoding="utf-8"))
    _selected_records(manifest, "variants", profile_ids)
    _selected_records(profiles, "profiles", profile_ids)
    for source in SOURCES:
        _checked_file(source["path"], source["sha256"], source["source_id"])
    if arguments.work_dir.exists() or arguments.listener_dir.exists():
        raise HeldoutRenderError("work and listener outputs must be new")
    if not os.environ.get("LIVECONV_API_TOKEN"):
        raise HeldoutRenderError("LIVECONV_API_TOKEN is required")
    if not os.environ.get("LIVECONV_ALLOWED_ORIGINS"):
        raise HeldoutRenderError("LIVECONV_ALLOWED_ORIGINS is required")
    return deployment, _load_renderer()


async def execute(
    arguments: argparse.Namespace, deployment: Path, renderer: ModuleType
) -> dict[str, Any]:
    profile_set = PROFILE_SETS[arguments.profile_set]
    profile_ids = profile_set["profile_ids"]
    if not isinstance(profile_ids, tuple):
        raise HeldoutRenderError("profile set is malformed")
    arguments.work_dir.mkdir(parents=True)
    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    source_root = arguments.work_dir / "source-f32"
    source_root.mkdir()

    manifest = renderer.read_json(deployment / "manifest.json")
    profile_document = renderer.read_json(deployment / "profiles.json")
    variants = _selected_records(manifest, "variants", profile_ids)
    profiles = _selected_records(profile_document, "profiles", profile_ids)
    variants_by_id = {str(item["profile_id"]): item for item in variants}
    profiles_by_id = {str(item["profile_id"]): item for item in profiles}

    token = os.environ["LIVECONV_API_TOKEN"]
    origin = next(
        value.strip()
        for value in os.environ["LIVECONV_ALLOWED_ORIGINS"].split(",")
        if value.strip()
    )
    gateway_url = arguments.gateway_url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    row_state: dict[str, dict[str, Any]] = {}
    for order, source in enumerate(SOURCES, start=1):
        row_dir = staging / f"{order:02d}-{source['source_id']}"
        row_dir.mkdir()
        shutil.copyfile(source["path"], row_dir / "00-source.wav")
        f32 = source_root / f"{source['source_id']}.f32le"
        samples = wav_to_f32le(source["path"], f32)
        input_frames, reopened_samples, source_stats = renderer.source_frames(f32)
        if samples != reopened_samples:
            raise HeldoutRenderError("source PCM conversion frame count drifted")
        row_state[source["source_id"]] = {
            "directory": row_dir,
            "input_frames": input_frames,
            "samples": samples,
            "source_stats": source_stats,
            "variants": [],
        }

    async with httpx.AsyncClient(follow_redirects=False) as client:
        catalog_response = await client.get(
            f"{gateway_url}/v1/models",
            headers=headers,
            timeout=arguments.timeout_seconds,
        )
        if catalog_response.status_code != 200:
            raise HeldoutRenderError(
                f"Gateway catalog returned HTTP {catalog_response.status_code}"
            )
        advertised = {
            item.get("profile_id"): item
            for item in catalog_response.json().get("profiles", [])
            if isinstance(item, dict)
        }
        for profile_order, profile_id in enumerate(profile_ids, start=1):
            variant = variants_by_id[profile_id]
            sealed_profile = profiles_by_id[profile_id]
            current = advertised.get(profile_id)
            if not isinstance(current, dict):
                raise HeldoutRenderError(f"Gateway does not advertise {profile_id}")
            if (
                current.get("profile_hash") != variant.get("profile_hash")
                or current.get("configuration_hash")
                != variant.get("configuration_hash")
            ):
                raise HeldoutRenderError(f"Gateway identity differs for {profile_id}")
            profile = {
                **sealed_profile,
                "profile_hash": variant["profile_hash"],
                "configuration_hash": variant["configuration_hash"],
            }
            for source in SOURCES:
                state = row_state[source["source_id"]]
                print(f"rendering {profile_id} / {source['source_id']}", flush=True)
                started = time.monotonic()
                pcm, generation = await renderer.render_profile(
                    client,
                    gateway_url=gateway_url,
                    token=token,
                    origin=origin,
                    profile=profile,
                    input_frames=state["input_frames"],
                    timeout_seconds=arguments.timeout_seconds,
                )
                output_file = f"{profile_order}0-{profile_id}.wav"
                output_path = state["directory"] / output_file
                renderer.write_wav(output_path, pcm)
                state["variants"].append(
                    {
                        "variant_id": variant["variant_id"],
                        "profile_id": profile_id,
                        "family_id": variant["family_id"],
                        "display_name": variant["display_name"],
                        "display_order": profile_order,
                        "status": "passed",
                        "operator_judgment": "unreviewed",
                        "quality_status": "not_assessed",
                        "route_status": "listen_now_gateway",
                        "output_file": output_file,
                        "output_sha256": "sha256:" + sha256_file(output_path),
                        "wall_seconds": round(time.monotonic() - started, 3),
                        "generation": generation,
                    }
                )

    output_hashes: dict[str, dict[str, str]] = {}
    for source in SOURCES:
        state = row_state[source["source_id"]]
        index = {
            "schema_version": 1,
            "title": f"{profile_set['title']} / {source['source_id']}",
            "run_kind": profile_set["run_kind"],
            "status": "completed-listen-now-unselected",
            "source_file": f"Hadou public heldout / {source['source_id']}",
            "source_text": source["display_text"],
            "source_id": source["source_id"],
            "source_output_file": "00-source.wav",
            "source_sha256": "sha256:" + source["sha256"],
            "source_samples": state["samples"],
            "source_levels": state["source_stats"],
            "comparison_scope": {
                "question": profile_set["question"],
                "single_changed_variable": profile_set["single_changed_variable"],
                "human_hearing_pending": True,
                "machine_selection_allowed": False,
            },
            "variants": state["variants"],
        }
        (state["directory"] / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        output_hashes[source["source_id"]] = {
            item["profile_id"]: item["output_sha256"]
            for item in state["variants"]
        }

    result = {
        "schema_version": 1,
        "kind": profile_set["result_kind"],
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "profile_ids": list(profile_ids),
        "source_ids": [source["source_id"] for source in SOURCES],
        "output_sha256": output_hashes,
        "claims": {
            "product_selected": False,
            "perceptual_winner": False,
            "promoted": False,
        },
    }
    (arguments.work_dir / "listen-now-result.json").write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    staging.rename(arguments.listener_dir)
    return result


async def run(arguments: argparse.Namespace) -> int:
    deployment, renderer = validate_inputs(arguments)
    if arguments.check:
        print("ok   RVC Sasayaki heldout CPU admission complete")
        return 0
    result = await execute(arguments, deployment, renderer)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--execute", action="store_true")
    value.add_argument("--deployment", type=Path, required=True)
    value.add_argument(
        "--profile-set", choices=tuple(PROFILE_SETS), default="sasayaki"
    )
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    value.add_argument("--gateway-url", default="http://127.0.0.1:8877")
    value.add_argument("--timeout-seconds", type=float, default=180.0)
    return value


def main() -> int:
    arguments = parser().parse_args()
    try:
        if arguments.check == arguments.execute:
            raise HeldoutRenderError("choose exactly one of --check or --execute")
        return asyncio.run(run(arguments))
    except (HeldoutRenderError, OSError, ValueError) as error:
        print(f"render_sasayaki_heldout: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
