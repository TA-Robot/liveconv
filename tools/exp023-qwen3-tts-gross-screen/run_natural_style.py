#!/usr/bin/env python3
"""Compare default and natural-conversation Qwen3-TTS style on 12 texts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
TOOL_ROOT = Path(__file__).resolve().parent
BASE_RUNNER = TOOL_ROOT / "run.py"
BASE_CHILD = TOOL_ROOT / "synthesize.py"
STYLE_CHILD = TOOL_ROOT / "synthesize_natural_style.py"
ARTIFACT_ROOT = ROOT / "artifacts/qwen3-tts-ono-anna"
FIXTURE = (
    ROOT / "experiments/EXP-023-qwen3-tts-japanese-gross-screen/fixtures/texts.v1.json"
)
BASELINE_ROOT = (
    ROOT / "artifacts/ms3/listening/exp023-qwen3-tts-ono-anna-ja12-plain-20260812"
)
OUTPUT_ROOT = (
    ROOT
    / "artifacts/ms3/listening/exp023-qwen3-tts-ono-anna-natural-style-v1"
)
STYLE_OUTPUT_NAME = "qwen3-tts-ono-anna-natural.wav"
BASELINE_OUTPUT_NAME = "qwen3-tts-ono-anna-default.wav"
STYLE_INSTRUCTION = (
    "自然な日常会話として、明るく親しみやすく、"
    "過剰に演技せずに話してください。"
)


class StyleProbeError(RuntimeError):
    """The bounded style comparison cannot continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_base_runner() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "liveconv_exp023_base_runner", BASE_RUNNER
    )
    if specification is None or specification.loader is None:
        raise StyleProbeError("EXP-023 base runner cannot load")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _base_admission(base: ModuleType) -> dict[str, object]:
    arguments = argparse.Namespace(
        artifact_root=ARTIFACT_ROOT,
        fixture=FIXTURE,
        expected_fixture_sha256=base.FIXTURE_SHA256,
        expected_runner_sha256=sha256_file(BASE_RUNNER),
        expected_child_sha256=sha256_file(BASE_CHILD),
    )
    return base._admission(arguments)


