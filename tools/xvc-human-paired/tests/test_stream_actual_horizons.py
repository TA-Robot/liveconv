from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
MODULE_PATH = TOOL_ROOT / "stream_actual_horizons.py"
SPEC = importlib.util.spec_from_file_location(
    "xvc_human_paired_stream_actual_horizons", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
STREAM = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = STREAM
SPEC.loader.exec_module(STREAM)


def test_stream_window_matches_the_pinned_upstream_online_shape() -> None:
    assert STREAM.CHUNK_MS == 2400
    assert STREAM.CURRENT_MS == 120
    assert STREAM.SMOOTH_MS == 20
    assert STREAM.FUTURE_MS == 100
    assert STREAM.HISTORY_MS == 2160
    assert STREAM.EXPECTED_MODEL_SOURCE_SAMPLES == 131_840
    assert STREAM.EXPECTED_OUTPUT_SAMPLES == 130_731


def test_latency_summary_reports_p50_p95_and_failures() -> None:
    summary = STREAM.latency_summary([10.0, 20.0, 30.0, 40.0])

    assert summary == {
        "chunk_count": 4,
        "compute_ms_p50": 25.0,
        "compute_ms_p95": pytest.approx(38.5),
        "compute_ms_max": 40.0,
        "failure_count": 0,
    }


def test_listener_index_has_actual_source_and_four_explicit_variants() -> None:
    hashes = {0: "a" * 64, 4: "b" * 64, 8: "c" * 64, 12: "d" * 64}

    document = STREAM.listening_index(
        output_hashes=hashes, source_duration_seconds=8.1706875
    )

    assert document["source_output_file"] == "00-native-source.wav"
    assert [item["display_name"] for item in document["variants"]] == [
        "X-VC base / upstream streaming / adapterなし",
        "X-VC human87 / 4 epochs / upstream streaming",
        "X-VC human87 / 8 epochs / upstream streaming",
        "X-VC human87 / 12 epochs / upstream streaming",
    ]
    assert [item["output_sha256"] for item in document["variants"]] == list(
        hashes.values()
    )


def test_measurement_wraps_the_pinned_upstream_stream_function() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "infer_utils.run_streaming(" in source
    assert "infer_utils.run_stream_chunk_forward = measured_forward" in source
    assert "torch.cuda.synchronize(device)" in source
    assert "PeftModel.from_pretrained" in source
    assert '"conversational_latency_measured": False' in source
