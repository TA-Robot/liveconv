#!/usr/bin/env python3
"""Render stable RVC and X-VC on three unused public validation utterances."""

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
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
REPEAT_RUNNER = Path(__file__).with_name("render_rvc_repeat_turn.py")
SOURCE_ROOT = ROOT / "artifacts/xvc-human-paired/source-audio/hadou-ita"
SOURCE_MANIFEST = ROOT / "artifacts/xvc-human-paired/runrun-human-paired.manifest.json"
SOURCE_MANIFEST_SHA256 = (
    "12e334fb3649fa57a90713a8fe3d036a59bbc7d5aa8971f4cdc4f785941b772b"
)
RVC_PROFILE_ID = "vc.rvc-v2.amitaro-sasayaki-clean-bright-seed0.v1"
XVC_PROFILE_ID = "vc.x-vc.amitaro-yofukashi-q34.v1"
PROFILE_SPECS = (
    {
        "profile_id": RVC_PROFILE_ID,
        "family_id": "rvc-v2",
        "display_name": "Stable seed-0 RVC",
        "output_file": "10-stable-rvc-seed0.wav",
        "gateway_argument": "rvc_gateway_url",
        "deployment_argument": "rvc_deployment",
    },
    {
        "profile_id": XVC_PROFILE_ID,
        "family_id": "x-vc",
        "display_name": "Stable X-VC Yofukashi Q034",
        "output_file": "20-stable-xvc-q34.wav",
        "gateway_argument": "xvc_gateway_url",
        "deployment_argument": "xvc_deployment",
    },
)
SOURCES = (
    {
        "source_id": "RECITATION324_049",
        "display_text": "社長からの指示です。",
        "relative_path": "audio/recitation/RECITATION324_049.wav",
        "sha256": "96d7584edb8cc91a9a5ab0a2201191b8d9de23c0f00cba7a1e7a2259d8077f0f",
        "duration_seconds": 3.009,
    },
    {
        "source_id": "RECITATION324_007",
        "display_text": "フランス人シェフと日本人シェフは全然違う。",
        "relative_path": "audio/recitation/RECITATION324_007.wav",
        "sha256": "6c9384482e69c04aa99d4517a094826c7ff19e62e3074505bcc86b4f8dcc1e32",
        "duration_seconds": 4.814,
    },
    {
        "source_id": "EMOTION100_027",
        "display_text": (
            "彼女はハンドバッグを開けて家の鍵を探してみたが、見つからなかった。"
        ),
        "relative_path": "audio/emotion/EMOTION100_027.wav",
        "sha256": "11c0b1b2fa4d1f604d979a66bafcd659137d2bb2b6f51a4c98a9e48eaeee6ee2",
        "duration_seconds": 7.294,
    },
)


