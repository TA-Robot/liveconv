from __future__ import annotations

import hashlib
import json
import wave
from importlib import resources
from pathlib import Path

import jsonschema
import pytest

import liveconv_speaker.authorization as speaker_authorization
from liveconv_speaker.authorization import (
    REVIEWED_TARGET_REGISTRY_SHA256,
    ReviewedTarget,
    bind_target_authorization,
)
from liveconv_speaker.backend import SpeechBrainEcapaBackend
from liveconv_speaker.cli import _immutable_model_revision, main, parser
from liveconv_speaker.evidence import (
    SpeakerEvidenceError,
    inspect_pcm_wav,
    sha256_model_tree,
)
from liveconv_speaker.runtime import (
    RUNTIME_LOCK_REVISION,
    RUNTIME_LOCK_SHA256,
    RuntimeLock,
    _active_pins,
    _lock_bytes,
    verify_runtime_lock,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_TARGET_SHA256 = (
    "a92aaa78a600be0afa2425e55a8adb57dc0630789ce9a50284bf467345631ff7"
)
SYNTHETIC_AUTHORIZATION_SHA256 = (
    "6ccedfbd58e2d0ab6e2b463c91c1c38d92654857dd4cb63e2d2e8075d9e3284c"
)


def _canonical_digest(value) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _with_integrity(value: dict) -> dict:
    return {
        **value,
        "integrity": {
            "algorithm": "sha256",
            "canonicalization": ("utf8-json-sort-keys-compact-excluding-integrity-v1"),
            "sha256": _canonical_digest(value),
        },
    }


def _wav(path: Path, sample: int) -> Path:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24_000)
        audio.writeframes(sample.to_bytes(2, "little", signed=True) * 240)
    return path


def _authorization(path: Path, target: Path, *, digest: str | None = None) -> Path:
    record = {
        "schema_version": 1,
        "record_type": "reviewed-target-authorization",
        "type": "target-voice-authorization",
        "authorization_id": "fixture-target-v1",
        "status": "approved",
        "owner": "liveconv-test",
        "permitted_purpose": "technical validation",
        "retention_policy": "delete after test",
        "deletion_path": "fixture cleanup",
        "target_artifact_sha256": digest or inspect_pcm_wav(target).sha256,
        "source_id": "fixture-target-v1",
    }
    path.write_text(
        json.dumps(_with_integrity(record)),
        encoding="utf-8",
    )
    return path


def _reviewed_fixture(path: Path) -> ReviewedTarget:
    value = json.loads(path.read_text(encoding="utf-8"))
    record = {key: child for key, child in value.items() if key != "integrity"}
    return ReviewedTarget(record, _canonical_digest(record))


def _synthetic_manifest(path: Path, target_digest: str) -> Path:
    def artifact(role: str, artifact_path: str, digest: str) -> dict:
        settings = (
            {"composition": "ordered-wave-concatenation"}
            if role == "target-reference"
            else {"voice": "ja", "speed": 150, "pitch": 50, "gap": 5}
        )
        return {
            "path": artifact_path,
            "sha256": digest,
            "frames": 240,
            "duration_seconds": 0.01,
            "settings": settings,
            "utterance_id": "FIXTURE-001" if role != "target-reference" else "MULTI",
            "role": role,
        }

    value = {
        "schema_version": 1,
        "corpus_id": "liveconv-project-authored-synthetic-ja-v1",
        "purpose": "technical voice-conversion validation only",
        "authorization": {
            "classification": "project-authored-synthetic",
            "status": "approved",
            "contains_human_voice": False,
            "production_target_approval": "not-applicable-to-this-corpus",
        },
        "source_text": {
            "locator": "artifact:sha256:" + "a" * 64,
            "sha256": "a" * 64,
            "revision": "fixture@sha256:" + "a" * 64,
            "utterance_count": 1,
        },
        "generator": {
            "implementation": "liveconv-synthetic-ja-corpus-v1",
            "repository_commit": "b" * 40,
            "script": {
                "locator": "artifact:sha256:" + "c" * 64,
                "sha256": "c" * 64,
            },
        },
        "runtime": {
            "espeak_ng": {
                "version": "fixture-espeak==1.0",
                "executable": {
                    "locator": "artifact:sha256:" + "d" * 64,
                    "sha256": "d" * 64,
                },
                "voice": "ja",
                "voice_data": {
                    "locator": "artifact-tree:sha256:" + "e" * 64,
                    "sha256": "e" * 64,
                    "digest_revision": "liveconv-synthetic-runtime-tree-v1",
                },
                "ja_voice_inventory_sha256": "f" * 64,
            },
            "ffmpeg": {
                "version": "fixture-ffmpeg==1.0",
                "executable": {
                    "locator": "artifact:sha256:" + "1" * 64,
                    "sha256": "1" * 64,
                },
            },
            "sample_rate_hz": 24_000,
            "channels": 1,
            "sample_format": "pcm_s16le",
        },
        "source": [artifact("source-evaluation", "source/fixture.wav", "2" * 64)],
        "target_training": [
            artifact("target-training", "target/train/fixture.wav", "3" * 64)
        ],
        "target_reference": artifact(
            "target-reference", "target/reference.wav", target_digest
        ),
        "totals": {
            "source_seconds": 0.01,
            "target_training_seconds": 0.01,
            "file_count": 3,
        },
    }
    path.write_text(json.dumps(_with_integrity(value)), encoding="utf-8")
    return path


