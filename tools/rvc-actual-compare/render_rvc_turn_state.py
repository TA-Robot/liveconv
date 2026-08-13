#!/usr/bin/env python3
"""Compare reset versus preserved RVC state at one natural turn boundary."""

from __future__ import annotations

import argparse
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

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SUPPORT_RUNNER = Path(__file__).with_name("render_rvc_zero_latent_noise.py")
PROFILE_ID = "vc.rvc-v2.amitaro-sasayaki-clean-bright-seed0.v1"
SOURCE_ID = "ACTUAL_CHATGPT_20260811_114251"
SOURCE_WAV_SHA256 = "78b15cd5e9d25ee10d8cb27084c63275221d773a04b21d11e4e3ba2be8056da6"
SOURCE_F32_SHA256 = "b114aed49c79291b10caf30f9828e6efb0e191773aa2fe8ab77d786f7a83b5f2"
GATEWAY_TWO_TURN_SHA256 = (
    "e79cc12e00f9a2fa95a8c32bdab8f649aea9d7dbd1e7268a9e876c928c000598"
)
SOURCE_REVISION = "81eed5e8f68b6bed1789f682fe78cdd324495afc"
SPLIT_FRAME = 212
FRAME_SAMPLES = 960
EXPECTED_SAMPLES = 409 * FRAME_SAMPLES
SAMPLE_RATE = 48_000


class TurnStateError(RuntimeError):
    """The bounded RVC generation-state comparison cannot continue."""


def load_support() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "liveconv_rvc_turn_state_support", SUPPORT_RUNNER
    )
    if specification is None or specification.loader is None:
        raise TurnStateError("zero-latent support runner cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def convert_turns(
    backend: Any,
    first: np.ndarray,
    second: np.ndarray,
    *,
    preserve_state: bool,
) -> tuple[np.ndarray, np.ndarray]:
    backend.reset()
    first_output = np.asarray(backend.convert(first.tolist(), SAMPLE_RATE), dtype="<f4")
    if not preserve_state:
        backend.reset()
    second_output = np.asarray(
        backend.convert(second.tolist(), SAMPLE_RATE), dtype="<f4"
    )
    return first_output, second_output


def internal_render(arguments: argparse.Namespace) -> int:
    source_root = arguments.internal_source_root.absolute()
    os.environ["LIVECONV_RVC_SOURCE_ROOT"] = str(source_root)
    os.environ["LIVECONV_RVC_SOURCE_REVISION"] = SOURCE_REVISION
    from workers.adapters.rvc_v2.backend import RvcConfiguration, UpstreamRvcBackend
    from workers.adapters.rvc_v2.network_isolation import deny_non_unix_sockets

    samples = np.fromfile(arguments.internal_source_f32, dtype="<f4")
    if samples.size > EXPECTED_SAMPLES or not np.isfinite(samples).all():
        raise TurnStateError("exact source PCM is invalid")
    samples = np.pad(samples, (0, EXPECTED_SAMPLES - samples.size))
    split_sample = SPLIT_FRAME * FRAME_SAMPLES
    first, second = samples[:split_sample], samples[split_sample:]
    configuration = RvcConfiguration.from_environment()
    deny_non_unix_sockets()
    backend = UpstreamRvcBackend(configuration)
    try:
        outputs = convert_turns(
            backend,
            first,
            second,
            preserve_state=arguments.internal_preserve_state,
        )
    finally:
        backend.close()
    if (
        outputs[0].size != first.size
        or outputs[1].size != second.size
        or not all(np.isfinite(output).all() for output in outputs)
    ):
        raise TurnStateError("direct turn output is invalid")
    arguments.internal_output.write_bytes(
        outputs[0].astype("<f4").tobytes() + outputs[1].astype("<f4").tobytes()
    )
    return 0


def validate(
    arguments: argparse.Namespace, support: ModuleType
) -> tuple[dict[str, Any], dict[str, str]]:
    support.checked_file(arguments.source_wav, SOURCE_WAV_SHA256, "listening source")
    support.checked_file(arguments.source_f32, SOURCE_F32_SHA256, "original float PCM")
    support.checked_file(
        arguments.gateway_two_turn_wav,
        GATEWAY_TWO_TURN_SHA256,
        "Gateway two-turn baseline",
    )
    source_root = arguments.source_root.resolve(strict=True)
    if support.git_revision(
        source_root
    ) != SOURCE_REVISION or not support.tracked_tree_clean(
        source_root, SOURCE_REVISION
    ):
        raise TurnStateError("baseline source identity drifted")
    if arguments.work_dir.exists() or arguments.listener_dir.exists():
        raise TurnStateError("work and listener outputs must be new")
    profiles = json.loads(
        (arguments.deployment.resolve(strict=True) / "profiles.json").read_text()
    )
    records = [
        item
        for item in profiles.get("profiles", [])
        if isinstance(item, dict) and item.get("profile_id") == PROFILE_ID
    ]
    if len(records) != 1:
        raise TurnStateError("stable RVC profile is unavailable")
    parent = support.read_process_environment(arguments.gateway_pid)
    return records[0], support.profile_environment(records[0], parent)


