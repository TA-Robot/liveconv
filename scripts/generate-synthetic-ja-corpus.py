#!/usr/bin/env python3
"""Generate authorized synthetic Japanese audio for technical VC validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import wave
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SAMPLE_RATE = 24_000
SOURCE_SETTINGS = {"voice": "ja", "speed": 175, "pitch": 32, "gap": 5}
TARGET_TAKES = (
    {"voice": "ja", "speed": 132, "pitch": 72, "gap": 8},
    {"voice": "ja", "speed": 138, "pitch": 76, "gap": 8},
    {"voice": "ja", "speed": 144, "pitch": 80, "gap": 8},
    {"voice": "ja", "speed": 150, "pitch": 74, "gap": 8},
    {"voice": "ja", "speed": 136, "pitch": 82, "gap": 8},
    {"voice": "ja", "speed": 146, "pitch": 78, "gap": 8},
)
GENERATOR_REVISION = "liveconv-synthetic-ja-corpus-v1"
TREE_DIGEST_REVISION = "liveconv-synthetic-runtime-tree-v1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class AudioRecord:
    path: str
    sha256: str
    frames: int
    duration_seconds: float
    settings: dict[str, int | str]
    utterance_id: str
    role: str


class PublicationRollbackError(RuntimeError):
    """Publication failed and at least one recovery artifact must be retained."""

    def __init__(self, retained_paths: Sequence[Path]) -> None:
        self.retained_paths = tuple(path for path in retained_paths if path.exists())
        super().__init__(
            "corpus publication rollback failed; staged/backup artifacts were retained"
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("packages/evaluation/corpus/lv-001-ja-smoke-v1.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    return parser.parse_args(argv)


def command_version(command: str, *args: str) -> str:
    result = subprocess.run(
        [command, *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return (result.stdout or result.stderr).splitlines()[0].strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(path: Path) -> str:
    root = path.resolve(strict=True)
    if not root.is_dir():
        raise RuntimeError("runtime data artifact must be a directory")
    digest = hashlib.sha256((TREE_DIGEST_REVISION + "\0").encode("ascii"))
    files: list[Path] = []
    for item in root.rglob("*"):
        if item.is_symlink():
            raise RuntimeError("runtime data artifact must not contain symlinks")
        if item.is_file():
            files.append(item)
        elif not item.is_dir():
            raise RuntimeError("runtime data artifact contains a non-regular entry")
    if not files:
        raise RuntimeError("runtime data artifact must not be empty")
    for item in sorted(files, key=lambda value: value.relative_to(root).as_posix()):
        relative = item.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(item.stat().st_size.to_bytes(8, "big"))
        with item.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _repository_commit() -> str:
    result = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "--verify", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    revision = result.stdout.strip()
    if not _COMMIT_RE.fullmatch(revision):
        raise RuntimeError("generator repository revision is not immutable")
    return revision


def _command_artifact(command: str) -> tuple[Path, dict[str, str]]:
    located = shutil.which(command)
    if located is None:
        raise RuntimeError(f"required command is missing: {command}")
    executable = Path(located).resolve(strict=True)
    digest = sha256(executable)
    return executable, {
        "locator": f"artifact:sha256:{digest}",
        "sha256": digest,
    }


def _runtime_provenance() -> dict[str, Any]:
    espeak, espeak_artifact = _command_artifact("espeak-ng")
    ffmpeg, ffmpeg_artifact = _command_artifact("ffmpeg")
    espeak_version = command_version(str(espeak), "--version")
    match = re.search(r"\bData at:\s*(.+?)\s*$", espeak_version)
    if match is None:
        raise RuntimeError("espeak-ng did not identify its voice-data artifact")
    voice_data = Path(match.group(1)).resolve(strict=True)
    stable_espeak_version = espeak_version[: match.start()].strip()
    voice_data_digest = sha256_tree(voice_data)
    voice_inventory = subprocess.run(
        [str(espeak), "--voices=ja"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.encode("utf-8")
    return {
        "espeak_ng": {
            "version": stable_espeak_version,
            "executable": espeak_artifact,
            "voice": SOURCE_SETTINGS["voice"],
            "voice_data": {
                "locator": f"artifact-tree:sha256:{voice_data_digest}",
                "sha256": voice_data_digest,
                "digest_revision": TREE_DIGEST_REVISION,
            },
            "ja_voice_inventory_sha256": hashlib.sha256(voice_inventory).hexdigest(),
        },
        "ffmpeg": {
            "version": command_version(str(ffmpeg), "-version"),
            "executable": ffmpeg_artifact,
        },
        "sample_rate_hz": SAMPLE_RATE,
        "channels": 1,
        "sample_format": "pcm_s16le",
    }


def _validate_output_path(requested: Path, corpus_path: Path) -> Path:
    if requested.is_symlink():
        raise RuntimeError("output must not be a symlink")
    output = requested.resolve()
    if len(output.parts) < 3:
        raise RuntimeError("refusing unsafe broad output root")
    broad_system_roots = {
        Path("/usr/bin"),
        Path("/usr/include"),
        Path("/usr/lib"),
        Path("/usr/lib32"),
        Path("/usr/lib64"),
        Path("/usr/libexec"),
        Path("/usr/local"),
        Path("/usr/sbin"),
        Path("/usr/share"),
        Path("/usr/src"),
        Path("/var/cache"),
        Path("/var/lib"),
        Path("/var/local"),
        Path("/var/log"),
        Path("/var/spool"),
        Path("/var/tmp"),
    }
    if output in broad_system_roots:
        raise RuntimeError("refusing unsafe broad system output root")
    protected = {
        Path.cwd().resolve(),
        Path.home().resolve(),
        REPOSITORY_ROOT,
        Path(__file__).resolve(),
        corpus_path,
    }
    if any(output == item or output in item.parents for item in protected):
        raise RuntimeError("refusing output that contains a protected root or input")
    if output.exists() and not output.is_dir():
        raise RuntimeError("existing output must be a directory")
    return output


def _canonical_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_staged_corpus(root: Path, manifest: dict[str, Any]) -> None:
    records = [
        *manifest["source"],
        *manifest["target_training"],
        manifest["target_reference"],
    ]
    if len(records) != manifest["totals"]["file_count"]:
        raise RuntimeError("generated manifest file count is inconsistent")
    for record in records:
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("generated manifest contains an unsafe artifact path")
        artifact = root / relative
        if artifact.is_symlink() or not artifact.is_file():
            raise RuntimeError("generated manifest references a missing artifact")
        if sha256(artifact) != record["sha256"]:
            raise RuntimeError("generated artifact digest does not match manifest")
        inspect_audio(
            root,
            artifact,
            record["settings"],
            record["utterance_id"],
            record["role"],
        )
    unsigned = {key: value for key, value in manifest.items() if key != "integrity"}
    if manifest["integrity"]["sha256"] != _canonical_digest(unsigned):
        raise RuntimeError("generated manifest integrity digest is invalid")


def _fsync_tree(root: Path) -> None:
    directories = [root]
    for item in root.rglob("*"):
        if item.is_file():
            with item.open("rb") as artifact:
                os.fsync(artifact.fileno())
        elif item.is_dir():
            directories.append(item)
    for directory in reversed(directories):
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _reserve_backup_path(output: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{output.name}.backup-", dir=output.parent
    )
    os.close(descriptor)
    backup = Path(name)
    backup.unlink()
    return backup


def _publish_directory(staged: Path, output: Path) -> None:
    backup: Path | None = None
    published = False
    try:
        if output.exists():
            if output.is_symlink() or not output.is_dir():
                raise RuntimeError("existing output must be a non-symlink directory")
            backup = _reserve_backup_path(output)
            os.replace(output, backup)
        os.replace(staged, output)
        published = True
        descriptor = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except Exception:
        rollback_complete = True
        if published:
            try:
                os.replace(output, staged)
            except OSError:
                rollback_complete = False
        if backup is not None and backup.exists():
            try:
                os.replace(backup, output)
            except OSError:
                rollback_complete = False
        if not rollback_complete:
            retained = [staged]
            if backup is not None:
                retained.append(backup)
            raise PublicationRollbackError(retained) from None
        raise
    if backup is not None:
        shutil.rmtree(backup)


def render(text: str, settings: dict[str, int | str], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="liveconv-espeak-") as temp_dir:
        raw = Path(temp_dir) / "raw.wav"
        subprocess.run(
            [
                "espeak-ng",
                "-v",
                str(settings["voice"]),
                "-s",
                str(settings["speed"]),
                "-p",
                str(settings["pitch"]),
                "-g",
                str(settings["gap"]),
                "-w",
                str(raw),
                text,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(raw),
                "-ac",
                "1",
                "-ar",
                str(SAMPLE_RATE),
                "-c:a",
                "pcm_s16le",
                str(output),
            ],
            check=True,
        )


def inspect_audio(
    root: Path,
    path: Path,
    settings: dict[str, int | str],
    utterance_id: str,
    role: str,
) -> AudioRecord:
    with wave.open(str(path), "rb") as audio:
        if (
            audio.getnchannels(),
            audio.getsampwidth(),
            audio.getframerate(),
            audio.getcomptype(),
        ) != (1, 2, SAMPLE_RATE, "NONE"):
            raise RuntimeError(f"non-canonical generated WAV: {path}")
        frames = audio.getnframes()
    return AudioRecord(
        path=path.relative_to(root).as_posix(),
        sha256=sha256(path),
        frames=frames,
        duration_seconds=round(frames / SAMPLE_RATE, 6),
        settings=settings,
        utterance_id=utterance_id,
        role=role,
    )


def concatenate(root: Path, records: list[AudioRecord], output: Path) -> AudioRecord:
    output.parent.mkdir(parents=True, exist_ok=True)
    total_frames = 0
    with wave.open(str(output), "wb") as destination:
        destination.setnchannels(1)
        destination.setsampwidth(2)
        destination.setframerate(SAMPLE_RATE)
        for record in records:
            with wave.open(str(root / record.path), "rb") as source:
                frames = source.readframes(source.getnframes())
                destination.writeframes(frames)
                total_frames += source.getnframes()
    return AudioRecord(
        path=output.relative_to(root).as_posix(),
        sha256=sha256(output),
        frames=total_frames,
        duration_seconds=round(total_frames / SAMPLE_RATE, 6),
        settings={"composition": "ordered-wave-concatenation"},
        utterance_id="MULTI",
        role="target-reference",
    )


def serialize(record: AudioRecord) -> dict[str, Any]:
    return {
        "path": record.path,
        "sha256": record.sha256,
        "frames": record.frames,
        "duration_seconds": record.duration_seconds,
        "settings": record.settings,
        "utterance_id": record.utterance_id,
        "role": record.role,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    corpus_path = args.corpus.resolve(strict=True)
    output = _validate_output_path(args.output, corpus_path)
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    utterances = corpus["utterances"]
    if args.limit is not None:
        if args.limit <= 0:
            raise SystemExit("--limit must be positive")
        utterances = utterances[: args.limit]

    output.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    retain_recovery_artifacts = False
    try:
        runtime = _runtime_provenance()
        source_records: list[AudioRecord] = []
        target_records: list[AudioRecord] = []
        for utterance in utterances:
            utterance_id = utterance["id"]
            text = utterance["expected_spoken_text"]
            source_path = staged / "source" / f"{utterance_id}.wav"
            render(text, SOURCE_SETTINGS, source_path)
            source_records.append(
                inspect_audio(
                    staged,
                    source_path,
                    SOURCE_SETTINGS,
                    utterance_id,
                    "source-evaluation",
                )
            )
            for take_index, settings in enumerate(TARGET_TAKES, start=1):
                target_path = (
                    staged
                    / "target"
                    / "train"
                    / f"{utterance_id}-take-{take_index:02d}.wav"
                )
                render(text, settings, target_path)
                target_records.append(
                    inspect_audio(
                        staged,
                        target_path,
                        settings,
                        utterance_id,
                        "target-training",
                    )
                )

        reference = concatenate(
            staged,
            target_records[: min(4, len(target_records))],
            staged / "target" / "reference.wav",
        )
        all_records = source_records + target_records
        source_digest = sha256(corpus_path)
        generator_digest = sha256(Path(__file__).resolve(strict=True))
        manifest = {
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
                "locator": f"artifact:sha256:{source_digest}",
                "sha256": source_digest,
                "revision": corpus["revision"],
                "utterance_count": len(utterances),
            },
            "generator": {
                "implementation": GENERATOR_REVISION,
                "repository_commit": _repository_commit(),
                "script": {
                    "locator": f"artifact:sha256:{generator_digest}",
                    "sha256": generator_digest,
                },
            },
            "runtime": runtime,
            "source": [serialize(record) for record in source_records],
            "target_training": [serialize(record) for record in target_records],
            "target_reference": serialize(reference),
            "totals": {
                "source_seconds": round(
                    sum(record.duration_seconds for record in source_records), 6
                ),
                "target_training_seconds": round(
                    sum(record.duration_seconds for record in target_records), 6
                ),
                "file_count": len(all_records) + 1,
            },
        }
        manifest["integrity"] = {
            "algorithm": "sha256",
            "canonicalization": "utf8-json-sort-keys-compact-excluding-integrity-v1",
            "sha256": _canonical_digest(manifest),
        }
        manifest_path = staged / "synthetic-corpus.manifest.json"
        with manifest_path.open("w", encoding="utf-8", newline="\n") as destination:
            destination.write(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            )
            destination.flush()
            os.fsync(destination.fileno())
        _validate_staged_corpus(staged, manifest)
        _fsync_tree(staged)
        try:
            _publish_directory(staged, output)
        except PublicationRollbackError:
            retain_recovery_artifacts = True
            raise
    finally:
        if staged.exists() and not retain_recovery_artifacts:
            shutil.rmtree(staged)

    print(output / "synthetic-corpus.manifest.json")
    print(f"source_seconds={manifest['totals']['source_seconds']}")
    print(f"target_training_seconds={manifest['totals']['target_training_seconds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
