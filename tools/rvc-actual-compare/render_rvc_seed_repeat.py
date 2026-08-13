#!/usr/bin/env python3
"""Repeat one public utterance with an explicitly seeded direct RVC backend."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workers.adapters.rvc_v2.backend import (  # noqa: E402
    RvcConfiguration,
    UpstreamRvcBackend,
)
from workers.adapters.rvc_v2.network_isolation import (  # noqa: E402
    deny_non_unix_sockets,
)

PROFILE_ID = "vc.rvc-v2.amitaro-sasayaki-clean-bright.v1"
SOURCE_ID = "EMOTION100_017"
REPEAT_COUNT = 3
SAMPLE_RATE = 48_000
SOURCE = {
    "source_id": SOURCE_ID,
    "display_text": "あっベルが鳴ってる。",
    "path": ROOT
    / "artifacts/ms3/listening/exp026-human87-horizon-v1/03-EMOTION100_017"
    / "00-source-reference.wav",
    "sha256": "9fad53ec17379745bc7e56d9306a1ffa1fda1ee0dfdf077826792e6e8199d455",
}


class SeedRepeatError(RuntimeError):
    """The bounded seeded RVC diagnostic cannot continue."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
    profile: dict[str, Any], parent_environment: dict[str, str], seed: int
) -> dict[str, str]:
    profile_id = profile.get("profile_id")
    runtime = profile.get("runtime")
    configuration = runtime.get("configuration") if isinstance(runtime, dict) else None
    settings = (
        configuration.get("settings") if isinstance(configuration, dict) else None
    )
    if profile_id != PROFILE_ID or not isinstance(settings, dict):
        raise SeedRepeatError("sealed RVC profile configuration is invalid")
    suffix = "".join(
        character if character.isalnum() else "_" for character in PROFILE_ID
    ).strip("_").upper()
    prefix = f"LIVECONV_RVC_VARIANT_{suffix}"
    environment_names = {
        "LIVECONV_RVC_SOURCE_ROOT": "LIVECONV_RVC_SOURCE_ROOT",
        "LIVECONV_RVC_SOURCE_REVISION": "LIVECONV_RVC_SOURCE_REVISION",
        "LIVECONV_RVC_V2_WORKER_WHEEL_PATH": (
            "LIVECONV_RVC_V2_WORKER_WHEEL_PATH"
        ),
        "LIVECONV_RVC_V2_WORKER_WHEEL_SHA256": (
            "LIVECONV_RVC_V2_WORKER_WHEEL_SHA256"
        ),
        "LIVECONV_RVC_V2_CHECKPOINT_PATH": f"{prefix}_CHECKPOINT_PATH",
        "LIVECONV_RVC_V2_CHECKPOINT_SHA256": f"{prefix}_CHECKPOINT_SHA256",
        "LIVECONV_RVC_V2_INDEX_PATH": f"{prefix}_INDEX_PATH",
        "LIVECONV_RVC_V2_INDEX_SHA256": f"{prefix}_INDEX_SHA256",
    }
    environment: dict[str, str] = {}
    for output_name, source_name in environment_names.items():
        value = parent_environment.get(source_name)
        if not value:
            raise SeedRepeatError(f"identity environment is missing: {source_name}")
        environment[output_name] = value
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
    }
    for setting, name in setting_names.items():
        value = settings.get(setting)
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise SeedRepeatError(f"sealed RVC setting is invalid: {setting}")
        environment[name] = str(value)
    if "input_gain_db" in settings:
        environment["LIVECONV_RVC_V2_INPUT_GAIN_DB"] = str(
            settings["input_gain_db"]
        )
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wav_to_f32le(source: Path, destination: Path) -> int:
    try:
        with wave.open(str(source), "rb") as stream:
            if (
                stream.getframerate(),
                stream.getnchannels(),
                stream.getsampwidth(),
                stream.getcomptype(),
            ) != (SAMPLE_RATE, 1, 2, "NONE"):
                raise SeedRepeatError("source must be mono PCM16 at 48 kHz")
            frames = stream.getnframes()
            pcm = stream.readframes(frames)
    except (OSError, wave.Error) as error:
        raise SeedRepeatError("source WAV cannot be decoded") from error
    if frames <= 0 or len(pcm) != frames * 2:
        raise SeedRepeatError("source WAV is empty or truncated")
    destination.write_bytes(
        b"".join(
            struct.pack("<f", sample / 32768.0)
            for (sample,) in struct.iter_unpack("<h", pcm)
        )
    )
    return frames


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


def execute(arguments: argparse.Namespace) -> dict[str, Any]:
    # Upstream RVC owns process cwd while loaded, so all runner paths must be
    # absolute before model startup.
    arguments.deployment = arguments.deployment.resolve(strict=True)
    arguments.work_dir = arguments.work_dir.resolve()
    arguments.listener_dir = arguments.listener_dir.resolve()
    if arguments.identity_env is not None:
        arguments.identity_env = arguments.identity_env.resolve(strict=True)
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
    profile = records[0]
    source = SOURCE
    if sha256_file(source["path"]) != source["sha256"]:
        raise SeedRepeatError("source identity drifted")

    arguments.work_dir.mkdir(parents=True)
    source_f32 = arguments.work_dir / "source.f32le"
    wav_to_f32le(source["path"], source_f32)
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

    deny_non_unix_sockets()
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
        if not 0 <= arguments.seed < 2**63:
            raise SeedRepeatError("seed is outside the supported range")
        if arguments.check:
            print("ok   seeded RVC direct diagnostic CPU admission complete")
            return 0
        result = execute(arguments)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    except (OSError, SeedRepeatError, subprocess.SubprocessError, ValueError) as error:
        print(f"render_rvc_seed_repeat: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
