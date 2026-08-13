#!/usr/bin/env python3
"""Render EXP-035 on EXP-033's frozen ten audio-condition rows."""

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


class ConditionRenderError(RuntimeError):
    """The fixed EXP-035 condition render cannot safely continue."""


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], list[tuple[str, Path, str]]]:
    evaluation = method.load_evaluation_set(arguments.evaluation_set)
    for item in evaluation["items"]:
        method._source_path(
            item, jvs_root=arguments.jvs_root, heldout_root=arguments.heldout_root
        )
    targets = method.target_inventory(arguments.pair_root)
    for label, adapter in (
        ("EXP-033 control", arguments.control_adapter),
        ("EXP-035 candidate", arguments.candidate_adapter),
    ):
        if adapter.is_symlink() or not (
            adapter / "adapter_model.safetensors"
        ).is_file():
            raise ConditionRenderError(f"{label} adapter is unavailable")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-035 condition work directory",
    )
    base._require_new_output(
        arguments.listener_dir,
        REPO_ROOT / "artifacts" / "ms3" / "listening",
        "EXP-035 condition listener directory",
    )
    return evaluation, targets


def listening_index(
    source: base.RenderSource,
    *,
    target_reference_id: str,
    hashes: Mapping[str, str],
) -> dict[str, object]:
    variants = (
        ("base", "X-VC base", "10-xvc-base.wav", 1),
        (
            "jvs3-generated-pairs",
            "EXP-033 / JVS 3 donor x 4 epochs / 1,044 updates",
            "20-xvc-jvs3-generated-pairs.wav",
            2,
        ),
        (
            "cv12-generated-pairs",
            "EXP-035 / Common Voice 12 donor x 1 epoch / 1,044 updates",
            "30-xvc-cv12-generated-pairs.wav",
            3,
        ),
    )
    return {
        "schema_version": 1,
        "run_kind": "EXP-035 X-VC frozen condition evaluation",
        "status": "completed-listen-now-unselected",
        "source_file": source.display_text,
        "source_output_file": "00-source-reference.wav",
        "target_reference_output_file": "01-target-reference.wav",
        "reference_audio": [
            {
                "kind": "source",
                "label": source.display_text,
                "output_file": "00-source-reference.wav",
                "excluded_from_preference": True,
            },
            {
                "kind": "target",
                "label": f"Amitaro runrun / {target_reference_id}",
                "output_file": "01-target-reference.wav",
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
                "profile_id": f"xvc.exp035.conditions.{variant_id}.listen-now",
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
            raise ConditionRenderError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise ConditionRenderError("EXP-035 condition render requires the gpu0 lease")
    started = time.monotonic()
    arguments.work_dir.mkdir()

    import torch
    from peft import PeftModel

    if not torch.cuda.is_available():
        raise ConditionRenderError("CUDA is unavailable")
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
    model = method._load_xvc(arguments, XVC, device)
    target_id, target_path, target_digest = target_rows[0]
    target_pair = base.MaterializedPair(
        target_id, target_path, target_path, target_digest, target_digest
    )
    target_tensor = base._extract_pair_tensors(
        model,
        target_pair,
        process_audio=process_audio,
        config=config,
        torch=torch,
        device=device,
    )
    sources = method.materialize_evaluation_sources(
        evaluation,
        output_root=arguments.work_dir / "evaluation-sources",
        jvs_root=arguments.jvs_root,
        heldout_root=arguments.heldout_root,
        process_audio=process_audio,
        config=config,
    )
    source_tensors = [
        base._extract_render_source(
            model,
            source,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        for source in sources
    ]

    def render(current: Any) -> list[Any]:
        return [
            base._inference(
                current,
                source,
                target_tensor,
                seed=base.SEED + index,
                torch=torch,
                device=device,
            )
            .detach()
            .cpu()
            for index, source in enumerate(source_tensors)
        ]

    outputs = {"base": render(model)}
    for label, adapter in (
        ("jvs3-generated-pairs", arguments.control_adapter),
        ("cv12-generated-pairs", arguments.candidate_adapter),
    ):
        adapted_base = method._load_xvc(arguments, XVC, device)
        adapted = PeftModel.from_pretrained(
            adapted_base, str(adapter), is_trainable=False
        )
        outputs[label] = render(adapted)
        del adapted, adapted_base
        torch.cuda.empty_cache()

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    listener_rows: list[dict[str, object]] = []
    for index, source in enumerate(sources):
        row_root = staging / f"{index:02d}-{source.pair_id}"
        row_root.mkdir()
        shutil.copyfile(source.source_path, row_root / "00-source-reference.wav")
        shutil.copyfile(target_pair.target_path, row_root / "01-target-reference.wav")
        hashes = {
            "base": base._write_float_wav(
                row_root / "10-xvc-base.wav", outputs["base"][index], sample_rate
            ),
            "jvs3-generated-pairs": base._write_float_wav(
                row_root / "20-xvc-jvs3-generated-pairs.wav",
                outputs["jvs3-generated-pairs"][index],
                sample_rate,
            ),
            "cv12-generated-pairs": base._write_float_wav(
                row_root / "30-xvc-cv12-generated-pairs.wav",
                outputs["cv12-generated-pairs"][index],
                sample_rate,
            ),
        }
        method._write_json(
            row_root / "index.json",
            listening_index(
                source, target_reference_id=target_pair.pair_id, hashes=hashes
            ),
        )
        listener_rows.append(
            {
                "source_id": source.pair_id,
                "group": evaluation["items"][index]["group"],
                "hashes": hashes,
            }
        )

    result = {
        "schema_version": 1,
        "kind": "liveconv-exp035-xvc-condition-render-result/v1",
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "training_update_count": 0,
        "evaluation_set_sha256": base.sha256_file(arguments.evaluation_set),
        "evaluation_rows": listener_rows,
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
                "evaluation_rows": len(listener_rows),
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
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--jvs-root", type=Path, required=True)
    parser.add_argument("--heldout-root", type=Path, required=True)
    parser.add_argument("--control-adapter", type=Path, required=True)
    parser.add_argument("--candidate-adapter", type=Path, required=True)
    parser.add_argument("--xvc-source-root", type=Path, required=True)
    parser.add_argument("--xvc-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=REPO_ROOT
        / "artifacts"
        / "exp007"
        / "phase0-inputs-v1"
        / "inventory.json",
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
                        "training_updates": 0,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, evaluation, targets)
    except (
        base.ListenNowError,
        ConditionRenderError,
        method.SourceDiversityError,
        OSError,
        ValueError,
    ) as error:
        print(f"exp035-condition-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
