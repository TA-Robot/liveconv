#!/usr/bin/env python3
"""Repeat one public utterance with an explicitly seeded direct RVC backend."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
from liveconv_audio._adapter_registry import _rvc_environment
from liveconv_audio.profiles import ModelProfile

from workers.adapters.rvc_v2.backend import RvcConfiguration, UpstreamRvcBackend

ROOT = Path(__file__).resolve().parents[2]
HELDOUT_RUNNER = Path(__file__).with_name("render_sasayaki_heldout.py")
PROFILE_ID = "vc.rvc-v2.amitaro-sasayaki-clean-bright.v1"
SOURCE_ID = "EMOTION100_017"
REPEAT_COUNT = 3
SAMPLE_RATE = 48_000


class SeedRepeatError(RuntimeError):
    """The bounded seeded RVC diagnostic cannot continue."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_heldout() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "liveconv_rvc_seed_repeat_heldout", HELDOUT_RUNNER
    )
    if specification is None or specification.loader is None:
        raise SeedRepeatError("heldout runner cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def read_process_environment(pid: int) -> dict[str, str]:
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    result: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        name, value = item.split(b"=", 1)
        result[name.decode("utf-8")] = value.decode("utf-8")
    return result


def read_identity_environment(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("unset "):
            continue
        assignment = line.removeprefix("export ")
        name, separator, encoded = assignment.partition("=")
        decoded = shlex.split(encoded, posix=True) if separator else []
        if (
            not name.startswith("LIVECONV_")
            or len(decoded) != 1
            or "$" in encoded
            or "`" in encoded
        ):
            raise SeedRepeatError(
                f"identity environment line {line_number} is invalid"
            )
        result[name] = decoded[0]
    return result


def profile_environment(
    profile: ModelProfile, parent_environment: dict[str, str], seed: int
) -> dict[str, str]:
    previous = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(parent_environment)
        environment, _ = _rvc_environment(profile, profile.runtime.configuration)
    finally:
        os.environ.clear()
        os.environ.update(previous)
    environment["LIVECONV_RVC_V2_INFERENCE_SEED"] = str(seed)
    return environment


def signal_comparison(anchor: bytes, candidate: bytes) -> dict[str, float | bool]:
    left = np.frombuffer(anchor, dtype="<f4").astype(np.float64)
    right = np.frombuffer(candidate, dtype="<f4").astype(np.float64)
    if left.shape != right.shape or not left.size:
        raise SeedRepeatError("seeded outputs are not shape-compatible")
    difference = left - right
    difference_rms = float(np.sqrt(np.mean(difference * difference)))
    return {
        "exact": anchor == candidate,
        "correlation_to_repeat_1": float(np.corrcoef(left, right)[0, 1]),
        "max_abs_difference": float(np.max(np.abs(difference))),
        "rms_difference": difference_rms,
    }


def write_wav(path: Path, pcm: bytes) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "f32le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-i",
            "pipe:0",
            "-c:a",
            "pcm_s24le",
            str(path),
        ],
        input=pcm,
        check=True,
    )


