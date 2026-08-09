from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

from liveconv_stt import ArtifactVerificationError, read_pcm_wav, sha256_model_tree
from liveconv_stt.backends.faster_whisper import FasterWhisperBackend, _runtime_lock
from liveconv_stt.errors import ConfigurationError
from liveconv_stt.model_artifact import verify_model_tree


def model_tree(tmp_path):
    root = tmp_path / "model"
    root.mkdir()
    (root / "config.json").write_text("{}", encoding="utf-8")
    (root / "model.bin").write_bytes(b"model")
    (root / "tokenizer.json").write_text("{}", encoding="utf-8")
    return root


def test_model_tree_digest_ignores_mtime_but_detects_content(tmp_path):
    root = model_tree(tmp_path)
    first = sha256_model_tree(root)
    os.utime(root / "model.bin", (1, 1))
    assert sha256_model_tree(root) == first

    (root / "model.bin").write_bytes(b"changed")
    assert sha256_model_tree(root) != first


def test_model_tree_rejects_symlinks_and_digest_mismatch(tmp_path):
    root = model_tree(tmp_path)
    (root / "linked.bin").symlink_to(root / "model.bin")
    with pytest.raises(ArtifactVerificationError, match="symlinks"):
        sha256_model_tree(root)

    (root / "linked.bin").unlink()
    with pytest.raises(ArtifactVerificationError, match="does not match"):
        verify_model_tree(root, "0" * 64)


def test_faster_whisper_uses_verified_local_model_and_lazy_segments(
    tmp_path, pcm_wav, monkeypatch
):
    root = model_tree(tmp_path)
    digest = sha256_model_tree(root)
    observed = {}

    class WhisperModel:
        def __init__(self, model_path, **options):
            observed["model_path"] = model_path
            observed["init"] = options

        def transcribe(self, samples, **options):
            observed["sample_count"] = len(samples)
            observed["transcribe"] = options

            def segments():
                yield SimpleNamespace(text=" 日本語")
                yield SimpleNamespace(text="です ")

            return segments(), SimpleNamespace(language="ja")

    runtime_digest, runtime_versions = _runtime_lock()
    monkeypatch.setattr("importlib.metadata.version", runtime_versions.__getitem__)
    monkeypatch.setitem(
        sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=WhisperModel)
    )

    backend = FasterWhisperBackend(root, expected_sha256=digest)
    config = backend.canonicalize_decode_config({"beam_size": 1, "temperature": 0.0})
    transcript = backend.transcribe(
        read_pcm_wav(pcm_wav), language="ja", decode_config=config
    )

    assert observed["init"]["local_files_only"] is True
    assert observed["model_path"] == str(root)
    assert observed["sample_count"] > 0
    assert observed["transcribe"]["language"] == "ja"
    assert observed["transcribe"]["log_progress"] is False
    assert config["runtime_packages"]["ctranslate2"] == "4.8.1"
    assert config["runtime_packages"]["huggingface-hub"] == "1.27.0"
    assert config["runtime_packages"]["pyyaml"] == "6.0.3"
    assert config["runtime_packages"]["setuptools"] == "84.0.0"
    assert config["runtime_packages"]["tqdm"] == "4.70.0"
    assert config["runtime_lock_sha256"] == runtime_digest
    assert transcript == "日本語です"


def test_faster_whisper_rejects_mismatched_transitive_runtime(tmp_path, monkeypatch):
    root = model_tree(tmp_path)
    digest = sha256_model_tree(root)
    _, runtime_versions = _runtime_lock()

    def installed_version(name):
        if name == "huggingface-hub":
            return "0.0.0"
        return runtime_versions[name]

    monkeypatch.setattr("importlib.metadata.version", installed_version)

    with pytest.raises(ConfigurationError, match="runtime revisions"):
        FasterWhisperBackend(root, expected_sha256=digest)


def test_runtime_lock_is_complete_and_content_addressed():
    digest, versions = _runtime_lock()

    assert digest.startswith("sha256:") and len(digest) == 71
    assert versions["faster-whisper"] == "1.2.1"
    assert {"huggingface-hub", "tqdm", "pyyaml", "setuptools"} <= versions.keys()


def test_faster_whisper_requires_local_tokenizer_before_engine_import(tmp_path):
    root = model_tree(tmp_path)
    (root / "tokenizer.json").unlink()
    digest = sha256_model_tree(root)

    with pytest.raises(ArtifactVerificationError, match="incomplete"):
        FasterWhisperBackend(root, expected_sha256=digest)
