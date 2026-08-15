#!/usr/bin/env python3
"""Prepare and (only with an explicit lease) run the Beatrice 2 target train.

The runner deliberately keeps data admission separate from the upstream
trainer.  It reads the sealed X-VC manifest, extracts only its ``train`` rows,
and then delegates training to the pinned MIT trainer checkout.  No torch (or
other third-party package) is imported here; the prepare path is consequently
safe to exercise on a CPU-only host.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import wave
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "EXP-346"
EXPECTED_TRAINER_REVISION = "f34836de014b86956096878aecb8d3b17feaaa0b"
EXPECTED_MANIFEST_SHA256 = (
    "2f35e75f169c7cb5664f9f9cc201ff7e79c4d5ba2e700f5c769c6ba1f22f351a"
)
EXPECTED_ARCHIVE_SHA256 = (
    "1fc131f18554625038aaa9876bab0d75660f266ff5e9e18d74cdbb3e6e0df000"
)
EXPECTED_SPLIT_COUNTS = {"train": 334, "validation": 36, "heldout": 54}
EXPECTED_MEMBER_PREFIX = "ITAcorpus_amitaro_runrun/"
SAMPLE_RATE = 48_000
SAMPLE_WIDTH = 2


class RunnerError(RuntimeError):
    """An admission or execution precondition failed."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "ascii"
    )


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise RunnerError(f"cannot read {path}: {error}") from error
    return digest.hexdigest()


