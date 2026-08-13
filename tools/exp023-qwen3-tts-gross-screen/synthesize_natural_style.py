#!/usr/bin/env python3
"""Render the bounded EXP-023 natural-conversation style candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import time
import traceback
import wave
from pathlib import Path

SPEAKER = "Ono_Anna"
LANGUAGE = "Japanese"
SEED = 8878
OUTPUT_NAME = "qwen3-tts-ono-anna-natural.wav"
STYLE_INSTRUCTION = (
    "自然な日常会話として、明るく親しみやすく、"
    "過剰に演技せずに話してください。"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deny_network() -> None:
    original = socket.socket

    class LocalOnlySocket(original):
        def __init__(self, family=socket.AF_INET, *args, **kwargs):  # type: ignore[no-untyped-def]
            if family != socket.AF_UNIX:
                raise OSError("the style probe forbids non-Unix sockets")
            super().__init__(family, *args, **kwargs)

    socket.socket = LocalOnlySocket


def write_pcm16(path: Path, samples, np) -> dict[str, float | int]:  # type: ignore[no-untyped-def]
    data = np.asarray(samples, dtype=np.float32).reshape(-1)
    if data.size == 0 or data.size > 24_000 * 30 or not np.isfinite(data).all():
        raise RuntimeError("Qwen output is empty, too long, or nonfinite")
    peak = float(np.max(np.abs(data)))
    if peak >= 1.0:
        raise RuntimeError("Qwen output reaches full scale")
    pcm = np.rint(data * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=False)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24_000)
        stream.writeframes(pcm.tobytes())
    return {"frames": int(data.size), "peak_float": peak}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-self-sha256", required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--expected-fixture-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--expected-gpu-uuid", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if sha256_file(Path(__file__)) != args.expected_self_sha256:
        raise RuntimeError("synthesis child sha256 differs")
    if sha256_file(args.fixture) != args.expected_fixture_sha256:
        raise RuntimeError("fixture sha256 differs in child")
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    rows = fixture["utterances"]
    if len(rows) != 12:
        raise RuntimeError("child fixture must contain 12 texts")
    deny_network()

    import numpy as np
    import torch
    from qwen_tts import Qwen3TTSModel

    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("exactly one visible CUDA GPU is required")
    observed_uuid = str(torch.cuda.get_device_properties(0).uuid)
    if not observed_uuid.startswith("GPU-"):
        observed_uuid = f"GPU-{observed_uuid}"
    if observed_uuid.lower() != args.expected_gpu_uuid.lower():
        raise RuntimeError(f"CUDA UUID differs: {observed_uuid}")
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model = Qwen3TTSModel.from_pretrained(
        str(args.model),
        local_files_only=True,
        device_map="cuda:0",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )

    def generate(row: dict[str, str], seed: int):  # type: ignore[no-untyped-def]
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        started = time.monotonic()
        wavs, sample_rate = model.generate_custom_voice(
            text=row["text"],
            language=LANGUAGE,
            speaker=SPEAKER,
            instruct=STYLE_INSTRUCTION,
            non_streaming_mode=True,
            do_sample=True,
            repetition_penalty=1.05,
            temperature=0.9,
            top_p=1.0,
            top_k=50,
            subtalker_dosample=True,
            subtalker_temperature=0.9,
            subtalker_top_p=1.0,
            subtalker_top_k=50,
            max_new_tokens=2048,
        )
        elapsed = (time.monotonic() - started) * 1000
        if sample_rate != 24_000 or len(wavs) != 1:
            raise RuntimeError("Qwen returned an unexpected sample rate or batch size")
        return wavs[0], elapsed

    generate(rows[0], SEED)
    records: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        samples, elapsed = generate(row, SEED + index + 1)
        info = write_pcm16(args.output / row["id"] / OUTPUT_NAME, samples, np)
        records.append(
            {
                "id": row["id"],
                "seed": SEED + index + 1,
                "model_generation_ms": elapsed,
                **info,
            }
        )
    args.result.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "warmup_count": 1,
                "retained_count": 12,
                "style_instruction": STYLE_INSTRUCTION,
                "records": records,
                "gpu": {
                    "uuid": observed_uuid,
                    "name": torch.cuda.get_device_name(0),
                    "torch": torch.__version__,
                    "cuda": torch.version.cuda,
                },
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    torch.cuda.empty_cache()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(1)
