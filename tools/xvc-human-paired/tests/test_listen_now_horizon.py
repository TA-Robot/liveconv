from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
MODULE_PATH = TOOL_ROOT / "listen_now_horizon.py"
SPEC = importlib.util.spec_from_file_location(
    "xvc_human_paired_listen_now_horizon", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
HORIZON = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HORIZON
SPEC.loader.exec_module(HORIZON)


def test_horizon_changes_only_training_duration() -> None:
    assert HORIZON.CHECKPOINT_EPOCHS == (4, 8, 12)
    assert HORIZON.TOTAL_UPDATES == 1044
    assert HORIZON.base.EXPECTED_TRAIN_PAIRS == 87
    assert HORIZON.base.LEARNING_RATE == 1e-4
    assert HORIZON.base.GRADIENT_CLIP_NORM == 5.0


def test_listener_index_exposes_base_and_three_plain_horizons(
    tmp_path: Path,
) -> None:
    source = HORIZON.base.RenderSource(
        pair_id="EMOTION100_002",
        display_text="これは公開sourceです。",
        source_path=tmp_path / "source.wav",
    )
    hashes = {0: "a" * 64, 4: "b" * 64, 8: "c" * 64, 12: "d" * 64}

    document = HORIZON.listening_index(
        source,
        target_reference_id="EMOTION100_003",
        hashes=hashes,
    )

    variants = document["variants"]
    assert [item["display_name"] for item in variants] == [
        "X-VC base / human input / adapterなし",
        "X-VC / 人間whole-short 87ペア / 4 epochs / 348 updates",
        "X-VC / 人間whole-short 87ペア / 8 epochs / 696 updates",
        "X-VC / 人間whole-short 87ペア / 12 epochs / 1044 updates",
    ]
    assert [item["output_sha256"] for item in variants] == list(hashes.values())


def test_epoch4_control_is_fail_closed() -> None:
    source_id = "EMOTION100_002"
    HORIZON.assert_epoch4_control(
        source_id,
        base_sha256=HORIZON.EXPECTED_BASE_HASHES[source_id],
        epoch4_sha256=HORIZON.EXPECTED_EPOCH4_HASHES[source_id],
    )

    with pytest.raises(HORIZON.base.ListenNowError, match="epoch-4 control"):
        HORIZON.assert_epoch4_control(
            source_id,
            base_sha256=HORIZON.EXPECTED_BASE_HASHES[source_id],
            epoch4_sha256="0" * 64,
        )


def test_runner_uses_atomic_listener_publication_and_no_heldout_target() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert 'staging.rename(arguments.listener_dir)' in source
    assert '"heldout_target_access_count": 0' in source
    render_materialization = source[
        source.index("render_sources =") : source.index("import torch")
    ]
    assert "target_archive" not in render_materialization