def _regular_file(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise RunnerError(f"{label} must be a regular file: {path}")
    return path


def _directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise RunnerError(f"{label} must be a real directory: {path}")
    return path


def load_manifest(path: Path) -> dict[str, Any]:
    _regular_file(path, "manifest")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RunnerError(f"manifest is not valid UTF-8 JSON: {path}") from error
    if not isinstance(document, dict):
        raise RunnerError("manifest must be a JSON object")

    declared = document.get("manifest_sha256")
    if declared != EXPECTED_MANIFEST_SHA256:
        raise RunnerError(
            "manifest declared SHA-256 is not the frozen EXP-346 value: "
            f"{declared!r}"
        )
    body = dict(document)
    body.pop("manifest_sha256", None)
    actual = sha256_bytes(canonical_json(body))
    if actual != declared:
        raise RunnerError(
            f"manifest self-hash mismatch: declared {declared}, calculated {actual}"
        )

    rows = document.get("rows")
    if not isinstance(rows, list) or len(rows) != sum(EXPECTED_SPLIT_COUNTS.values()):
        raise RunnerError("manifest must contain exactly 424 rows")
    split_counts = document.get("split_counts")
    if split_counts != EXPECTED_SPLIT_COUNTS:
        raise RunnerError(f"manifest split counts drifted: {split_counts!r}")
    sources = document.get("sources")
    if not isinstance(sources, dict):
        raise RunnerError("manifest sources are missing")
    target_archive = sources.get("target_archive")
    if not isinstance(target_archive, dict):
        raise RunnerError("manifest target archive binding is missing")
    if target_archive.get("sha256") != EXPECTED_ARCHIVE_SHA256:
        raise RunnerError("manifest target archive SHA-256 drifted")
    if target_archive.get("member_prefix") != EXPECTED_MEMBER_PREFIX:
        raise RunnerError("manifest target archive member prefix drifted")

    train_rows = []
    seen_ids: set[str] = set()
    seen_members: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise RunnerError("manifest row is not an object")
        row_id = row.get("row_id")
        if not isinstance(row_id, str) or not row_id or row_id in seen_ids:
            raise RunnerError("manifest row IDs must be nonempty and unique")
        seen_ids.add(row_id)
        split = row.get("split")
        if split not in EXPECTED_SPLIT_COUNTS:
            raise RunnerError(f"unsupported split for {row_id}: {split!r}")
        target_wav = row.get("target_wav")
        if not isinstance(target_wav, dict):
            raise RunnerError(f"target WAV binding missing for {row_id}")
        member = target_wav.get("archive_member")
        digest = target_wav.get("sha256")
        if not isinstance(member, str) or not member.startswith(EXPECTED_MEMBER_PREFIX):
            raise RunnerError(f"invalid target archive member for {row_id}")
        if ".." in Path(member).parts or member.endswith("/"):
            raise RunnerError(f"unsafe target archive member for {row_id}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise RunnerError(f"target SHA-256 missing for {row_id}")
        if member in seen_members:
            raise RunnerError(f"duplicate target archive member: {member}")
        seen_members.add(member)
        if split == "train":
            train_rows.append(row)
    expected = EXPECTED_SPLIT_COUNTS["train"]
    if len(train_rows) != expected:
        raise RunnerError(f"expected {expected} train rows, found {len(train_rows)}")
    return document


def validate_wav_bytes(payload: bytes, *, label: str, expected_frames: int | None = None) -> int:
    """Validate strict mono PCM16/48k WAV framing and return its frame count."""

    try:
        with wave.open(io.BytesIO(payload), "rb") as stream:
            if stream.getnchannels() != 1:
                raise RunnerError(f"{label} is not mono")
            if stream.getsampwidth() != SAMPLE_WIDTH:
                raise RunnerError(f"{label} is not PCM16")
            if stream.getframerate() != SAMPLE_RATE:
                raise RunnerError(f"{label} is not 48 kHz")
            if stream.getcomptype() != "NONE":
                raise RunnerError(f"{label} is compressed")
            frames = stream.getnframes()
            if frames <= 0:
                raise RunnerError(f"{label} is empty")
            pcm = stream.readframes(frames)
            if len(pcm) != frames * SAMPLE_WIDTH:
                raise RunnerError(f"{label} has truncated PCM payload")
    except (wave.Error, EOFError) as error:
        raise RunnerError(f"{label} is not a valid WAV: {error}") from error
    if expected_frames is not None and frames != expected_frames:
        raise RunnerError(f"{label} frame count drifted: {frames} != {expected_frames}")
    return frames


def _zip_member_is_regular(info: zipfile.ZipInfo) -> None:
    mode = (info.external_attr >> 16) & 0xFFFF
    if mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG):
        raise RunnerError(f"archive member is not a regular file: {info.filename}")


def validate_archive(path: Path) -> zipfile.ZipFile:
    _regular_file(path, "target archive")
    actual = sha256_file(path)
    if actual != EXPECTED_ARCHIVE_SHA256:
        raise RunnerError(
            f"target archive SHA-256 mismatch: expected {EXPECTED_ARCHIVE_SHA256}, got {actual}"
        )
    try:
        archive = zipfile.ZipFile(path)
        infos = archive.infolist()
    except (OSError, zipfile.BadZipFile) as error:
        raise RunnerError(f"target archive is not a readable ZIP: {path}") from error
    names: set[str] = set()
    for info in infos:
        if info.filename in names:
            archive.close()
            raise RunnerError(f"duplicate archive member: {info.filename}")
        names.add(info.filename)
        _zip_member_is_regular(info)
        parts = Path(info.filename).parts
        if info.filename.startswith("/") or ".." in parts:
            archive.close()
            raise RunnerError(f"archive path traversal member: {info.filename}")
    return archive


def train_rows(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = document.get("rows")
    assert isinstance(rows, list)
    selected = [row for row in rows if isinstance(row, dict) and row.get("split") == "train"]
    expected = EXPECTED_SPLIT_COUNTS["train"]
    if len(selected) != expected:
        raise RunnerError(f"selected row count drifted: {len(selected)} != {expected}")
    # Make it impossible for callers to accidentally use a validation/heldout row.
    if any(row.get("split") != "train" for row in selected):
        raise RunnerError("non-train row selected")
    return selected


def materialize_train_dataset(
    document: Mapping[str, Any], archive_path: Path, dataset_dir: Path
) -> dict[str, Any]:
    """Extract the 334 target WAVs into ``dataset_dir/amitaro``.

    The destination must be new or empty.  This prevents stale validation or
    heldout files from silently becoming part of a later trainer invocation.
    """

    archive = validate_archive(archive_path)
    try:
        selected = train_rows(document)
        expected_members = {
            row["target_wav"]["archive_member"] for row in selected if isinstance(row.get("target_wav"), dict)
        }
        names = set(archive.namelist())
        missing = expected_members - names
        if missing:
            raise RunnerError(f"archive is missing {len(missing)} selected target members")
        expected_count = EXPECTED_SPLIT_COUNTS["train"]
        if len(expected_members) != expected_count:
            raise RunnerError(
                f"selected target member set is not exactly {expected_count} unique files"
            )

        if dataset_dir.exists() and any(dataset_dir.iterdir()):
            raise RunnerError(f"dataset destination is not empty: {dataset_dir}")
        dataset_dir.mkdir(parents=True, exist_ok=True)
        speaker_dir = dataset_dir / "amitaro"
        speaker_dir.mkdir()
        records: list[dict[str, Any]] = []
        for row in selected:
            target = row["target_wav"]
            member = target["archive_member"]
            payload = archive.read(member)
            digest = sha256_bytes(payload)
            if digest != target["sha256"]:
                raise RunnerError(
                    f"target SHA-256 mismatch for {row['row_id']}: expected {target['sha256']}, got {digest}"
                )
            frames = validate_wav_bytes(
                payload,
                label=f"archive member {member}",
                expected_frames=target.get("frames"),
            )
            utterance_id = row.get("utterance_id")
            if not isinstance(utterance_id, str) or not utterance_id:
                raise RunnerError(f"utterance ID missing for {row['row_id']}")
            destination = speaker_dir / f"{utterance_id}.wav"
            if destination.exists():
                raise RunnerError(f"duplicate materialized target: {destination.name}")
            temporary = destination.with_suffix(".wav.tmp")
            temporary.write_bytes(payload)
            temporary.replace(destination)
            if sha256_file(destination) != digest:
                raise RunnerError(f"materialized SHA-256 mismatch: {destination}")
            records.append(
                {
                    "row_id": row["row_id"],
                    "utterance_id": utterance_id,
                    "split": "train",
                    "archive_member": member,
                    "sha256": digest,
                    "frames": frames,
                    "sample_rate_hz": SAMPLE_RATE,
                    "channels": 1,
                    "sample_width_bytes": SAMPLE_WIDTH,
                    "relative_path": str(destination.relative_to(dataset_dir)),
                }
            )
        if len(list(speaker_dir.glob("*.wav"))) != expected_count:
            raise RunnerError(
                "materialized speaker directory does not contain the expected WAV count"
            )
        return {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "manifest_sha256": document["manifest_sha256"],
            "archive_sha256": EXPECTED_ARCHIVE_SHA256,
            "split": "train",
            "count": len(records),
            "speaker": "amitaro",
            "records": records,
        }
    except KeyError as error:
        raise RunnerError(f"manifest train row is missing {error}") from error
    finally:
        archive.close()


def load_existing_materialization(
    document: Mapping[str, Any], archive_path: Path, dataset_dir: Path, receipt_path: Path
) -> dict[str, Any]:
    """Revalidate a prior prepare result before a later ``train`` invocation."""

    _regular_file(receipt_path, "materialization receipt")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RunnerError(f"materialization receipt is not valid JSON: {receipt_path}") from error
    if not isinstance(receipt, dict):
        raise RunnerError("materialization receipt must be an object")
    if receipt.get("experiment_id") != EXPERIMENT_ID:
        raise RunnerError("materialization receipt experiment drifted")
    if receipt.get("manifest_sha256") != document.get("manifest_sha256"):
        raise RunnerError("materialization receipt is bound to a different manifest")
    if receipt.get("archive_sha256") != EXPECTED_ARCHIVE_SHA256:
        raise RunnerError("materialization receipt archive binding drifted")
    expected_count = EXPECTED_SPLIT_COUNTS["train"]
    if receipt.get("split") != "train" or receipt.get("count") != expected_count:
        raise RunnerError("materialization receipt is not the exact train-only set")
    records = receipt.get("records")
    if not isinstance(records, list) or len(records) != expected_count:
        raise RunnerError("materialization receipt record count drifted")

    archive = validate_archive(archive_path)
    try:
        # Recheck the archive itself before trusting the copied files.  This is
        # intentionally a full archive hash check, not only a receipt lookup.
        selected = train_rows(document)
        expected_by_id = {row["row_id"]: row for row in selected}
        seen_paths: set[Path] = set()
        for record in records:
            if not isinstance(record, dict):
                raise RunnerError("materialization record is not an object")
            row_id = record.get("row_id")
            if row_id not in expected_by_id:
                raise RunnerError(f"materialization record is not a train row: {row_id!r}")
            if record.get("split") != "train" or record.get("speaker") not in (None, "amitaro"):
                raise RunnerError("materialization record split/speaker drifted")
            relative = record.get("relative_path")
            if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
                raise RunnerError("materialization record path is unsafe")
            target = expected_by_id[row_id]["target_wav"]
            if record.get("sha256") != target.get("sha256"):
                raise RunnerError(f"materialization record hash drifted for {row_id}")
            path = dataset_dir / relative
            if path.parent != dataset_dir / "amitaro" or path.suffix.lower() != ".wav":
                raise RunnerError(f"materialized path is outside amitaro/: {relative}")
            if path in seen_paths:
                raise RunnerError(f"duplicate materialized path: {relative}")
            seen_paths.add(path)
            _regular_file(path, "materialized target")
            payload = path.read_bytes()
            if sha256_bytes(payload) != record["sha256"]:
                raise RunnerError(f"materialized target hash mismatch: {path}")
            validate_wav_bytes(
                payload,
                label=str(path),
                expected_frames=target.get("frames"),
            )
        if not dataset_dir.is_dir() or set(dataset_dir.iterdir()) != {dataset_dir / "amitaro"}:
            raise RunnerError("materialized dataset contains a non-train speaker or extra file")
        speaker_dir = dataset_dir / "amitaro"
        if set(speaker_dir.glob("*.wav")) != seen_paths:
            raise RunnerError("materialized dataset has extra or missing WAVs")
        return receipt
    finally:
        archive.close()


def validate_trainer_and_runtime(trainer_root: Path, python: Path) -> dict[str, Path]:
    _directory(trainer_root, "trainer worktree")
    # A venv's ``bin/python`` is commonly a symlink to its interpreter.  It is
    # still accepted, while a missing/non-file path is rejected.
    if not python.is_file():
        raise RunnerError(f"isolated Python must be a file: {python}")
    if not os.access(python, os.X_OK):
        raise RunnerError(f"isolated Python is not executable: {python}")
    git_dir = trainer_root / ".git"
    if not git_dir.exists():
        raise RunnerError("trainer worktree must contain .git")
    try:
        result = subprocess.run(
            ["git", "-C", str(trainer_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RunnerError(f"cannot read trainer revision: {trainer_root}") from error
    revision = result.stdout.strip()
    if revision != EXPECTED_TRAINER_REVISION:
        raise RunnerError(
            f"trainer revision mismatch: expected {EXPECTED_TRAINER_REVISION}, got {revision}"
        )
    required_files = {
        "module": trainer_root / "beatrice_trainer" / "__main__.py",
        "defaults": trainer_root / "assets" / "default_config.json",
    }
    for label, path in required_files.items():
        _regular_file(path, f"trainer {label}")
    return required_files


def validate_training_assets(
    trainer_root: Path,
    ir_dir: Path | None,
    noise_dir: Path | None,
    test_dir: Path | None,
    phone_checkpoint: Path | None,
    pitch_checkpoint: Path | None,
    pretrained_checkpoint: Path | None,
) -> dict[str, Path]:
    paths = {
        "ir_dir": ir_dir or trainer_root / "assets" / "ir",
        "noise_dir": noise_dir or trainer_root / "assets" / "noise",
        "test_dir": test_dir or trainer_root / "assets" / "test",
        "phone_checkpoint": phone_checkpoint
        or trainer_root / "assets" / "pretrained" / "122_checkpoint_03000000.pt",
        "pitch_checkpoint": pitch_checkpoint
        or trainer_root / "assets" / "pretrained" / "104_3_checkpoint_00300000.pt",
        "pretrained_checkpoint": pretrained_checkpoint
        or trainer_root / "assets" / "pretrained" / "151_checkpoint_libritts_r_200_02750000.pt.gz",
    }
    for key in ("ir_dir", "noise_dir", "test_dir"):
        _directory(paths[key], f"trainer {key}")
        if not any(paths[key].iterdir()):
            raise RunnerError(f"trainer {key} is empty: {paths[key]}")
    for key in ("phone_checkpoint", "pitch_checkpoint", "pretrained_checkpoint"):
        _regular_file(paths[key], f"trainer {key}")
    return paths


def write_config(
    trainer_root: Path,
    dataset_dir: Path,
    output_dir: Path,
    assets: Mapping[str, Path],
    config_path: Path,
    *,
    smoke: bool,
) -> dict[str, Any]:
    defaults_path = trainer_root / "assets" / "default_config.json"
    try:
        config = json.loads(defaults_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RunnerError(f"cannot read upstream default config: {defaults_path}") from error
    if not isinstance(config, dict) or config.get("n_steps") != 10_000:
        raise RunnerError("upstream default config must retain n_steps=10000")
    config.update(
        {
            "data_dir": str(dataset_dir.resolve()),
            "out_dir": str(output_dir.resolve()),
            "in_ir_wav_dir": str(assets["ir_dir"].resolve()),
            "in_noise_wav_dir": str(assets["noise_dir"].resolve()),
            "in_test_wav_dir": str(assets["test_dir"].resolve()),
            "phone_extractor_file": str(assets["phone_checkpoint"].resolve()),
            "pitch_estimator_file": str(assets["pitch_checkpoint"].resolve()),
            "pretrained_file": str(assets["pretrained_checkpoint"].resolve()),
        }
    )
    if smoke:
        config["n_steps"] = 1
    elif config["n_steps"] != 10_000:
        raise RunnerError("non-smoke config may not change upstream n_steps=10000")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return config


def validate_existing_config(
    trainer_root: Path,
    config_path: Path,
    dataset_dir: Path,
    output_dir: Path,
    assets: Mapping[str, Path],
    *,
    smoke: bool,
) -> dict[str, Any]:
    """Check that a train command reuses the prepare-time config unchanged."""

    _regular_file(config_path, "training config")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        defaults = json.loads(
            (trainer_root / "assets" / "default_config.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RunnerError(f"training config is not valid JSON: {config_path}") from error
    if not isinstance(config, dict) or not isinstance(defaults, dict):
        raise RunnerError("training config/default config must be objects")
    expected_steps = 1 if smoke else 10_000
    if config.get("n_steps") != expected_steps:
        raise RunnerError("existing training config n_steps does not match this invocation")
    path_keys = {
        "data_dir",
        "out_dir",
        "in_ir_wav_dir",
        "in_noise_wav_dir",
        "in_test_wav_dir",
        "phone_extractor_file",
        "pitch_estimator_file",
        "pretrained_file",
    }
    for key, value in defaults.items():
        if key == "n_steps" or key in path_keys:
            continue
        if config.get(key) != value:
            raise RunnerError(f"existing training config changed upstream default: {key}")
    expected_paths = {
        "data_dir": dataset_dir.resolve(),
        "out_dir": output_dir.resolve(),
        "in_ir_wav_dir": assets["ir_dir"].resolve(),
        "in_noise_wav_dir": assets["noise_dir"].resolve(),
        "in_test_wav_dir": assets["test_dir"].resolve(),
        "phone_extractor_file": assets["phone_checkpoint"].resolve(),
        "pitch_estimator_file": assets["pitch_checkpoint"].resolve(),
        "pretrained_file": assets["pretrained_checkpoint"].resolve(),
    }
    for key, path in expected_paths.items():
        if Path(str(config.get(key, ""))).resolve() != path:
            raise RunnerError(f"existing training config path changed: {key}")
    return config


def _git_head(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RunnerError(f"cannot read repository HEAD for CUDA boundary: {repo_root}") from error
    return result.stdout.strip()


def launch_trainer(
    trainer_root: Path,
    python: Path,
    dataset_dir: Path,
    output_dir: Path,
    config_path: Path,
    *,
    lease: str | None,
    commit_before_cuda: str | None,
    repo_root: Path,
) -> int:
    if lease != "gpu0":
        raise RunnerError("CUDA launch requires --confirm-gpu-lease gpu0")
    if not commit_before_cuda:
        raise RunnerError(
            "CUDA launch requires --commit-before-cuda <workspace HEAD>; "
            "prepare and commit this runner before launching"
        )
    actual_head = _git_head(repo_root)
    if actual_head != commit_before_cuda:
        raise RunnerError(
            f"commit-before-CUDA boundary failed: expected {commit_before_cuda}, got {actual_head}"
        )
    command = [
        str(python),
        "-m",
        "beatrice_trainer",
        "-d",
        str(dataset_dir.resolve()),
        "-o",
        str(output_dir.resolve()),
        "-c",
        str(config_path.resolve()),
    ]
    print("launching pinned Beatrice trainer:", " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=trainer_root, check=False)
    return completed.returncode


def render_missing(_: argparse.Namespace) -> int:
    print(
        "EXP-346 render is not available in this slice: the upstream trainer "
        "does not ship a standalone checkpoint-to-WAV CLI. Train first, then "
        "add a pinned inference adapter before publishing audio.",
        file=sys.stderr,
    )
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("prepare", "train", "render"), default="prepare")
    parser.add_argument("--trainer-root", type=Path, required=True)
    parser.add_argument("--python", dest="python", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--target-archive", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--ir-dir", type=Path)
    parser.add_argument("--noise-dir", type=Path)
    parser.add_argument("--test-dir", type=Path)
    parser.add_argument("--phone-checkpoint", type=Path)
    parser.add_argument("--pitch-checkpoint", type=Path)
    parser.add_argument("--pretrained-checkpoint", type=Path)
    parser.add_argument("--confirm-gpu-lease")
    parser.add_argument("--commit-before-cuda")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--smoke", action="store_true", help="explicit one-step trainer gate")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "render":
        return render_missing(args)
    try:
        document = load_manifest(args.manifest)
        validate_trainer_and_runtime(args.trainer_root, args.python)
        assets = validate_training_assets(
            args.trainer_root,
            args.ir_dir,
            args.noise_dir,
            args.test_dir,
            args.phone_checkpoint,
            args.pitch_checkpoint,
            args.pretrained_checkpoint,
        )
        dataset_dir = args.work_dir / "dataset"
        output_dir = args.work_dir / "checkpoint"
        materialization_path = args.work_dir / "materialization.json"
        config_path = args.work_dir / "config.json"
        if args.command == "train" and materialization_path.is_file():
            materialization = load_existing_materialization(
                document, args.target_archive, dataset_dir, materialization_path
            )
        else:
            materialization = materialize_train_dataset(document, args.target_archive, dataset_dir)
            materialization_path.write_text(
                json.dumps(materialization, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if args.command == "train" and config_path.is_file():
            config = validate_existing_config(
                args.trainer_root,
                config_path,
                dataset_dir,
                output_dir,
                assets,
                smoke=args.smoke,
            )
        else:
            config = write_config(
                args.trainer_root,
                dataset_dir,
                output_dir,
                assets,
                config_path,
                smoke=args.smoke,
            )
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "manifest_sha256": document["manifest_sha256"],
                    "archive_sha256": EXPECTED_ARCHIVE_SHA256,
                    "trainer_revision": EXPECTED_TRAINER_REVISION,
                    "train_rows": materialization["count"],
                    "n_steps": config["n_steps"],
                    "dataset_dir": str(dataset_dir),
                    "config": str(config_path),
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        if args.command == "train":
            return launch_trainer(
                args.trainer_root,
                args.python,
                dataset_dir,
                output_dir,
                config_path,
                lease=args.confirm_gpu_lease,
                commit_before_cuda=args.commit_before_cuda,
                repo_root=args.repo_root,
            )
        return 0
    except RunnerError as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
