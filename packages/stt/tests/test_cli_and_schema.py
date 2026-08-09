from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest
from liveconv_evaluation import SttEvidence

from liveconv_stt.cli import main
from liveconv_stt.model_artifact import sha256_model_tree


class FakeBackend:
    def canonicalize_decode_config(self, config):
        return {**config, "fixed_language": "ja"}

    def transcribe(self, audio, *, language, decode_config):
        return "電話番号は09012345678です"


def make_cli_files(tmp_path: Path):
    model = tmp_path / "model"
    model.mkdir()
    (model / "fixture.bin").write_bytes(b"fixture model")
    digest = sha256_model_tree(model)
    decode = tmp_path / "decode.json"
    decode.write_text('{"beam_size": 1}', encoding="utf-8")
    return model, digest, decode


def cli_arguments(tmp_path, pcm_wav, model, digest, decode):
    return [
        "transcribe",
        str(pcm_wav),
        "--role",
        "source",
        "--backend",
        "faster-whisper",
        "--engine-revision",
        "fixture-stt==1.0.0",
        "--model-revision",
        f"fixture-ja@sha256:{digest}",
        "--model-artifact",
        str(model),
        "--model-sha256",
        digest,
        "--decode-config",
        str(decode),
        "--exact-entity",
        "09012345678",
        "--bundle-out",
        str(tmp_path / "source.bundle.json"),
        "--evidence-out",
        str(tmp_path / "source.evidence.json"),
        "--transcript-out",
        str(tmp_path / "source.txt"),
    ]


def test_cli_help_does_not_import_optional_backend(capsys):
    with pytest.raises(SystemExit) as captured:
        main(["transcribe", "--help"])

    assert captured.value.code == 0
    output = capsys.readouterr().out
    assert "--model-sha256" in output
    assert "--evidence-out" in output


def test_model_digest_command_outputs_only_digest(tmp_path, capsys):
    model, digest, _ = make_cli_files(tmp_path)
    assert main(["model-digest", str(model)]) == 0
    captured = capsys.readouterr()
    assert captured.out == digest + "\n"
    assert captured.err == ""