def _arguments(tmp_path: Path) -> tuple[list[str], Path, str]:
    source = _wav(tmp_path / "source.wav", 100)
    target = _wav(tmp_path / "target.wav", 200)
    converted = _wav(tmp_path / "converted.wav", 300)
    model = tmp_path / "model"
    model.mkdir()
    (model / "weights.bin").write_bytes(b"fixture-model")
    digest = sha256_model_tree(model)
    authorization = _authorization(tmp_path / "authorization.json", target)
    output = tmp_path / "speaker-evidence.json"
    return (
        [
            "compare",
            str(source),
            str(target),
            str(converted),
            "--model-artifact",
            str(model),
            "--model-sha256",
            digest,
            "--model-revision",
            f"fixture-ecapa@sha256:{digest}",
            "--policy-label",
            "approved fixture policy",
            "--policy-status",
            "approved",
            "--min-target-similarity",
            "0.8",
            "--min-target-gain",
            "0.1",
            "--min-target-advantage",
            "0.2",
            "--target-authorization",
            str(authorization),
            "--output",
            str(output),
        ],
        output,
        digest,
    )


class FakeBackend:
    def __init__(self, model_path, *, expected_sha256, device):
        self.runtime_lock = RuntimeLock(
            RUNTIME_LOCK_REVISION,
            RUNTIME_LOCK_SHA256,
            {
                "requests": "2.32.5",
                "speechbrain": "1.0.3",
                "torch": "2.6.0",
                "torchaudio": "2.6.0",
            },
        )
        self.embeddings = iter(((1.0, 0.0), (0.0, 1.0), (0.1, 0.9)))

    def embed(self, path):
        return next(self.embeddings)