def execute(arguments: argparse.Namespace, heldout: ModuleType) -> dict[str, Any]:
    if arguments.work_dir.exists() or arguments.listener_dir.exists():
        raise SeedRepeatError("work and listener outputs must be new")
    document = json.loads((arguments.deployment / "profiles.json").read_text())
    records = [
        item
        for item in document.get("profiles", [])
        if isinstance(item, dict) and item.get("profile_id") == PROFILE_ID
    ]
    if len(records) != 1:
        raise SeedRepeatError("sealed RVC profile is unavailable")
    profile = ModelProfile.model_validate(records[0])
    source = next(item for item in heldout.SOURCES if item["source_id"] == SOURCE_ID)
    heldout._checked_file(source["path"], source["sha256"], SOURCE_ID)  # noqa: SLF001

    arguments.work_dir.mkdir(parents=True)
    source_f32 = arguments.work_dir / "source.f32le"
    heldout.wav_to_f32le(source["path"], source_f32)
    samples = np.fromfile(source_f32, dtype="<f4")
    if not samples.size or not np.isfinite(samples).all():
        raise SeedRepeatError("source PCM is invalid")

    parent_environment = (
        read_process_environment(arguments.gateway_pid)
        if arguments.gateway_pid is not None
        else read_identity_environment(arguments.identity_env)
    )
    environment = profile_environment(profile, parent_environment, arguments.seed)
    for name in (
        "LIVECONV_RVC_V2_INPUT_GAIN_DB",
        "LIVECONV_RVC_V2_INFERENCE_SEED",
    ):
        os.environ.pop(name, None)
    os.environ.update(environment)
    os.environ["RVC_CUDA_GRAPH"] = "1" if arguments.cuda_graph else "0"
    configuration = RvcConfiguration.from_environment()

    backend = UpstreamRvcBackend(configuration)
    outputs: list[bytes] = []
    durations: list[float] = []
    try:
        for _ in range(REPEAT_COUNT):
            backend.reset()
            started = time.perf_counter()
            converted = np.asarray(
                backend.convert(samples.tolist(), SAMPLE_RATE), dtype="<f4"
            )
            durations.append(time.perf_counter() - started)
            outputs.append(converted.tobytes())
    finally:
        backend.close()

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    shutil.copyfile(source["path"], staging / "00-source.wav")
    variants: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    for repeat, pcm in enumerate(outputs, start=1):
        filename = f"{repeat}0-seeded-repeat-{repeat}.wav"
        write_wav(staging / filename, pcm)
        comparison = (
            {
                "exact": True,
                "correlation_to_repeat_1": 1.0,
                "max_abs_difference": 0.0,
                "rms_difference": 0.0,
            }
            if repeat == 1
            else signal_comparison(outputs[0], pcm)
        )
        comparisons.append(
            {
                "repeat": repeat,
                "pcm_sha256": sha256_bytes(pcm),
                "wall_seconds": round(durations[repeat - 1], 3),
                **comparison,
            }
        )
        variants.append(
            {
                "variant_id": f"rvc-seed-{arguments.seed}-repeat-{repeat}",
                "display_name": f"RVC seed {arguments.seed} / repeat {repeat}",
                "display_order": repeat,
                "output_file": filename,
                "output_sha256": "sha256:"
                + sha256_bytes((staging / filename).read_bytes()),
                "status": "passed",
                "operator_judgment": "unreviewed",
                "parameters": {
                    "inference_seed": arguments.seed,
                    "cuda_graph": arguments.cuda_graph,
                },
            }
        )
    deterministic = all(item["exact"] for item in comparisons)
    (staging / "index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "title": "RVC explicit-seed repeat diagnostic",
                "run_kind": "MS-3 direct seeded RVC determinism diagnostic",
                "status": "completed-listen-now-unselected",
                "source_file": f"Hadou public heldout / {SOURCE_ID}",
                "source_text": source["display_text"],
                "source_output_file": "00-source.wav",
                "comparison_scope": {
                    "single_changed_variable": "explicit RVC inference seed",
                    "machine_selection_allowed": False,
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
        "kind": "liveconv-ms3-rvc-seeded-repeat-result",
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
        "inference_seed": arguments.seed,
        "cuda_graph": arguments.cuda_graph,
        "configuration_hash": configuration.configuration_hash,
        "deterministic": deterministic,
        "comparisons": comparisons,
        "claims": {"perceptual_winner": False, "product_selected": False},
    }
    (arguments.work_dir / "seed-repeat-result.json").write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    )
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    mode = value.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    value.add_argument("--deployment", type=Path, required=True)
    environment = value.add_mutually_exclusive_group(required=True)
    environment.add_argument("--gateway-pid", type=int)
    environment.add_argument("--identity-env", type=Path)
    value.add_argument("--seed", type=int, default=34)
    value.add_argument(
        "--cuda-graph", action=argparse.BooleanOptionalAction, default=True
    )
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    return value


def main() -> int:
    arguments = parser().parse_args()
    try:
        heldout = _load_heldout()
        if not 0 <= arguments.seed < 2**63:
            raise SeedRepeatError("seed is outside the supported range")
        if arguments.check:
            print("ok   seeded RVC direct diagnostic CPU admission complete")
            return 0
        result = execute(arguments, heldout)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    except (OSError, SeedRepeatError, subprocess.SubprocessError, ValueError) as error:
        print(f"render_rvc_seed_repeat: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
