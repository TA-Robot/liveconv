from __future__ import annotations

import asyncio
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from liveconv_audio._adapter_registry import (
    _rvc_model_environment_names,
    validate_profile_adapter,
    worker_profile_for,
)
from liveconv_audio.profiles import ModelProfile
from liveconv_audio.worker_bridge import (
    WorkerBridge,
    _rvc_environment,
    builtin_supervisor_factory,
)
from liveconv_protocol import (
    ErrorCode,
    FrameHeader,
    FrameKind,
    PcmFrame,
    ProtocolValidationError,
)

from workers.runtime import AudioFrame
from workers.runtime.errors import WorkerRuntimeError

SOURCE_REVISION = "81eed5e8f68b6bed1789f682fe78cdd324495afc"
CHECKPOINT_SHA256 = "46b60b686a9f540aabc3788ac405dbdfb66e370c56751e592b496f8e6967789c"
INDEX_SHA256 = "1cec842c048757af4bc6dc7ab7ac9fa8e7ce7226b297c82c6837c8639ee04003"
WORKER_WHEEL_SHA256 = "828dbf6c26ff4cb6629e7070a8752928519503c9820498a255750920dddba0bc"

RETAINED_CONFIGURATION: dict[str, object] = {
    "worker_module": "workers.adapters.rvc_v2.worker",
    "adapter_revision": "liveconv-rvc-v2-worker-v1.4",
    "source_revision": SOURCE_REVISION,
    "artifacts": {
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "index_sha256": INDEX_SHA256,
        "hubert_config_sha256": (
            "0346950779dfb7f9316fa74ed846e2b8a22a08eedfdc5387b73f327cb1a4a7cf"
        ),
        "hubert_preprocessor_sha256": (
            "7c1976a680fb7acc757cd36fb08eef878fa36c70b4c9d2d595df9c608bbbbf0e"
        ),
        "hubert_weights_sha256": (
            "cc8c20f4b90a520757260197a3ff2505705a7adbd20ad9eeaa4e1a9b38442ef5"
        ),
        "rmvpe_sha256": (
            "6d62215f4306e3ca278246188607209f09af3dc77ed4232efdd069798c4ec193"
        ),
        "worker_wheel_sha256": WORKER_WHEEL_SHA256,
        "worker_wheel_record_sha256": (
            "07736d4c574d0b6008b9672ea2d8669c8d51c46553f1a507884b831da5c548f7"
        ),
        "worker_module_sha256": (
            "54ccbca2d7d9888dbe63e7af63985aaaf0e86019f164a27499ea4e2eb3da4484"
        ),
        "backend_module_sha256": (
            "96e46ae0d9c094b87bbaa52d89dc518a05240be25ed13d3fd772d0b1d67b173e"
        ),
        "network_isolation_module_sha256": (
            "6e46ae0d9c094b87bbaa52d89dc518a05240be25ed13d3fd772d0b1d67b173e"
        ),
        "requirements_lock_sha256": (
            "a722f050fd44030ce73e4b5f54e051d94759fe78bcddd98b0a7710280fc68679"
        ),
    },
    "settings": {
        "speaker_id": 0,
        "pitch_shift": 0,
        "f0_method": "rmvpe",
        "index_rate": 0.75,
        "rms_mix_rate": 1.0,
        "sample_rate": 48_000,
        "block_ms": 500,
        "crossfade_ms": 50,
        "context_ms": 2_500,
        "frame_ms": 20,
        "inference_batch_frames": 25,
        "queue_capacity_frames": 25,
        "resident_capacity_frames": 50,
        "formant_shift": 0.0,
        "threshold_dbfs": -60.0,
    },
}


def retained_profile() -> ModelProfile:
    return ModelProfile.model_validate(
        {
            "profile_id": "vc.rvc.synthetic-ja.v1",
            "kind": "voice_conversion",
            "readiness": "ready",
            "adapter_api_version": 1,
            "implementation_revision": (
                "liveconv-rvc-v2-worker-v1.4+rvc." + SOURCE_REVISION
            ),
            "weight_revision": f"sha256:{CHECKPOINT_SHA256}",
            "streaming": True,
            "cancellation": "cooperative",
            "input_sample_rates": [48_000],
            "output_sample_rates": [48_000],
            "frame_ms": 20,
            "minimum_context_ms": 500,
            "voice_requirement": "pretrained_voice",
            "warmup_policy": "lazy",
            "resource_class": "gpu",
            "license_record": "technical-validation-only",
            "promotion": {
                "status": "technical_validation",
                "pack_id": "rvc-v2",
                "pack_sha256": f"sha256:{'1' * 64}",
                "evidence_sha256": f"sha256:{'2' * 64}",
                "endpoint_sha256": f"sha256:{'3' * 64}",
            },
            "timeouts": {"first_output_ms": 15_000, "stall_ms": 5_000},
            "runtime": {
                "adapter": "worker",
                "configuration": RETAINED_CONFIGURATION,
                "worker_endpoint": sys.executable,
                "max_vram_mb": 2_048,
            },
        }
    )


