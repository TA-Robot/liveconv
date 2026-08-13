#!/usr/bin/env python3
"""Test bounded RVC context controls after a generation reset."""

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
STATE_RUNNER = Path(__file__).with_name("render_rvc_turn_state.py")
PROFILE_ID = "vc.rvc-v2.amitaro-sasayaki-clean-bright-seed0.v1"
SOURCE_ID = "ACTUAL_CHATGPT_20260811_114251"
SOURCE_WAV_SHA256 = "78b15cd5e9d25ee10d8cb27084c63275221d773a04b21d11e4e3ba2be8056da6"
SOURCE_F32_SHA256 = "b114aed49c79291b10caf30f9828e6efb0e191773aa2fe8ab77d786f7a83b5f2"
DIRECT_RESET_SHA256 = "4e1f08c38b4e367004e10c7b12627ff99533b2b527c7cb4fd7c79cc9a76b426f"
SOURCE_REVISION = "81eed5e8f68b6bed1789f682fe78cdd324495afc"
SPLIT_FRAME = 212
FRAME_SAMPLES = 960
EXPECTED_SAMPLES = 409 * FRAME_SAMPLES
SAMPLE_RATE = 48_000
PRIME_SECONDS = 3.5
PRIME_SAMPLES = int(PRIME_SECONDS * SAMPLE_RATE)


class SilencePrimeError(RuntimeError):
    """The bounded silence-only priming comparison cannot continue."""


def load_state_runner() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "liveconv_rvc_silence_prime_state", STATE_RUNNER
    )
    if specification is None or specification.loader is None:
        raise SilencePrimeError("turn-state runner cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def convert_with_silence_prime(
    backend: Any, second: np.ndarray, *, seed: int
) -> np.ndarray:
    backend.reset()
    silence = np.zeros(PRIME_SAMPLES, dtype=np.float32)
    discarded = np.asarray(
        backend.convert(silence.tolist(), SAMPLE_RATE), dtype=np.float32
    )
    if discarded.size != PRIME_SAMPLES or not np.isfinite(discarded).all():
        raise SilencePrimeError("silence priming output is invalid")
    backend._engine.torch.manual_seed(seed)  # noqa: SLF001
    return np.asarray(backend.convert(second.tolist(), SAMPLE_RATE), dtype="<f4")


def convert_with_input_context(
    backend: Any, first: np.ndarray, second: np.ndarray
) -> np.ndarray:
    backend.reset()
    first_output = np.asarray(
        backend.convert(first.tolist(), SAMPLE_RATE), dtype=np.float32
    )
    if first_output.size != first.size or not np.isfinite(first_output).all():
        raise SilencePrimeError("context-source turn output is invalid")
    input_wav = backend._engine.input_wav.clone()  # noqa: SLF001
    input_wav_res = backend._engine.input_wav_res.clone()  # noqa: SLF001
    backend._reset_state()  # noqa: SLF001
    backend._engine.input_wav.copy_(input_wav)  # noqa: SLF001
    backend._engine.input_wav_res.copy_(input_wav_res)  # noqa: SLF001
    return np.asarray(backend.convert(second.tolist(), SAMPLE_RATE), dtype="<f4")


def convert_with_pitch_cache(
    backend: Any, first: np.ndarray, second: np.ndarray
) -> np.ndarray:
    backend.reset()
    first_output = np.asarray(
        backend.convert(first.tolist(), SAMPLE_RATE), dtype=np.float32
    )
    if first_output.size != first.size or not np.isfinite(first_output).all():
        raise SilencePrimeError("pitch-source turn output is invalid")
    cache_pitch = backend._engine.rvc.cache_pitch.clone()  # noqa: SLF001
    cache_pitchf = backend._engine.rvc.cache_pitchf.clone()  # noqa: SLF001
    backend._reset_state()  # noqa: SLF001
    backend._engine.rvc.cache_pitch.copy_(cache_pitch)  # noqa: SLF001
    backend._engine.rvc.cache_pitchf.copy_(cache_pitchf)  # noqa: SLF001
    return np.asarray(backend.convert(second.tolist(), SAMPLE_RATE), dtype="<f4")