class StableGeneralizationError(RuntimeError):
    """The bounded stable-profile generalization batch cannot continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_file(path: Path, expected: str, label: str) -> Path:
    resolved = path.resolve(strict=True)
    if resolved.is_symlink() or not resolved.is_file():
        raise StableGeneralizationError(f"{label} must be a regular file")
    if sha256_file(resolved) != expected:
        raise StableGeneralizationError(f"{label} identity drifted")
    return resolved


def listener_staging_path(listener_dir: Path) -> Path:
    return listener_dir.with_name(f".{listener_dir.name}.staging")


def load_repeat_runner() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "liveconv_stable_generalization_repeat", REPEAT_RUNNER
    )
    if specification is None or specification.loader is None:
        raise StableGeneralizationError("repeat runner cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def selected_profile(
    heldout: ModuleType, renderer: ModuleType, deployment: Path, profile_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = renderer.read_json(deployment / "manifest.json")
    profiles = renderer.read_json(deployment / "profiles.json")
    variant = heldout._selected_records(  # noqa: SLF001
        manifest, "variants", (profile_id,)
    )[0]
    sealed = heldout._selected_records(  # noqa: SLF001
        profiles, "profiles", (profile_id,)
    )[0]
    return variant, {
        **sealed,
        "profile_hash": variant["profile_hash"],
        "configuration_hash": variant["configuration_hash"],
    }


def validate_source_manifest() -> None:
    checked_file(SOURCE_MANIFEST, SOURCE_MANIFEST_SHA256, "source manifest")
    document = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    rows = {
        row.get("utterance_id"): row
        for row in document.get("rows", [])
        if isinstance(row, dict)
    }
    for source in SOURCES:
        source_id = source["source_id"]
        row = rows.get(source_id)
        if not isinstance(row, dict) or row.get("split") != "validation":
            raise StableGeneralizationError(f"{source_id} is not frozen validation")
        source_wav = row.get("source_wav")
        if not isinstance(source_wav, dict) or any(
            source_wav.get(field) != source[expected]
            for field, expected in (
                ("relative_path", "relative_path"),
                ("sha256", "sha256"),
                ("duration_seconds", "duration_seconds"),
            )
        ):
            raise StableGeneralizationError(f"{source_id} source metadata drifted")
        if row.get("display_text") != source["display_text"]:
            raise StableGeneralizationError(f"{source_id} text drifted")
        checked_file(
            SOURCE_ROOT / source["relative_path"], source["sha256"], source_id
        )


def validate(
    arguments: argparse.Namespace,
) -> tuple[ModuleType, ModuleType, ModuleType]:
    validate_source_manifest()
    repeat = load_repeat_runner()
    session = repeat._load_session_runner()  # noqa: SLF001
    heldout = session._load_heldout_runner()  # noqa: SLF001
    renderer = heldout._load_renderer()  # noqa: SLF001
    for spec in PROFILE_SPECS:
        deployment = getattr(arguments, spec["deployment_argument"]).resolve(
            strict=True
        )
        selected_profile(heldout, renderer, deployment, spec["profile_id"])
    staging = listener_staging_path(arguments.listener_dir)
    if (
        arguments.work_dir.exists()
        or arguments.listener_dir.exists()
        or staging.exists()
    ):
        raise StableGeneralizationError("work and listener outputs must be new")
    if not os.environ.get("LIVECONV_API_TOKEN"):
        raise StableGeneralizationError("LIVECONV_API_TOKEN is required")
    if not os.environ.get("LIVECONV_ALLOWED_ORIGINS"):
        raise StableGeneralizationError("LIVECONV_ALLOWED_ORIGINS is required")
    return session, heldout, renderer


async def render_profile(
    arguments: argparse.Namespace,
    *,
    spec: dict[str, str],
    heldout: ModuleType,
    renderer: ModuleType,
    row_state: dict[str, dict[str, Any]],
) -> None:
    profile_id = spec["profile_id"]
    deployment = getattr(arguments, spec["deployment_argument"]).resolve(strict=True)
    gateway_url = getattr(arguments, spec["gateway_argument"]).rstrip("/")
    variant, profile = selected_profile(heldout, renderer, deployment, profile_id)
    token = os.environ["LIVECONV_API_TOKEN"]
    origin = next(
        item.strip()
        for item in os.environ["LIVECONV_ALLOWED_ORIGINS"].split(",")
        if item.strip()
    )
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(follow_redirects=False) as client:
        catalog = await client.get(
            f"{gateway_url}/v1/models",
            headers=headers,
            timeout=arguments.timeout_seconds,
        )
        if catalog.status_code != 200:
            raise StableGeneralizationError(
                f"{profile_id} catalog returned HTTP {catalog.status_code}"
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
            raise StableGeneralizationError(
                f"Gateway identity differs for {profile_id}"
            )
        for source in SOURCES:
            source_id = source["source_id"]
            state = row_state[source_id]
            print(f"rendering {profile_id} / {source_id}", flush=True)
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
            output_path = state["directory"] / spec["output_file"]
            renderer.write_wav(output_path, pcm)
            state["variants"].append(
                {
                    "variant_id": variant["variant_id"],
                    "profile_id": profile_id,
                    "family_id": spec["family_id"],
                    "display_name": spec["display_name"],
                    "display_order": len(state["variants"]) + 1,
                    "output_file": output_path.name,
                    "output_sha256": "sha256:" + sha256_file(output_path),
                    "status": "passed",
                    "operator_judgment": "unreviewed",
                    "quality_status": "not_assessed",
                    "wall_seconds": round(time.monotonic() - started, 3),
                    "generation": generation,
                }
            )


async def execute(
    arguments: argparse.Namespace,
    *,
    heldout: ModuleType,
    renderer: ModuleType,
) -> dict[str, Any]:
    arguments.work_dir.mkdir(parents=True)
    source_f32_dir = arguments.work_dir / "source-f32"
    source_f32_dir.mkdir()
    staging = listener_staging_path(arguments.listener_dir)
    staging.mkdir()
    row_state: dict[str, dict[str, Any]] = {}
    for order, source in enumerate(SOURCES, start=1):
        source_id = source["source_id"]
        source_wav = SOURCE_ROOT / source["relative_path"]
        directory = staging / f"{order:02d}-{source_id}"
        directory.mkdir()
        shutil.copyfile(source_wav, directory / "00-source.wav")
        source_f32 = source_f32_dir / f"{source_id}.f32le"
        samples = heldout.wav_to_f32le(source_wav, source_f32)
        input_frames, reopened_samples, source_levels = renderer.source_frames(
            source_f32
        )
        if samples != reopened_samples:
            raise StableGeneralizationError("source PCM frame count drifted")
        row_state[source_id] = {
            "directory": directory,
            "input_frames": input_frames,
            "source_samples": samples,
            "source_levels": source_levels,
            "variants": [],
        }

    # One GPU lane: finish all RVC rows before the X-VC worker may start.
    for spec in PROFILE_SPECS:
        await render_profile(
            arguments,
            spec=spec,
            heldout=heldout,
            renderer=renderer,
            row_state=row_state,
        )

    output_hashes: dict[str, dict[str, str]] = {}
    for source in SOURCES:
        source_id = source["source_id"]
        state = row_state[source_id]
        index = {
            "schema_version": 1,
            "title": f"Stable VC validation / {source_id}",
            "run_kind": "MS-3 stable VC public-validation generalization",
            "status": "completed-listen-now-unselected",
            "source_file": f"Hadou public validation / {source_id}",
            "source_text": source["display_text"],
            "source_id": source_id,
            "source_output_file": "00-source.wav",
            "source_sha256": "sha256:" + source["sha256"],
            "source_samples": state["source_samples"],
            "source_levels": state["source_levels"],
            "source_provenance": {
                "dataset": "Hadou Voice Dataset",
                "speaker_credit": "Hadou",
                "manifest_sha256": "sha256:" + SOURCE_MANIFEST_SHA256,
                "split": "validation",
                "use": "local listen-now evaluation",
            },
            "comparison_scope": {
                "question": (
                    "Do both stable VC families produce hearable, content-intact "
                    "output beyond the original three heldout utterances?"
                ),
                "fixed": ["source bytes per row", "Gateway route", "stable profiles"],
                "human_hearing_pending": True,
                "machine_selection_allowed": False,
            },
            "variants": state["variants"],
        }
        (state["directory"] / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        output_hashes[source_id] = {
            item["profile_id"]: item["output_sha256"]
            for item in state["variants"]
        }

    staging.rename(arguments.listener_dir)
    result = {
        "schema_version": 1,
        "kind": "liveconv-ms3-stable-vc-generalization-result",
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "profile_ids": [spec["profile_id"] for spec in PROFILE_SPECS],
        "source_ids": [source["source_id"] for source in SOURCES],
        "output_sha256": output_hashes,
        "claims": {
            "perceptual_winner": False,
            "product_selected": False,
            "promoted": False,
        },
    }
    (arguments.work_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return result


async def run(arguments: argparse.Namespace) -> int:
    _session, heldout, renderer = validate(arguments)
    if arguments.check:
        print("ok   stable VC public-validation CPU admission complete")
        return 0
    await execute(arguments, heldout=heldout, renderer=renderer)
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    mode = value.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    value.add_argument("--rvc-deployment", type=Path, required=True)
    value.add_argument("--xvc-deployment", type=Path, required=True)
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    value.add_argument("--rvc-gateway-url", default="http://127.0.0.1:8881")
    value.add_argument("--xvc-gateway-url", default="http://127.0.0.1:8882")
    value.add_argument("--timeout-seconds", type=float, default=300.0)
    return value


def main() -> int:
    try:
        return asyncio.run(run(parser().parse_args()))
    except (
        json.JSONDecodeError,
        OSError,
        StableGeneralizationError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        print(f"render_stable_vc_generalization: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