def install_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LIVECONV_RVC_SOURCE_ROOT", str(tmp_path / "source"))
    monkeypatch.setenv("LIVECONV_RVC_SOURCE_REVISION", SOURCE_REVISION)
    monkeypatch.setenv("LIVECONV_RVC_V2_CHECKPOINT_PATH", str(tmp_path / "model.pth"))
    monkeypatch.setenv("LIVECONV_RVC_V2_CHECKPOINT_SHA256", CHECKPOINT_SHA256)
    monkeypatch.setenv("LIVECONV_RVC_V2_INDEX_PATH", str(tmp_path / "model.index"))
    monkeypatch.setenv("LIVECONV_RVC_V2_INDEX_SHA256", INDEX_SHA256)
    monkeypatch.setenv(
        "LIVECONV_RVC_V2_WORKER_WHEEL_PATH", str(tmp_path / "worker.whl")
    )
    monkeypatch.setenv("LIVECONV_RVC_V2_WORKER_WHEEL_SHA256", WORKER_WHEEL_SHA256)


def test_current_rvc_configuration_shape_has_a_stable_hash() -> None:
    profile = retained_profile()
    assert profile.configuration_hash == (
        "sha256:659b9be585882042038f50cfa355fd8cc3cf3efcf1d7e6278f258d324351db99"
    )


def test_rvc_environment_binds_every_model_artifact_without_protect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_environment(monkeypatch, tmp_path)
    environment, artifacts = _rvc_environment(
        retained_profile(), RETAINED_CONFIGURATION
    )

    assert "LIVECONV_RVC_V2_PROTECT" not in environment
    assert len(artifacts) == 7
    artifact_configuration = RETAINED_CONFIGURATION["artifacts"]
    assert isinstance(artifact_configuration, dict)
    assert {artifact.sha256 for artifact in artifacts} == {
        artifact_configuration[key]
        for key in {
            "checkpoint_sha256",
            "index_sha256",
            "hubert_config_sha256",
            "hubert_preprocessor_sha256",
            "hubert_weights_sha256",
            "rmvpe_sha256",
            "worker_wheel_sha256",
        }
    }