def validate_baseline_row(
    base: ModuleType, row: dict[str, str]
) -> tuple[Path, str]:
    directory = BASELINE_ROOT / row["id"]
    index_path = directory / "index.json"
    if index_path.is_symlink() or not index_path.is_file():
        raise StyleProbeError(f"baseline index missing for {row['id']}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("source_text") != row["text"]:
        raise StyleProbeError(f"baseline source text drifted for {row['id']}")
    variants = index.get("variants")
    if not isinstance(variants, list) or len(variants) != 1:
        raise StyleProbeError(f"baseline variant inventory drifted for {row['id']}")
    expected = str(variants[0].get("output_sha256", "")).removeprefix("sha256:")
    wav = directory / str(variants[0].get("output_file", ""))
    base.validate_output_wav(wav)
    if len(expected) != 64 or sha256_file(wav) != expected:
        raise StyleProbeError(f"baseline WAV identity drifted for {row['id']}")
    return wav, expected


def build_index(
    row: dict[str, str], baseline_sha256: str, style_sha256: str
) -> dict[str, object]:
    seed = 8878 + int(row["id"][3:])
    common = {
        "family_id": "qwen3-tts",
        "operator_judgment": "unreviewed",
        "quality_status": "not_assessed",
        "route_status": "offline_diagnostic",
        "extension_eligible": False,
        "status": "passed",
    }
    return {
        "schema_version": 1,
        "title": f"EXP-023 {row['id']}: default vs natural conversation",
        "run_kind": "EXP-023 one-axis Qwen3-TTS style listen-now",
        "status": "completed-listen-now-unselected",
        "source_file": f"入力テキスト: {row['text']}",
        "source_text": row["text"],
        "text_id": row["id"],
        "text_category": row["category"],
        "comparison_scope": {
            "single_changed_variable": "instruct",
            "human_hearing_pending": True,
            "machine_selection_allowed": False,
        },
        "variants": [
            {
                **common,
                "variant_id": f"qwen3-tts-ono-anna-default-{row['id'].lower()}",
                "profile_id": "tts.qwen3-tts-12hz-1.7b-customvoice.ono-anna.v1",
                "display_name": "Ono_Anna / default instruct",
                "display_order": 1,
                "output_file": BASELINE_OUTPUT_NAME,
                "output_sha256": f"sha256:{baseline_sha256}",
                "effective_parameters": {
                    "speaker": "Ono_Anna",
                    "language": "Japanese",
                    "sample_rate": 24_000,
                    "seed": seed,
                    "instruct": "",
                    "training_performed": False,
                },
            },
            {
                **common,
                "variant_id": f"qwen3-tts-ono-anna-natural-{row['id'].lower()}",
                "profile_id": (
                    "tts.qwen3-tts-12hz-1.7b-customvoice.ono-anna-natural.v1"
                ),
                "display_name": "Ono_Anna / natural conversation instruct",
                "display_order": 2,
                "output_file": STYLE_OUTPUT_NAME,
                "output_sha256": f"sha256:{style_sha256}",
                "effective_parameters": {
                    "speaker": "Ono_Anna",
                    "language": "Japanese",
                    "sample_rate": 24_000,
                    "seed": seed,
                    "instruct": STYLE_INSTRUCTION,
                    "training_performed": False,
                },
            },
        ],
    }


def check() -> tuple[ModuleType, dict[str, object]]:
    base = _load_base_runner()
    admission = _base_admission(base)
    fixture = admission["fixture"]
    if not isinstance(fixture, dict):
        raise StyleProbeError("fixture admission is invalid")
    for row in fixture["utterances"]:
        validate_baseline_row(base, row)
    if OUTPUT_ROOT.exists():
        raise StyleProbeError("style listener output already exists")
    if STYLE_CHILD.is_symlink() or not STYLE_CHILD.is_file():
        raise StyleProbeError("style synthesis child is unavailable")
    return base, admission


def execute(base: ModuleType, admission: dict[str, object]) -> dict[str, object]:
    gpu = base._gpu_identity()
    staging = Path(
        tempfile.mkdtemp(prefix=f".{OUTPUT_ROOT.name}.tmp-", dir=OUTPUT_ROOT.parent)
    )
    try:
        child_result_path = staging / ".child-result.json"
        child_home = staging / ".home"
        child_home.mkdir()
        child_sha256 = sha256_file(STYLE_CHILD)
        command = [
            str(admission["runtime"]["python"]),
            str(STYLE_CHILD),
            "--expected-self-sha256",
            child_sha256,
            "--model",
            str(admission["model"]),
            "--fixture",
            str(FIXTURE),
            "--expected-fixture-sha256",
            str(admission["fixture_sha256"]),
            "--output",
            str(staging),
            "--result",
            str(child_result_path),
            "--expected-gpu-uuid",
            str(gpu["uuid"]),
        ]
        process = base._run_child(command, child_home)
        if process.returncode:
            raise StyleProbeError(
                "Qwen style child failed: "
                + process.stderr.decode("utf-8", "replace")[-4000:]
            )
        child = json.loads(child_result_path.read_text(encoding="utf-8"))
        if (
            child.get("warmup_count") != 1
            or child.get("retained_count") != 12
            or child.get("style_instruction") != STYLE_INSTRUCTION
        ):
            raise StyleProbeError("style child result inventory drifted")
        child_result_path.unlink()
        child_home.rmdir()
        fixture = admission["fixture"]
        outputs: list[dict[str, str]] = []
        for row in fixture["utterances"]:
            baseline_wav, baseline_sha256 = validate_baseline_row(base, row)
            directory = staging / row["id"]
            style_wav = directory / STYLE_OUTPUT_NAME
            style_info = base.validate_output_wav(style_wav)
            shutil.copyfile(baseline_wav, directory / BASELINE_OUTPUT_NAME)
            index = build_index(row, baseline_sha256, style_info["sha256"])
            base._write_json(directory / "index.json", index)
            outputs.append(
                {
                    "text_id": row["id"],
                    "baseline_sha256": baseline_sha256,
                    "style_sha256": style_info["sha256"],
                }
            )
        result = {
            "schema_version": 1,
            "kind": "liveconv-exp023-qwen-natural-style-listen-now-result",
            "status": "completed-listen-now-unselected",
            "git_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "runner_sha256": sha256_file(Path(__file__)),
            "child_sha256": child_sha256,
            "fixture_sha256": admission["fixture_sha256"],
            "style_instruction": STYLE_INSTRUCTION,
            "outputs": outputs,
            "claims": {
                "product_selected": False,
                "perceptual_winner": False,
                "transport_qualified": False,
            },
        }
        base._write_json(staging / "listen-now-result.json", result)
        staging.replace(OUTPUT_ROOT)
        return result
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--execute", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        if arguments.check == arguments.execute:
            raise StyleProbeError("choose exactly one of --check or --execute")
        base, admission = check()
        if arguments.check:
            print("ok   EXP-023 natural-style CPU admission complete")
            return 0
        print(json.dumps(execute(base, admission), ensure_ascii=False, sort_keys=True))
        return 0
    except (StyleProbeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"EXP-023 natural-style probe failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
