#!/usr/bin/env python3
"""Render a content-safe target-context admission check for EXP-037."""

from __future__ import annotations

import argparse
import json
import os
import shutil
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

import listen_now as base  # noqa: E402
import run as method  # noqa: E402
import run_breadth as breadth  # noqa: E402

TARGET_ID = "EMOTION100_003"
TARGET_SHA256 = "76f5a4a9b989ed692a55343a7681623fa4f18e354ca04026f022e3e449195ca2"
CONTEXT_ID = "EMOTION100_009"
CONTEXT_SHA256 = "b72968fdb75180397267bb8799fb12452d93c55a37719a845e1943c70f8205ac"


class ContextRenderError(RuntimeError):
    """The bounded EXP-037 context render cannot safely continue."""


def target_condition(reference: Any, context: Any, torch: Any) -> Any:
    """Append a zeroed current window after a separate target utterance."""
    target_wave = reference["target_wav"]
    context_wave = context["target_wav"]
    if target_wave.shape != context_wave.shape:
        raise ContextRenderError("target context waveform shape drifted")
    return torch.cat((context_wave, torch.zeros_like(target_wave)), dim=-1)


def contextual_inference(
    model: Any,
    source: Mapping[str, Any],
    reference: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    seed: int,
    torch: Any,
    device: Any,
) -> Any:
    index = device.index
    if index is None:
        raise ContextRenderError("render requires numbered cuda:0")
    batch = {
        "source_wav": source["source_wav"].to(device=device, dtype=torch.float32),
        "target_wav": reference["target_wav"].to(
            device=device, dtype=torch.float32
        ),
        "semantic_tokens": source["semantic_tokens"].to(
            device=device, dtype=torch.int64
        ),
        "ssl_feat": reference["ssl_feat"].to(device=device, dtype=torch.float32),
    }
    batch["target_wav_cond"] = target_condition(reference, context, torch).to(
        device=device, dtype=torch.float32
    )
    model.eval()
    with torch.random.fork_rng(devices=[index], enabled=True), torch.no_grad():
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        rendered = model.inference(batch).get("recons")
    if (
        rendered is None
        or rendered.shape != (1, 1, base.MODEL_SAMPLES)
        or not bool(torch.isfinite(rendered).all())
    ):
        raise ContextRenderError("contextual render is not finite 2.4-second mono")
    return rendered


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], list[tuple[str, Path, str]]]:
    evaluation = breadth._load_manifest(
        arguments.evaluation_set,
        kind=breadth.EVALUATION_KIND,
        count=breadth.EVALUATION_COUNT,
    )
    for item in evaluation["items"]:
        path = arguments.source_root / item["filename"]
        if (
            path.is_symlink()
            or not path.is_file()
            or base.sha256_file(path) != item["sha256"]
        ):
            raise ContextRenderError(f"Common Voice input drifted: {item['filename']}")
    targets = method.target_inventory(arguments.pair_root)
    identities = {pair_id: digest for pair_id, _path, digest in targets}
    if identities.get(TARGET_ID) != TARGET_SHA256:
        raise ContextRenderError("target reference identity drifted")
    if identities.get(CONTEXT_ID) != CONTEXT_SHA256:
        raise ContextRenderError("target context identity drifted")
    if arguments.adapter.is_symlink() or not (
        arguments.adapter / "adapter_model.safetensors"
    ).is_file():
        raise ContextRenderError("EXP-035 adapter is unavailable")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-037 work directory",
    )
    base._require_new_output(
        arguments.listener_dir,
        REPO_ROOT / "artifacts" / "ms3" / "listening",
        "EXP-037 listener directory",
    )
    return evaluation, targets


def listening_index(
    item: Mapping[str, Any], *, hashes: Mapping[str, str]
) -> dict[str, object]:
    variants = (
        (
            "cv12-zero-condition",
            "EXP-035 / CV12 / all-zero target condition",
            "10-xvc-cv12-zero-condition.wav",
            1,
        ),
        (
            "cv12-context-condition",
            "EXP-035 / CV12 / separate Amitaro context + masked current window",
            "20-xvc-cv12-context-condition.wav",
            2,
        ),
    )
    return {
        "schema_version": 1,
        "run_kind": "EXP-037 X-VC target-context admission render",
        "status": "completed-listen-now-unselected",
        "source_file": (
            f"Common Voice 25.0 / {item['age']} / {item['gender']} / {item['text']}"
        ),
        "source_output_file": "00-source-reference.wav",
        "target_reference_output_file": "01-target-reference.wav",
        "reference_audio": [
            {
                "kind": "source",
                "label": f"Common Voice heldout / {item['text']}",
                "output_file": "00-source-reference.wav",
                "excluded_from_preference": True,
            },
            {
                "kind": "target",
                "label": f"Amitaro runrun / target {TARGET_ID}",
                "output_file": "01-target-reference.wav",
                "excluded_from_preference": True,
            },
            {
                "kind": "target-context",
                "label": f"Amitaro runrun / separate context {CONTEXT_ID}",
                "output_file": "02-target-context.wav",
                "excluded_from_preference": True,
            },
        ],
        "variants": [
            {
                "variant_id": variant_id,
                "display_name": display_name,
                "display_order": order,
                "output_file": filename,
                "status": "passed",
                "profile_id": f"xvc.exp037.{variant_id}.listen-now",
                "family_id": "x-vc",
                "output_sha256": hashes[variant_id],
            }
            for variant_id, display_name, filename, order in variants
        ],
    }