def convert_with_rng_state(
    backend: Any, first: np.ndarray, second: np.ndarray
) -> np.ndarray:
    backend.reset()
    first_output = np.asarray(
        backend.convert(first.tolist(), SAMPLE_RATE), dtype=np.float32
    )
    if first_output.size != first.size or not np.isfinite(first_output).all():
        raise SilencePrimeError("RNG-source turn output is invalid")
    torch = backend._engine.torch  # noqa: SLF001
    cpu_rng = torch.get_rng_state().clone()
    cuda_rng = [state.clone() for state in torch.cuda.get_rng_state_all()]
    backend._reset_state()  # noqa: SLF001
    torch.set_rng_state(cpu_rng)
    torch.cuda.set_rng_state_all(cuda_rng)
    return np.asarray(backend.convert(second.tolist(), SAMPLE_RATE), dtype="<f4")


def internal_render(arguments: argparse.Namespace) -> int:
    source_root = arguments.internal_source_root.absolute()
    os.environ["LIVECONV_RVC_SOURCE_ROOT"] = str(source_root)
    os.environ["LIVECONV_RVC_SOURCE_REVISION"] = SOURCE_REVISION
    from workers.adapters.rvc_v2.backend import RvcConfiguration, UpstreamRvcBackend
    from workers.adapters.rvc_v2.network_isolation import deny_non_unix_sockets

    samples = np.fromfile(arguments.internal_source_f32, dtype="<f4")
    if samples.size > EXPECTED_SAMPLES or not np.isfinite(samples).all():
        raise SilencePrimeError("exact source PCM is invalid")
    samples = np.pad(samples, (0, EXPECTED_SAMPLES - samples.size))
    split_sample = SPLIT_FRAME * FRAME_SAMPLES
    first, second = samples[:split_sample], samples[split_sample:]
    configuration = RvcConfiguration.from_environment()
    if configuration.inference_seed is None:
        raise SilencePrimeError("silence prime requires an explicit inference seed")
    deny_non_unix_sockets()
    backend = UpstreamRvcBackend(configuration)
    try:
        if arguments.internal_rng_state_carry:
            output = convert_with_rng_state(backend, first, second)
        elif arguments.internal_pitch_cache_carry:
            output = convert_with_pitch_cache(backend, first, second)
        elif arguments.internal_context_carry:
            output = convert_with_input_context(backend, first, second)
        else:
            output = convert_with_silence_prime(
                backend, second, seed=configuration.inference_seed
            )
    finally:
        backend.close()
    if output.size != second.size or not np.isfinite(output).all():
        raise SilencePrimeError("silence-primed turn output is invalid")
    arguments.internal_output.write_bytes(output.astype("<f4").tobytes())
    return 0


def validate(
    arguments: argparse.Namespace, state: ModuleType
) -> tuple[dict[str, Any], dict[str, str], ModuleType]:
    support = state.load_support()
    support.checked_file(arguments.source_wav, SOURCE_WAV_SHA256, "listening source")
    support.checked_file(arguments.source_f32, SOURCE_F32_SHA256, "original float PCM")
    support.checked_file(
        arguments.direct_reset_wav, DIRECT_RESET_SHA256, "direct reset baseline"
    )
    source_root = arguments.source_root.resolve(strict=True)
    if support.git_revision(
        source_root
    ) != SOURCE_REVISION or not support.tracked_tree_clean(
        source_root, SOURCE_REVISION
    ):
        raise SilencePrimeError("baseline source identity drifted")
    if arguments.work_dir.exists() or arguments.listener_dir.exists():
        raise SilencePrimeError("work and listener outputs must be new")
    profiles = json.loads(
        (arguments.deployment.resolve(strict=True) / "profiles.json").read_text()
    )
    records = [
        item
        for item in profiles.get("profiles", [])
        if isinstance(item, dict) and item.get("profile_id") == PROFILE_ID
    ]
    if len(records) != 1:
        raise SilencePrimeError("stable RVC profile is unavailable")
    parent = support.read_process_environment(arguments.gateway_pid)
    return records[0], support.profile_environment(records[0], parent), support