def test_cli_binds_model_runtime_and_target_authorization(tmp_path, monkeypatch):
    arguments, output, digest = _arguments(tmp_path)
    authorization_path = Path(arguments[arguments.index("--target-authorization") + 1])
    reviewed = _reviewed_fixture(authorization_path)
    monkeypatch.setattr(
        "liveconv_speaker.authorization._reviewed_authorizations",
        lambda: (reviewed,),
    )

    assert main(arguments, backend_factory=FakeBackend) == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    schema = json.loads(
        (
            PACKAGE_ROOT / "src/liveconv_speaker/schemas/speaker-evidence.schema.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(report)
    assert report["evaluator"]["model_revision"] == (f"fixture-ecapa@sha256:{digest}")
    assert report["evaluator"]["runtime_lock"]["sha256"] == RUNTIME_LOCK_SHA256
    assert report["target_authorization"]["status"] == "approved"
    assert (
        report["target_authorization"]["target_artifact_sha256"]
        == (report["artifacts"]["target"]["sha256"])
    )


def test_parser_rejects_mutable_model_revision_and_requires_authorization(tmp_path):
    with pytest.raises(Exception, match="@sha256"):
        _immutable_model_revision("main")

    arguments, _, _ = _arguments(tmp_path)
    authorization_index = arguments.index("--target-authorization")
    del arguments[authorization_index : authorization_index + 2]
    with pytest.raises(SystemExit):
        parser().parse_args(arguments)


def test_model_revision_digest_mismatch_is_rejected_before_backend(tmp_path):
    arguments, _, _ = _arguments(tmp_path)
    revision_index = arguments.index("--model-revision") + 1
    arguments[revision_index] = "fixture-ecapa@sha256:" + "f" * 64
    called = False

    def backend_factory(*args, **kwargs):
        nonlocal called
        called = True
        return FakeBackend(*args, **kwargs)

    with pytest.raises(SystemExit):
        main(arguments, backend_factory=backend_factory)
    assert called is False


def test_target_authorization_must_bind_exact_target_audio(tmp_path):
    target = _wav(tmp_path / "target.wav", 200)
    authorization = _authorization(
        tmp_path / "authorization.json", target, digest="f" * 64
    )

    with pytest.raises(SpeakerEvidenceError, match="does not bind"):
        bind_target_authorization(
            inspect_pcm_wav(target).sha256,
            authorization_record=authorization,
        )


def test_synthetic_manifest_digest_binds_project_authored_target(tmp_path):
    manifest = _synthetic_manifest(
        tmp_path / "synthetic-corpus.manifest.json", SYNTHETIC_TARGET_SHA256
    )

    binding = bind_target_authorization(
        SYNTHETIC_TARGET_SHA256, synthetic_corpus_manifest=manifest
    )

    assert binding.authorization_type == "synthetic-corpus-manifest"
    assert binding.target_artifact_sha256 == SYNTHETIC_TARGET_SHA256
    assert binding.record_sha256 == SYNTHETIC_AUTHORIZATION_SHA256


def test_caller_authored_approved_target_is_rejected_when_unreviewed(tmp_path):
    target = _wav(tmp_path / "target.wav", 200)
    authorization = _authorization(tmp_path / "caller-approved.json", target)

    with pytest.raises(SpeakerEvidenceError, match="package-reviewed allowlist"):
        bind_target_authorization(
            inspect_pcm_wav(target).sha256,
            authorization_record=authorization,
        )


def test_reviewed_registry_rejects_tamper_with_recomputed_self_digest(
    tmp_path, monkeypatch
):
    registry = json.loads(
        resources.files("liveconv_speaker")
        .joinpath("authorizations/reviewed-targets.json")
        .read_text(encoding="utf-8")
    )
    registry["records"][0]["owner"] = "tampered owner"
    unsigned = {key: value for key, value in registry.items() if key != "integrity"}
    registry["integrity"]["sha256"] = _canonical_digest(unsigned)
    registry_dir = tmp_path / "authorizations"
    registry_dir.mkdir()
    (registry_dir / "reviewed-targets.json").write_text(
        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        speaker_authorization.importlib.resources, "files", lambda package: tmp_path
    )
    speaker_authorization._reviewed_authorizations.cache_clear()
    try:
        with pytest.raises(SpeakerEvidenceError, match="code-bound digest"):
            speaker_authorization._reviewed_authorizations()
    finally:
        speaker_authorization._reviewed_authorizations.cache_clear()


def test_current_reviewed_registry_matches_code_bound_digest():
    registry = resources.files("liveconv_speaker").joinpath(
        "authorizations/reviewed-targets.json"
    )

    assert hashlib.sha256(registry.read_bytes()).hexdigest() == (
        REVIEWED_TARGET_REGISTRY_SHA256
    )
    speaker_authorization._reviewed_authorizations.cache_clear()
    try:
        assert len(speaker_authorization._reviewed_authorizations()) == 1
    finally:
        speaker_authorization._reviewed_authorizations.cache_clear()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(unreviewed=True),
        lambda value: value["runtime"].update(sample_rate_hz=16_000),
        lambda value: value["target_reference"].update(frames=1),
        lambda value: value["integrity"].update(sha256="0" * 64),
    ],
)
def test_synthetic_authorization_requires_full_schema_and_integrity(tmp_path, mutation):
    manifest = _synthetic_manifest(
        tmp_path / "synthetic-corpus.manifest.json", SYNTHETIC_TARGET_SHA256
    )
    value = json.loads(manifest.read_text(encoding="utf-8"))
    mutation(value)
    if value["integrity"]["sha256"] != "0" * 64:
        unsigned = {key: child for key, child in value.items() if key != "integrity"}
        value["integrity"]["sha256"] = _canonical_digest(unsigned)
    manifest.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(SpeakerEvidenceError):
        bind_target_authorization(
            SYNTHETIC_TARGET_SHA256, synthetic_corpus_manifest=manifest
        )


def test_hash_locked_runtime_verifies_every_active_distribution_version():
    pins = _active_pins(_lock_bytes().decode("utf-8"))

    runtime = verify_runtime_lock(version_lookup=pins.__getitem__)

    assert runtime.sha256 == RUNTIME_LOCK_SHA256
    assert runtime.packages == pins
    assert pins["torch"] == pins["torchaudio"] == "2.6.0"
    assert pins["requests"] == "2.32.5"

    incompatible = dict(pins)
    incompatible["torch"] = "2.13.0"
    with pytest.raises(SpeakerEvidenceError, match="does not match lock"):
        verify_runtime_lock(version_lookup=incompatible.__getitem__)


def test_backend_verifies_runtime_lock_before_importing_model(tmp_path, monkeypatch):
    model = tmp_path / "model"
    model.mkdir()
    for name in (
        "hyperparams.yaml",
        "embedding_model.ckpt",
        "mean_var_norm_emb.ckpt",
        "classifier.ckpt",
        "label_encoder.txt",
        "custom.py",
    ):
        (model / name).write_text("fixture", encoding="utf-8")
    digest = sha256_model_tree(model)
    monkeypatch.setattr(
        "liveconv_speaker.backend.verify_runtime_lock",
        lambda: (_ for _ in ()).throw(SpeakerEvidenceError("runtime mismatch")),
    )

    with pytest.raises(SpeakerEvidenceError, match="runtime mismatch"):
        SpeechBrainEcapaBackend(model, expected_sha256=digest, device="cpu")