def run(
    arguments: argparse.Namespace,
    evaluation: Mapping[str, Any],
    target_rows: list[tuple[str, Path, str]],
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise ContextRenderError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise ContextRenderError("EXP-037 requires the explicit gpu0 lease")
    started = time.monotonic()
    arguments.work_dir.mkdir()
    evaluation_root = arguments.work_dir / "evaluation-sources"
    evaluation_root.mkdir()

    import torch
    from peft import PeftModel

    if not torch.cuda.is_available():
        raise ContextRenderError("CUDA is unavailable")
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
    sample_rate = int(config["sample_rate"])
    model_base = method._load_xvc(arguments, XVC, device)
    model = PeftModel.from_pretrained(
        model_base, str(arguments.adapter), is_trainable=False
    )
    by_id = {pair_id: (path, digest) for pair_id, path, digest in target_rows}

    def extract(pair_id: str) -> tuple[base.MaterializedPair, dict[str, Any]]:
        path, digest = by_id[pair_id]
        pair = base.MaterializedPair(pair_id, path, path, digest, digest)
        tensors = base._extract_pair_tensors(
            model,
            pair,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        return pair, tensors

    target_pair, target_tensor = extract(TARGET_ID)
    context_pair, context_tensor = extract(CONTEXT_ID)
    evaluation_pairs: list[base.MaterializedPair] = []
    evaluation_tensors: list[dict[str, Any]] = []
    for item in evaluation["items"]:
        pair, tensors = breadth._reference_tensor(
            model,
            item,
            source_root=arguments.source_root,
            output_root=evaluation_root,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        evaluation_pairs.append(pair)
        evaluation_tensors.append(tensors)

    zero_outputs = [
        base._inference(
            model,
            source,
            target_tensor,
            seed=base.SEED + index,
            torch=torch,
            device=device,
        )
        .detach()
        .cpu()
        for index, source in enumerate(evaluation_tensors)
    ]
    context_outputs = [
        contextual_inference(
            model,
            source,
            target_tensor,
            context_tensor,
            seed=base.SEED + index,
            torch=torch,
            device=device,
        )
        .detach()
        .cpu()
        for index, source in enumerate(evaluation_tensors)
    ]

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    listener_rows: list[dict[str, object]] = []
    for index, (item, pair) in enumerate(
        zip(evaluation["items"], evaluation_pairs, strict=True)
    ):
        row_root = staging / f"{index:02d}-{item['id']}"
        row_root.mkdir()
        shutil.copyfile(pair.source_path, row_root / "00-source-reference.wav")
        shutil.copyfile(target_pair.target_path, row_root / "01-target-reference.wav")
        shutil.copyfile(context_pair.target_path, row_root / "02-target-context.wav")
        hashes = {
            "cv12-zero-condition": base._write_float_wav(
                row_root / "10-xvc-cv12-zero-condition.wav",
                zero_outputs[index],
                sample_rate,
            ),
            "cv12-context-condition": base._write_float_wav(
                row_root / "20-xvc-cv12-context-condition.wav",
                context_outputs[index],
                sample_rate,
            ),
        }
        method._write_json(
            row_root / "index.json", listening_index(item, hashes=hashes)
        )
        listener_rows.append({"source_id": item["id"], "hashes": hashes})

    result = {
        "schema_version": 1,
        "kind": "liveconv-exp037-xvc-target-context-render-result/v1",
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": "Does content-safe target context avoid external corruption?",
        "independent_variable": (
            "target_wav_cond: all zeros versus separate Amitaro utterance followed "
            "by a zeroed 2.4-second current window"
        ),
        "training_update_count": 0,
        "target_reference": {"id": TARGET_ID, "sha256": TARGET_SHA256},
        "target_context": {"id": CONTEXT_ID, "sha256": CONTEXT_SHA256},
        "evaluation_set_sha256": base.sha256_file(arguments.evaluation_set),
        "adapter_model_sha256": base.sha256_file(
            arguments.adapter / "adapter_model.safetensors"
        ),
        "listener_rows": listener_rows,
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "claims": {
            "perceptual_winner": False,
            "promoted": False,
            "route_qualified": False,
        },
    }
    method._write_json(arguments.work_dir / "result.json", result)
    staging.rename(arguments.listener_dir)
    print(
        json.dumps(
            {
                "status": result["status"],
                "evaluation_rows": len(evaluation_pairs),
                "listener_dir": str(arguments.listener_dir),
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
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--xvc-source-root", type=Path, required=True)
    parser.add_argument("--xvc-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=(
            REPO_ROOT
            / "artifacts"
            / "exp007"
            / "phase0-inputs-v1"
            / "inventory.json"
        ),
    )
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--listener-dir", type=Path, required=True)
    parser.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    parser.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        evaluation, targets = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "evaluation_rows": len(evaluation["items"]),
                        "target_reference": TARGET_ID,
                        "target_context": CONTEXT_ID,
                        "training_updates": 0,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, evaluation, targets)
    except (
        base.ListenNowError,
        breadth.BreadthError,
        ContextRenderError,
        method.SourceDiversityError,
        OSError,
        ValueError,
    ) as error:
        print(f"exp037-context-render-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
