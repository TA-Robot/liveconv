from __future__ import annotations

import importlib.util
import json
import wave
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "screen_speaker_fit.py"
SPEC = importlib.util.spec_from_file_location("screen_speaker_fit", MODULE_PATH)
assert SPEC and SPEC.loader
screen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(screen)


def _wav(path: Path, value: int) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(int(value).to_bytes(2, "little", signed=True) * 160)
    return screen._sha256(path)


def _index(root: Path, variant_id: str, values: tuple[int, int, int]) -> None:
    row = root / "00-row"
    source_sha = _wav(row / "00-source.wav", values[0])
    del source_sha
    _wav(row / "01-target.wav", values[1])
    output_sha = _wav(row / "30-output.wav", values[2])
    (row / "index.json").write_text(
        json.dumps(
            {
                "status": "completed-listen-now-unselected",
                "source_output_file": "00-source.wav",
                "target_reference_output_file": "01-target.wav",
                "variants": [
                    {
                        "variant_id": variant_id,
                        "output_file": "30-output.wav",
                        "output_sha256": output_sha,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_aggregate_counts_direction() -> None:
    rows = [
        {
            "old": {
                "target_to_output": 0.2,
                "source_to_output": 0.5,
                "target_advantage": -0.3,
            },
            "new": {
                "target_to_output": 0.4,
                "source_to_output": 0.3,
                "target_advantage": 0.1,
            },
            "delta": {
                "target_to_output": 0.2,
                "source_to_output": -0.2,
                "target_advantage": 0.4,
            },
        },
        {
            "old": {
                "target_to_output": 0.5,
                "source_to_output": 0.4,
                "target_advantage": 0.1,
            },
            "new": {
                "target_to_output": 0.5,
                "source_to_output": 0.4,
                "target_advantage": 0.1,
            },
            "delta": {
                "target_to_output": 0.0,
                "source_to_output": 0.0,
                "target_advantage": 0.0,
            },
        },
    ]
    result = screen._aggregate(rows)
    assert result["delta"]["target_to_output"] == pytest.approx(0.1)
    assert result["new_vs_old_target_similarity"] == {
        "wins": 1,
        "ties": 1,
        "losses": 0,
        "tie_tolerance": 1e-6,
    }


def test_row_contract_rejects_output_hash_drift(tmp_path: Path) -> None:
    root = tmp_path / "listener"
    _index(root, "candidate", (100, 200, 300))
    _wav(root / "00-row" / "30-output.wav", 301)
    with pytest.raises(screen.SpeakerFitScreenError, match="output identity drifted"):
        screen._row_contract(
            root,
            "00-row",
            expected_variant="candidate",
            expected_target_sha=screen._sha256(root / "00-row" / "01-target.wav"),
        )


def test_validate_target_lineage_binds_archive_and_row(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "style": "runrun",
                "sources": {"target_archive": {"sha256": "a" * 64}},
                "rows": [
                    {
                        "row_id": "ITA:EMOTION100_003",
                        "target_wav": {"sha256": "b" * 64},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    plan = {
        "target": {
            "listener_sha256": "c" * 64,
            "manifest_row_id": "ITA:EMOTION100_003",
            "raw_sha256": "b" * 64,
            "archive_sha256": "a" * 64,
        }
    }
    assert screen._validate_target_lineage(plan, manifest) == "c" * 64


def test_report_kind_defaults_and_accepts_plan_override() -> None:
    assert screen._report_kind({}) == "liveconv-exp251-xvc-speaker-fit-screen/v1"
    assert screen._report_kind(
        {"report_kind": "liveconv-exp258-xvc-output-speaker-fit-direction/v1"}
    ) == "liveconv-exp258-xvc-output-speaker-fit-direction/v1"
    with pytest.raises(screen.SpeakerFitScreenError, match="liveconv v1"):
        screen._report_kind({"report_kind": "wrong"})
