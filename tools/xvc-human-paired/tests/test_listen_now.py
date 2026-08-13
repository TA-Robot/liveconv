from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

TOOL_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = TOOL_ROOT / "listen_now.py"
SPEC = importlib.util.spec_from_file_location(
    "xvc_human_paired_listen_now", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
LISTEN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LISTEN
SPEC.loader.exec_module(LISTEN)


def _row(pair_id: str, split: str) -> dict[str, object]:
    return {
        "pair_id": pair_id,
        "utterance_id": pair_id,
        "row_id": f"ITA:{pair_id}",
        "split": split,
        "display_text": f"text for {pair_id}",
        "source_wav": {"relative_path": f"{pair_id}.wav", "sha256": "a" * 64},
        "target_wav": {"archive_member": f"{pair_id}.wav", "sha256": "b" * 64},
    }


def _voiced_frames(count: int) -> np.ndarray:
    frames = np.full(
        (count, LISTEN.FRAME_SAMPLES), 4_000, dtype=np.int16
    )
    frames[0] = 0
    frames[-1] = 0
    return frames.reshape(-1)


def test_source_only_render_selection_never_resolves_a_heldout_target() -> None:
    rows = [
        _row("train-never-read", "train"),
        _row("heldout-too-long", "heldout"),
        _row("heldout-a", "heldout"),
        _row("heldout-b", "heldout"),
        _row("heldout-c", "heldout"),
        _row("heldout-not-needed", "heldout"),
    ]
    source_reads: list[str] = []

    def read_source(row: dict[str, object]) -> np.ndarray:
        pair_id = str(row["pair_id"])
        source_reads.append(pair_id)
        if pair_id == "heldout-too-long":
            return _voiced_frames(130)
        return _voiced_frames(100)

    selected = LISTEN.select_source_only_render_rows(rows, read_source=read_source)

    assert [row["pair_id"] for row, _samples in selected] == [
        "heldout-a",
        "heldout-b",
        "heldout-c",
    ]
    assert source_reads == [
        "heldout-too-long",
        "heldout-a",
        "heldout-b",
        "heldout-c",
    ]
    assert all(samples.shape == (LISTEN.WINDOW_48K,) for _row, samples in selected)


def test_listener_index_uses_plain_base_and_adapted_labels(tmp_path: Path) -> None:
    source = LISTEN.RenderSource(
        pair_id="RECITATION324_001",
        display_text="これは公開sourceです。",
        source_path=tmp_path / "source.wav",
    )

    document = LISTEN.listening_index(
        source,
        target_reference_id="EMOTION100_003",
        base_sha256="a" * 64,
        adapted_sha256="b" * 64,
    )

    assert document["status"] == "completed-listen-now-unselected"
    assert document["source_output_file"] == "00-source-reference.wav"
    assert document["target_reference_output_file"] == "01-target-reference.wav"
    assert [item["display_name"] for item in document["variants"]] == [
        "X-VC base / human input / adapterなし",
        "X-VC / 人間whole-short 87ペア / 348 updates",
    ]
    assert [item["output_sha256"] for item in document["variants"]] == [
        "a" * 64,
        "b" * 64,
    ]
    assert all(
        item["excluded_from_preference"] is True
        for item in document["reference_audio"]
    )


def test_listen_now_scope_is_one_fixed_short_trajectory() -> None:
    assert LISTEN.EXPECTED_TRAIN_PAIRS == 87
    assert LISTEN.EPOCHS == 4
    assert LISTEN.TOTAL_UPDATES == 348
    assert LISTEN.LEARNING_RATE == 1e-4
    assert LISTEN.RENDER_COUNT == 3