def test_external_rvc_supervisor_keeps_the_worker_budget_at_500_ms(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_environment(monkeypatch, tmp_path)
    supervisor = builtin_supervisor_factory(
        retained_profile(), "pipeline-1", queue_budget_ms=1_000
    )
    assert supervisor.input_capacity_frames == 25


def test_rvc_environment_rejects_a_gateway_source_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("LIVECONV_RVC_SOURCE_REVISION", "0" * 40)
    with pytest.raises(ValueError, match="source revision does not match"):
        _rvc_environment(retained_profile(), RETAINED_CONFIGURATION)


def test_rvc_variants_resolve_distinct_checkpoint_and_index_bindings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_environment(monkeypatch, tmp_path)
    profile = retained_profile()
    profile.profile_id = "vc.rvc-v2.amitaro-runrun.v1"
    checkpoint_sha = "a" * 64
    index_sha = "b" * 64
    configuration = deepcopy(RETAINED_CONFIGURATION)
    artifacts = configuration["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["checkpoint_sha256"] = checkpoint_sha
    artifacts["index_sha256"] = index_sha
    profile.runtime.configuration = configuration
    profile.weight_revision = f"sha256:{checkpoint_sha}"
    names = _rvc_model_environment_names(profile.profile_id)
    variant_checkpoint = tmp_path / "runrun.pth"
    variant_index = tmp_path / "runrun.index"
    monkeypatch.setenv(names["checkpoint_path"], str(variant_checkpoint))
    monkeypatch.setenv(names["checkpoint_sha256"], checkpoint_sha)
    monkeypatch.setenv(names["index_path"], str(variant_index))
    monkeypatch.setenv(names["index_sha256"], index_sha)

    environment, bound_artifacts = _rvc_environment(profile, configuration)

    assert environment["LIVECONV_RVC_V2_CHECKPOINT_PATH"] == str(variant_checkpoint)
    assert environment["LIVECONV_RVC_V2_INDEX_PATH"] == str(variant_index)
    assert {artifact.sha256 for artifact in bound_artifacts} >= {
        checkpoint_sha,
        index_sha,
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("worker_module", "workers.adapters.unreviewed.worker", "not approved"),
        ("unreviewed_configuration", True, "configuration shape is invalid"),
        ("command", ["/bin/sh", "-c", "id"], "configuration shape is invalid"),
        ("cwd", "/tmp", "configuration shape is invalid"),
        ("environment", {"UNREVIEWED": "1"}, "configuration shape is invalid"),
    ),
)
def test_worker_registration_rejects_unreviewed_profile_control(
    field: str,
    value: object,
    message: str,
) -> None:
    profile = retained_profile()
    configuration = deepcopy(RETAINED_CONFIGURATION)
    configuration[field] = value
    profile.runtime.configuration = configuration

    with pytest.raises(ValueError, match=message):
        validate_profile_adapter(profile)


def test_rvc_registration_owns_the_trusted_command_cwd_and_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("LIVECONV_UNREVIEWED_WORKER_ENVIRONMENT", "ignored")

    profile = retained_profile()
    worker_profile = worker_profile_for(profile, "pipeline-1", queue_budget_ms=1_000)

    assert worker_profile.command == (
        sys.executable,
        "-m",
        "workers.adapters.rvc_v2.worker",
    )
    assert worker_profile.cwd == Path("/tmp")
    assert worker_profile.input_capacity_frames == 25
    assert "LIVECONV_UNREVIEWED_WORKER_ENVIRONMENT" not in worker_profile.environment
    assert set(worker_profile.environment) == {
        "LIVECONV_RVC_SOURCE_ROOT",
        "LIVECONV_RVC_SOURCE_REVISION",
        "LIVECONV_RVC_V2_CHECKPOINT_PATH",
        "LIVECONV_RVC_V2_CHECKPOINT_SHA256",
        "LIVECONV_RVC_V2_WORKER_WHEEL_PATH",
        "LIVECONV_RVC_V2_WORKER_WHEEL_SHA256",
        "LIVECONV_RVC_V2_INDEX_PATH",
        "LIVECONV_RVC_V2_INDEX_SHA256",
        "LIVECONV_RVC_V2_SPEAKER_ID",
        "LIVECONV_RVC_V2_PITCH_SHIFT",
        "LIVECONV_RVC_V2_F0_METHOD",
        "LIVECONV_RVC_V2_INDEX_RATE",
        "LIVECONV_RVC_V2_RMS_MIX_RATE",
        "LIVECONV_RVC_V2_SAMPLE_RATE",
        "LIVECONV_RVC_V2_BLOCK_MS",
        "LIVECONV_RVC_V2_CROSSFADE_MS",
        "LIVECONV_RVC_V2_CONTEXT_MS",
        "LIVECONV_RVC_VERIFIED_ARTIFACT_1",
        "LIVECONV_RVC_VERIFIED_ARTIFACT_2",
        "LIVECONV_RVC_VERIFIED_ARTIFACT_3",
        "LIVECONV_RVC_VERIFIED_ARTIFACT_4",
    }


def test_runtime_worker_module_is_excluded_from_the_configuration_hash() -> None:
    profile = retained_profile()
    configuration = deepcopy(RETAINED_CONFIGURATION)
    configuration.pop("worker_module")
    profile.runtime.worker_module = "workers.adapters.rvc_v2.worker"
    profile.runtime.configuration = configuration

    validate_profile_adapter(profile)
    assert profile.configuration_hash == ModelProfile._canonical_hash(configuration)


def bridge_profile() -> ModelProfile:
    return ModelProfile.model_validate(
        {
            "profile_id": "test.bridge.v1",
            "kind": "deterministic_test",
            "readiness": "ready",
            "adapter_api_version": 1,
            "implementation_revision": "test-bridge-v1",
            "weight_revision": None,
            "streaming": True,
            "cancellation": "immediate",
            "input_sample_rates": [48_000],
            "output_sample_rates": [48_000],
            "frame_ms": 20,
            "minimum_context_ms": 0,
            "voice_requirement": "none",
            "warmup_policy": "none",
            "resource_class": "cpu",
            "license_record": "synthetic test profile",
            "timeouts": {"first_output_ms": 1_000, "stall_ms": 1_000},
            "runtime": {
                "adapter": "passthrough",
                "configuration": {},
                "worker_endpoint": None,
                "max_vram_mb": 0,
            },
        }
    )


def bridge_input(sequence: int) -> PcmFrame:
    return PcmFrame.from_samples(
        FrameHeader(
            kind=FrameKind.INPUT,
            generation_id=1,
            sequence=sequence,
            source_monotonic_ns=sequence + 1,
        ),
        [0.5] * 960,
    )


class ControllableSupervisor:
    input_capacity_frames = 2

    def __init__(self) -> None:
        self._active_generation_id: int | None = None
        self._outputs: asyncio.Queue[AudioFrame] = asyncio.Queue()
        self.fail_sequences: set[int] = set()
        self.block_before_output: set[int] = set()
        self.block_after_output: set[int] = set()
        self.started: dict[int, asyncio.Event] = {}
        self.published: dict[int, asyncio.Event] = {}
        self.release_before_output: dict[int, asyncio.Event] = {}
        self.release_after_output: dict[int, asyncio.Event] = {}

    async def start(self) -> None:
        return None

    async def start_generation(self, generation_id: int) -> None:
        self._active_generation_id = generation_id
        self._outputs = asyncio.Queue()

    async def push_audio(self, frame: AudioFrame) -> None:
        if frame.generation_id != self._active_generation_id:
            raise WorkerRuntimeError("WORKER_CRASH", "inactive generation")
        self._event(self.started, frame.sequence).set()
        if frame.sequence in self.fail_sequences:
            raise WorkerRuntimeError("WORKER_CRASH", "scripted push failure")
        if frame.sequence in self.block_before_output:
            await self._event(self.release_before_output, frame.sequence).wait()
        await self._outputs.put(frame)
        self._event(self.published, frame.sequence).set()
        if frame.sequence in self.block_after_output:
            await self._event(self.release_after_output, frame.sequence).wait()

    async def next_output(self) -> AudioFrame:
        return await self._outputs.get()

    async def end_generation(self, generation_id: int) -> None:
        if generation_id != self._active_generation_id:
            raise WorkerRuntimeError("WORKER_CRASH", "inactive generation")
        self._active_generation_id = None

    async def cancel_generation(self, generation_id: int) -> None:
        if generation_id == self._active_generation_id:
            self._active_generation_id = None
        self._release_all()

    async def close(self) -> None:
        self._active_generation_id = None
        self._release_all()

    @staticmethod
    def _event(
        events: dict[int, asyncio.Event],
        sequence: int,
    ) -> asyncio.Event:
        return events.setdefault(sequence, asyncio.Event())

    def _release_all(self) -> None:
        for event in (
            *self.release_before_output.values(),
            *self.release_after_output.values(),
        ):
            event.set()


async def start_bridge(supervisor: ControllableSupervisor) -> WorkerBridge:
    bridge = WorkerBridge(
        lambda _profile, _pipeline_id, _queue_budget_ms: supervisor,
        queue_budget_ms=500,
    )
    await bridge.start_generation(bridge_profile(), "pipeline-1", 1)
    return bridge


@pytest.mark.asyncio
async def test_worker_bridge_accepts_output_published_before_push_returns() -> None:
    supervisor = ControllableSupervisor()
    supervisor.block_after_output.add(0)
    bridge = await start_bridge(supervisor)
    try:
        push = asyncio.create_task(bridge.push_frame(bridge_input(0)))
        await supervisor._event(supervisor.published, 0).wait()

        output = await bridge.next_frame(1)
        assert output.header.sequence == 0

        supervisor._event(supervisor.release_after_output, 0).set()
        await push
    finally:
        await bridge.close()


@pytest.mark.asyncio
async def test_worker_bridge_rolls_back_the_exact_failed_reservation() -> None:
    supervisor = ControllableSupervisor()
    supervisor.block_before_output.add(0)
    supervisor.fail_sequences.add(1)
    bridge = await start_bridge(supervisor)
    try:
        first_push = asyncio.create_task(bridge.push_frame(bridge_input(0)))
        await supervisor._event(supervisor.started, 0).wait()

        with pytest.raises(ProtocolValidationError) as raised:
            await bridge.push_frame(bridge_input(1))
        assert raised.value.code == ErrorCode.WORKER_CRASH

        supervisor._event(supervisor.release_before_output, 0).set()
        await first_push
        assert (await bridge.next_frame(1)).header.sequence == 0

        await bridge.push_frame(bridge_input(2))
        assert (await bridge.next_frame(1)).header.sequence == 2
    finally:
        await bridge.close()


@pytest.mark.asyncio
async def test_worker_bridge_rolls_back_the_exact_cancelled_reservation() -> None:
    supervisor = ControllableSupervisor()
    supervisor.block_before_output.update({0, 1})
    bridge = await start_bridge(supervisor)
    try:
        first_push = asyncio.create_task(bridge.push_frame(bridge_input(0)))
        await supervisor._event(supervisor.started, 0).wait()
        cancelled_push = asyncio.create_task(bridge.push_frame(bridge_input(1)))
        await supervisor._event(supervisor.started, 1).wait()

        cancelled_push.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled_push

        supervisor._event(supervisor.release_before_output, 0).set()
        await first_push
        assert (await bridge.next_frame(1)).header.sequence == 0

        await bridge.push_frame(bridge_input(2))
        assert (await bridge.next_frame(1)).header.sequence == 2
    finally:
        await bridge.close()
