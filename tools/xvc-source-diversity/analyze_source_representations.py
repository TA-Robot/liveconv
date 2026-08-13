#!/usr/bin/env python3
"""Extract source-side X-VC representation diagnostics for loop-prone inputs.

The output is exploratory fault-isolation evidence. It cannot authorize a
quality winner or a production bypass threshold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

TOOL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOL_ROOT.parents[1]
HUMAN_TOOL_ROOT = REPO_ROOT / "tools" / "xvc-human-paired"
for import_root in (TOOL_ROOT, HUMAN_TOOL_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import listen_now as base  # noqa: E402
import render_commonvoice as external  # noqa: E402

KIND = "liveconv-exp093-xvc-source-representation-audit/v1"
EVALUATION_KIND = "liveconv-exp055-commonvoice-local-unused/v1"
EXPECTED_ROWS = 33
EXPECTED_SCREEN_KIND = "liveconv-xvc-machine-content-screen/v2"
EXPECTED_CANDIDATE_VARIANTS = {
    "cv12-target275",
    "cv12-wave-adversarial",
    "cv12-source-semantic",
    "cv12-denoise-semantic",
}


class RepresentationAuditError(RuntimeError):
    """The fixed EXP-093 diagnostic cannot safely continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def token_statistics(values: Sequence[int]) -> dict[str, float | int]:
    if not values:
        raise RepresentationAuditError("semantic token sequence is empty")
    counts = Counter(int(value) for value in values)
    longest_run = 1
    current_run = 1
    for previous, current in zip(values, values[1:], strict=False):
        if current == previous:
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 1
    total = len(values)
    entropy = -sum(
        (count / total) * math.log2(count / total) for count in counts.values()
    )
    adjacent_repeats = sum(
        previous == current
        for previous, current in zip(values, values[1:], strict=False)
    )
    return {
        "token_count": total,
        "unique_tokens": len(counts),
        "dominant_token_fraction": max(counts.values()) / total,
        "entropy_bits": entropy,
        "adjacent_repeat_fraction": adjacent_repeats / max(total - 1, 1),
        "longest_token_run": longest_run,
        "transition_count": total - 1 - adjacent_repeats,
    }


def waveform_statistics(values: Sequence[float]) -> dict[str, float | int]:
    if not values:
        raise RepresentationAuditError("source waveform is empty")
    samples = [float(value) for value in values]
    total = len(samples)
    peak = max(abs(value) for value in samples)
    rms = math.sqrt(sum(value * value for value in samples) / total)
    active_threshold = max(peak * 0.01, 1e-4)
    active = [
        index
        for index, value in enumerate(samples)
        if abs(value) >= active_threshold
    ]
    sign_changes = sum(
        (left < 0.0 <= right) or (right < 0.0 <= left)
        for left, right in zip(samples, samples[1:], strict=False)
    )
    return {
        "sample_count": total,
        "peak_abs": peak,
        "rms": rms,
        "mean_abs": sum(abs(value) for value in samples) / total,
        "active_sample_fraction": len(active) / total,
        "first_active_fraction": active[0] / total if active else 1.0,
        "last_active_fraction": active[-1] / total if active else 0.0,
        "zero_crossing_fraction": sign_changes / max(total - 1, 1),
    }


def load_loop_observations(paths: Sequence[Path]) -> list[dict[str, object]]:
    observations: list[dict[str, object]] = []
    seen_candidate_variants: set[str] = set()
    for path in paths:
        try:
            screen = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RepresentationAuditError(f"screen is unreadable: {path}") from error
        kind = screen.get("kind")
        rows = screen.get("rows")
        variants = screen.get("variants")
        if (
            kind != EXPECTED_SCREEN_KIND
            or not isinstance(rows, list)
            or not isinstance(variants, dict)
        ):
            raise RepresentationAuditError(f"unexpected expanded screen: {path}")
        candidates = (
            set(variants)
            - {"base", "cv12-control69", "cv12-standard"}
        )
        if len(candidates) != 1:
            raise RepresentationAuditError(f"candidate arm drifted: {path}")
        seen_candidate_variants.update(candidates)
        for row in rows:
            repetition = row.get("repetition") if isinstance(row, dict) else None
            if not isinstance(repetition, dict) or not repetition.get(
                "gross_repetition"
            ):
                continue
            observations.append(
                {
                    "screen_kind": kind,
                    "source_id": row.get("source_id"),
                    "variant": row.get("variant"),
                    "source_relative_distance": row.get("source_relative_distance"),
                }
            )
    if seen_candidate_variants != EXPECTED_CANDIDATE_VARIANTS:
        raise RepresentationAuditError("expanded screen set is incomplete")
    return observations


