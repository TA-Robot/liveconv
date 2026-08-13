from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

MODULE_PATH = Path(__file__).with_name("render_stable_rvc_rnnoise.py")
SPEC = importlib.util.spec_from_file_location("stable_rvc_rnnoise", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run
SPEC.loader.exec_module(run)


def test_listener_staging_is_on_final_parent() -> None:
    final = Path("/listening/ms3-stable-rvc-rnnoise-v1")

    assert run.listener_staging_path(final) == Path(
        "/listening/.ms3-stable-rvc-rnnoise-v1.staging"
    )


def test_preprocess_rnnoise_preserves_frame_shape(tmp_path: Path) -> None:
    helper = tmp_path / "helper.py"
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n"
    )
    helper.chmod(0o755)
    frame = struct.pack("<960f", *np.linspace(-0.5, 0.5, 960, dtype=np.float32))

    output = run.preprocess_rnnoise([frame, frame], helper)

    assert len(output) == 2
    assert all(len(item) == 960 * 4 for item in output)
    assert np.all(np.isfinite(np.frombuffer(b"".join(output), dtype="<f4")))


def test_preprocess_rnnoise_rejects_incomplete_frames(tmp_path: Path) -> None:
    with pytest.raises(run.StableRnnoiseError, match="complete 20 ms"):
        run.preprocess_rnnoise([b"short"], tmp_path / "unused")
