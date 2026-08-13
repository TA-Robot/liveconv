from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

MODULE_PATH = Path(__file__).with_name("render_rvc_zero_latent_noise.py")
SPEC = importlib.util.spec_from_file_location(
    "render_rvc_zero_latent_noise", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_signal_comparison_identical() -> None:
    pcm = np.linspace(-0.5, 0.5, 960, dtype="<f4").tobytes()

    result = MODULE.signal_comparison(pcm, pcm)

    assert result["exact"] is True
    assert result["correlation"] == pytest.approx(1.0)
    assert result["max_abs_difference"] == 0.0
    assert result["rms_difference"] == 0.0


def test_signal_comparison_detects_change() -> None:
    left = np.linspace(-0.5, 0.5, 960, dtype="<f4")
    right = left * 0.5

    result = MODULE.signal_comparison(left.tobytes(), right.astype("<f4").tobytes())

    assert result["exact"] is False
    assert result["correlation"] == pytest.approx(1.0)
    assert result["max_abs_difference"] == pytest.approx(0.25)
    assert result["snr_db"] == pytest.approx(6.0206, abs=1e-4)


def test_signal_comparison_rejects_shape_mismatch() -> None:
    with pytest.raises(MODULE.ZeroLatentNoiseError, match="shape-compatible"):
        MODULE.signal_comparison(b"\0" * 8, b"\0" * 4)


def test_profile_environment_binds_seeded_profile() -> None:
    profile = {
        "profile_id": MODULE.PROFILE_ID,
        "runtime": {
            "configuration": {
                "settings": {
                    "speaker_id": 0,
                    "pitch_shift": 4,
                    "f0_method": "rmvpe",
                    "index_rate": 0.3,
                    "rms_mix_rate": 0.5,
                    "sample_rate": 48000,
                    "block_ms": 500,
                    "crossfade_ms": 90,
                    "context_ms": 3500,
                    "threshold_dbfs": -60.0,
                    "inference_seed": 0,
                }
            }
        },
    }
    suffix = (
        "".join(
            character if character.isalnum() else "_" for character in MODULE.PROFILE_ID
        )
        .strip("_")
        .upper()
    )
    prefix = f"LIVECONV_RVC_VARIANT_{suffix}"
    parent = {
        "LIVECONV_RVC_V2_WORKER_WHEEL_PATH": "/wheel",
        "LIVECONV_RVC_V2_WORKER_WHEEL_SHA256": "a" * 64,
        f"{prefix}_CHECKPOINT_PATH": "/checkpoint",
        f"{prefix}_CHECKPOINT_SHA256": "b" * 64,
        f"{prefix}_INDEX_PATH": "/index",
        f"{prefix}_INDEX_SHA256": "c" * 64,
    }

    result = MODULE.profile_environment(profile, parent)

    assert result["LIVECONV_RVC_V2_INFERENCE_SEED"] == "0"
    assert result["LIVECONV_RVC_V2_CHECKPOINT_PATH"] == "/checkpoint"
    assert result["RVC_CUDA_GRAPH"] == "1"
