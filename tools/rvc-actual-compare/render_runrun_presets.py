#!/usr/bin/env python3
"""Render exact deployed RVC Runrun presets on the actual 8.17-second input."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ROUTE_RENDERER = (
    REPOSITORY_ROOT
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
EXPECTED_SOURCE_WAV_SHA256 = (
    "78b15cd5e9d25ee10d8cb27084c63275221d773a04b21d11e4e3ba2be8056da6"
)
EXPECTED_SOURCE_F32_SHA256 = (
    "b114aed49c79291b10caf30f9828e6efb0e191773aa2fe8ab77d786f7a83b5f2"
)
PROFILE_IDS = (
    "vc.rvc-v2.amitaro-runrun.v1",
    "vc.rvc-v2.amitaro-runrun-girl-soft.v1",
    "vc.rvc-v2.amitaro-runrun-girl-bright.v1",
    "vc.rvc-v2.amitaro-runrun-girl-high.v1",
    "vc.rvc-v2.amitaro-runrun-clean-bright.v1",
    "vc.rvc-v2.amitaro-sasayaki.v1",
)


class CompareError(RuntimeError):
    """The bounded actual-input preset comparison cannot continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def filter_deployment_document(
    document: Mapping[str, Any], filename: str
) -> dict[str, Any]:
    """Return only the six exact profiles while preserving sealed records."""

    field = "variants" if filename == "manifest.json" else "profiles"
    values = document.get(field)
    if not isinstance(values, list):
        raise CompareError(f"deployment {filename} has no {field}")
    selected = [
        dict(item)
        for item in values
        if isinstance(item, Mapping) and item.get("profile_id") in PROFILE_IDS
    ]
    identities = [str(item["profile_id"]) for item in selected]
    if len(selected) != len(PROFILE_IDS) or set(identities) != set(PROFILE_IDS):
        raise CompareError(f"deployment {filename} profile set drifted")
    return {**dict(document), field: selected}


def _load_renderer() -> ModuleType:
    if (
        ROUTE_RENDERER.is_symlink()
        or not ROUTE_RENDERER.is_file()
        or sha256_file(ROUTE_RENDERER) != EXPECTED_RENDERER_SHA256
    ):
        raise CompareError("the established Gateway route renderer drifted")
    specification = importlib.util.spec_from_file_location(
        "liveconv_rvc_actual_route_renderer", ROUTE_RENDERER
    )
    if specification is None or specification.loader is None:
        raise CompareError("the established Gateway route renderer cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _checked_file(path: Path, expected: str, label: str) -> Path:
    if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
        raise CompareError(f"{label} identity drifted")
    return path


def validate_inputs(arguments: argparse.Namespace) -> Path:
    deployment = arguments.deployment.resolve(strict=True)
    _checked_file(
        deployment / "manifest.json", EXPECTED_MANIFEST_SHA256, "deployment manifest"
    )
    _checked_file(
        deployment / "profiles.json", EXPECTED_PROFILES_SHA256, "deployment profiles"
    )
    _checked_file(arguments.source_wav, EXPECTED_SOURCE_WAV_SHA256, "actual source")
    _checked_file(arguments.source_f32, EXPECTED_SOURCE_F32_SHA256, "source PCM")
    if (
        arguments.source_original.is_symlink()
        or not arguments.source_original.is_file()
    ):
        raise CompareError("source provenance file is unavailable")
    if arguments.work_dir.exists() or arguments.listener_dir.exists():
        raise CompareError("work and listener outputs must be new")
    return deployment


def _filtered_reader(
    original: Callable[[Path], dict[str, Any]], deployment: Path
) -> Callable[[Path], dict[str, Any]]:
    def read(path: Path) -> dict[str, Any]:
        document = original(path)
        if path.parent.resolve() == deployment and path.name in {
            "manifest.json",
            "profiles.json",
        }:
            return filter_deployment_document(document, path.name)
        return document

    return read


async def run(arguments: argparse.Namespace) -> int:
    deployment = validate_inputs(arguments)
    if arguments.check:
        print(
            json.dumps(
                {
                    "status": "checked-no-gateway-session",
                    "deployment": deployment.name,
                    "profile_count": len(PROFILE_IDS),
                },
                sort_keys=True,
            )
        )
        return 0
    renderer = _load_renderer()
    renderer.read_json = _filtered_reader(renderer.read_json, deployment)
    arguments.work_dir.mkdir(parents=True)
    staging = arguments.work_dir / "listener-staging"
    render_arguments = argparse.Namespace(
        gateway_url=arguments.gateway_url,
        timeout_seconds=arguments.timeout_seconds,
        deployment=deployment,
        source_original=arguments.source_original,
        source_f32=arguments.source_f32,
        source_wav=arguments.source_wav,
        output_dir=staging,
    )
    await renderer.main_async(render_arguments)
    index_path = staging / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["run_kind"] = "EXP-020 actual-input RVC Runrun preset comparison"
    index["status"] = "completed-listen-now-unselected"
    index["source_file"] = "Native / actual ChatGPT-tab input (2026-08-11)"
    index["comparison_scope"] = {
        "question": "Which existing preset avoids gross content corruption?",
        "runrun_presets": 5,
        "sasayaki_cross_style_reference": 1,
        "machine_selection_allowed": False,
        "human_hearing_pending": True,
    }
    index.pop("post_ab_decision_tree", None)
    index.pop("stage_1_scope", None)
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = {
        "schema_version": 1,
        "kind": "liveconv-exp020-rvc-runrun-preset-listen-now-result",
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "source_sha256": EXPECTED_SOURCE_WAV_SHA256,
        "profile_ids": list(PROFILE_IDS),
        "output_sha256": {
            str(item["profile_id"]): str(item["output_sha256"])
            for item in index["variants"]
        },
        "claims": {
            "product_selected": False,
            "promoted": False,
            "perceptual_winner": False,
        },
    }
    (arguments.work_dir / "listen-now-result.json").write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    staging.rename(arguments.listener_dir)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--deployment", type=Path, required=True)
    value.add_argument("--source-original", type=Path, required=True)
    value.add_argument("--source-f32", type=Path, required=True)
    value.add_argument("--source-wav", type=Path, required=True)
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    value.add_argument("--gateway-url", default="http://127.0.0.1:8877")
    value.add_argument("--timeout-seconds", type=float, default=180.0)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return asyncio.run(run(parser().parse_args(argv)))
    except (CompareError, OSError, ValueError) as error:
        print(f"render_runrun_presets: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
