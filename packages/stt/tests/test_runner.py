from __future__ import annotations

import hashlib
from collections import UserList
from datetime import UTC, datetime

import pytest
from liveconv_evaluation import SttEvidence
from liveconv_evaluation import normalize_japanese as evaluation_normalize

from liveconv_stt import (
    NORMALIZATION_REVISION,
    BackendExecutionError,
    ConfigurationError,
    normalize_japanese,
    transcribe_pcm_wav,
)

DIGEST = "a" * 64
ENGINE_REVISION = "fixture-stt==1.0.0"
MODEL_REVISION = f"fixture-ja@sha256:{DIGEST}"


class FakeBackend:
    def __init__(self, transcript="電話番号は09012345678、音声はカタカナです"):
        self.transcript = transcript
        self.calls = []

    def canonicalize_decode_config(self, config):
        return {**config, "resolved_option": "fixed"}

    def transcribe(self, audio, *, language, decode_config):
        self.calls.append((audio, language, decode_config))
        return self.transcript


def run(pcm_wav, backend=None, **overrides):
    arguments = {
        "backend": backend or FakeBackend(),
        "engine_revision": ENGINE_REVISION,
        "model_revision": MODEL_REVISION,
        "model_artifact_sha256": DIGEST,
        "decode_config": {"beam_size": 1},
        "role": "source",
        "exact_entities": ["09012345678", "カタカナ"],
        "clock": lambda: datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
    }
    arguments.update(overrides)
    return transcribe_pcm_wav(str(pcm_wav), **arguments)


def test_emits_provenance_normalization_digest_and_exact_entities(pcm_wav):
    backend = FakeBackend()
    bundle = run(pcm_wav, backend)
    value = bundle.to_dict()

    assert value["role"] == "source"
    assert value["engine_revision"] == ENGINE_REVISION
    assert value["model_revision"] == MODEL_REVISION
    assert value["model_artifact_sha256"] == DIGEST
    assert (
        value["audio_artifact"]["sha256"]
        == hashlib.sha256(pcm_wav.read_bytes()).hexdigest()
    )
    assert value["normalized_transcript"] == "電話番号は09012345678音声はかたかなです"
    assert value["exact_entities"]["matched"] == ["09012345678", "カタカナ"]
    assert value["exact_entities"]["exact_match_rate"] == 1.0
    assert value["stt_evidence"]["provider"] == ENGINE_REVISION
    assert value["stt_evidence"]["decode_config"] == {
        "beam_size": 1,
        "resolved_option": "fixed",
    }
    assert value["stt_evidence"]["transcribed_at"] == "2026-08-09T12:00:00Z"
    assert value["stt_evidence"]["normalization_revision"] == NORMALIZATION_REVISION
    assert backend.calls[0][1] == "ja"


def test_evidence_is_accepted_by_evaluation_contract(pcm_wav):
    evidence = SttEvidence.from_dict(run(pcm_wav).stt_evidence.to_dict())

    assert evidence.provider == ENGINE_REVISION
    assert evidence.model_revision == MODEL_REVISION
    assert evidence.normalization_revision == NORMALIZATION_REVISION


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("engine_revision", "fixture-stt@latest", "name==version"),
        ("engine_revision", "fixture-stt==latest", "name==version"),
        ("model_revision", "fixture-ja@main", "@sha256"),
        ("model_revision", "fixture-ja@sha256:ABC", "@sha256"),
    ],
)
def test_rejects_mutable_or_malformed_revisions(pcm_wav, field, value, message):
    with pytest.raises(ConfigurationError, match=message):
        run(pcm_wav, **{field: value})


def test_rejects_model_revision_artifact_digest_mismatch(pcm_wav):
    with pytest.raises(ConfigurationError, match="does not match"):
        run(pcm_wav, model_artifact_sha256="b" * 64)


@pytest.mark.parametrize(
    "decode_config",
    [
        {},
        {"api_token": "not-recordable"},
        {"nested": {"initial_prompt": "restricted transcript"}},
        {"temperature": float("nan")},
        {"unsupported": object()},
    ],
)
def test_rejects_empty_sensitive_or_non_json_decode_configuration(
    pcm_wav, decode_config
):
    with pytest.raises(ConfigurationError):
        run(pcm_wav, decode_config=decode_config)


def test_allows_pinned_tokenizers_runtime_package_provenance(pcm_wav):
    class RuntimeProvenanceBackend(FakeBackend):
        def canonicalize_decode_config(self, config):
            return {
                **config,
                "runtime_packages": {"tokenizers": "0.23.1"},
            }

    bundle = run(pcm_wav, RuntimeProvenanceBackend())

    assert bundle.stt_evidence.decode_config["runtime_packages"] == {
        "tokenizers": "0.23.1"
    }


@pytest.mark.parametrize(
    "sensitive_key",
    [
        "api_key",
        "api-key",
        "access_key",
        "access-key",
        "private_key",
        "private-key",
    ],
)
def test_rejects_common_credential_key_names_at_any_depth(pcm_wav, sensitive_key):
    with pytest.raises(ConfigurationError, match="forbidden sensitive field"):
        run(pcm_wav, decode_config={"nested": {sensitive_key: "not-recordable"}})


@pytest.mark.parametrize(
    "decode_config",
    [
        {"tokenizers": "0.23.1"},
        {"other": {"tokenizers": "0.23.1"}},
        {"runtime_packages": {"nested": {"tokenizers": "0.23.1"}}},
        {"Runtime_Packages": {"tokenizers": "0.23.1"}},
        {"runtime_packages": {"Tokenizers": "0.23.1"}},
    ],
)
def test_tokenizers_exception_is_restricted_to_runtime_package_provenance(
    pcm_wav, decode_config
):
    with pytest.raises(ConfigurationError, match="forbidden sensitive field"):
        run(pcm_wav, decode_config=decode_config)


@pytest.mark.parametrize(
    "container",
    [
        ({"api_key": "not-recordable"},),
        UserList([{"private-key": "not-recordable"}]),
    ],
)
def test_rejects_sensitive_keys_inside_every_sequence_container(pcm_wav, container):
    with pytest.raises(ConfigurationError, match="forbidden sensitive field"):
        run(pcm_wav, decode_config={"safe": container})


def test_tokenizers_exception_cannot_be_reached_through_a_sequence(pcm_wav):
    with pytest.raises(ConfigurationError, match="forbidden sensitive field"):
        run(
            pcm_wav,
            decode_config={"runtime_packages": ({"tokenizers": "0.23.1"},)},
        )


def test_backend_exception_detail_is_redacted(pcm_wav, caplog, capsys):
    class ExplodingBackend(FakeBackend):
        def transcribe(self, audio, *, language, decode_config):
            raise RuntimeError("restricted raw transcript and /secret/audio.wav")

    with pytest.raises(BackendExecutionError) as captured:
        run(pcm_wav, ExplodingBackend())

    assert "restricted" not in str(captured.value)
    assert "secret" not in str(captured.value)
    assert not caplog.records
    assert capsys.readouterr() == ("", "")


def test_requires_timezone_aware_clock(pcm_wav):
    with pytest.raises(ConfigurationError, match="timezone-aware"):
        run(pcm_wav, clock=lambda: datetime(2026, 8, 9, 12, 0))


def test_normalizer_is_byte_for_byte_compatible_with_evaluation():
    samples = [" ＡＢＣ１２３、カタカナ。\n", "日本", "０９０－１２３４"]
    for sample in samples:
        assert normalize_japanese(sample) == evaluation_normalize(sample)
