from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
MODULE_PATH = TOOL_ROOT / "render_actual_offline_horizons.py"
SPEC = importlib.util.spec_from_file_location(
    "xvc_human_paired_render_actual_offline_horizons", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
OFFLINE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OFFLINE
SPEC.loader.exec_module(OFFLINE)


def test_listener_index_exposes_four_offline_controls() -> None:
    hashes = {0: "a" * 64, 4: "b" * 64, 8: "c" * 64, 12: "d" * 64}

    document = OFFLINE.listening_index(hashes)

    assert [item["display_name"] for item in document["variants"]] == [
        "X-VC base / actual input / offline",
        "X-VC human87 / 4 epochs / actual input / offline",
        "X-VC human87 / 8 epochs / actual input / offline",
        "X-VC human87 / 12 epochs / actual input / offline",
    ]
    assert [item["output_sha256"] for item in document["variants"]] == list(
        hashes.values()
    )


def test_runner_is_offline_only_and_reuses_exact_exp027_boundary() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "model.inference(batch)" in source
    assert "run_streaming" not in source
    assert "stream.validate_inputs(arguments)" in source
    assert '"streaming_cause_decided": False' in source
