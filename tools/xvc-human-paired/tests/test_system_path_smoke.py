from __future__ import annotations

import importlib.util
import sys
import threading
import time
from pathlib import Path

import numpy as np

MODULE_PATH = Path(__file__).parents[1] / "system_path_smoke.py"
SPEC = importlib.util.spec_from_file_location("xvc_system_path_smoke", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_candidate_geometry_reuses_bounded_worker_and_restores_defaults() -> None:
    worker_module = MODULE.worker_module
    backend_module = MODULE.backend_module
    original = (
        worker_module.LOOKAHEAD_FRAMES,
        worker_module.HISTORY_FRAMES,
        backend_module.NATIVE_LOOKAHEAD_SAMPLES,
    )

    with MODULE.candidate_geometry(120):
        assert worker_module.LOOKAHEAD_FRAMES == 7
        assert worker_module.HISTORY_FRAMES == 107
        assert backend_module.NATIVE_LOOKAHEAD_SAMPLES == 2240
        assert (
            worker_module.HISTORY_FRAMES
            + worker_module.CURRENT_FRAMES
            + worker_module.LOOKAHEAD_FRAMES
            == worker_module.WINDOW_FRAMES
        )

    assert (
        worker_module.LOOKAHEAD_FRAMES,
        worker_module.HISTORY_FRAMES,
        backend_module.NATIVE_LOOKAHEAD_SAMPLES,
    ) == original


def test_candidate_geometry_emits_six_frames_after_thirteen_inputs() -> None:
    emitted: list[dict[str, object]] = []
    frame = np.full(MODULE.FRAME_SAMPLES, 0.25, dtype=np.float32)

    with MODULE.candidate_geometry(120):
        worker = MODULE.worker_module.XvcWorker(
            MODULE.backend_module.DeterministicTestBackend(), emitted.append
        )
        worker.handle(MODULE.control("generation.start", 1, generation_id=7))
        for sequence in range(13):
            worker.handle(
                MODULE.audio_message(frame, generation_id=7, sequence=sequence)
            )
        deadline = time.monotonic() + 2
        while (
            len([item for item in emitted if item["type"] == "audio.output"]) < 6
            and time.monotonic() < deadline
        ):
            time.sleep(0.005)
        worker.handle(MODULE.control("generation.cancel", 2, generation_id=7))

    output = [item for item in emitted if item["type"] == "audio.output"]
    assert [item["sequence"] for item in output] == list(range(6))


def test_future_geometry_rejects_subframe_values() -> None:
    try:
        with MODULE.candidate_geometry(125):
            pass
    except ValueError as error:
        assert "multiple of 20" in str(error)
    else:
        raise AssertionError("125 ms must not enter the 20 ms worker contract")


def test_candidate_profiles_bind_distinct_exact_adapters() -> None:
    expanded = MODULE.CANDIDATE_PROFILES["expanded79-e08"]
    control = MODULE.CANDIDATE_PROFILES["control69-e12"]

    assert expanded.adapter_sha256 == MODULE.EXPECTED_ADAPTER_SHA256
    assert control.adapter_sha256 == MODULE.CONTROL69_E12_ADAPTER_SHA256
    assert expanded.adapter_sha256 != control.adapter_sha256
    assert control.output_file == "10-xvc-control69-e12-future-120-system.wav"


def test_gateway_credit_waits_for_output_before_accepting_frame_26() -> None:
    capture = MODULE.Capture()

    def release() -> None:
        time.sleep(0.02)
        capture.emit({"type": "audio.output", "generation_id": 2})

    thread = threading.Thread(target=release)
    thread.start()
    waited_ms = MODULE.wait_for_credit(
        capture,
        generation_id=2,
        sent_frames=25,
        capacity_frames=25,
        timeout=1,
    )
    thread.join()

    assert waited_ms >= 10
