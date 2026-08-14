#!/usr/bin/env python3
"""Materialize one fixed cross-corpus, alignment-free X-VC curriculum."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import wave
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from prepare_clean_post_rehearsal import load_json, sha256_file
from prepare_unpaired_human_curriculum import OUTPUT_KIND as HUMAN_OUTPUT_KIND

OUTPUT_KIND = "liveconv-exp213-cross-corpus-unpaired-output-cycle-inputs/v1"
COMMONVOICE_KIND = "liveconv-exp186-commonvoice48-speech-active-windows/v1"
JSUT_KIND = "liveconv-exp169-jsut-retention-sources85/v1"
JVS_KIND = "liveconv-exp138-window-breadth201/v1"
JVS_SCREEN_KIND = "liveconv-xvc-pseudo-teacher-output-screen/v1"
EXPECTED_ROWS = 170
EXPECTED_COMPOSITION = {
    "commonvoice-unpaired": 48,
    "hadou-unpaired": 34,
    "jsut-unpaired": 85,
    "jvs-unpaired": 3,
}
HADOU_ROWS = EXPECTED_COMPOSITION["hadou-unpaired"]
WINDOW_SECONDS = 2.4
ACTIVE_THRESHOLD_DBFS = -45.0


class CrossCorpusUnpairedError(RuntimeError):
    """The cross-corpus curriculum cannot be materialized safely."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def selected_hadou_indices(count: int = EXPECTED_ROWS) -> list[int]:
    """Spread the fixed 34-row Hadou remainder over the complete predecessor."""
    if count != EXPECTED_ROWS:
        raise CrossCorpusUnpairedError("Hadou predecessor count drifted")
    selected = [(index * count) // HADOU_ROWS for index in range(HADOU_ROWS)]
    if len(selected) != HADOU_ROWS or len(set(selected)) != HADOU_ROWS:
        raise CrossCorpusUnpairedError("Hadou selection drifted")
    return selected


def speech_active_window(samples: np.ndarray, *, sample_rate: int) -> np.ndarray:
    """Choose one guarded active 2.4 s window without resampling or stretching."""
    if sample_rate <= 0:
        raise CrossCorpusUnpairedError("invalid source sample rate")
    values = np.asarray(samples, dtype=np.int16).reshape(-1)
    frame_samples = max(1, int(round(sample_rate * 0.02)))
    window_samples = int(round(sample_rate * WINDOW_SECONDS))
    complete_frames = values.size // frame_samples
    if complete_frames:
        framed = values[: complete_frames * frame_samples].reshape(
            complete_frames, frame_samples
        )
        rms = np.sqrt(np.mean(framed.astype(np.float64) ** 2, axis=1))
        threshold = 32768.0 * 10.0 ** (ACTIVE_THRESHOLD_DBFS / 20.0)
        active = np.flatnonzero(rms >= threshold)
    else:
        active = np.empty(0, dtype=np.int64)
    if active.size:
        start = max(0, (int(active[0]) - 1) * frame_samples)
        end = min(values.size, (int(active[-1]) + 2) * frame_samples)
        values = values[start:end]
    if values.size > window_samples:
        squared = values.astype(np.float64) ** 2
        cumulative = np.concatenate(([0.0], np.cumsum(squared)))
        starts = np.arange(
            0,
            values.size - window_samples + 1,
            frame_samples,
            dtype=np.int64,
        )
        energies = cumulative[starts + window_samples] - cumulative[starts]
        start = int(starts[int(np.argmax(energies))])
        values = values[start : start + window_samples]
    if values.size < window_samples:
        values = np.pad(values, (0, window_samples - values.size))
    output = np.ascontiguousarray(values[:window_samples], dtype=np.int16)
    if output.shape != (window_samples,):
        raise CrossCorpusUnpairedError("active-window shape drifted")
    return output


def active_window_wav_bytes(value: bytes, *, label: str) -> bytes:
    """Validate mono PCM16 and preserve its native rate while taking 2.4 s."""
    try:
        with wave.open(io.BytesIO(value), "rb") as handle:
            if (
                handle.getnchannels() != 1
                or handle.getsampwidth() != 2
                or handle.getcomptype() != "NONE"
            ):
                raise CrossCorpusUnpairedError(f"unsupported WAV format: {label}")
            sample_rate = handle.getframerate()
            samples = np.frombuffer(
                handle.readframes(handle.getnframes()), dtype="<i2"
            ).copy()
    except (EOFError, wave.Error) as error:
        raise CrossCorpusUnpairedError(f"invalid WAV: {label}") from error
    if samples.size == 0:
        raise CrossCorpusUnpairedError(f"empty WAV: {label}")
    selected = speech_active_window(samples, sample_rate=sample_rate)
    output = io.BytesIO()
    with wave.open(output, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(selected.astype("<i2", copy=False).tobytes())
    return output.getvalue()


def _validated_items(
    manifest: Mapping[str, Any], *, kind: str, count: int, label: str
) -> list[dict[str, Any]]:
    items = manifest.get("items")
    if manifest.get("kind") != kind or not isinstance(items, list) or len(items) != count:
        raise CrossCorpusUnpairedError(f"{label} manifest identity drifted")
    if not all(isinstance(item, dict) for item in items):
        raise CrossCorpusUnpairedError(f"{label} row is malformed")
    return [dict(item) for item in items]


def _source_record(
    *,
    domain: str,
    identifier: str,
    transcript: str | None,
    path: Path,
    expected_sha256: str,
    manifest_id: str,
) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CrossCorpusUnpairedError(f"source WAV unavailable: {identifier}")
    value = path.read_bytes()
    if _sha256_bytes(value) != expected_sha256:
        raise CrossCorpusUnpairedError(f"source WAV drifted: {identifier}")
    return {
        "domain": domain,
        "teacher_id": f"{domain}-{identifier}",
        "source_manifest_id": manifest_id,
        "source_text": transcript,
        "source_bytes": active_window_wav_bytes(value, label=identifier),
    }


def scheduled_sources(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mix domains deterministically so sequential SGD does not see four blocks."""
    if len(records) != EXPECTED_ROWS:
        raise CrossCorpusUnpairedError("source count drifted")
    ordered = sorted(
        records,
        key=lambda item: hashlib.sha256(
            f"{item['domain']}:{item['teacher_id']}".encode("utf-8")
        ).digest(),
    )
    if len({str(item["teacher_id"]) for item in ordered}) != EXPECTED_ROWS:
        raise CrossCorpusUnpairedError("source identity is not unique")
    return ordered


def materialize(
    *,
    commonvoice_manifest: Mapping[str, Any],
    commonvoice_root: Path,
    jsut_manifest: Mapping[str, Any],
    jsut_root: Path,
    jvs_manifest: Mapping[str, Any],
    jvs_source_screen: Mapping[str, Any],
    jvs_root: Path,
    human_manifest: Mapping[str, Any],
    human_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    cv_items = _validated_items(
        commonvoice_manifest,
        kind=COMMONVOICE_KIND,
        count=48,
        label="Common Voice",
    )
    jsut_items = _validated_items(
        jsut_manifest, kind=JSUT_KIND, count=85, label="JSUT"
    )
    jvs_all = _validated_items(
        jvs_manifest, kind=JVS_KIND, count=201, label="JVS source"
    )
    jvs_items = [item for item in jvs_all if item.get("domain") == "jvs"]
    jvs_screen_rows = jvs_source_screen.get("rows")
    if (
        jvs_source_screen.get("kind") != JVS_SCREEN_KIND
        or not isinstance(jvs_screen_rows, list)
    ):
        raise CrossCorpusUnpairedError("JVS materialized-source screen drifted")
    jvs_materialized_sha256 = {
        str(row["teacher_id"]): str(row["source_sha256"])
        for row in jvs_screen_rows
        if isinstance(row, dict) and str(row.get("teacher_id", "")).startswith("jvs-")
    }
    human_items = _validated_items(
        human_manifest,
        kind=HUMAN_OUTPUT_KIND,
        count=EXPECTED_ROWS,
        label="human unpaired",
    )

    records: list[dict[str, Any]] = []
    for item in cv_items:
        records.append(
            _source_record(
                domain="commonvoice-unpaired",
                identifier=str(item["id"]),
                transcript=str(item["source_transcript"]),
                path=commonvoice_root / str(item["filename"]),
                expected_sha256=str(item["window_sha256"]),
                manifest_id=f"EXP186:{item['id']}",
            )
        )
    for item in jsut_items:
        records.append(
            _source_record(
                domain="jsut-unpaired",
                identifier=str(item["id"]),
                transcript=str(item["source_transcript"]),
                path=jsut_root / str(item["filename"]),
                expected_sha256=str(item["sha256"]),
                manifest_id=f"EXP169:{item['id']}",
            )
        )
    if len(jvs_items) != 3:
        raise CrossCorpusUnpairedError("JVS source count drifted")
    for item in jvs_items:
        records.append(
            _source_record(
                domain="jvs-unpaired",
                identifier=str(item["source_id"]),
                transcript=item.get("source_transcript"),
                path=jvs_root / str(item["filename"]),
                expected_sha256=jvs_materialized_sha256[str(item["id"])],
                manifest_id=f"EXP138:{item['id']}",
            )
        )
    for index in selected_hadou_indices():
        item = human_items[index]
        records.append(
            _source_record(
                domain="hadou-unpaired",
                identifier=str(item["teacher_id"]),
                transcript=str(item["source_text"]),
                path=human_root / str(item["source_file"]),
                expected_sha256=str(item["source_sha256"]),
                manifest_id=str(item["source_manifest_id"]),
            )
        )

    sources = scheduled_sources(records)
    composition = dict(Counter(str(item["domain"]) for item in sources))
    if composition != EXPECTED_COMPOSITION:
        raise CrossCorpusUnpairedError("curriculum composition drifted")
    output_root.mkdir(parents=True)
    sources_root = output_root / "sources"
    targets_root = output_root / "targets"
    sources_root.mkdir()
    targets_root.mkdir()
    items: list[dict[str, Any]] = []
    for position, (source, target) in enumerate(
        zip(sources, human_items, strict=True)
    ):
        target_path = human_root / str(target["target_file"])
        if target_path.is_symlink() or not target_path.is_file():
            raise CrossCorpusUnpairedError(
                f"target WAV unavailable: {target['target_id']}"
            )
        target_bytes = target_path.read_bytes()
        if _sha256_bytes(target_bytes) != target["target_sha256"]:
            raise CrossCorpusUnpairedError(
                f"target WAV drifted: {target['target_id']}"
            )
        source_text = source.get("source_text")
        if source_text and source_text == target.get("target_text"):
            raise CrossCorpusUnpairedError("unpaired text separation drifted")
        source_file = Path("sources") / f"{position:03d}-{source['teacher_id']}.wav"
        target_file = Path("targets") / f"{position:03d}-{target['target_id']}.wav"
        (output_root / source_file).write_bytes(source["source_bytes"])
        shutil.copyfile(target_path, output_root / target_file)
        items.append(
            {
                "id": f"{position:03d}-{source['teacher_id']}--{target['target_id']}",
                "source_manifest_id": source["source_manifest_id"],
                "teacher_id": source["teacher_id"],
                "target_id": target["target_id"],
                "domain": source["domain"],
                "source_root": "diverse-work",
                "source_file": str(source_file),
                "source_sha256": _sha256_bytes(source["source_bytes"]),
                "target_root": "diverse-work",
                "target_file": str(target_file),
                "target_sha256": str(target["target_sha256"]),
                "source_relative_distance": 0.0,
                "source_text": source_text,
                "target_text": target.get("target_text"),
                "learning_target": "source-content-plus-unpaired-target-identity",
            }
        )
    return {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "selection": (
                "all frozen training-only Common Voice 48, all JSUT 85 excluding "
                "the frozen JSUT24 evaluation IDs, all JVS3, and 34 rows spread "
                "over the frozen EXP-203 Hadou170 predecessor"
            ),
            "schedule": "ascending sha256(domain:teacher_id) over the fixed 170 rows",
            "target_boundary": (
                "the exact ordered multiset of 170 unrelated Amitaro target windows "
                "from EXP-203 is unchanged"
            ),
            "window": (
                "one maximum-energy speech-active 2.4 s source window at its native "
                "sample rate; no resampling, stretch, DTW, transcript loss, or "
                "heldout access"
            ),
        },
        "composition": composition,
        "items": items,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--commonvoice-manifest", type=Path, required=True)
    value.add_argument("--commonvoice-root", type=Path, required=True)
    value.add_argument("--jsut-manifest", type=Path, required=True)
    value.add_argument("--jsut-root", type=Path, required=True)
    value.add_argument("--jvs-manifest", type=Path, required=True)
    value.add_argument("--jvs-source-screen", type=Path, required=True)
    value.add_argument("--jvs-root", type=Path, required=True)
    value.add_argument("--human-manifest", type=Path, required=True)
    value.add_argument("--human-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.output_root.exists() or arguments.output_root.is_symlink():
            raise CrossCorpusUnpairedError("output root already exists")
        result = materialize(
            commonvoice_manifest=load_json(arguments.commonvoice_manifest),
            commonvoice_root=arguments.commonvoice_root,
            jsut_manifest=load_json(arguments.jsut_manifest),
            jsut_root=arguments.jsut_root,
            jvs_manifest=load_json(arguments.jvs_manifest),
            jvs_source_screen=load_json(arguments.jvs_source_screen),
            jvs_root=arguments.jvs_root,
            human_manifest=load_json(arguments.human_manifest),
            human_root=arguments.human_root,
            output_root=arguments.output_root,
        )
        result["source"]["manifest_file_sha256"] = {
            "commonvoice": sha256_file(arguments.commonvoice_manifest),
            "jsut": sha256_file(arguments.jsut_manifest),
            "jvs": sha256_file(arguments.jvs_manifest),
            "jvs_materialized_source_screen": sha256_file(
                arguments.jvs_source_screen
            ),
            "human": sha256_file(arguments.human_manifest),
        }
        output = arguments.output_root / "curriculum.json"
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "materialized",
                    "rows": len(result["items"]),
                    "composition": result["composition"],
                    "output": str(output),
                    "sha256": sha256_file(output),
                },
                sort_keys=True,
            )
        )
        return 0
    except (KeyError, OSError, CrossCorpusUnpairedError, ValueError) as error:
        print(f"cross-corpus-unpaired-error: {error}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
