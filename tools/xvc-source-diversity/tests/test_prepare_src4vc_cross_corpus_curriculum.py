from __future__ import annotations

import hashlib
import io
import sys
import wave
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import fetch_src4vc_subset as fetch  # noqa: E402
import prepare_cross_corpus_unpaired_curriculum as predecessor  # noqa: E402
import prepare_src4vc_cross_corpus_curriculum as src4vc  # noqa: E402


def _wav() -> bytes:
    value = io.BytesIO()
    with wave.open(value, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(48_000)
        handle.writeframes(np.full(4_800, 1_000, dtype="<i2").tobytes())
    return value.getvalue()


def _fixtures(root: Path) -> tuple[dict, dict, Path, Path]:
    old_root = root / "old"
    corpus_root = root / "src4vc"
    old_root.mkdir()
    corpus_root.mkdir()
    source = _wav()
    source_sha = hashlib.sha256(source).hexdigest()
    (old_root / "source.wav").write_bytes(source)
    (old_root / "target.wav").write_bytes(source)
    domains = (
        ["commonvoice-unpaired"] * 48
        + ["hadou-unpaired"] * 34
        + ["jvs-unpaired"] * 3
        + ["jsut-unpaired"] * 85
    )
    old_rows = [
        {
            "id": f"old-{index:03d}",
            "domain": domain,
            "teacher_id": f"{domain}-{index:03d}",
            "source_manifest_id": f"old:{index:03d}",
            "source_file": "source.wav",
            "source_sha256": source_sha,
            "source_text": f"source {index}",
            "target_id": f"target-{index:03d}",
            "target_file": "target.wav",
            "target_sha256": source_sha,
            "target_text": f"target {index}",
        }
        for index, domain in enumerate(domains)
    ]
    heldout = fetch.heldout_speakers()
    corpus_rows = []
    for speaker_index in range(1, 101):
        speaker = f"SRC4VC{speaker_index:03d}"
        split = "evaluation" if speaker in heldout else "train"
        for row_index in range(2 if split == "evaluation" else 1):
            filename = f"{speaker}-{row_index}.wav"
            (corpus_root / filename).write_bytes(source)
            corpus_rows.append(
                {
                    "id": f"{speaker.lower()}-{row_index}",
                    "speaker_id": speaker,
                    "split": split,
                    "filename": filename,
                    "sha256": source_sha,
                    "text": f"SRC4VC text {speaker} {row_index}",
                }
            )
    return (
        {"kind": predecessor.OUTPUT_KIND, "items": old_rows},
        {"kind": fetch.OUTPUT_KIND, "items": corpus_rows},
        old_root,
        corpus_root,
    )


def test_materialize_changes_only_jsut_source_block_and_preserves_targets(
    tmp_path: Path,
) -> None:
    old, corpus, old_root, corpus_root = _fixtures(tmp_path)

    result = src4vc.materialize(
        predecessor_manifest=old,
        predecessor_root=old_root,
        src4vc_manifest=corpus,
        src4vc_root=corpus_root,
        output_root=tmp_path / "output",
    )

    assert result["kind"] == src4vc.OUTPUT_KIND
    assert Counter(row["domain"] for row in result["items"]) == (
        src4vc.EXPECTED_COMPOSITION
    )
    assert [row["target_id"] for row in result["items"]] == [
        row["target_id"] for row in old["items"]
    ]
    src_rows = [
        row for row in result["items"] if row["domain"] == "src4vc-smartphone-unpaired"
    ]
    assert len(src_rows) == 85
    assert len({row["source_speaker_id"] for row in src_rows}) == 85
    assert not any(row["domain"] == "jsut-unpaired" for row in result["items"])


def test_source_records_rejects_train_evaluation_speaker_leak(tmp_path: Path) -> None:
    old, corpus, old_root, corpus_root = _fixtures(tmp_path)
    corpus["items"][-1]["speaker_id"] = corpus["items"][0]["speaker_id"]

    with pytest.raises(src4vc.Src4vcCurriculumError, match="split"):
        src4vc.source_records(
            predecessor_manifest=old,
            predecessor_root=old_root,
            src4vc_manifest=corpus,
            src4vc_root=corpus_root,
        )
