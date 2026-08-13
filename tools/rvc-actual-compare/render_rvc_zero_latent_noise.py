#!/usr/bin/env python3
"""Compare standard and zero-latent-noise RVC on exact actual input."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PROFILE_ID = "vc.rvc-v2.amitaro-sasayaki-clean-bright-seed0.v1"
SOURCE_ID = "ACTUAL_CHATGPT_20260811_114251"
SOURCE_WAV_SHA256 = "78b15cd5e9d25ee10d8cb27084c63275221d773a04b21d11e4e3ba2be8056da6"
SOURCE_F32_SHA256 = "b114aed49c79291b10caf30f9828e6efb0e191773aa2fe8ab77d786f7a83b5f2"
GATEWAY_BASELINE_SHA256 = (
    "e00b7f6ec53e838ee3b7cd77d1c6af3035ff3a8e49b724c674631f53cc56e13f"
)
BASELINE_SOURCE_REVISION = "81eed5e8f68b6bed1789f682fe78cdd324495afc"
ZERO_SOURCE_REVISION = "9b61903ba20399600a6fa16892ffdcbc69070a34"
EXPECTED_SAMPLES = 409 * 960
SAMPLE_RATE = 48_000


class ZeroLatentNoiseError(RuntimeError):
    """The isolated zero-latent-noise comparison cannot continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_file(path: Path, expected: str, label: str) -> Path:
    resolved = path.resolve(strict=True)
    if resolved.is_symlink() or sha256_file(resolved) != expected:
        raise ZeroLatentNoiseError(f"{label} identity drifted")
    return resolved


def git_revision(path: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def tracked_tree_clean(path: Path, revision: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(path), "diff", "--quiet", revision, "--"],
            check=False,
        ).returncode
        == 0
    )


def read_process_environment(pid: int) -> dict[str, str]:
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    result: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        name, value = item.split(b"=", 1)
        result[name.decode()] = value.decode()
    return result


def profile_environment(
    profile: dict[str, Any], parent: dict[str, str]
) -> dict[str, str]:
    runtime = profile.get("runtime")
    configuration = runtime.get("configuration") if isinstance(runtime, dict) else None
    settings = (
        configuration.get("settings") if isinstance(configuration, dict) else None
    )
    if profile.get("profile_id") != PROFILE_ID or not isinstance(settings, dict):
        raise ZeroLatentNoiseError("sealed stable RVC profile is invalid")
    suffix = (
        "".join(character if character.isalnum() else "_" for character in PROFILE_ID)
        .strip("_")
        .upper()
    )
    prefix = f"LIVECONV_RVC_VARIANT_{suffix}"
    names = {
        "LIVECONV_RVC_V2_WORKER_WHEEL_PATH": "LIVECONV_RVC_V2_WORKER_WHEEL_PATH",
        "LIVECONV_RVC_V2_WORKER_WHEEL_SHA256": ("LIVECONV_RVC_V2_WORKER_WHEEL_SHA256"),
        "LIVECONV_RVC_V2_CHECKPOINT_PATH": f"{prefix}_CHECKPOINT_PATH",
        "LIVECONV_RVC_V2_CHECKPOINT_SHA256": f"{prefix}_CHECKPOINT_SHA256",
        "LIVECONV_RVC_V2_INDEX_PATH": f"{prefix}_INDEX_PATH",
        "LIVECONV_RVC_V2_INDEX_SHA256": f"{prefix}_INDEX_SHA256",
    }
    environment: dict[str, str] = {}
    for output, source in names.items():
        value = parent.get(source)
        if not value:
            raise ZeroLatentNoiseError(f"Gateway environment is missing: {source}")
        environment[output] = value
    setting_names = {
        "speaker_id": "LIVECONV_RVC_V2_SPEAKER_ID",
        "pitch_shift": "LIVECONV_RVC_V2_PITCH_SHIFT",
        "f0_method": "LIVECONV_RVC_V2_F0_METHOD",
        "index_rate": "LIVECONV_RVC_V2_INDEX_RATE",
        "rms_mix_rate": "LIVECONV_RVC_V2_RMS_MIX_RATE",
        "sample_rate": "LIVECONV_RVC_V2_SAMPLE_RATE",
        "block_ms": "LIVECONV_RVC_V2_BLOCK_MS",
        "crossfade_ms": "LIVECONV_RVC_V2_CROSSFADE_MS",
        "context_ms": "LIVECONV_RVC_V2_CONTEXT_MS",
        "threshold_dbfs": "LIVECONV_RVC_V2_THRESHOLD_DBFS",
        "inference_seed": "LIVECONV_RVC_V2_INFERENCE_SEED",
    }
    for setting, output in setting_names.items():
        value = settings.get(setting)
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ZeroLatentNoiseError(f"stable RVC setting is invalid: {setting}")
        environment[output] = str(value)
    if "input_gain_db" in settings:
        environment["LIVECONV_RVC_V2_INPUT_GAIN_DB"] = str(settings["input_gain_db"])
    environment["RVC_CUDA_GRAPH"] = "1"
    return environment


