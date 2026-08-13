from __future__ import annotations

import hashlib
import io
import json
import sys
import wave
import zipfile
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_jsut_evaluation as jsut  # noqa: E402


def wav_bytes(frames: int = 4_800) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as opened:
        opened.setnchannels(1)
        opened.setsampwidth(2)
        opened.setframerate(48_000)
        opened.writeframes(b"\x00\x00" * frames)
    return output.getvalue()


def fake_archive(path: Path) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        for category, count in jsut.CATEGORY_COUNTS.items():
            rows = max(count * 3, count)
            prefix = category.upper()
            transcript = []
            for index in range(rows):
                identifier = f"{prefix}_{index + 1:04d}"
                transcript.append(f"{identifier}:評価文{index + 1}")
                archive.writestr(
                    f"jsut_ver1.1/{category}/wav/{identifier}.wav", wav_bytes()
                )
            archive.writestr(
                f"jsut_ver1.1/{category}/transcript_utf8.txt",
                "\n".join(transcript) + "\n",
            )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stratified_positions_are_bin_centers() -> None:
    assert jsut.stratified_positions(12, 4) == [1, 4, 7, 10]
    assert jsut.stratified_positions(26, 4) == [3, 9, 16, 22]


def test_build_and_materialize_category_balanced_set(tmp_path: Path) -> None:
    archive = tmp_path / "jsut.zip"
    digest = fake_archive(archive)
    manifest, audio = jsut.build(archive, expected_archive_sha256=digest)

    assert manifest["kind"] == jsut.OUTPUT_KIND
    assert len(manifest["items"]) == 24
    assert len(audio) == 24
    assert {item["client_id_sha256"] for item in manifest["items"]} == {
        jsut.SPEAKER_SHA256
    }
    observed = {
        category: sum(
            item["jsut_category"] == category for item in manifest["items"]
        )
        for category in jsut.CATEGORY_COUNTS
    }
    assert observed == dict(jsut.CATEGORY_COUNTS)

    output = tmp_path / "evaluation"
    jsut.materialize(output, manifest, audio)
    saved = json.loads((output / "evaluation.json").read_text(encoding="utf-8"))
    assert saved == manifest
    assert len(list((output / "source-wav").glob("*.wav"))) == 24
    with pytest.raises(jsut.JsutEvaluationError, match="already exists"):
        jsut.materialize(output, manifest, audio)


def test_archive_identity_is_required(tmp_path: Path) -> None:
    archive = tmp_path / "jsut.zip"
    fake_archive(archive)
    with pytest.raises(jsut.JsutEvaluationError, match="identity drifted"):
        jsut.build(archive, expected_archive_sha256="0" * 64)
