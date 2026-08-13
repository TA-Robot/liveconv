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
    assert HORIZON.EXTENDED_CHECKPOINT_EPOCHS == (12, 18, 24)
    assert HORIZON.parse_checkpoint_epochs("12,18,24") == (12, 18, 24)


def test_checkpoint_plan_rejects_arbitrary_sweeps() -> None:
    with pytest.raises(Exception, match="checkpoint epochs must be"):
        HORIZON.parse_checkpoint_epochs("12,16,20")


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
        "X-VC / 人間whole-short 87ペア / expanded79 / 4 epochs / 348 updates",
        "X-VC / 人間whole-short 87ペア / expanded79 / 8 epochs / 696 updates",
        "X-VC / 人間whole-short 87ペア / expanded79 / 12 epochs / 1044 updates",
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


def test_extended_listener_and_epoch12_control_are_fail_closed(tmp_path: Path) -> None:
    source_id = "EMOTION100_002"
    source = HORIZON.base.RenderSource(
        pair_id=source_id,
        display_text="これは公開sourceです。",
        source_path=tmp_path / "source.wav",
    )
    hashes = {0: "a" * 64, 12: "b" * 64, 18: "c" * 64, 24: "d" * 64}
    document = HORIZON.listening_index(
        source,
        target_reference_id="EMOTION100_003",
        hashes=hashes,
        checkpoint_epochs=HORIZON.EXTENDED_CHECKPOINT_EPOCHS,
    )
    assert [item["display_name"] for item in document["variants"]] == [
        "X-VC base / human input / adapterなし",
        "X-VC / 人間whole-short 87ペア / expanded79 / 12 epochs / 1044 updates",
        "X-VC / 人間whole-short 87ペア / expanded79 / 18 epochs / 1566 updates",
        "X-VC / 人間whole-short 87ペア / expanded79 / 24 epochs / 2088 updates",
    ]
    HORIZON.assert_extended_control(
        source_id,
        base_sha256=HORIZON.EXPECTED_BASE_HASHES[source_id],
        epoch12_sha256=HORIZON.EXPECTED_EPOCH12_HASHES[source_id],
    )
    with pytest.raises(HORIZON.base.ListenNowError, match="epoch-12 control"):
        HORIZON.assert_extended_control(
            source_id,
            base_sha256=HORIZON.EXPECTED_BASE_HASHES[source_id],
            epoch12_sha256="0" * 64,
        )


def test_control69_scope_is_exact_subset() -> None:
    scope = HORIZON.lora_scope(
        HORIZON.base.REPO_ROOT
        / "artifacts"
        / "exp007"
        / "phase0-inputs-v1"
        / "inventory.json",
        "control69",
    )
    assert len(scope["target_modules"]) == 69
    assert scope["trainable_parameter_count"] == 835_584
    assert all(
        ".attn." in name or ".ff_c." in name or ".ff_x." in name
        for name in scope["target_modules"]
    )
    HORIZON.assert_base_control(
        "EMOTION100_002",
        base_sha256=HORIZON.EXPECTED_BASE_HASHES["EMOTION100_002"],
    )
    HORIZON.assert_control69_extended_control(
        "EMOTION100_002",
        base_sha256=HORIZON.EXPECTED_BASE_HASHES["EMOTION100_002"],
        epoch12_sha256=HORIZON.EXPECTED_CONTROL69_EPOCH12_HASHES[
            "EMOTION100_002"
        ],
    )
    with pytest.raises(HORIZON.base.ListenNowError, match="control69 epoch-12"):
        HORIZON.assert_control69_extended_control(
            "EMOTION100_002",
            base_sha256=HORIZON.EXPECTED_BASE_HASHES["EMOTION100_002"],
            epoch12_sha256="0" * 64,
        )


def test_runner_uses_atomic_listener_publication_and_no_heldout_target() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert 'staging.rename(arguments.listener_dir)' in source
    assert '"heldout_target_access_count": 0' in source
    render_materialization = source[
        source.index("render_sources =") : source.index("import torch")
    ]
    assert "target_archive" not in render_materialization
