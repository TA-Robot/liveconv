#!/usr/bin/env python3
"""Validate EXP-093's frozen low-token rule on disjoint X-VC failures."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

TOOL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOL_ROOT.parents[1]
HUMAN_TOOL_ROOT = REPO_ROOT / "tools" / "xvc-human-paired"
for import_root in (TOOL_ROOT, HUMAN_TOOL_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import analyze_source_representations as representation
import listen_now as base
import render_commonvoice as external

KIND = "liveconv-exp137-xvc-semantic-gate-validation/v1"
SCREEN_KIND = "liveconv-xvc-machine-content-screen/v2"
UNIQUE_TOKEN_THRESHOLD = 5
INPUTS = (
    (
        "fresh48",
        "liveconv-exp112-commonvoice-fresh48/v1",
        48,
        "cv12-real-teacher-output-window48",
    ),
    (
        "hadou31",
        "liveconv-exp060-hadou-clean-heldout/v1",
        31,
        "cv12-real-teacher-output-window48",
    ),
)


class SemanticGateError(RuntimeError):
    """The disjoint semantic-gate validation cannot continue safely."""


def load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SemanticGateError(f"invalid JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise SemanticGateError(f"JSON root is not an object: {path.name}")
    return value


def load_input(
    name: str,
    manifest_path: Path,
    source_root: Path,
    screen_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, set[str]]]:
    expected = next(value for value in INPUTS if value[0] == name)
    manifest = load_json(manifest_path)
    screen = load_json(screen_path)
    items = manifest.get("items")
    screen_rows = screen.get("rows")
    if (
        manifest.get("kind") != expected[1]
        or not isinstance(items, list)
        or len(items) != expected[2]
        or screen.get("kind") != SCREEN_KIND
        or not isinstance(screen_rows, list)
    ):
        raise SemanticGateError(f"{name} input schema drifted")
    ids = {str(item.get("id")) for item in items if isinstance(item, dict)}
    if len(ids) != expected[2]:
        raise SemanticGateError(f"{name} input identities drifted")
    output: list[dict[str, Any]] = []
    for item in items:
        filename = item.get("filename") if isinstance(item, dict) else None
        path = source_root / str(filename)
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or path.is_symlink()
            or not path.is_file()
            or representation.sha256_file(path) != item.get("sha256")
        ):
            raise SemanticGateError(f"{name} source drifted: {filename}")
        output.append(
            {
                "dataset": name,
                "source_id": str(item["id"]),
                "source_sha256": item["sha256"],
                "path": path,
            }
        )
    variants = {str(row.get("variant")) for row in screen_rows if isinstance(row, dict)}
    candidate = expected[3]
    if not {"base", candidate} <= variants:
        raise SemanticGateError(f"{name} screen variants drifted")
    screen_ids = {str(row.get("source_id")) for row in screen_rows if isinstance(row, dict)}
    if screen_ids != ids:
        raise SemanticGateError(f"{name} screen identities drifted")
    loops: dict[str, set[str]] = {variant: set() for variant in variants}
    for row in screen_rows:
        repetition = row.get("repetition") if isinstance(row, dict) else None
        if isinstance(repetition, dict) and repetition.get("gross_repetition"):
            loops[str(row["variant"])].add(str(row["source_id"]))
    loops["candidate_added_vs_base"] = loops[candidate] - loops["base"]
    loops["candidate_all"] = set(loops[candidate])
    return output, loops


def evaluate_rule(
    rows: Sequence[Mapping[str, Any]],
    labels: set[str],
    *,
    threshold: int = UNIQUE_TOKEN_THRESHOLD,
) -> dict[str, Any]:
    identifiers = {str(row["source_id"]) for row in rows}
    if not labels <= identifiers:
        raise SemanticGateError("loop labels are absent from extracted rows")
    flagged = {
        str(row["source_id"])
        for row in rows
        if int(row["tokens"]["unique_tokens"]) <= threshold
    }
    return {
        "rule": f"tokens.unique_tokens <= {threshold}",
        "rows": len(rows),
        "labelled_loop_rows": len(labels),
        "flagged_rows": len(flagged),
        "true_positive_rows": len(flagged & labels),
        "false_negative_rows": len(labels - flagged),
        "false_positive_rows": len(flagged - labels),
        "labelled_loop_ids": sorted(labels),
        "flagged_ids": sorted(flagged),
        "false_negative_ids": sorted(labels - flagged),
        "false_positive_ids": sorted(flagged - labels),
    }


def git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as error:
        raise SemanticGateError("cannot resolve git commit") from error


def run(arguments: argparse.Namespace) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise SemanticGateError(f"{name}=1 is required")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise SemanticGateError("EXP-137 requires the explicit gpu0 lease")
    if arguments.output.exists() or arguments.output.is_symlink():
        raise SemanticGateError("output already exists")

    all_inputs: list[dict[str, Any]] = []
    labels_by_dataset: dict[str, dict[str, set[str]]] = {}
    for name, manifest, source_root, screen in (
        ("fresh48", arguments.fresh_evaluation, arguments.fresh_root, arguments.fresh_screen),
        ("hadou31", arguments.hadou_evaluation, arguments.hadou_root, arguments.hadou_screen),
    ):
        inputs, labels = load_input(name, manifest, source_root, screen)
        all_inputs.extend(inputs)
        labels_by_dataset[name] = labels

    started = time.monotonic()
    import torch

    if not torch.cuda.is_available():
        raise SemanticGateError("CUDA is unavailable")
    device = torch.device(arguments.device)
    base._configure_deterministic_cuda(torch, device)
    torch.cuda.reset_peak_memory_stats(device)
    xvc_root = str(arguments.xvc_source_root.resolve())
    if xvc_root not in sys.path:
        sys.path.insert(0, xvc_root)
    from models.codec.sac.model import XVC
    from models.codec.sac.utils import process_audio
    from utils.file import load_config

    config = load_config(str(arguments.xvc_config))
    if "config" in config:
        config = config["config"]
    model = XVC.load_from_checkpoint(
        str(arguments.xvc_config), str(arguments.checkpoint), device, ema_load=False
    )
    rows: list[dict[str, Any]] = []
    for item in all_inputs:
        values = external.padded_model_audio(item["path"], process_audio, config)
        waveform = torch.from_numpy(values).reshape(1, -1).to(device=device)
        with torch.inference_mode():
            features = model.semantic_encoder.extract_and_encode(waveform)
        tokens = features.get("speech_tokens")
        hidden = features.get("whisper_hidden_states_50hz")
        if tokens is None or hidden is None:
            raise SemanticGateError(f"semantic features missing: {item['source_id']}")
        token_values = tokens[:, : base.SEMANTIC_FRAMES].reshape(-1).cpu().tolist()
        hidden_values = hidden[..., : base.TARGET_HIDDEN_FRAMES].to(torch.float32)
        temporal_delta = torch.diff(hidden_values, dim=-1)
        rows.append(
            {
                "dataset": item["dataset"],
                "source_id": item["source_id"],
                "source_sha256": item["source_sha256"],
                "tokens": representation.token_statistics(token_values),
                "waveform": representation.waveform_statistics(values.tolist()),
                "hidden": {
                    "global_std": float(hidden_values.std().item()),
                    "mean_abs": float(hidden_values.abs().mean().item()),
                    "temporal_delta_rms": float(
                        torch.sqrt(torch.mean(temporal_delta.square())).item()
                    ),
                },
            }
        )

    evaluations: dict[str, Any] = {}
    for name in ("fresh48", "hadou31"):
        dataset_rows = [row for row in rows if row["dataset"] == name]
        evaluations[name] = {
            label: evaluate_rule(dataset_rows, labels_by_dataset[name][label])
            for label in ("candidate_added_vs_base", "candidate_all")
        }
    combined_added = set().union(
        *(labels_by_dataset[name]["candidate_added_vs_base"] for name in labels_by_dataset)
    )
    evaluations["combined_candidate_added_vs_base"] = evaluate_rule(rows, combined_added)
    result = {
        "schema_version": 1,
        "kind": KIND,
        "status": "completed-disjoint-validation",
        "git_commit": git_commit(),
        "precommitted_rule": "tokens.unique_tokens <= 5 from EXP-093",
        "boundary": (
            "disjoint source-representation safety validation only; not a "
            "naturalness, target-identity, or quality-winner metric and not a "
            "production bypass authorization"
        ),
        "inputs": {
            "fresh_evaluation_sha256": representation.sha256_file(arguments.fresh_evaluation),
            "fresh_screen_sha256": representation.sha256_file(arguments.fresh_screen),
            "hadou_evaluation_sha256": representation.sha256_file(arguments.hadou_evaluation),
            "hadou_screen_sha256": representation.sha256_file(arguments.hadou_screen),
        },
        "evaluations": evaluations,
        "rows": rows,
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "claims": {"production_gate": False, "perceptual_winner": False},
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evaluations, ensure_ascii=False, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--fresh-evaluation", type=Path, required=True)
    value.add_argument("--fresh-root", type=Path, required=True)
    value.add_argument("--fresh-screen", type=Path, required=True)
    value.add_argument("--hadou-evaluation", type=Path, required=True)
    value.add_argument("--hadou-root", type=Path, required=True)
    value.add_argument("--hadou-screen", type=Path, required=True)
    value.add_argument("--xvc-source-root", type=Path, required=True)
    value.add_argument("--xvc-config", type=Path, required=True)
    value.add_argument("--checkpoint", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    value.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(parser().parse_args(argv))
    except (SemanticGateError, OSError, ValueError) as error:
        print(f"semantic-gate-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
