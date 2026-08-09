from __future__ import annotations

import importlib.util
import json
import os
import sys
import wave
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[3] / "scripts" / "generate-synthetic-ja-corpus.py"
)


def _load_generator():
    spec = importlib.util.spec_from_file_location("liveconv_synthetic_corpus", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _corpus(path: Path, text: str = "日本語です") -> Path:
    path.write_text(
        json.dumps(
            {
                "revision": "fixture@sha256:" + "a" * 64,
                "utterances": [{"id": "FIXTURE-001", "expected_spoken_text": text}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _patch_runtime(monkeypatch, generator) -> None:
    monkeypatch.setattr(
        generator,
        "_runtime_provenance",
        lambda: {
            "espeak_ng": {
                "version": "fixture-espeak==1.0",
                "executable": {
                    "locator": "artifact:sha256:" + "b" * 64,
                    "sha256": "b" * 64,
                },
                "voice": "ja",
                "voice_data": {
                    "locator": "artifact-tree:sha256:" + "c" * 64,
                    "sha256": "c" * 64,
                    "digest_revision": generator.TREE_DIGEST_REVISION,
                },
                "ja_voice_inventory_sha256": "d" * 64,
            },
            "ffmpeg": {
                "version": "fixture-ffmpeg==1.0",
                "executable": {
                    "locator": "artifact:sha256:" + "e" * 64,
                    "sha256": "e" * 64,
                },
            },
            "sample_rate_hz": generator.SAMPLE_RATE,
            "channels": 1,
            "sample_format": "pcm_s16le",
        },
    )
    monkeypatch.setattr(generator, "_repository_commit", lambda: "f" * 40)
    monkeypatch.setattr(generator, "TARGET_TAKES", (generator.TARGET_TAKES[0],))

    def render(text, settings, output):
        if "\0" in text:
            raise ValueError("embedded NUL")
        output.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(generator.SAMPLE_RATE)
            audio.writeframes(bytes(480))

    monkeypatch.setattr(generator, "render", render)


def test_render_failure_preserves_previous_corpus_transactionally(
    tmp_path, monkeypatch
):
    generator = _load_generator()
    _patch_runtime(monkeypatch, generator)
    corpus = _corpus(tmp_path / "corpus.json", "unsafe\0text")
    output = tmp_path / "published"
    output.mkdir()
    previous = output / "previous-good-manifest.json"
    previous.write_text("good\n", encoding="utf-8")

    with pytest.raises(ValueError, match="embedded NUL"):
        generator.main(["--corpus", str(corpus), "--output", str(output)])

    assert previous.read_text(encoding="utf-8") == "good\n"
    assert list(tmp_path.glob(".published.staging-*")) == []


def test_rejects_repository_and_broad_output_roots_before_render(tmp_path):
    generator = _load_generator()
    corpus = _corpus(tmp_path / "corpus.json")

    for unsafe in (
        generator.REPOSITORY_ROOT,
        Path("/"),
        Path("/usr/local"),
        Path.cwd(),
    ):
        with pytest.raises(RuntimeError, match="unsafe|protected"):
            generator.main(["--corpus", str(corpus), "--output", str(unsafe)])

    bounded = Path("/usr/local/liveconv-synthetic-corpus-fixture")
    assert generator._validate_output_path(bounded, corpus.resolve()) == bounded


def test_publication_failure_rolls_back_existing_directory(tmp_path, monkeypatch):
    generator = _load_generator()
    output = tmp_path / "published"
    output.mkdir()
    (output / "previous.txt").write_text("previous", encoding="utf-8")
    staged = tmp_path / ".published.staging-fixture"
    staged.mkdir()
    (staged / "next.txt").write_text("next", encoding="utf-8")
    real_replace = os.replace

    def fail_staged_publish(source, target):
        if Path(source) == staged and Path(target) == output:
            raise OSError("simulated publication failure")
        return real_replace(source, target)

    monkeypatch.setattr(generator.os, "replace", fail_staged_publish)

    with pytest.raises(OSError, match="simulated"):
        generator._publish_directory(staged, output)

    assert (output / "previous.txt").read_text(encoding="utf-8") == "previous"
    assert (staged / "next.txt").read_text(encoding="utf-8") == "next"
    assert list(tmp_path.glob(".published.backup-*")) == []


def test_outer_finally_retains_recovery_artifacts_after_rollback_failure(
    tmp_path, monkeypatch
):
    generator = _load_generator()
    _patch_runtime(monkeypatch, generator)
    corpus = _corpus(tmp_path / "corpus.json")
    output = tmp_path / "published"
    output.mkdir()
    (output / "previous.txt").write_text("previous", encoding="utf-8")
    retained: dict[str, Path] = {}

    def fail_with_recovery_artifacts(staged, destination):
        backup = destination.parent / ".published.backup-injected"
        backup.mkdir()
        (backup / "previous.txt").write_text("previous", encoding="utf-8")
        retained.update(staged=staged, backup=backup)
        raise generator.PublicationRollbackError((staged, backup))

    monkeypatch.setattr(generator, "_publish_directory", fail_with_recovery_artifacts)

    with pytest.raises(generator.PublicationRollbackError, match="retained"):
        generator.main(["--corpus", str(corpus), "--output", str(output)])

    assert retained["staged"].is_dir()
    assert (retained["staged"] / "synthetic-corpus.manifest.json").is_file()
    assert (retained["backup"] / "previous.txt").read_text(encoding="utf-8") == (
        "previous"
    )


def test_manifest_is_path_spelling_stable_and_binds_generator_runtime_artifacts(
    tmp_path, monkeypatch
):
    generator = _load_generator()
    _patch_runtime(monkeypatch, generator)
    corpus = _corpus(tmp_path / "corpus.json")
    monkeypatch.chdir(tmp_path)

    generator.main(["--corpus", "corpus.json", "--output", "relative-output"])
    generator.main(
        [
            "--corpus",
            str(corpus.resolve()),
            "--output",
            str((tmp_path / "absolute-output").resolve()),
        ]
    )

    relative_manifest = (
        tmp_path / "relative-output" / "synthetic-corpus.manifest.json"
    ).read_bytes()
    absolute_manifest = (
        tmp_path / "absolute-output" / "synthetic-corpus.manifest.json"
    ).read_bytes()
    assert relative_manifest == absolute_manifest

    manifest = json.loads(relative_manifest)
    assert set(manifest["source_text"]) == {
        "locator",
        "sha256",
        "revision",
        "utterance_count",
    }
    assert manifest["source_text"]["locator"].startswith("artifact:sha256:")
    assert manifest["generator"]["repository_commit"] == "f" * 40
    assert manifest["generator"]["script"]["sha256"]
    assert manifest["runtime"]["espeak_ng"]["executable"]["sha256"] == "b" * 64
    assert manifest["runtime"]["espeak_ng"]["voice_data"]["sha256"] == "c" * 64
    unsigned = {key: value for key, value in manifest.items() if key != "integrity"}
    assert manifest["integrity"]["sha256"] == generator._canonical_digest(unsigned)
