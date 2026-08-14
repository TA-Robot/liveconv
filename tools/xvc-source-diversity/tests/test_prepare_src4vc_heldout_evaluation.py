from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import fetch_src4vc_subset as fetch  # noqa: E402
import prepare_src4vc_heldout_evaluation as heldout  # noqa: E402


def _manifest() -> dict:
    frozen = fetch.heldout_speakers()
    items = []
    for index in range(1, 101):
        speaker = f"SRC4VC{index:03d}"
        split = "evaluation" if speaker in frozen else "train"
        for row in range(2 if split == "evaluation" else 1):
            items.append(
                {
                    "id": f"{speaker.lower()}-{row}",
                    "speaker_id": speaker,
                    "split": split,
                }
            )
    return {"kind": fetch.OUTPUT_KIND, "items": items}


def test_selection_keeps_fifteen_disjoint_speakers_twice() -> None:
    selected = heldout.selected_rows(_manifest())

    speakers = {item["speaker_id"] for item in selected}
    assert len(selected) == 30
    assert len(speakers) == 15
    assert speakers == fetch.heldout_speakers()


def test_selection_rejects_train_speaker_leak() -> None:
    manifest = _manifest()
    evaluation = next(
        item for item in manifest["items"] if item["split"] == "evaluation"
    )
    evaluation["speaker_id"] = next(
        item["speaker_id"] for item in manifest["items"] if item["split"] == "train"
    )

    with pytest.raises(heldout.Src4vcHeldoutError, match="boundary"):
        heldout.selected_rows(manifest)
