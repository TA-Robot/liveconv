from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .authorization import bind_target_authorization
from .backend import SpeechBrainEcapaBackend
from .evidence import (
    ComparisonPolicy,
    SpeakerEvidenceError,
    compare_embeddings,
    inspect_pcm_wav,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MODEL_REVISION_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,191}@sha256:([0-9a-f]{64})$"
)
BackendFactory = Callable[..., Any]


def _immutable_model_revision(value: str) -> str:
    if _MODEL_REVISION_RE.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(
            "model revision must end with @sha256:<lowercase digest>"
        )
    return value


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="liveconv-speaker")
    commands = root.add_subparsers(dest="command", required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("source", type=Path)
    compare.add_argument("target", type=Path)
    compare.add_argument("converted", type=Path)
    compare.add_argument("--model-artifact", type=Path, required=True)
    compare.add_argument("--model-sha256", required=True)
    compare.add_argument(
        "--model-revision", type=_immutable_model_revision, required=True
    )
    compare.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    compare.add_argument("--policy-label", required=True)
    compare.add_argument(
        "--policy-status", choices=("proposed", "approved"), required=True
    )
    compare.add_argument("--min-target-similarity", type=float, required=True)
    compare.add_argument("--min-target-gain", type=float, required=True)
    compare.add_argument("--min-target-advantage", type=float, required=True)
    authorization = compare.add_mutually_exclusive_group(required=True)
    authorization.add_argument("--target-authorization", type=Path)
    authorization.add_argument("--synthetic-corpus-manifest", type=Path)
    compare.add_argument("--output", type=Path, required=True)
    return root


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise SpeakerEvidenceError("output must be a regular non-symlink file")
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            destination.write(encoded)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def run(
    arguments: argparse.Namespace,
    *,
    backend_factory: BackendFactory = SpeechBrainEcapaBackend,
) -> int:
    if not _SHA256_RE.fullmatch(arguments.model_sha256):
        raise SpeakerEvidenceError("model SHA-256 must be lowercase hexadecimal")
    revision_match = _MODEL_REVISION_RE.fullmatch(arguments.model_revision)
    if revision_match is None or revision_match.group(1) != arguments.model_sha256:
        raise SpeakerEvidenceError(
            "model revision digest does not match the verified model artifact"
        )
    paths = [arguments.source, arguments.target, arguments.converted]
    resolved = [path.resolve(strict=True) for path in paths]
    if len(set(resolved)) != 3:
        raise SpeakerEvidenceError("source, target, and converted audio must differ")
    output = arguments.output.resolve()
    model_root = arguments.model_artifact.resolve(strict=True)
    authorization_path = (
        arguments.target_authorization
        if arguments.target_authorization is not None
        else arguments.synthetic_corpus_manifest
    )
    assert authorization_path is not None
    protected = [*resolved, model_root, authorization_path.resolve(strict=True)]
    if output in protected:
        raise SpeakerEvidenceError("output must not overwrite an input")
    if output == model_root or model_root in output.parents:
        raise SpeakerEvidenceError("output must not overlap the model artifact")

    artifacts = {
        role: inspect_pcm_wav(path)
        for role, path in zip(("source", "target", "output"), resolved)
    }
    target_authorization = bind_target_authorization(
        artifacts["target"].sha256,
        authorization_record=arguments.target_authorization,
        synthetic_corpus_manifest=arguments.synthetic_corpus_manifest,
    )

    policy = ComparisonPolicy(
        arguments.policy_label,
        arguments.policy_status,
        arguments.min_target_similarity,
        arguments.min_target_gain,
        arguments.min_target_advantage,
    )
    backend = backend_factory(
        arguments.model_artifact,
        expected_sha256=arguments.model_sha256,
        device=arguments.device,
    )
    embeddings = [backend.embed(path) for path in resolved]
    comparison = compare_embeddings(*embeddings, policy)
    lane_summary = (
        "All caller-supplied speaker-change thresholds passed."
        if comparison.status == "pass"
        else "At least one caller-supplied speaker-change threshold failed."
    )
    result = {
        "schema_version": 1,
        "report_type": "speaker-change-evidence",
        "evaluator": {
            "implementation": "liveconv-speaker-ecapa-v1",
            "model_revision": arguments.model_revision,
            "model_sha256": arguments.model_sha256,
            "runtime_lock": backend.runtime_lock.to_dict(),
            "device": arguments.device,
            "embedding_dimensions": 192,
            "embeddings_persisted": False,
        },
        "artifacts": {role: asdict(artifact) for role, artifact in artifacts.items()},
        "target_authorization": target_authorization.to_dict(),
        "policy": {
            "label": policy.label,
            "status": policy.status,
            "min_target_similarity": policy.min_target_similarity,
            "min_target_gain": policy.min_target_gain,
            "min_target_advantage": policy.min_target_advantage,
        },
        "speaker_change": comparison.to_dict(),
        "evaluation_lane": {
            "status": comparison.status,
            "summary": lane_summary,
            "evidence": list(comparison.evidence),
        },
        "limitations": [
            "Speaker embeddings estimate similarity; they do not identify a person.",
            "A proposed policy is technical evidence, not a product acceptance rule.",
        ],
    }
    _write_atomic(output, result)
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    backend_factory: BackendFactory = SpeechBrainEcapaBackend,
) -> int:
    arguments = parser().parse_args(argv)
    try:
        return run(arguments, backend_factory=backend_factory)
    except (OSError, SpeakerEvidenceError, ValueError):
        parser().error("speaker comparison failed")
    return 2
