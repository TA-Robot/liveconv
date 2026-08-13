from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "analyze_source_representations.py"
SPEC = importlib.util.spec_from_file_location("xvc_representation_audit", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


def test_token_statistics_exposes_collapse() -> None:
    result = AUDIT.token_statistics([4, 4, 4, 2, 3, 3])

    assert result["token_count"] == 6
    assert result["unique_tokens"] == 3
    assert result["dominant_token_fraction"] == 0.5
    assert result["longest_token_run"] == 3
    assert result["transition_count"] == 2


def test_waveform_statistics_tracks_active_span() -> None:
    result = AUDIT.waveform_statistics([0.0, 0.0, -0.5, 0.5, 0.0])

    assert math.isclose(result["rms"], math.sqrt(0.1))
    assert result["active_sample_fraction"] == 0.4
    assert result["first_active_fraction"] == 0.4
    assert result["last_active_fraction"] == 0.6


def test_exploratory_separation_counts_nonloop_rows() -> None:
    rows = [
        {
            "source_id": "loop-a",
            "waveform": {"rms": 0.01},
            "tokens": {"unique_tokens": 2},
            "hidden": {"global_std": 0.1},
        },
        {
            "source_id": "loop-b",
            "waveform": {"rms": 0.02},
            "tokens": {"unique_tokens": 3},
            "hidden": {"global_std": 0.2},
        },
        {
            "source_id": "good",
            "waveform": {"rms": 0.2},
            "tokens": {"unique_tokens": 8},
            "hidden": {"global_std": 0.8},
        },
    ]

    rules = AUDIT.exploratory_separation(rows, {"loop-a", "loop-b"})

    assert rules[0]["nonloop_rows_flagged"] == 0
    assert rules[0]["loop_rows_covered"] == 2
