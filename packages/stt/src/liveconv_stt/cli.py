"""CLI for local, revision-pinned Japanese STT evidence generation."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .audio import InputLimits
from .backends.faster_whisper import ENGINE_REVISION, FasterWhisperBackend
from .errors import ConfigurationError, SttError
from .model_artifact import sha256_model_tree, verify_model_tree
from .runner import (
    SttBackend,
    transcribe_pcm_wav,
    validate_engine_revision,
    validate_model_revision,
)

MAX_DECODE_CONFIG_FILE_BYTES = 64 * 1024
BackendFactory = Callable[[argparse.Namespace], SttBackend]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="liveconv-stt",
        description=(
            "Generate redacted-provenance Japanese STT evidence from local PCM WAV"
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    digest = commands.add_parser(
        "model-digest",
        help="print the deterministic SHA-256 of a local model directory",
    )
    digest.add_argument("model_artifact", type=Path)

    transcribe = commands.add_parser(
        "transcribe", help="transcribe one bounded mono PCM16 WAV artifact"
    )
    transcribe.add_argument("input_wav", type=Path)
    transcribe.add_argument("--role", choices=("source", "output"), required=True)
    transcribe.add_argument("--backend", choices=("faster-whisper",), required=True)
    transcribe.add_argument("--engine-revision", required=True)
    transcribe.add_argument("--model-revision", required=True)
    transcribe.add_argument("--model-artifact", type=Path, required=True)
    transcribe.add_argument("--model-sha256", required=True)
    transcribe.add_argument("--decode-config", type=Path, required=True)
    transcribe.add_argument("--language", choices=("ja", "ja-JP"), default="ja")
    transcribe.add_argument("--exact-entity", action="append", default=[])
    transcribe.add_argument("--bundle-out", type=Path, required=True)
    transcribe.add_argument("--evidence-out", type=Path, required=True)
    transcribe.add_argument("--transcript-out", type=Path)
    transcribe.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    transcribe.add_argument("--compute-type", default="int8")
    transcribe.add_argument("--cpu-threads", type=int, default=4)
    transcribe.add_argument("--num-workers", type=int, default=1)
    transcribe.add_argument("--max-input-bytes", type=int, default=32 * 1024 * 1024)
    transcribe.add_argument("--max-duration-seconds", type=float, default=300.0)
    return parser


def _load_decode_config(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ConfigurationError(
                "decode configuration must be a regular non-symlink file"
            )
        with path.open("rb") as source:
            encoded = source.read(MAX_DECODE_CONFIG_FILE_BYTES + 1)
        if len(encoded) > MAX_DECODE_CONFIG_FILE_BYTES:
            raise ConfigurationError("decode configuration file exceeds the size limit")
        value = json.loads(encoded)
    except ConfigurationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ConfigurationError(
            "decode configuration could not be loaded as JSON"
        ) from None
    if not isinstance(value, dict):
        raise ConfigurationError("decode configuration must be a JSON object")
    return value


def _stage_private_output(path: Path, content: str) -> Path:
    temporary_path: str | None = None
    try:
        if not path.parent.is_dir():
            raise OSError
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        staged = Path(temporary_path)
        temporary_path = None
        return staged
    except OSError:
        raise ConfigurationError("output artifact could not be written") from None
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass


def _private_atomic_publish(outputs: Sequence[tuple[Path, str]]) -> None:
    staged: list[tuple[Path, Path]] = []
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    committed = False
    try:
        for target, content in outputs:
            staged.append((target, _stage_private_output(target, content)))

        for target, temporary in staged:
            if target.exists():
                if target.is_symlink() or not target.is_file():
                    raise OSError
                descriptor, raw_backup = tempfile.mkstemp(
                    prefix=f".{target.name}.backup.", dir=target.parent
                )
                os.close(descriptor)
                backup = Path(raw_backup)
                try:
                    os.replace(target, backup)
                except OSError:
                    backup.unlink(missing_ok=True)
                    raise
                backups[target] = backup
                os.chmod(backup, 0o600)
            os.replace(temporary, target)
            published.append(target)
        committed = True
    except OSError:
        rollback_complete = True
        for target in reversed(published):
            try:
                target.unlink(missing_ok=True)
            except OSError:
                rollback_complete = False
        for target, backup in reversed(tuple(backups.items())):
            try:
                if backup.exists():
                    os.replace(backup, target)
            except OSError:
                rollback_complete = False
        if not rollback_complete:
            raise ConfigurationError(
                "output publication rollback failed; private backups were retained"
            ) from None
        raise ConfigurationError("output artifacts could not be published") from None
    finally:
        for _, temporary in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        if committed:
            for backup in backups.values():
                try:
                    backup.unlink(missing_ok=True)
                except OSError:
                    pass


def _default_backend(arguments: argparse.Namespace) -> SttBackend:
    if (
        arguments.backend != "faster-whisper"
        or arguments.engine_revision != ENGINE_REVISION
    ):
        raise ConfigurationError(f"backend requires engine revision {ENGINE_REVISION}")
    return FasterWhisperBackend(
        arguments.model_artifact,
        expected_sha256=arguments.model_sha256,
        device=arguments.device,
        compute_type=arguments.compute_type,
        cpu_threads=arguments.cpu_threads,
        num_workers=arguments.num_workers,
    )


def _validated_outputs(arguments: argparse.Namespace) -> list[Path]:
    outputs = [arguments.bundle_out, arguments.evidence_out]
    if arguments.transcript_out is not None:
        outputs.append(arguments.transcript_out)
    resolved = [path.resolve() for path in outputs]
    if len(set(resolved)) != len(resolved):
        raise ConfigurationError("output artifact paths must be distinct")
    protected_files = {
        arguments.input_wav.resolve(),
        arguments.decode_config.resolve(),
    }
    model_root = arguments.model_artifact.resolve()
    for output in resolved:
        if output in protected_files:
            raise ConfigurationError("output artifact paths must not overlap inputs")
        if output == model_root or model_root in output.parents:
            raise ConfigurationError(
                "output artifact paths must not overlap the model artifact"
            )
    return resolved


def main(
    argv: Sequence[str] | None = None,
    *,
    backend_factory: BackendFactory | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "model-digest":
            sys.stdout.write(sha256_model_tree(arguments.model_artifact) + "\n")
            return 0

        output_paths = _validated_outputs(arguments)
        validate_engine_revision(arguments.engine_revision)
        verify_model_tree(arguments.model_artifact, arguments.model_sha256)
        validate_model_revision(arguments.model_revision, arguments.model_sha256)
        decode_config = _load_decode_config(arguments.decode_config)
        limits = InputLimits(
            max_input_bytes=arguments.max_input_bytes,
            max_duration_seconds=arguments.max_duration_seconds,
        )
        backend = (backend_factory or _default_backend)(arguments)
        bundle = transcribe_pcm_wav(
            str(arguments.input_wav),
            backend=backend,
            engine_revision=arguments.engine_revision,
            model_revision=arguments.model_revision,
            model_artifact_sha256=arguments.model_sha256,
            decode_config=decode_config,
            role=arguments.role,
            exact_entities=arguments.exact_entity,
            language=arguments.language,
            limits=limits,
            clock=clock,
        )
        serialized_bundle = (
            json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2, allow_nan=False)
            + "\n"
        )
        serialized_evidence = (
            json.dumps(
                bundle.stt_evidence.to_dict(),
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )
        outputs = [
            (output_paths[0], serialized_bundle),
            (output_paths[1], serialized_evidence),
        ]
        if arguments.transcript_out is not None:
            outputs.append((output_paths[2], bundle.transcript + "\n"))
        _private_atomic_publish(outputs)
        return 0
    except (SttError, ValueError) as error:
        parser.error(str(error))
    except Exception:
        parser.error("STT evidence generation failed")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
