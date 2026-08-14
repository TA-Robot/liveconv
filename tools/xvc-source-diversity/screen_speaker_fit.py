#!/usr/bin/env python3
"""Batch-screen X-VC listener surfaces with one verified ECAPA model load.

This is an auxiliary direction diagnostic.  It compares speaker embeddings; it
does not identify a person, measure naturalness, or select a perceptual winner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEAKER_ROOT = REPO_ROOT / "packages" / "speaker" / "src"
if str(SPEAKER_ROOT) not in sys.path:
    sys.path.insert(0, str(SPEAKER_ROOT))

from liveconv_speaker.backend import SpeechBrainEcapaBackend  # noqa: E402
from liveconv_speaker.evidence import (  # noqa: E402
    ComparisonPolicy,
    compare_embeddings,
    inspect_pcm_wav,
    sha256_model_tree,
)


class SpeakerFitScreenError(RuntimeError):
    """The bounded speaker-fit screen cannot continue safely."""


ALWAYS_PASS = ComparisonPolicy(
    label="auxiliary-direction-only-v1",
    status="proposed",
    min_target_similarity=-1.0,
    min_target_gain=-1.0,
    min_target_advantage=-1.0,
)


def _load_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise SpeakerFitScreenError(f"{label} must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SpeakerFitScreenError(f"{label} is not valid JSON") from error
    if not isinstance(value, dict):
        raise SpeakerFitScreenError(f"{label} must be a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise SpeakerFitScreenError(f"{label} must be a lowercase SHA-256")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpeakerFitScreenError(f"{label} must be a non-empty string")
    return value


def _resolve_repo_path(value: Any, label: str) -> Path:
    relative = Path(_text(value, label))
    if relative.is_absolute() or ".." in relative.parts:
        raise SpeakerFitScreenError(f"{label} must be repository-relative")
    path = (REPO_ROOT / relative).resolve(strict=True)
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as error:
        raise SpeakerFitScreenError(f"{label} escapes the repository") from error
    return path


def _validate_target_lineage(plan: Mapping[str, Any], manifest: Path) -> str:
    target = plan.get("target")
    if not isinstance(target, dict):
        raise SpeakerFitScreenError("plan target must be an object")
    expected_listener_sha = _digest(
        target.get("listener_sha256"), "target listener_sha256"
    )
    row_id = _text(target.get("manifest_row_id"), "target manifest_row_id")
    expected_raw_sha = _digest(target.get("raw_sha256"), "target raw_sha256")
    expected_archive_sha = _digest(
        target.get("archive_sha256"), "target archive_sha256"
    )
    value = _load_object(manifest, "target lineage manifest")
    if value.get("style") != "runrun":
        raise SpeakerFitScreenError("target lineage style drifted")
    sources = value.get("sources")
    if not isinstance(sources, dict):
        raise SpeakerFitScreenError("target lineage sources are missing")
    archive = sources.get("target_archive")
    if not isinstance(archive, dict) or archive.get("sha256") != expected_archive_sha:
        raise SpeakerFitScreenError("target archive identity drifted")
    rows = value.get("rows")
    if not isinstance(rows, list):
        raise SpeakerFitScreenError("target lineage rows are missing")
    matching = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("row_id") == row_id
    ]
    if len(matching) != 1:
        raise SpeakerFitScreenError("target lineage row is not unique")
    raw = matching[0].get("target_wav")
    if not isinstance(raw, dict) or raw.get("sha256") != expected_raw_sha:
        raise SpeakerFitScreenError("target lineage raw WAV drifted")
    return expected_listener_sha


def _row_contract(
    root: Path,
    row_name: str,
    *,
    expected_variant: str,
    expected_target_sha: str,
) -> tuple[Path, Path, Path, str, str, str]:
    row_root = root / row_name
    index = _load_object(row_root / "index.json", f"{row_name} listener index")
    if index.get("status") != "completed-listen-now-unselected":
        raise SpeakerFitScreenError(f"{row_name} is not a completed unselected row")
    source = row_root / _text(index.get("source_output_file"), "source_output_file")
    target = row_root / _text(
        index.get("target_reference_output_file"), "target_reference_output_file"
    )
    variants = index.get("variants")
    if not isinstance(variants, list):
        raise SpeakerFitScreenError(f"{row_name} variants are missing")
    matching = [
        variant
        for variant in variants
        if isinstance(variant, dict) and variant.get("variant_id") == expected_variant
    ]
    if len(matching) != 1:
        raise SpeakerFitScreenError(f"{row_name} expected variant is not unique")
    variant = matching[0]
    output = row_root / _text(variant.get("output_file"), "variant output_file")
    for path, label in ((source, "source"), (target, "target"), (output, "output")):
        if path.is_symlink() or not path.is_file():
            raise SpeakerFitScreenError(f"{row_name} {label} WAV is unavailable")
    source_sha = inspect_pcm_wav(source).sha256
    target_sha = inspect_pcm_wav(target).sha256
    output_sha = inspect_pcm_wav(output).sha256
    if target_sha != expected_target_sha:
        raise SpeakerFitScreenError(f"{row_name} target reference drifted")
    if output_sha != _digest(variant.get("output_sha256"), "variant output_sha256"):
        raise SpeakerFitScreenError(f"{row_name} output identity drifted")
    return source, target, output, source_sha, target_sha, output_sha


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise SpeakerFitScreenError("cannot aggregate an empty surface")
    result = sum(values) / len(values)
    if not math.isfinite(result):
        raise SpeakerFitScreenError("speaker aggregate is not finite")
    return result


def _aggregate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    deltas = [float(row["delta"]["target_to_output"]) for row in rows]
    tolerance = 1e-6
    return {
        "rows": len(rows),
        "old": {
            key: _mean([float(row["old"][key]) for row in rows])
            for key in ("target_to_output", "source_to_output", "target_advantage")
        },
        "new": {
            key: _mean([float(row["new"][key]) for row in rows])
            for key in ("target_to_output", "source_to_output", "target_advantage")
        },
        "delta": {
            key: _mean([float(row["delta"][key]) for row in rows])
            for key in ("target_to_output", "source_to_output", "target_advantage")
        },
        "new_vs_old_target_similarity": {
            "wins": sum(delta > tolerance for delta in deltas),
            "ties": sum(abs(delta) <= tolerance for delta in deltas),
            "losses": sum(delta < -tolerance for delta in deltas),
            "tie_tolerance": tolerance,
        },
    }


def run(
    arguments: argparse.Namespace,
    *,
    backend_factory: Callable[..., Any] = SpeechBrainEcapaBackend,
) -> dict[str, Any]:
    plan = _load_object(arguments.surface_plan, "surface plan")
    if plan.get("schema_version") != 1:
        raise SpeakerFitScreenError("surface plan schema_version must be 1")
    expected_target_sha = _validate_target_lineage(plan, arguments.target_manifest)
    expected_model_sha = _digest(arguments.model_sha256, "model_sha256")
    if sha256_model_tree(arguments.model_artifact) != expected_model_sha:
        raise SpeakerFitScreenError("speaker model digest does not match")

    surfaces = plan.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise SpeakerFitScreenError("surface plan must contain surfaces")
    contracts: list[dict[str, Any]] = []
    for surface in surfaces:
        if not isinstance(surface, dict):
            raise SpeakerFitScreenError("surface entry must be an object")
        name = _text(surface.get("name"), "surface name")
        old_root = _resolve_repo_path(surface.get("old_listener_root"), "old root")
        new_root = _resolve_repo_path(surface.get("new_listener_root"), "new root")
        old_variant = _text(surface.get("old_variant_id"), "old variant_id")
        new_variant = _text(surface.get("new_variant_id"), "new variant_id")
        old_rows = sorted(path.name for path in old_root.iterdir() if path.is_dir())
        new_rows = sorted(path.name for path in new_root.iterdir() if path.is_dir())
        if not old_rows or old_rows != new_rows:
            raise SpeakerFitScreenError(f"{name} row frontier drifted")
        for row_name in old_rows:
            old = _row_contract(
                old_root,
                row_name,
                expected_variant=old_variant,
                expected_target_sha=expected_target_sha,
            )
            new = _row_contract(
                new_root,
                row_name,
                expected_variant=new_variant,
                expected_target_sha=expected_target_sha,
            )
            if old[3] != new[3] or old[4] != new[4]:
                raise SpeakerFitScreenError(f"{name}/{row_name} references drifted")
            contracts.append(
                {
                    "surface": name,
                    "row_id": row_name,
                    "source_path": old[0],
                    "target_path": old[1],
                    "old_path": old[2],
                    "new_path": new[2],
                    "source_sha256": old[3],
                    "target_sha256": old[4],
                    "old_sha256": old[5],
                    "new_sha256": new[5],
                }
            )

    backend = backend_factory(
        arguments.model_artifact,
        expected_sha256=expected_model_sha,
        device=arguments.device,
    )
    embedding_cache: dict[str, Sequence[float]] = {}

    def embed(path: Path, digest: str) -> Sequence[float]:
        if digest not in embedding_cache:
            embedding_cache[digest] = tuple(backend.embed(path))
        return embedding_cache[digest]

    result_rows: list[dict[str, Any]] = []
    for contract in contracts:
        source = embed(contract["source_path"], contract["source_sha256"])
        target = embed(contract["target_path"], contract["target_sha256"])
        old = compare_embeddings(
            source,
            target,
            embed(contract["old_path"], contract["old_sha256"]),
            ALWAYS_PASS,
        )
        new = compare_embeddings(
            source,
            target,
            embed(contract["new_path"], contract["new_sha256"]),
            ALWAYS_PASS,
        )
        old_metrics = old.to_dict()
        new_metrics = new.to_dict()
        keys = ("target_to_output", "source_to_output", "target_advantage")
        result_rows.append(
            {
                "surface": contract["surface"],
                "row_id": contract["row_id"],
                "sha256": {
                    name: contract[f"{name}_sha256"]
                    for name in ("source", "target", "old", "new")
                },
                "old": {key: old_metrics[key] for key in keys},
                "new": {key: new_metrics[key] for key in keys},
                "delta": {key: new_metrics[key] - old_metrics[key] for key in keys},
            }
        )

    names = [_text(surface.get("name"), "surface name") for surface in surfaces]
    per_surface = {
        name: _aggregate([row for row in result_rows if row["surface"] == name])
        for name in names
    }
    git_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    report = {
        "schema_version": 1,
        "kind": "liveconv-exp251-xvc-speaker-fit-screen/v1",
        "status": "completed-auxiliary-unselected",
        "git_commit": git_commit,
        "surface_plan_sha256": _sha256(arguments.surface_plan),
        "target_lineage_manifest_sha256": _sha256(arguments.target_manifest),
        "model": {
            "implementation": "speechbrain-ecapa-voxceleb",
            "tree_sha256": expected_model_sha,
            "device": arguments.device,
            "embedding_dimensions": 192,
            "unique_audio_embeddings": len(embedding_cache),
            "embeddings_persisted": False,
        },
        "aggregate": _aggregate(result_rows),
        "surfaces": per_surface,
        "rows": result_rows,
        "claims": {
            "person_identified": False,
            "naturalness_measured": False,
            "perceptual_winner": False,
            "promoted": False,
        },
        "limitations": [
            "Speaker embeddings are an auxiliary target-fit direction diagnostic.",
            "They cannot select naturalness, prosody, emotion, or a perceptual winner.",
            "The human target is operator-authorized private material; no audio "
            "or embedding is persisted by this report.",
        ],
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface-plan", type=Path, required=True)
    parser.add_argument("--target-manifest", type=Path, required=True)
    parser.add_argument("--model-artifact", type=Path, required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        report = run(arguments)
    except (OSError, SpeakerFitScreenError, ValueError) as error:
        print(f"screen_speaker_fit: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": report["status"],
                "rows": report["aggregate"]["rows"],
                "unique_audio_embeddings": report["model"]["unique_audio_embeddings"],
                "output": str(arguments.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
