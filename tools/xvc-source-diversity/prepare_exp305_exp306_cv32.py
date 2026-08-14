#!/usr/bin/env python3
"""Prepare the EXP-305/306 Common Voice breadth lane without CUDA.

The 33-row EXP-055 local-unused screen is an old evaluation surface, not a
training manifest.  This module retires the one client that overlaps the
current stress surface and admits the other 32 rows only after checking their
identity against every active Common Voice boundary.  EXP-305 is a matched
32-row repeat-control append to EXP-238.  EXP-306 is the corresponding new
source pool; its control69 targets are rendered by
``render_exp306_cv32_targets.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import wave
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

EXP238_KIND = "liveconv-exp238-cross-corpus-control69-pseudoparallel-inputs/v1"
EXP055_KIND = "liveconv-exp055-commonvoice-local-unused/v1"
EXP186_KIND = "liveconv-exp186-commonvoice48-speech-active-windows/v1"
REPEAT_OUTPUT_KIND = "liveconv-exp305-xvc-pseudoparallel-repeat32-inputs/v1"
BREADTH_POOL_KIND = "liveconv-exp306-xvc-pseudoparallel-cv32-pool/v1"
BREADTH_OUTPUT_KIND = "liveconv-exp306-xvc-pseudoparallel-cv32-inputs/v1"

EXPECTED_BASE_ROWS = 170
EXPECTED_NEW_ROWS = 32
EXPECTED_ROWS = EXPECTED_BASE_ROWS + EXPECTED_NEW_ROWS
EXPECTED_COMPOSITION = {
    "commonvoice-unpaired": 80,
    "jsut-unpaired": 85,
    "jvs-unpaired": 3,
    "hadou-unpaired": 34,
}
BASE_COMPOSITION = {
    "commonvoice-unpaired": 48,
    "jsut-unpaired": 85,
    "jvs-unpaired": 3,
    "hadou-unpaired": 34,
}
EXCLUDED_ID = "cv27706775u"
EXPECTED_WAV_FRAMES = 38_400
EXPECTED_WAV_RATE = 16_000


class Cv32PreparationError(RuntimeError):
    """Inputs are not the frozen, disjoint EXP-305/306 contract."""


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Cv32PreparationError(f"JSON object required: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _items(
    value: Mapping[str, Any], *, kind: str, count: int, label: str
) -> list[dict[str, Any]]:
    rows = value.get("items")
    if value.get("kind") != kind or not isinstance(rows, list) or len(rows) != count:
        raise Cv32PreparationError(f"{label} manifest identity drifted")
    if not all(isinstance(row, dict) for row in rows):
        raise Cv32PreparationError(f"{label} row is malformed")
    return [dict(row) for row in rows]


def _safe_relative(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise Cv32PreparationError(f"{label} path is malformed")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise Cv32PreparationError(f"{label} path escapes its root")
    return value


def _validate_base(curriculum: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _items(
        curriculum, kind=EXP238_KIND, count=EXPECTED_BASE_ROWS, label="EXP-238"
    )
    if curriculum.get("composition") != BASE_COMPOSITION:
        raise Cv32PreparationError("EXP-238 composition drifted")
    ids: set[str] = set()
    domains: Counter[str] = Counter()
    for row in rows:
        identifier = row.get("id")
        if not isinstance(identifier, str) or identifier in ids:
            raise Cv32PreparationError("EXP-238 row IDs drifted")
        ids.add(identifier)
        domains[str(row.get("domain"))] += 1
        for key in ("source_file", "target_file", "real_target_file"):
            _safe_relative(row.get(key), f"EXP-238 {key}")
        for key in ("source_sha256", "target_sha256", "real_target_sha256"):
            if not is_sha256(row.get(key)):
                raise Cv32PreparationError(f"EXP-238 {key} drifted")
        if (
            row.get("source_root") != "source-work"
            or row.get("target_root") != "diverse-work"
            or row.get("real_target_root") != "source-work"
            or row.get("target_text") != row.get("source_text")
        ):
            raise Cv32PreparationError("EXP-238 source/target boundary drifted")
    if dict(domains) != BASE_COMPOSITION:
        raise Cv32PreparationError("EXP-238 domain composition drifted")
    return rows


def _wav_identity(path: Path, identifier: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise Cv32PreparationError(f"new Common Voice WAV unavailable: {identifier}")
    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            sample_rate = handle.getframerate()
            frames = handle.getnframes()
            raw = handle.readframes(frames)
    except (EOFError, wave.Error, OSError) as error:
        raise Cv32PreparationError(
            f"new Common Voice WAV malformed: {identifier}"
        ) from error
    if (
        channels != 1
        or sample_width != 2
        or sample_rate != EXPECTED_WAV_RATE
        or frames != EXPECTED_WAV_FRAMES
        or not raw
        or len(raw) != frames * sample_width * channels
    ):
        raise Cv32PreparationError(f"new Common Voice WAV format drifted: {identifier}")
    samples = np.frombuffer(raw, dtype="<i2")
    if (
        samples.size != EXPECTED_WAV_FRAMES
        or not np.isfinite(samples.astype(np.float32)).all()
    ):
        raise Cv32PreparationError(
            f"new Common Voice WAV samples drifted: {identifier}"
        )
    return {
        "source_wav_sha256": sha256_file(path),
        "source_wav_frames": frames,
        "source_wav_sample_rate": sample_rate,
        "source_wav_channels": channels,
        "source_wav_sample_width": sample_width,
    }


def validate_disjoint_commonvoice(
    expanded: Mapping[str, Any],
    *,
    evaluation_roots: Mapping[str, Mapping[str, Any]],
    training_windows: Mapping[str, Any],
    wav_root: Path,
) -> list[dict[str, Any]]:
    rows = _items(expanded, kind=EXP055_KIND, count=33, label="EXP-055 expanded")
    rows_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        identifier = row.get("id")
        if not isinstance(identifier, str) or identifier in rows_by_id:
            raise Cv32PreparationError("EXP-055 IDs are not unique")
        if (
            not is_sha256(row.get("sha256"))
            or not isinstance(row.get("filename"), str)
            or not isinstance(row.get("text"), str)
            or not is_sha256(row.get("client_id_sha256"))
        ):
            raise Cv32PreparationError("EXP-055 row identity is malformed")
        rows_by_id[identifier] = row
    rows = [row for row in rows if row["id"] != EXCLUDED_ID]
    if len(rows) != EXPECTED_NEW_ROWS:
        raise Cv32PreparationError("EXP-055 excluded-row selection drifted")
    for field in ("id", "sha256", "text", "client_id_sha256"):
        values = [str(row[field]) for row in rows]
        if len(values) != len(set(values)):
            raise Cv32PreparationError(
                f"new Common Voice {field} values are not unique"
            )

    blocked_clients: dict[str, set[str]] = {}
    for name, manifest in evaluation_roots.items():
        manifest_rows = manifest.get("items")
        if not isinstance(manifest_rows, list):
            raise Cv32PreparationError(f"{name} evaluation rows are malformed")
        clients: set[str] = set()
        for row in manifest_rows:
            if not isinstance(row, dict) or not is_sha256(row.get("client_id_sha256")):
                raise Cv32PreparationError(f"{name} evaluation client identity drifted")
            clients.add(str(row["client_id_sha256"]))
        blocked_clients[name] = clients

    training_rows = _items(
        training_windows,
        kind=EXP186_KIND,
        count=48,
        label="EXP-238 Common Voice training",
    )
    training_clients: set[str] = set()
    for row in training_rows:
        if not is_sha256(row.get("client_id_sha256")):
            raise Cv32PreparationError("EXP-238 training client identity drifted")
        training_clients.add(str(row["client_id_sha256"]))
    blocked_clients["exp238-training-cv48"] = training_clients

    for row in rows:
        identifier = str(row["id"])
        client = str(row["client_id_sha256"])
        overlaps = [
            name for name, clients in blocked_clients.items() if client in clients
        ]
        if overlaps:
            raise Cv32PreparationError(
                f"new Common Voice client overlaps {','.join(overlaps)}: {identifier}"
            )
        _wav_identity(wav_root / f"{identifier}.wav", identifier)
    return rows


def _copy_verified(source: Path, destination: Path, digest: str, label: str) -> None:
    if source.is_symlink() or not source.is_file() or sha256_file(source) != digest:
        raise Cv32PreparationError(f"{label} input audio drifted")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise Cv32PreparationError(f"output path already exists: {destination}")
    shutil.copyfile(source, destination)
    if sha256_file(destination) != digest:
        raise Cv32PreparationError(f"{label} copy hash drifted")


def _copy_base_audio(
    base_rows: Sequence[Mapping[str, Any]],
    *,
    base_source_work: Path,
    base_diverse_work: Path,
    output_source_work: Path,
    output_diverse_work: Path,
) -> None:
    for row in base_rows:
        _copy_verified(
            base_source_work / str(row["source_file"]),
            output_source_work / str(row["source_file"]),
            str(row["source_sha256"]),
            f"EXP-238 source {row['id']}",
        )
        _copy_verified(
            base_source_work / str(row["real_target_file"]),
            output_source_work / str(row["real_target_file"]),
            str(row["real_target_sha256"]),
            f"EXP-238 real target {row['id']}",
        )
        _copy_verified(
            base_diverse_work / str(row["target_file"]),
            output_diverse_work / str(row["target_file"]),
            str(row["target_sha256"]),
            f"EXP-238 teacher target {row['id']}",
        )


def _new_source_row(
    row: Mapping[str, Any], index: int, wav_digest: str
) -> dict[str, Any]:
    identifier = str(row["id"])
    source_file = f"new-sources/{index:02d}-{identifier}.wav"
    return {
        "id": f"cv32-{index:02d}-{identifier}",
        "teacher_id": f"commonvoice-cv32-{index:02d}-{identifier}",
        "domain": "commonvoice-unpaired",
        "source_manifest_id": f"EXP055:{identifier}",
        "source_root": "source-work",
        "source_file": source_file,
        "source_sha256": wav_digest,
        "source_text": str(row["text"]),
        "source_client_id_sha256": str(row["client_id_sha256"]),
        "source_original_sha256": str(row["sha256"]),
        "source_relative_distance": 0.0,
        "target_id": "",
        "target_text": "",
        "target_root": "diverse-work",
        "real_target_root": "source-work",
        "real_target_file": "",
        "real_target_sha256": "",
        "learning_target": "source-aligned-control69-plus-real-target-adversarial",
        "source_order": index,
    }


def build_manifests(
    exp238: Mapping[str, Any],
    expanded_rows: Sequence[Mapping[str, Any]],
    *,
    source_wav_digests: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    base_rows = _validate_base(exp238)
    selected = [
        row for row in base_rows if row.get("domain") == "commonvoice-unpaired"
    ][:EXPECTED_NEW_ROWS]
    if len(selected) != EXPECTED_NEW_ROWS:
        raise Cv32PreparationError("EXP-238 Common Voice selection drifted")
    repeat_items = [dict(row) for row in base_rows]
    new_rows: list[dict[str, Any]] = []
    for index, (source_row, assignment) in enumerate(
        zip(expanded_rows, selected, strict=True)
    ):
        source_id = str(source_row["id"])
        if source_id not in source_wav_digests:
            raise Cv32PreparationError(
                f"new Common Voice source digest missing: {source_id}"
            )
        source = _new_source_row(source_row, index, source_wav_digests[source_id])
        source["target_id"] = str(assignment["target_id"])
        source["target_text"] = str(assignment["target_text"])
        source["real_target_file"] = str(assignment["real_target_file"])
        source["real_target_sha256"] = str(assignment["real_target_sha256"])
        source["assignment_from"] = str(assignment["id"])
        new_rows.append(source)
        repeated = dict(assignment)
        repeated["id"] = f"{assignment['id']}--repeat32-{index:02d}"
        repeated["source_manifest_id"] = f"EXP305:repeat32:{assignment['id']}"
        repeated["repeat_of_id"] = assignment["id"]
        repeated["repeat_index"] = index
        repeat_items.append(repeated)

    repeat = {
        "schema_version": 1,
        "kind": REPEAT_OUTPUT_KIND,
        "source": {
            "base_kind": EXP238_KIND,
            "selection": (
                "exact first 32 EXP-238 commonvoice-unpaired rows in original order"
            ),
            "control": (
                "append each selected row once; source, control69 teacher, and real "
                "Amitaro target are byte-identical"
            ),
            "boundary": (
                "training-only horizon-matched repeat control; no evaluation or "
                "perceptual claim"
            ),
        },
        "composition": dict(Counter(str(row["domain"]) for row in repeat_items)),
        "learning_target_counts": dict(
            Counter(str(row["learning_target"]) for row in repeat_items)
        ),
        "items": repeat_items,
    }
    if (
        repeat["composition"] != EXPECTED_COMPOSITION
        or len(repeat_items) != EXPECTED_ROWS
    ):
        raise Cv32PreparationError("EXP-305 composition drifted")

    pool_items: list[dict[str, Any]] = []
    for index, row in enumerate(new_rows):
        item = dict(row)
        item["position"] = index
        item["pool_kind"] = BREADTH_POOL_KIND
        pool_items.append(item)
    pool = {
        "schema_version": 1,
        "kind": BREADTH_POOL_KIND,
        "source": {
            "selection": (
                "EXP-055 local-unused expanded33 in evaluation order, excluding "
                "cv27706775u"
            ),
            "assignment": (
                "same ordered real Amitaro target assignments as the EXP-305 "
                "appended rows"
            ),
            "boundary": "new-source target-render pool; no product or perceptual claim",
        },
        "composition": {"commonvoice-unpaired": EXPECTED_NEW_ROWS},
        "items": pool_items,
    }
    return repeat, pool, new_rows


def materialize(
    *,
    exp238: Mapping[str, Any],
    expanded_rows: Sequence[Mapping[str, Any]],
    wav_root: Path,
    base_source_work: Path,
    base_diverse_work: Path,
    output_root: Path,
) -> dict[str, Any]:
    base_rows = _validate_base(exp238)
    digests: dict[str, str] = {}
    for row in expanded_rows:
        identifier = str(row["id"])
        digest_info = _wav_identity(wav_root / f"{identifier}.wav", identifier)
        digests[identifier] = str(digest_info["source_wav_sha256"])
    repeat, pool, new_rows = build_manifests(
        exp238, expanded_rows, source_wav_digests=digests
    )
    if output_root.exists() or output_root.is_symlink():
        raise Cv32PreparationError("output root already exists")
    source_work = output_root / "source-work"
    diverse_work = output_root / "diverse-work"
    source_work.mkdir(parents=True)
    diverse_work.mkdir()
    _copy_base_audio(
        base_rows,
        base_source_work=base_source_work,
        base_diverse_work=base_diverse_work,
        output_source_work=source_work,
        output_diverse_work=diverse_work,
    )
    for index, row in enumerate(expanded_rows):
        identifier = str(row["id"])
        _copy_verified(
            wav_root / f"{identifier}.wav",
            source_work / f"new-sources/{index:02d}-{identifier}.wav",
            digests[identifier],
            f"new Common Voice source {identifier}",
        )
    repeat_path = output_root / "exp305-curriculum.json"
    pool_path = output_root / "exp306-pool.json"
    repeat["source"].update(
        {
            "exp238_curriculum_sha256": _canonical_sha256(exp238),
            "expanded_evaluation_sha256": _canonical_sha256(
                {"items": list(expanded_rows)}
            ),
        }
    )
    pool["source"].update({"exp305_curriculum_sha256": _canonical_sha256(repeat)})
    repeat_path.write_text(
        json.dumps(repeat, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    pool_path.write_text(
        json.dumps(pool, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "materialized",
        "rows": len(repeat["items"]),
        "new_rows": len(new_rows),
        "repeat_curriculum": str(repeat_path),
        "pool": str(pool_path),
        "source_work": str(source_work),
        "diverse_work": str(diverse_work),
        "repeat_sha256": sha256_file(repeat_path),
        "pool_sha256": sha256_file(pool_path),
    }


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--exp238-curriculum", type=Path, required=True)
    value.add_argument("--exp238-source-work", type=Path, required=True)
    value.add_argument("--exp238-diverse-work", type=Path, required=True)
    value.add_argument("--exp055-expanded-evaluation", type=Path, required=True)
    value.add_argument("--exp168-evaluation-sources", type=Path, required=True)
    value.add_argument("--exp238-training-cv-manifest", type=Path, required=True)
    value.add_argument("--external7-evaluation", type=Path, required=True)
    value.add_argument("--fresh48-evaluation", type=Path, required=True)
    value.add_argument("--stress60-evaluation", type=Path, required=True)
    value.add_argument("--expanded144-evaluation", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--check", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        exp238 = load_json(arguments.exp238_curriculum)
        expanded = load_json(arguments.exp055_expanded_evaluation)
        training = load_json(arguments.exp238_training_cv_manifest)
        evals = {
            "external7": load_json(arguments.external7_evaluation),
            "fresh48": load_json(arguments.fresh48_evaluation),
            "stress60": load_json(arguments.stress60_evaluation),
            "expanded144": load_json(arguments.expanded144_evaluation),
        }
        new_rows = validate_disjoint_commonvoice(
            expanded,
            evaluation_roots=evals,
            training_windows=training,
            wav_root=arguments.exp168_evaluation_sources,
        )
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-write",
                        "new_rows": len(new_rows),
                        "excluded": EXCLUDED_ID,
                    },
                    sort_keys=True,
                )
            )
            return 0
        result = materialize(
            exp238=exp238,
            expanded_rows=new_rows,
            wav_root=arguments.exp168_evaluation_sources,
            base_source_work=arguments.exp238_source_work,
            base_diverse_work=arguments.exp238_diverse_work,
            output_root=arguments.output_root,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (Cv32PreparationError, OSError, ValueError, KeyError) as error:
        print(f"exp305-exp306-cv32-error: {error}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
