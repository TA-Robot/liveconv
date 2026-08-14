from __future__ import annotations

import hashlib
import io
import json
import sys
import wave
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import fetch_src4vc_subset as fetch  # noqa: E402
import prepare_exp325_src4vc_two_utterance as pair  # noqa: E402


def _wav(seed: int) -> bytes:
    value = io.BytesIO()
    with wave.open(value, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(48_000)
        handle.writeframes(((seed % 65_536).to_bytes(2, "little", signed=False)) * 2_400)
    return value.getvalue()


def _write(root: Path, relative: str, value: bytes) -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
    return hashlib.sha256(value).hexdigest()


def _subset(root: Path, index: int) -> dict[str, object]:
    heldout = fetch.heldout_speakers()
    rows: list[dict[str, object]] = []
    seed = 1_000_000 * (index + 1)
    for speaker_number in range(1, 101):
        speaker = f"SRC4VC{speaker_number:03d}"
        split = "evaluation" if speaker in heldout else "train"
        count = 2 if split == "evaluation" else 1
        for row_index in range(count):
            selected_index = row_index if split == "evaluation" else index
            identifier = f"{speaker.lower()}-recitation-{selected_index}"
            relative = f"audio/{speaker}/RECITATION_{selected_index:03d}.wav"
            value = _wav(seed)
            seed += 1
            digest = _write(root, relative, value)
            rows.append(
                {
                    "id": identifier,
                    "speaker_id": speaker,
                    "split": split,
                    "filename": relative,
                    "sha256": digest,
                    "text": f"{speaker} utterance {selected_index}",
                }
            )
    return {
        "kind": fetch.OUTPUT_KIND,
        "train_utterance_index": index,
        "items": rows,
    }


def _exp244(manifest: dict[str, object]) -> dict[str, object]:
    return {
        "kind": fetch.OUTPUT_KIND,
        "items": [
            row
            for row in manifest["items"]
            if isinstance(row, dict) and row["split"] == "train"
        ]
        + [
            row
            for row in manifest["items"]
            if isinstance(row, dict) and row["split"] == "evaluation"
        ],
    }


def _exp238(root: Path) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for position in range(pair.EXPECTED_ROWS):
        relative = f"targets/{position:03d}-RECITATION324_{position:03d}.wav"
        value = _wav(900_000 + position)
        digest = _write(root, relative, value)
        rows.append(
            {
                "id": f"exp238-{position:03d}",
                "target_id": f"RECITATION324_{position:03d}",
                "real_target_file": relative,
                "real_target_sha256": digest,
                "real_target_text": f"target transcript {position}",
                "real_target_root": "source-work",
            }
        )
    return {"kind": pair.EXP238_KIND, "items": rows}


def _fixtures(tmp_path: Path) -> tuple[dict, dict, dict, dict, Path, Path, Path]:
    zero_root = tmp_path / "zero"
    one_root = tmp_path / "one"
    target_root = tmp_path / "targets"
    zero = _subset(zero_root, 0)
    one = _subset(one_root, 1)
    return (
        _exp244(zero),
        zero,
        one,
        _exp238(target_root),
        zero_root,
        one_root,
        target_root,
    )


def test_materialize_orders_two_rows_per_speaker_and_binds_exp238_targets(
    tmp_path: Path,
) -> None:
    exp244, zero, one, exp238, zero_root, one_root, target_root = _fixtures(tmp_path)
    output = tmp_path / "output"

    result = pair.materialize(
        exp244_manifest=exp244,
        subset_zero_manifest=zero,
        subset_one_manifest=one,
        subset_zero_root=zero_root,
        subset_one_root=one_root,
        exp238_manifest=exp238,
        exp238_root=target_root,
        output_root=output,
    )

    assert result["kind"] == pair.OUTPUT_KIND
    assert len(result["items"]) == 170
    assert [row["source_speaker_id"] for row in result["items"][:4]] == [
        "SRC4VC001",
        "SRC4VC001",
        "SRC4VC002",
        "SRC4VC002",
    ]
    assert [row["source_utterance_index"] for row in result["items"][:4]] == [0, 1, 0, 1]
    assert [row["target_id"] for row in result["items"]] == [
        row["target_id"] for row in exp238["items"]
    ]
    assert [row["real_target_file"] for row in result["items"]] == [
        row["real_target_file"] for row in exp238["items"]
    ]
    assert [row["real_target_sha256"] for row in result["items"]] == [
        row["real_target_sha256"] for row in exp238["items"]
    ]
    assert [row["real_target_text"] for row in result["items"]] == [
        row["real_target_text"] for row in exp238["items"]
    ]
    assert all(row["target_text"] == row["source_text"] for row in result["items"])
    assert all(
        key not in row for row in result["items"] for key in ("target_root", "target_file")
    )
    assert len({row["source_sha256"] for row in result["items"]}) == 170
    assert len({row["source_id"] for row in result["items"]}) == 170
    assert {row["source_speaker_id"] for row in result["items"]} == (
        set(f"SRC4VC{index:03d}" for index in range(1, 101)) - fetch.heldout_speakers()
    )
    assert (output / "pool.json").is_file()


def test_build_pool_rejects_heldout_speaker_leak(tmp_path: Path) -> None:
    exp244, zero, one, exp238, zero_root, one_root, target_root = _fixtures(tmp_path)
    heldout = sorted(fetch.heldout_speakers())[0]
    train_row = next(row for row in zero["items"] if row["split"] == "train")
    train_row["speaker_id"] = heldout

    with pytest.raises(pair.Src4vcTwoUtteranceError, match="boundary"):
        pair.build_pool(
            exp244_manifest=exp244,
            subset_zero_manifest=zero,
            subset_one_manifest=one,
            subset_zero_root=zero_root,
            subset_one_root=one_root,
            exp238_manifest=exp238,
            exp238_root=target_root,
        )


def test_build_pool_rejects_duplicate_source_identity(tmp_path: Path) -> None:
    exp244, zero, one, exp238, zero_root, one_root, target_root = _fixtures(tmp_path)
    first = next(row for row in zero["items"] if row["split"] == "train")
    second = next(row for row in one["items"] if row["split"] == "train")
    second["sha256"] = first["sha256"]

    with pytest.raises(pair.Src4vcTwoUtteranceError, match="duplicated"):
        pair.build_pool(
            exp244_manifest=exp244,
            subset_zero_manifest=zero,
            subset_one_manifest=one,
            subset_zero_root=zero_root,
            subset_one_root=one_root,
            exp238_manifest=exp238,
            exp238_root=target_root,
        )


def test_build_pool_rejects_target_hash_drift(tmp_path: Path) -> None:
    exp244, zero, one, exp238, zero_root, one_root, target_root = _fixtures(tmp_path)
    exp238["items"][0]["real_target_sha256"] = "0" * 64

    with pytest.raises(pair.Src4vcTwoUtteranceError, match="target"):
        pair.build_pool(
            exp244_manifest=exp244,
            subset_zero_manifest=zero,
            subset_one_manifest=one,
            subset_zero_root=zero_root,
            subset_one_root=one_root,
            exp238_manifest=exp238,
            exp238_root=target_root,
        )


def test_main_check_does_not_write_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exp244, zero, one, exp238, zero_root, one_root, target_root = _fixtures(tmp_path)
    exp244_path = tmp_path / "exp244.json"
    zero_path = tmp_path / "zero.json"
    one_path = tmp_path / "one.json"
    exp238_path = tmp_path / "exp238.json"
    for path, value in (
        (exp244_path, exp244),
        (zero_path, zero),
        (one_path, one),
        (exp238_path, exp238),
    ):
        path.write_text(json.dumps(value), encoding="utf-8")
    output = tmp_path / "not-created"

    assert pair.main(
        [
            "--check",
            "--exp244-manifest",
            str(exp244_path),
            "--subset-zero-manifest",
            str(zero_path),
            "--subset-one-manifest",
            str(one_path),
            "--subset-zero-root",
            str(zero_root),
            "--subset-one-root",
            str(one_root),
            "--exp238-manifest",
            str(exp238_path),
            "--exp238-root",
            str(target_root),
            "--output-root",
            str(output),
        ]
    ) == 0
    assert not output.exists()
    assert '"status": "checked-no-write-no-cuda"' in capsys.readouterr().out