def signal_comparison(anchor: bytes, candidate: bytes) -> dict[str, float | bool]:
    left = np.frombuffer(anchor, dtype="<f4").astype(np.float64)
    right = np.frombuffer(candidate, dtype="<f4").astype(np.float64)
    if left.shape != right.shape or not left.size:
        raise ZeroLatentNoiseError("direct outputs are not shape-compatible")
    difference = left - right
    difference_rms = float(np.sqrt(np.mean(difference**2)))
    anchor_rms = float(np.sqrt(np.mean(left**2)))
    return {
        "exact": anchor == candidate,
        "correlation": float(np.corrcoef(left, right)[0, 1]),
        "max_abs_difference": float(np.max(np.abs(difference))),
        "rms_difference": difference_rms,
        "snr_db": (
            float(20.0 * np.log10(anchor_rms / difference_rms))
            if difference_rms
            else float("inf")
        ),
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


def decode_wav(path: Path) -> bytes:
    completed = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    return completed.stdout


def internal_render(arguments: argparse.Namespace) -> int:
    source_root = arguments.internal_source_root.resolve(strict=True)
    output = arguments.internal_output.resolve()
    source_f32 = arguments.internal_source_f32.resolve(strict=True)
    os.environ["LIVECONV_RVC_SOURCE_ROOT"] = str(source_root)
    os.environ["LIVECONV_RVC_SOURCE_REVISION"] = arguments.internal_source_revision
    from workers.adapters.rvc_v2.backend import RvcConfiguration, UpstreamRvcBackend
    from workers.adapters.rvc_v2.network_isolation import deny_non_unix_sockets

    samples = np.fromfile(source_f32, dtype="<f4")
    if samples.size > EXPECTED_SAMPLES or not np.isfinite(samples).all():
        raise ZeroLatentNoiseError("exact source PCM is invalid")
    samples = np.pad(samples, (0, EXPECTED_SAMPLES - samples.size))
    configuration = RvcConfiguration.from_environment()
    deny_non_unix_sockets()
    backend = UpstreamRvcBackend(configuration)
    try:
        backend.reset()
        converted = np.asarray(
            backend.convert(samples.tolist(), SAMPLE_RATE), dtype="<f4"
        )
    finally:
        backend.close()
    if converted.size != EXPECTED_SAMPLES or not np.isfinite(converted).all():
        raise ZeroLatentNoiseError("direct RVC output is invalid")
    output.write_bytes(converted.tobytes())
    return 0


def validate(arguments: argparse.Namespace) -> tuple[dict[str, Any], dict[str, str]]:
    checked_file(arguments.source_wav, SOURCE_WAV_SHA256, "listening source")
    checked_file(arguments.source_f32, SOURCE_F32_SHA256, "original float PCM")
    checked_file(
        arguments.gateway_baseline_wav, GATEWAY_BASELINE_SHA256, "Gateway baseline"
    )
    baseline = arguments.baseline_source_root.resolve(strict=True)
    zero = arguments.zero_source_root.resolve(strict=True)
    for path, revision, label in (
        (baseline, BASELINE_SOURCE_REVISION, "baseline source"),
        (zero, ZERO_SOURCE_REVISION, "zero-noise source"),
    ):
        if git_revision(path) != revision or not tracked_tree_clean(path, revision):
            raise ZeroLatentNoiseError(f"{label} identity drifted")
    if arguments.work_dir.exists() or arguments.listener_dir.exists():
        raise ZeroLatentNoiseError("work and listener outputs must be new")
    profiles = json.loads(
        (arguments.deployment.resolve(strict=True) / "profiles.json").read_text()
    )
    records = [
        item
        for item in profiles.get("profiles", [])
        if isinstance(item, dict) and item.get("profile_id") == PROFILE_ID
    ]
    if len(records) != 1:
        raise ZeroLatentNoiseError("stable RVC profile is unavailable")
    parent = read_process_environment(arguments.gateway_pid)
    return records[0], profile_environment(records[0], parent)


def execute(
    arguments: argparse.Namespace,
    profile: dict[str, Any],
    environment: dict[str, str],
) -> dict[str, Any]:
    runtime = profile.get("runtime")
    worker_endpoint = (
        runtime.get("worker_endpoint") if isinstance(runtime, dict) else None
    )
    if not isinstance(worker_endpoint, str):
        raise ZeroLatentNoiseError("stable RVC worker endpoint is unavailable")
    worker_python = Path(worker_endpoint).absolute()
    if not worker_python.is_file():
        raise ZeroLatentNoiseError("stable RVC worker Python is unavailable")
    arguments.work_dir.mkdir(parents=True)
    standard_raw = arguments.work_dir / "standard.f32le"
    zero_raw = arguments.work_dir / "zero-latent-noise.f32le"
    durations: dict[str, float] = {}
    for label, root, revision, output in (
        (
            "standard",
            arguments.baseline_source_root,
            BASELINE_SOURCE_REVISION,
            standard_raw,
        ),
        (
            "zero_latent_noise",
            arguments.zero_source_root,
            ZERO_SOURCE_REVISION,
            zero_raw,
        ),
    ):
        started = time.perf_counter()
        subprocess.run(
            [
                str(worker_python),
                str(Path(__file__).resolve()),
                "--internal-render",
                "--internal-source-f32",
                str(arguments.source_f32.resolve()),
                "--internal-output",
                str(output.resolve()),
                "--internal-source-root",
                str(root.resolve()),
                "--internal-source-revision",
                revision,
            ],
            env={**os.environ, **environment},
            check=True,
        )
        durations[label] = round(time.perf_counter() - started, 3)
    standard_pcm = standard_raw.read_bytes()
    zero_pcm = zero_raw.read_bytes()
    gateway_pcm = decode_wav(arguments.gateway_baseline_wav)
    if any(
        len(item) != EXPECTED_SAMPLES * 4
        for item in (standard_pcm, zero_pcm, gateway_pcm)
    ):
        raise ZeroLatentNoiseError("comparison PCM length drifted")

    staging = arguments.listener_dir.with_name(
        f".{arguments.listener_dir.name}.staging"
    )
    if staging.exists():
        raise ZeroLatentNoiseError("listener staging output must be new")
    staging.mkdir()
    shutil.copyfile(arguments.source_wav, staging / "00-source.wav")
    shutil.copyfile(
        arguments.gateway_baseline_wav, staging / "10-seed0-gateway-baseline.wav"
    )
    write_wav(staging / "20-seed0-direct-standard.wav", standard_pcm)
    write_wav(staging / "30-seed0-direct-zero-latent.wav", zero_pcm)
    variants = [
        {
            "variant_id": "seed0-gateway-baseline",
            "display_name": "Stable seed-0 RVC / Gateway baseline",
            "display_order": 1,
            "output_file": "10-seed0-gateway-baseline.wav",
            "output_sha256": "sha256:" + GATEWAY_BASELINE_SHA256,
            "status": "passed",
            "operator_judgment": "unreviewed",
            "reused_by_exact_hash": True,
        },
        {
            "variant_id": "seed0-direct-standard",
            "display_name": "Stable seed-0 RVC / direct standard latent noise",
            "display_order": 2,
            "output_file": "20-seed0-direct-standard.wav",
            "output_sha256": "sha256:"
            + sha256_file(staging / "20-seed0-direct-standard.wav"),
            "status": "passed",
            "operator_judgment": "unreviewed",
        },
        {
            "variant_id": "seed0-direct-zero-latent",
            "display_name": "Stable seed-0 RVC / direct zero latent noise",
            "display_order": 3,
            "output_file": "30-seed0-direct-zero-latent.wav",
            "output_sha256": "sha256:"
            + sha256_file(staging / "30-seed0-direct-zero-latent.wav"),
            "status": "passed",
            "operator_judgment": "unreviewed",
        },
    ]
    comparisons = {
        "gateway_vs_direct_standard": signal_comparison(gateway_pcm, standard_pcm),
        "direct_standard_vs_zero_latent": signal_comparison(standard_pcm, zero_pcm),
    }
    index = {
        "schema_version": 1,
        "title": "RVC actual input: standard vs zero latent noise",
        "run_kind": "MS-3 isolated RVC latent-noise root-cause control",
        "status": "completed-listen-now-unselected",
        "source_id": SOURCE_ID,
        "source_file": "Native / actual ChatGPT-tab input (2026-08-11)",
        "source_output_file": "00-source.wav",
        "comparison_scope": {
            "changed_variable": "latent posterior noise scale 0.66666 versus 0",
            "fixed": ["input", "checkpoint", "index", "seed", "RVC settings"],
            "machine_selection_allowed": False,
            "question": (
                "Does zero latent noise remove generation-boundary sensitivity?"
            ),
        },
        "runtime": {
            "baseline_source_revision": BASELINE_SOURCE_REVISION,
            "zero_source_revision": ZERO_SOURCE_REVISION,
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
        "kind": "liveconv-ms3-rvc-zero-latent-noise-result",
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "source_id": SOURCE_ID,
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
    value.add_argument("--baseline-source-root", type=Path, required=True)
    value.add_argument("--zero-source-root", type=Path, required=True)
    value.add_argument("--source-wav", type=Path, required=True)
    value.add_argument("--source-f32", type=Path, required=True)
    value.add_argument("--gateway-baseline-wav", type=Path, required=True)
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    return value


def internal_parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(add_help=False)
    value.add_argument("--internal-render", action="store_true")
    value.add_argument("--internal-source-f32", type=Path, required=True)
    value.add_argument("--internal-output", type=Path, required=True)
    value.add_argument("--internal-source-root", type=Path, required=True)
    value.add_argument("--internal-source-revision", required=True)
    return value


def main() -> int:
    try:
        if "--internal-render" in sys.argv:
            return internal_render(internal_parser().parse_args())
        arguments = parser().parse_args()
        profile, environment = validate(arguments)
        if arguments.check:
            print("ok   RVC zero-latent-noise CPU admission complete")
            return 0
        execute(arguments, profile, environment)
        return 0
    except (
        OSError,
        ZeroLatentNoiseError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        print(f"render_rvc_zero_latent_noise: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