def exploratory_separation(
    rows: Sequence[Mapping[str, object]], loop_source_ids: set[str]
) -> list[dict[str, object]]:
    """Rank simple one-sided rules; never treat them as fitted production gates."""
    if not loop_source_ids:
        raise RepresentationAuditError("no labelled loop sources were supplied")
    metric_names = sorted(
        key
        for section in ("waveform", "tokens", "hidden")
        for key in rows[0][section]
    )
    candidates: list[dict[str, object]] = []
    for metric in metric_names:
        section = next(
            name for name in ("waveform", "tokens", "hidden") if metric in rows[0][name]
        )
        labelled = [
            (str(row["source_id"]), float(row[section][metric])) for row in rows
        ]
        loop_values = [
            value for source_id, value in labelled if source_id in loop_source_ids
        ]
        if len(loop_values) != len(loop_source_ids):
            raise RepresentationAuditError("loop source is missing from extracted rows")
        rules = (("low", max(loop_values)), ("high", min(loop_values)))
        for direction, threshold in rules:
            flagged = [
                source_id
                for source_id, value in labelled
                if (value <= threshold if direction == "low" else value >= threshold)
            ]
            if not loop_source_ids <= set(flagged):
                continue
            candidates.append(
                {
                    "metric": f"{section}.{metric}",
                    "direction": direction,
                    "threshold_inclusive": threshold,
                    "flagged_rows": len(flagged),
                    "nonloop_rows_flagged": len(set(flagged) - loop_source_ids),
                    "loop_rows_covered": len(loop_source_ids),
                }
            )
    return sorted(
        candidates,
        key=lambda item: (
            int(item["nonloop_rows_flagged"]),
            int(item["flagged_rows"]),
            str(item["metric"]),
            str(item["direction"]),
        ),
    )


def load_evaluation(path: Path, source_root: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RepresentationAuditError("evaluation set is unreadable") from error
    items = value.get("items") if isinstance(value, dict) else None
    if value.get("kind") != EVALUATION_KIND or not isinstance(items, list):
        raise RepresentationAuditError("expanded evaluation identity drifted")
    identifiers = {item.get("id") for item in items}
    if len(items) != EXPECTED_ROWS or len(identifiers) != EXPECTED_ROWS:
        raise RepresentationAuditError("expanded evaluation row count drifted")
    for item in items:
        path = source_root / str(item.get("filename"))
        invalid = (
            not path.is_file()
            or path.is_symlink()
            or sha256_file(path) != item.get("sha256")
        )
        if invalid:
            raise RepresentationAuditError(f"evaluation source drifted: {path.name}")
    return value


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
        raise RepresentationAuditError("cannot resolve git commit") from error


def run(arguments: argparse.Namespace, evaluation: Mapping[str, Any]) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise RepresentationAuditError(f"{name}=1 is required")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise RepresentationAuditError("EXP-093 requires the explicit gpu0 lease")
    if arguments.output.exists() or arguments.output.is_symlink():
        raise RepresentationAuditError("output already exists")
    if not arguments.output.parent.is_dir():
        raise RepresentationAuditError("output parent is unavailable")

    loop_observations = load_loop_observations(arguments.screen)
    loop_source_ids = {str(item["source_id"]) for item in loop_observations}
    started = time.monotonic()

    import torch

    if not torch.cuda.is_available():
        raise RepresentationAuditError("CUDA is unavailable")
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
        str(arguments.xvc_config),
        str(arguments.checkpoint),
        device,
        ema_load=False,
    )

    rows: list[dict[str, object]] = []
    for item in evaluation["items"]:
        values = external.padded_model_audio(
            arguments.source_root / item["filename"], process_audio, config
        )
        waveform = torch.from_numpy(values).reshape(1, -1).to(device=device)
        with torch.inference_mode():
            features = model.semantic_encoder.extract_and_encode(waveform)
        tokens = features.get("speech_tokens")
        hidden = features.get("whisper_hidden_states_50hz")
        if tokens is None or hidden is None:
            raise RepresentationAuditError(f"semantic features missing: {item['id']}")
        token_values = tokens[:, : base.SEMANTIC_FRAMES].reshape(-1).cpu().tolist()
        hidden_values = hidden[..., : base.TARGET_HIDDEN_FRAMES].to(torch.float32)
        temporal_delta = torch.diff(hidden_values, dim=-1)
        rows.append(
            {
                "source_id": item["id"],
                "source_sha256": item["sha256"],
                "known_text_characters": len(str(item["text"])),
                "waveform": waveform_statistics(values.tolist()),
                "tokens": token_statistics(token_values),
                "hidden": {
                    "global_std": float(hidden_values.std().item()),
                    "mean_abs": float(hidden_values.abs().mean().item()),
                    "temporal_delta_rms": float(
                        torch.sqrt(torch.mean(temporal_delta.square())).item()
                    ),
                    "temporal_std_mean": float(
                        hidden_values.std(dim=-1).mean().item()
                    ),
                },
            }
        )

    result = {
        "schema_version": 1,
        "kind": KIND,
        "status": "completed-exploratory-diagnostic",
        "git_commit": git_commit(),
        "evaluation_set_sha256": sha256_file(arguments.evaluation_set),
        "evaluation_rows": len(rows),
        "loop_source_ids": sorted(loop_source_ids),
        "loop_observations": loop_observations,
        "rows": rows,
        "exploratory_one_sided_rules": exploratory_separation(rows, loop_source_ids),
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "claims": {
            "production_gate": False,
            "perceptual_winner": False,
            "causal_explanation": False,
        },
    }
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "rows": len(rows),
                "loop_sources": sorted(loop_source_ids),
                "best_exploratory_rules": result["exploratory_one_sided_rules"][:5],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--evaluation-set", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--screen", type=Path, action="append", required=True)
    parser.add_argument("--xvc-source-root", type=Path, required=True)
    parser.add_argument("--xvc-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    parser.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        evaluation = load_evaluation(arguments.evaluation_set, arguments.source_root)
        observations = load_loop_observations(arguments.screen)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "evaluation_rows": len(evaluation["items"]),
                        "loop_sources": sorted(
                            {str(item["source_id"]) for item in observations}
                        ),
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, evaluation)
    except (RepresentationAuditError, OSError, ValueError) as error:
        print(f"exp093-representation-audit-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