def test_cli_writes_schema_valid_private_bundle_and_compatible_evidence(
    tmp_path, pcm_wav, capsys
):
    model, digest, decode = make_cli_files(tmp_path)
    arguments = cli_arguments(tmp_path, pcm_wav, model, digest, decode)

    assert (
        main(
            arguments,
            backend_factory=lambda unused: FakeBackend(),
            clock=lambda: datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
        )
        == 0
    )

    assert capsys.readouterr() == ("", "")
    bundle_path = tmp_path / "source.bundle.json"
    evidence_path = tmp_path / "source.evidence.json"
    transcript_path = tmp_path / "source.txt"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    schema_path = (
        Path(__file__).parents[1] / "src/liveconv_stt/schemas/stt-bundle.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    ).validate(bundle)
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert SttEvidence.from_dict(evidence).provider == "fixture-stt==1.0.0"
    assert transcript_path.read_text(encoding="utf-8") == "電話番号は09012345678です\n"
    for path in (bundle_path, evidence_path, transcript_path):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_cli_redacts_backend_exception_details(tmp_path, pcm_wav, capsys):
    model, digest, decode = make_cli_files(tmp_path)
    arguments = cli_arguments(tmp_path, pcm_wav, model, digest, decode)

    class ExplodingBackend(FakeBackend):
        def transcribe(self, audio, *, language, decode_config):
            raise RuntimeError("private transcript and /private/audio.wav")

    with pytest.raises(SystemExit) as captured:
        main(arguments, backend_factory=lambda unused: ExplodingBackend())

    assert captured.value.code == 2
    error = capsys.readouterr().err
    assert "STT backend execution failed" in error
    assert "private transcript" not in error
    assert "/private/audio.wav" not in error
    assert not (tmp_path / "source.bundle.json").exists()


def test_cli_rejects_overlapping_output_paths(tmp_path, pcm_wav, capsys):
    model, digest, decode = make_cli_files(tmp_path)
    arguments = cli_arguments(tmp_path, pcm_wav, model, digest, decode)
    evidence_index = arguments.index("--evidence-out") + 1
    bundle_index = arguments.index("--bundle-out") + 1
    arguments[evidence_index] = arguments[bundle_index]

    with pytest.raises(SystemExit):
        main(arguments, backend_factory=lambda unused: FakeBackend())

    assert "must be distinct" in capsys.readouterr().err


@pytest.mark.parametrize("protected", ["input", "decode", "model_file"])
def test_cli_rejects_output_collision_with_inputs(tmp_path, pcm_wav, capsys, protected):
    model, digest, decode = make_cli_files(tmp_path)
    arguments = cli_arguments(tmp_path, pcm_wav, model, digest, decode)
    bundle_index = arguments.index("--bundle-out") + 1
    targets = {
        "input": pcm_wav,
        "decode": decode,
        "model_file": model / "fixture.bin",
    }
    original = targets[protected].read_bytes()
    arguments[bundle_index] = str(targets[protected])

    with pytest.raises(SystemExit):
        main(arguments, backend_factory=lambda unused: FakeBackend())

    assert "must not overlap" in capsys.readouterr().err
    assert targets[protected].read_bytes() == original


def test_cli_rolls_back_all_outputs_when_publication_fails(
    tmp_path, pcm_wav, capsys, monkeypatch
):
    model, digest, decode = make_cli_files(tmp_path)
    arguments = cli_arguments(tmp_path, pcm_wav, model, digest, decode)
    real_replace = os.replace
    publications = 0

    def fail_second_publication(source, target):
        nonlocal publications
        if ".backup." not in str(source):
            publications += 1
            if publications == 2:
                raise OSError("injected publication failure")
        real_replace(source, target)

    monkeypatch.setattr("liveconv_stt.cli.os.replace", fail_second_publication)

    with pytest.raises(SystemExit) as captured:
        main(arguments, backend_factory=lambda unused: FakeBackend())

    assert captured.value.code == 2
    assert "could not be published" in capsys.readouterr().err
    assert not (tmp_path / "source.bundle.json").exists()
    assert not (tmp_path / "source.evidence.json").exists()
    assert not (tmp_path / "source.txt").exists()


@pytest.mark.parametrize("failed_publication", [1, 2, 3])
def test_cli_restores_existing_outputs_after_each_publication_failure(
    tmp_path, pcm_wav, monkeypatch, failed_publication
):
    model, digest, decode = make_cli_files(tmp_path)
    arguments = cli_arguments(tmp_path, pcm_wav, model, digest, decode)
    targets = [
        tmp_path / "source.bundle.json",
        tmp_path / "source.evidence.json",
        tmp_path / "source.txt",
    ]
    for index, target in enumerate(targets):
        target.write_text(f"original-{index}\n", encoding="utf-8")
    real_replace = os.replace
    publications = 0

    def fail_selected_publication(source, target):
        nonlocal publications
        if ".backup." not in str(target):
            publications += 1
            if publications == failed_publication:
                raise OSError("injected publication failure")
        real_replace(source, target)

    monkeypatch.setattr("liveconv_stt.cli.os.replace", fail_selected_publication)

    with pytest.raises(SystemExit):
        main(arguments, backend_factory=lambda unused: FakeBackend())

    assert [target.read_text(encoding="utf-8") for target in targets] == [
        "original-0\n",
        "original-1\n",
        "original-2\n",
    ]
    assert not list(tmp_path.glob(".*.backup.*"))


def test_cli_retains_private_backup_when_rollback_itself_fails(
    tmp_path, pcm_wav, capsys, monkeypatch
):
    model, digest, decode = make_cli_files(tmp_path)
    arguments = cli_arguments(tmp_path, pcm_wav, model, digest, decode)
    targets = [
        tmp_path / "source.bundle.json",
        tmp_path / "source.evidence.json",
        tmp_path / "source.txt",
    ]
    for index, target in enumerate(targets):
        target.write_text(f"original-{index}\n", encoding="utf-8")
    real_replace = os.replace
    publications = 0

    def fail_publication_and_one_restore(source, target):
        nonlocal publications
        source_path = Path(source)
        target_path = Path(target)
        if ".backup." not in target_path.name:
            if ".backup." in source_path.name and target_path == targets[0]:
                raise OSError("injected rollback failure")
            if ".backup." not in source_path.name:
                publications += 1
                if publications == 2:
                    raise OSError("injected publication failure")
        real_replace(source, target)

    monkeypatch.setattr("liveconv_stt.cli.os.replace", fail_publication_and_one_restore)

    with pytest.raises(SystemExit) as captured:
        main(arguments, backend_factory=lambda unused: FakeBackend())

    assert captured.value.code == 2
    assert "private backups were retained" in capsys.readouterr().err
    retained = list(tmp_path.glob(".source.bundle.json.backup.*"))
    assert len(retained) == 1
    assert retained[0].read_text(encoding="utf-8") == "original-0\n"
    assert stat.S_IMODE(retained[0].stat().st_mode) == 0o600