def execute(
    arguments: argparse.Namespace,
    profile: dict[str, Any],
    environment: dict[str, str],
    support: ModuleType,
) -> dict[str, Any]:
    runtime = profile.get("runtime")
    endpoint = runtime.get("worker_endpoint") if isinstance(runtime, dict) else None
    if not isinstance(endpoint, str):
        raise SilencePrimeError("stable RVC worker endpoint is unavailable")
    worker_python = Path(endpoint).absolute()
    if not worker_python.is_file():
        raise SilencePrimeError("stable RVC worker Python is unavailable")
    arguments.work_dir.mkdir(parents=True)
    context_carry = arguments.context_carry
    pitch_cache_carry = arguments.pitch_cache_carry
    rng_state_carry = arguments.rng_state_carry
    if rng_state_carry:
        mode = "rng-state-carry"
    elif pitch_cache_carry:
        mode = "pitch-cache-carry"
    elif context_carry:
        mode = "input-context-carry"
    else:
        mode = "silence-prime"
    second_output = arguments.work_dir / f"{mode}-turn-2.f32le"
    command = [
        str(worker_python),
        str(Path(__file__).resolve()),
        "--internal-render",
        "--internal-source-f32",
        str(arguments.source_f32.resolve()),
        "--internal-output",
        str(second_output.resolve()),
        "--internal-source-root",
        str(arguments.source_root.resolve()),
    ]
    if rng_state_carry:
        command.append("--internal-rng-state-carry")
    elif pitch_cache_carry:
        command.append("--internal-pitch-cache-carry")
    elif context_carry:
        command.append("--internal-context-carry")
    started = time.perf_counter()
    subprocess.run(
        command,
        env={**os.environ, **environment},
        check=True,
    )
    wall_seconds = round(time.perf_counter() - started, 3)
    baseline_pcm = support.decode_wav(arguments.direct_reset_wav)
    second_pcm = second_output.read_bytes()
    split_bytes = SPLIT_FRAME * FRAME_SAMPLES * 4
    if (
        len(baseline_pcm) != EXPECTED_SAMPLES * 4
        or len(second_pcm) != (EXPECTED_SAMPLES - SPLIT_FRAME * FRAME_SAMPLES) * 4
    ):
        raise SilencePrimeError("comparison PCM length drifted")
    candidate_pcm = baseline_pcm[:split_bytes] + second_pcm

    staging = arguments.listener_dir.with_name(
        f".{arguments.listener_dir.name}.staging"
    )
    if staging.exists():
        raise SilencePrimeError("listener staging output must be new")
    staging.mkdir()
    shutil.copyfile(arguments.source_wav, staging / "00-source.wav")
    shutil.copyfile(arguments.direct_reset_wav, staging / "10-direct-reset.wav")
    candidate_file = f"20-direct-{mode}.wav"
    support.write_wav(staging / candidate_file, candidate_pcm)
    if rng_state_carry:
        candidate_id = "direct-rng-state-carry"
        candidate_name = "Stable seed-0 RVC / reset buffers + continue RNG state"
    elif pitch_cache_carry:
        candidate_id = "direct-pitch-cache-carry"
        candidate_name = "Stable seed-0 RVC / reset + prior RMVPE pitch cache only"
    elif context_carry:
        candidate_id = "direct-input-context-carry"
        candidate_name = "Stable seed-0 RVC / reset + prior input context only"
    else:
        candidate_id = "direct-silence-prime"
        candidate_name = "Stable seed-0 RVC / reset + 3.5 s silence prime"
    variants = [
        {
            "variant_id": "direct-reset",
            "display_name": "Stable seed-0 RVC / full reset at turn 2",
            "display_order": 1,
            "output_file": "10-direct-reset.wav",
            "output_sha256": "sha256:" + DIRECT_RESET_SHA256,
            "status": "passed",
            "operator_judgment": "unreviewed",
            "reused_by_exact_hash": True,
        },
        {
            "variant_id": candidate_id,
            "display_name": candidate_name,
            "display_order": 2,
            "output_file": candidate_file,
            "output_sha256": "sha256:" + support.sha256_file(staging / candidate_file),
            "status": "passed",
            "operator_judgment": "unreviewed",
        },
    ]
    comparison = support.signal_comparison(baseline_pcm, candidate_pcm)
    if rng_state_carry:
        title = "RVC turn 2: reseed vs continue RNG state"
        changed_variable = "RNG continuation point after otherwise full reset"
        question = "Does RNG continuation explain recovered turn-2 content?"
        control = {
            "cpu_rng_carried": True,
            "cuda_rng_carried": True,
            "input_context_reset": True,
            "pitch_cache_reset": True,
            "rms_reset": True,
            "sola_reset": True,
            "shipping_candidate": False,
        }
    elif pitch_cache_carry:
        title = "RVC turn 2: full reset vs prior RMVPE pitch cache only"
        changed_variable = "prior RMVPE pitch/pitchf cache after otherwise full reset"
        question = "Can prior pitch cache recover turn 2 with other state cleared?"
        control = {
            "pitch_cache_carried": True,
            "pitchf_cache_carried": True,
            "rng_reset": True,
            "input_context_reset": True,
            "rms_reset": True,
            "sola_reset": True,
            "must_clear_on_interrupt": True,
        }
    elif context_carry:
        title = "RVC turn 2: full reset vs prior input context only"
        changed_variable = "prior input context buffers after otherwise full reset"
        question = "Can prior input context recover turn 2 with other state cleared?"
        control = {
            "input_wav_carried": True,
            "input_wav_res_carried": True,
            "rng_reset": True,
            "pitch_cache_reset": True,
            "rms_reset": True,
            "sola_reset": True,
            "must_clear_on_interrupt": True,
        }
    else:
        title = "RVC turn 2: full reset vs silence-only context prime"
        changed_variable = "3.5 seconds of zero PCM after full reset"
        question = "Can silence-only priming safely recover turn-2 content?"
        control = {
            "seconds": PRIME_SECONDS,
            "samples": PRIME_SAMPLES,
            "audio": "zero PCM",
            "output": "discarded",
            "seed_reapplied_after_prime": True,
            "prior_generation_audio_used": False,
        }
    index = {
        "schema_version": 1,
        "title": title,
        "run_kind": "MS-3 safe RVC generation-context root-cause control",
        "status": "completed-listen-now-unselected",
        "source_id": SOURCE_ID,
        "source_file": "Native / actual ChatGPT-tab input (2026-08-11)",
        "source_output_file": "00-source.wav",
        "comparison_scope": {
            "changed_variable": changed_variable,
            "fixed": ["input", "split", "checkpoint", "seed", "RVC settings"],
            "machine_selection_allowed": False,
            "question": question,
        },
        "context_control": control,
        "runtime": {
            "source_revision": SOURCE_REVISION,
            "wall_seconds": wall_seconds,
            "signal_comparison": comparison,
        },
        "variants": variants,
    }
    (staging / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    staging.rename(arguments.listener_dir)
    result = {
        "schema_version": 1,
        "kind": (
            "liveconv-ms3-rvc-rng-state-result"
            if rng_state_carry
            else (
                "liveconv-ms3-rvc-pitch-cache-result"
                if pitch_cache_carry
                else (
                    "liveconv-ms3-rvc-input-context-result"
                    if context_carry
                    else "liveconv-ms3-rvc-silence-prime-result"
                )
            )
        ),
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "wall_seconds": wall_seconds,
        "signal_comparison": comparison,
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
    value.add_argument("--direct-reset-wav", type=Path, required=True)
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    context = value.add_mutually_exclusive_group()
    context.add_argument("--context-carry", action="store_true")
    context.add_argument("--pitch-cache-carry", action="store_true")
    context.add_argument("--rng-state-carry", action="store_true")
    return value


def internal_parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(add_help=False)
    value.add_argument("--internal-render", action="store_true")
    value.add_argument("--internal-source-f32", type=Path, required=True)
    value.add_argument("--internal-output", type=Path, required=True)
    value.add_argument("--internal-source-root", type=Path, required=True)
    value.add_argument("--internal-context-carry", action="store_true")
    value.add_argument("--internal-pitch-cache-carry", action="store_true")
    value.add_argument("--internal-rng-state-carry", action="store_true")
    return value


def main() -> int:
    try:
        if "--internal-render" in sys.argv:
            return internal_render(internal_parser().parse_args())
        arguments = parser().parse_args()
        state = load_state_runner()
        profile, environment, support = validate(arguments, state)
        if arguments.check:
            if arguments.rng_state_carry:
                control = "RNG-state carry"
            elif arguments.pitch_cache_carry:
                control = "pitch-cache carry"
            elif arguments.context_carry:
                control = "input-context carry"
            else:
                control = "silence-only prime"
            print(f"ok   RVC {control} CPU admission complete")
            return 0
        execute(arguments, profile, environment, support)
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as error:
        print(f"render_rvc_silence_prime: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