def execute(
    arguments: argparse.Namespace,
    profile: dict[str, Any],
    environment: dict[str, str],
    support: ModuleType,
) -> dict[str, Any]:
    runtime = profile.get("runtime")
    endpoint = runtime.get("worker_endpoint") if isinstance(runtime, dict) else None
    if not isinstance(endpoint, str):
        raise TurnStateError("stable RVC worker endpoint is unavailable")
    worker_python = Path(endpoint).absolute()
    if not worker_python.is_file():
        raise TurnStateError("stable RVC worker Python is unavailable")
    arguments.work_dir.mkdir(parents=True)
    outputs: dict[str, Path] = {}
    durations: dict[str, float] = {}
    for label, preserve in (("reset", False), ("preserve_state", True)):
        output = arguments.work_dir / f"{label}.f32le"
        command = [
            str(worker_python),
            str(Path(__file__).resolve()),
            "--internal-render",
            "--internal-source-f32",
            str(arguments.source_f32.resolve()),
            "--internal-output",
            str(output.resolve()),
            "--internal-source-root",
            str(arguments.source_root.resolve()),
        ]
        if preserve:
            command.append("--internal-preserve-state")
        started = time.perf_counter()
        subprocess.run(command, env={**os.environ, **environment}, check=True)
        durations[label] = round(time.perf_counter() - started, 3)
        outputs[label] = output
    reset_pcm = outputs["reset"].read_bytes()
    preserve_pcm = outputs["preserve_state"].read_bytes()
    gateway_pcm = support.decode_wav(arguments.gateway_two_turn_wav)
    expected_bytes = EXPECTED_SAMPLES * 4
    if any(
        len(item) != expected_bytes for item in (reset_pcm, preserve_pcm, gateway_pcm)
    ):
        raise TurnStateError("comparison PCM length drifted")

    staging = arguments.listener_dir.with_name(
        f".{arguments.listener_dir.name}.staging"
    )
    if staging.exists():
        raise TurnStateError("listener staging output must be new")
    staging.mkdir()
    shutil.copyfile(arguments.source_wav, staging / "00-source.wav")
    shutil.copyfile(
        arguments.gateway_two_turn_wav, staging / "10-gateway-reset-baseline.wav"
    )
    support.write_wav(staging / "20-direct-reset.wav", reset_pcm)
    support.write_wav(staging / "30-direct-preserve-state.wav", preserve_pcm)
    variants = [
        {
            "variant_id": "gateway-reset-baseline",
            "display_name": "Stable seed-0 RVC / Gateway reset at turn 2",
            "display_order": 1,
            "output_file": "10-gateway-reset-baseline.wav",
            "output_sha256": "sha256:" + GATEWAY_TWO_TURN_SHA256,
            "status": "passed",
            "operator_judgment": "unreviewed",
            "reused_by_exact_hash": True,
        },
        {
            "variant_id": "direct-reset",
            "display_name": "Stable seed-0 RVC / direct reset at turn 2",
            "display_order": 2,
            "output_file": "20-direct-reset.wav",
            "output_sha256": "sha256:"
            + support.sha256_file(staging / "20-direct-reset.wav"),
            "status": "passed",
            "operator_judgment": "unreviewed",
        },
        {
            "variant_id": "direct-preserve-state",
            "display_name": "Stable seed-0 RVC / preserve state at turn 2",
            "display_order": 3,
            "output_file": "30-direct-preserve-state.wav",
            "output_sha256": "sha256:"
            + support.sha256_file(staging / "30-direct-preserve-state.wav"),
            "status": "passed",
            "operator_judgment": "unreviewed",
        },
    ]
    comparisons = {
        "gateway_vs_direct_reset": support.signal_comparison(gateway_pcm, reset_pcm),
        "direct_reset_vs_preserve_state": support.signal_comparison(
            reset_pcm, preserve_pcm
        ),
    }
    index = {
        "schema_version": 1,
        "title": "RVC natural turn boundary: reset vs preserve state",
        "run_kind": "MS-3 isolated RVC generation-state root-cause control",
        "status": "completed-listen-now-unselected",
        "source_id": SOURCE_ID,
        "source_file": "Native / actual ChatGPT-tab input (2026-08-11)",
        "source_output_file": "00-source.wav",
        "comparison_scope": {
            "changed_variable": "backend reset before turn 2",
            "fixed": ["input", "split", "checkpoint", "seed", "RVC settings"],
            "machine_selection_allowed": False,
            "question": "Does preserving RVC state recover turn-2 content?",
        },
        "turn_boundary": {"split_frame": SPLIT_FRAME, "split_seconds": 4.24},
        "runtime": {
            "source_revision": SOURCE_REVISION,
            "durations_seconds": durations,
            "signal_comparisons": comparisons,
        },
        "variants": variants,
    }
    (staging / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    staging.rename(arguments.listener_dir)
    result = {
        "schema_version": 1,
        "kind": "liveconv-ms3-rvc-turn-state-result",
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "durations_seconds": durations,
        "signal_comparisons": comparisons,
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


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    mode = value.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    value.add_argument("--deployment", type=Path, required=True)
    value.add_argument("--gateway-pid", type=int, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--source-wav", type=Path, required=True)
    value.add_argument("--source-f32", type=Path, required=True)
    value.add_argument("--gateway-two-turn-wav", type=Path, required=True)
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    return value


def internal_parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(add_help=False)
    value.add_argument("--internal-render", action="store_true")
    value.add_argument("--internal-source-f32", type=Path, required=True)
    value.add_argument("--internal-output", type=Path, required=True)
    value.add_argument("--internal-source-root", type=Path, required=True)
    value.add_argument("--internal-preserve-state", action="store_true")
    return value


def main() -> int:
    try:
        if "--internal-render" in sys.argv:
            return internal_render(internal_parser().parse_args())
        arguments = parser().parse_args()
        support = load_support()
        profile, environment = validate(arguments, support)
        if arguments.check:
            print("ok   RVC turn-state CPU admission complete")
            return 0
        execute(arguments, profile, environment, support)
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as error:
        print(f"render_rvc_turn_state: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
