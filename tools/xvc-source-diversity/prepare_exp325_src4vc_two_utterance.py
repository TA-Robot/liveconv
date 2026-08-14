#!/usr/bin/env python3
"""Materialize the matched EXP-325/326 two-utterance SRC4VC source pool.

The SRC4VC archive is private and is prepared by ``fetch_src4vc_subset.py``
into two ignored roots: one for train utterance index zero and one for index
one.  This module only admits those already-materialized manifests.  It never
fetches or decodes model output.

The output order is deliberately simple and auditable::

    SRC4VC001/u0, SRC4VC001/u1, SRC4VC002/u0, SRC4VC002/u1, ...

The 170 rows receive the exact ordered EXP-238 real Amitaro target references.
The resulting ``pool.json`` and copied private WAVs are suitable inputs for a
fresh teacher renderer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import wave
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from fetch_src4vc_subset import OUTPUT_KIND as SRC4VC_KIND
from fetch_src4vc_subset import heldout_speakers

EXP238_KIND = "liveconv-exp238-cross-corpus-control69-pseudoparallel-inputs/v1"
OUTPUT_KIND = "liveconv-exp325-326-src4vc-two-utterance-pool/v1"
SOURCE_LICENSE = "SRC4VC research-use; redistribution prohibited"

EXPECTED_ROWS = 170
EXPECTED_TRAIN_SPEAKERS = 85
EXPECTED_HELDOUT_SPEAKERS = 15
EXPECTED_SUBSET_ROWS = 115
EXPECTED_TRAIN_UTTERANCE_INDICES = (0, 1)


class Src4vcTwoUtteranceError(RuntimeError):
    """The two-utterance source pool cannot be admitted safely."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Src4vcTwoUtteranceError(f"invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise Src4vcTwoUtteranceError(f"JSON object required: {path}")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise Src4vcTwoUtteranceError(f"audio unavailable: {path}") from error
    return digest.hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _safe_relative(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise Src4vcTwoUtteranceError(f"{label} path is malformed")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise Src4vcTwoUtteranceError(f"{label} path escapes its root")
    return value


def _items(
    manifest: Mapping[str, Any], *, kind: str, count: int, label: str
) -> list[dict[str, Any]]:
    items = manifest.get("items")
    if manifest.get("kind") != kind or not isinstance(items, list) or len(items) != count:
        raise Src4vcTwoUtteranceError(f"{label} manifest identity drifted")
    if not all(isinstance(item, dict) for item in items):
        raise Src4vcTwoUtteranceError(f"{label} row is malformed")
    return [dict(item) for item in items]


def _validate_audio(path: Path, expected_sha256: str, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise Src4vcTwoUtteranceError(f"{label} WAV unavailable")
    try:
        value = path.read_bytes()
    except OSError as error:
        raise Src4vcTwoUtteranceError(f"{label} WAV unavailable") from error
    if sha256_bytes(value) != expected_sha256:
        raise Src4vcTwoUtteranceError(f"{label} WAV hash drifted")
    # The fetcher already performs this admission.  Recheck the cheap WAV
    # invariant here so a changed private file cannot silently reach CUDA.
    try:
        with wave.open(str(path), "rb") as handle:
            if (
                handle.getnchannels() != 1
                or handle.getsampwidth() != 2
                or handle.getframerate() <= 0
                or handle.getnframes() <= 0
            ):
                raise Src4vcTwoUtteranceError(f"{label} WAV format drifted")
            handle.readframes(handle.getnframes())
    except (EOFError, OSError, wave.Error) as error:
        raise Src4vcTwoUtteranceError(f"{label} WAV format drifted") from error
    return value


def _validate_subset_manifest(
    manifest: Mapping[str, Any],
    *,
    expected_utterance_index: int,
    expected_train_speakers: set[str],
    label: str,
) -> dict[str, dict[str, Any]]:
    """Validate one private subset and return its train rows by speaker."""

    items = _items(manifest, kind=SRC4VC_KIND, count=EXPECTED_SUBSET_ROWS, label=label)
    declared_index = manifest.get("train_utterance_index")
    # EXP-244's original index-zero manifest predates the explicit field.  Its
    # row selection is the frozen index-zero substrate, so absence is accepted
    # only for that legacy manifest; index one must always be declared.
    if declared_index != expected_utterance_index and not (
        expected_utterance_index == 0 and declared_index is None
    ):
        raise Src4vcTwoUtteranceError(
            f"{label} train utterance index is not {expected_utterance_index}"
        )
    train = [row for row in items if row.get("split") == "train"]
    evaluation = [row for row in items if row.get("split") == "evaluation"]
    train_ids = {str(row.get("speaker_id")) for row in train}
    heldout = heldout_speakers()
    evaluation_counts = Counter(str(row.get("speaker_id")) for row in evaluation)
    if (
        len(train) != EXPECTED_TRAIN_SPEAKERS
        or train_ids != expected_train_speakers
        or len(evaluation) != 30
        or set(evaluation_counts) != heldout
        or set(evaluation_counts.values()) != {2}
        or train_ids & heldout
    ):
        raise Src4vcTwoUtteranceError(f"{label} train/heldout speaker boundary drifted")

    seen_ids: set[str] = set()
    by_speaker: dict[str, dict[str, Any]] = {}
    for row in train:
        identifier = row.get("id")
        speaker = row.get("speaker_id")
        filename = row.get("filename")
        text = row.get("text")
        digest = row.get("sha256")
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in seen_ids
            or not isinstance(speaker, str)
            or speaker not in expected_train_speakers
            or speaker in by_speaker
            or not isinstance(text, str)
            or not text.strip()
            or not isinstance(filename, str)
            or not filename
            or not _is_sha256(digest)
        ):
            raise Src4vcTwoUtteranceError(f"{label} train source identity drifted")
        _safe_relative(filename, f"{label} source")
        seen_ids.add(identifier)
        by_speaker[speaker] = row

    if set(by_speaker) != expected_train_speakers:
        raise Src4vcTwoUtteranceError(f"{label} train speaker coverage drifted")
    return by_speaker


def _exp244_train_speakers(manifest: Mapping[str, Any]) -> set[str]:
    """Extract the frozen EXP-244 training boundary from either input form."""

    items = manifest.get("items")
    if not isinstance(items, list):
        raise Src4vcTwoUtteranceError("EXP-244 speaker manifest is malformed")
    if manifest.get("kind") == SRC4VC_KIND:
        if len(items) != EXPECTED_SUBSET_ROWS:
            raise Src4vcTwoUtteranceError("EXP-244 subset row count drifted")
        speakers = {
            str(item.get("speaker_id"))
            for item in items
            if isinstance(item, dict) and item.get("split") == "train"
        }
    else:
        # The EXP-244 curriculum is also accepted as a convenient frozen
        # boundary reference; it contains two source domains but only one
        # source row per SRC4VC train speaker.
        if manifest.get("kind") != "liveconv-exp244-src4vc-cross-corpus-unpaired-inputs/v1":
            raise Src4vcTwoUtteranceError("EXP-244 speaker manifest kind drifted")
        speakers = {
            str(item.get("source_speaker_id"))
            for item in items
            if isinstance(item, dict)
            and item.get("domain") == "src4vc-smartphone-unpaired"
        }
    if (
        len(speakers) != EXPECTED_TRAIN_SPEAKERS
        or not all(speaker.startswith("SRC4VC") for speaker in speakers)
        or speakers & heldout_speakers()
    ):
        raise Src4vcTwoUtteranceError("EXP-244 training speaker boundary drifted")
    return speakers


def _validate_exp238_targets(
    manifest: Mapping[str, Any], target_root: Path
) -> list[dict[str, Any]]:
    rows = _items(manifest, kind=EXP238_KIND, count=EXPECTED_ROWS, label="EXP-238")
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    seen_hashes: set[str] = set()
    for position, row in enumerate(rows):
        target_id = row.get("target_id")
        target_file = row.get("real_target_file")
        target_text = row.get("real_target_text")
        target_hash = row.get("real_target_sha256")
        if (
            not isinstance(target_id, str)
            or not target_id
            or target_id in seen_ids
            or not isinstance(target_text, str)
            or not target_text.strip()
            or not _is_sha256(target_hash)
            or not isinstance(target_file, str)
            or target_file in seen_files
            or target_hash in seen_hashes
            or row.get("real_target_root") != "source-work"
        ):
            raise Src4vcTwoUtteranceError(f"EXP-238 target identity drifted at {position}")
        _safe_relative(target_file, f"EXP-238 real target {position}")
        _validate_audio(target_root / target_file, target_hash, f"EXP-238 target {position}")
        seen_ids.add(target_id)
        seen_files.add(target_file)
        seen_hashes.add(target_hash)
    return rows


def _source_rows(
    *,
    zero: Mapping[str, Mapping[str, Any]],
    one: Mapping[str, Mapping[str, Any]],
    root_zero: Path,
    root_one: Path,
    target_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    speakers = sorted(zero)
    if speakers != sorted(one) or len(speakers) != EXPECTED_TRAIN_SPEAKERS:
        raise Src4vcTwoUtteranceError("SRC4VC train speaker sets do not match")

    rows: list[dict[str, Any]] = []
    source_bytes: dict[str, bytes] = {}
    seen_source_ids: set[str] = set()
    seen_source_files: set[str] = set()
    seen_source_hashes: set[str] = set()
    for speaker in speakers:
        pair = (zero[speaker], one[speaker])
        if pair[0].get("id") == pair[1].get("id") or pair[0].get("filename") == pair[1].get("filename"):
            raise Src4vcTwoUtteranceError(f"{speaker} utterance identity duplicated")
        if pair[0].get("sha256") == pair[1].get("sha256"):
            raise Src4vcTwoUtteranceError(f"{speaker} source WAV duplicated")
        if pair[0].get("text") == pair[1].get("text"):
            raise Src4vcTwoUtteranceError(f"{speaker} source transcript duplicated")
        for utterance_index, (item, root) in enumerate(zip(pair, (root_zero, root_one), strict=True)):
            source_id = str(item["id"])
            source_hash = str(item["sha256"])
            source_file = str(item["filename"])
            if source_id in seen_source_ids or source_file in seen_source_files or source_hash in seen_source_hashes:
                raise Src4vcTwoUtteranceError("SRC4VC source identity duplicated")
            value = _validate_audio(root / source_file, source_hash, f"SRC4VC {source_id}")
            output_file = (
                Path("sources")
                / speaker
                / f"u{utterance_index}-{source_id}.wav"
            ).as_posix()
            target = target_rows[len(rows)]
            target_file = str(target["real_target_file"])
            target_hash = str(target["real_target_sha256"])
            row = {
                "position": len(rows),
                "id": f"{len(rows):03d}-src4vc-{speaker.lower()}-u{utterance_index}--{target['target_id']}",
                "teacher_id": f"src4vc-{speaker.lower()}-u{utterance_index}",
                "domain": "src4vc-smartphone-unpaired",
                "source_manifest_id": f"EXP325:{source_id}",
                "source_id": source_id,
                "source_speaker_id": speaker,
                "source_utterance_index": utterance_index,
                "source_text": str(item["text"]),
                "source_transcript": str(item["text"]),
                "source_root": "source-work",
                "source_file": output_file,
                "source_sha256": source_hash,
                "source_original_file": source_file,
                "source_original_sha256": source_hash,
                "target_id": str(target["target_id"]),
                # The fresh teacher renderer will create the same-content
                # control69 target later.  Keep that supervision text equal to
                # the source transcript; the frozen Amitaro reference remains
                # explicitly separate below.
                "target_text": str(item["text"]),
                "real_target_text": str(target["real_target_text"]),
                "real_target_root": "source-work",
                "real_target_file": target_file,
                "real_target_sha256": target_hash,
                "learning_target": "source-aligned-control69-plus-real-target-adversarial",
            }
            rows.append(row)
            source_bytes[output_file] = value
            seen_source_ids.add(source_id)
            seen_source_files.add(source_file)
            seen_source_hashes.add(source_hash)
    if len(rows) != EXPECTED_ROWS:
        raise Src4vcTwoUtteranceError("SRC4VC source cardinality drifted")
    return rows, source_bytes


def build_pool(
    *,
    exp244_manifest: Mapping[str, Any],
    subset_zero_manifest: Mapping[str, Any],
    subset_one_manifest: Mapping[str, Any],
    subset_zero_root: Path,
    subset_one_root: Path,
    exp238_manifest: Mapping[str, Any],
    exp238_root: Path,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    expected = _exp244_train_speakers(exp244_manifest)
    zero = _validate_subset_manifest(
        subset_zero_manifest,
        expected_utterance_index=0,
        expected_train_speakers=expected,
        label="SRC4VC index0",
    )
    one = _validate_subset_manifest(
        subset_one_manifest,
        expected_utterance_index=1,
        expected_train_speakers=expected,
        label="SRC4VC index1",
    )
    targets = _validate_exp238_targets(exp238_manifest, exp238_root)
    items, source_bytes = _source_rows(
        zero=zero,
        one=one,
        root_zero=subset_zero_root,
        root_one=subset_one_root,
        target_rows=targets,
    )
    pool = {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "corpus": "SRC4VC version 1",
            "license": SOURCE_LICENSE,
            "boundary": (
                "private research artifact; 85 EXP-244 train speakers only; "
                "the fixed fifteen SRC4VC heldout speakers are excluded"
            ),
            "selection": "speaker ascending, RECITATION train utterance index 0 then 1",
            "target_binding": "exact ordered EXP-238 real Amitaro target IDs/files/hashes/text",
            "source_speaker_classes": EXPECTED_TRAIN_SPEAKERS,
            "rows_per_source_speaker": 2,
        },
        "composition": {"src4vc-smartphone-unpaired": EXPECTED_ROWS},
        "items": items,
    }
    return pool, source_bytes


def materialize(
    *,
    exp244_manifest: Mapping[str, Any],
    subset_zero_manifest: Mapping[str, Any],
    subset_one_manifest: Mapping[str, Any],
    subset_zero_root: Path,
    subset_one_root: Path,
    exp238_manifest: Mapping[str, Any],
    exp238_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    if output_root.exists() or output_root.is_symlink():
        raise Src4vcTwoUtteranceError("output root already exists")
    pool, source_bytes = build_pool(
        exp244_manifest=exp244_manifest,
        subset_zero_manifest=subset_zero_manifest,
        subset_one_manifest=subset_one_manifest,
        subset_zero_root=subset_zero_root,
        subset_one_root=subset_one_root,
        exp238_manifest=exp238_manifest,
        exp238_root=exp238_root,
    )
    output_root.mkdir(parents=True)
    for relative, value in source_bytes.items():
        destination = output_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(value)
    for item in pool["items"]:
        relative = str(item["real_target_file"])
        destination = output_root / relative
        if destination.exists() or destination.is_symlink():
            raise Src4vcTwoUtteranceError(f"target output path duplicated: {relative}")
        source = exp238_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        if sha256_file(destination) != item["real_target_sha256"]:
            raise Src4vcTwoUtteranceError("copied target hash drifted")
    (output_root / "pool.json").write_text(
        json.dumps(pool, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return pool


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--exp244-manifest", type=Path, required=True)
    value.add_argument("--subset-zero-manifest", type=Path, required=True)
    value.add_argument("--subset-one-manifest", type=Path, required=True)
    value.add_argument("--subset-zero-root", type=Path, required=True)
    value.add_argument("--subset-one-root", type=Path, required=True)
    value.add_argument("--exp238-manifest", type=Path, required=True)
    value.add_argument("--exp238-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        inputs = {
            "exp244_manifest": load_json(arguments.exp244_manifest),
            "subset_zero_manifest": load_json(arguments.subset_zero_manifest),
            "subset_one_manifest": load_json(arguments.subset_one_manifest),
            "exp238_manifest": load_json(arguments.exp238_manifest),
        }
        pool, _ = build_pool(
            **inputs,
            subset_zero_root=arguments.subset_zero_root,
            subset_one_root=arguments.subset_one_root,
            exp238_root=arguments.exp238_root,
        )
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-write-no-cuda",
                        "rows": len(pool["items"]),
                        "speakers": len(
                            {item["source_speaker_id"] for item in pool["items"]}
                        ),
                        "rows_per_speaker": 2,
                    },
                    sort_keys=True,
                )
            )
            return 0
        materialize(
            **inputs,
            subset_zero_root=arguments.subset_zero_root,
            subset_one_root=arguments.subset_one_root,
            exp238_root=arguments.exp238_root,
            output_root=arguments.output_root,
        )
        print(
            json.dumps(
                {
                    "status": "materialized-private-src4vc-two-utterance-pool",
                    "rows": len(pool["items"]),
                    "speakers": EXPECTED_TRAIN_SPEAKERS,
                    "output": str(arguments.output_root / "pool.json"),
                },
                sort_keys=True,
            )
        )
        return 0
    except (OSError, ValueError, Src4vcTwoUtteranceError) as error:
        print(f"src4vc-two-utterance-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
