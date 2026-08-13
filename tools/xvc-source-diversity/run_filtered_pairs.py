#!/usr/bin/env python3
"""Train X-VC on EXP-059's content-filtered EXP-035 pseudo sources."""

from __future__ import annotations

import argparse
import json
import math
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

import audit_training_pairs as audit_tool  # noqa: E402
import listen_now as base  # noqa: E402
import listen_now_horizon as horizon  # noqa: E402
import run as method  # noqa: E402
import run_breadth as breadth  # noqa: E402

TOTAL_UPDATES = 1044
SELECTED_UNIQUE_PAIRS = 522
MIN_DONORS = 10
MAX_SELECTED_MEAN_RATIO = 0.75


class FilteredPairError(RuntimeError):
    """The bounded content-filtered retraining run cannot safely continue."""


def load_audit(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FilteredPairError("training-pair audit is not valid JSON") from error
    if not isinstance(value, dict):
        raise FilteredPairError("training-pair audit schema drifted")
    bound_digest = value.get("audit_sha256")
    digest_input = dict(value)
    digest_input.pop("audit_sha256", None)
    selection = value.get("selection")
    aggregate = value.get("aggregate")
    rows = value.get("rows")
    schedule = selection.get("schedule") if isinstance(selection, dict) else None
    donor_counts = (
        aggregate.get("selected_donor_update_counts")
        if isinstance(aggregate, dict)
        else None
    )
    all_mean = (
        aggregate.get("all_mean_distance") if isinstance(aggregate, dict) else None
    )
    selected_mean = (
        aggregate.get("selected_mean_distance")
        if isinstance(aggregate, dict)
        else None
    )
    if (
        value.get("kind") != "liveconv-xvc-pseudo-source-content-audit/v1"
        or value.get("status") != "completed-training-input-audit"
        or bound_digest != audit_tool.canonical_sha256(digest_input)
        or not isinstance(rows, list)
        or len(rows) != TOTAL_UPDATES
        or not isinstance(schedule, list)
        or len(schedule) != TOTAL_UPDATES
        or not isinstance(donor_counts, dict)
        or len(donor_counts) < MIN_DONORS
        or not isinstance(all_mean, (int, float))
        or not isinstance(selected_mean, (int, float))
        or float(selected_mean) > float(all_mean) * MAX_SELECTED_MEAN_RATIO
    ):
        raise FilteredPairError("training-pair audit did not pass admission")
    selected_rows = [
        row for row in rows if isinstance(row, dict) and row.get("selected")
    ]
    if len(selected_rows) != SELECTED_UNIQUE_PAIRS:
        raise FilteredPairError("selected pair count drifted")
    selected_keys = {
        (str(row.get("pair_id")), str(row.get("donor_id"))) for row in selected_rows
    }
    schedule_keys: list[tuple[str, str]] = []
    for row in schedule:
        if not isinstance(row, dict):
            raise FilteredPairError("training schedule row is malformed")
        key = (str(row.get("pair_id")), str(row.get("donor_id")))
        if key not in selected_keys:
            raise FilteredPairError("training schedule references an unselected pair")
        schedule_keys.append(key)
    if schedule_keys[:SELECTED_UNIQUE_PAIRS] != schedule_keys[SELECTED_UNIQUE_PAIRS:]:
        raise FilteredPairError("training schedule is not two identical passes")
    return value


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[
    dict[str, Any], dict[str, Any], list[tuple[str, Path, str]], dict[str, Any]
]:
    try:
        donors, evaluation, targets = breadth.validate_inputs(arguments)
    except breadth.BreadthError as error:
        raise FilteredPairError(str(error)) from error
    audit = load_audit(arguments.selection_audit)
    target_ids = {row[0] for row in targets}
    donor_ids = {str(item["id"]) for item in donors["items"]}
    audit_keys: set[tuple[str, str]] = set()
    for row in audit["rows"]:
        pair_id = str(row.get("pair_id"))
        donor_id = str(row.get("donor_id"))
        source = arguments.pseudo_root / pair_id / f"source-{donor_id}-16k.wav"
        if (
            pair_id not in target_ids
            or donor_id not in donor_ids
            or (pair_id, donor_id) in audit_keys
            or source.is_symlink()
            or not source.is_file()
            or base.sha256_file(source) != row.get("source_sha256")
        ):
            raise FilteredPairError("audited pseudo-source identity drifted")
        audit_keys.add((pair_id, donor_id))
    if len(audit_keys) != TOTAL_UPDATES:
        raise FilteredPairError("audited pseudo-source inventory drifted")
    return donors, evaluation, targets, audit


def listening_index(
    item: Mapping[str, Any], *, hashes: Mapping[str, str]
) -> dict[str, object]:
    variants = (
        ("base", "X-VC base", "10-xvc-base.wav", 1),
        (
            "cv12-control69",
            "EXP-035 / all 12 pseudo donors / 1,044 updates",
            "20-xvc-cv12-control69.wav",
            2,
        ),
        (
            "cv12-content-filtered6x2",
            "EXP-060 / best 6 pseudo donors x 2 passes / 1,044 updates",
            "30-xvc-content-filtered6x2.wav",
            3,
        ),
    )
    return {
        "schema_version": 1,
        "run_kind": "EXP-060 X-VC content-filtered pseudo-pair evaluation",
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
                "label": "Amitaro runrun / fixed target reference",
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
                "profile_id": f"xvc.exp060.{variant_id}.listen-now",
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
    audit: Mapping[str, Any],
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise FilteredPairError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise FilteredPairError("EXP-060 requires the explicit gpu0 lease")
    started = time.monotonic()
    arguments.work_dir.mkdir()
    evaluation_root = arguments.work_dir / "evaluation-sources"
    evaluation_root.mkdir()

    import torch
    from peft import LoraConfig, PeftModel, get_peft_model

    if not torch.cuda.is_available():
        raise FilteredPairError("CUDA is unavailable")
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
    base._initialize_loss(model, arguments.xvc_config)

    target_pairs = [
        base.MaterializedPair(pair_id, target, target, digest, digest)
        for pair_id, target, digest in target_rows
    ]
    target_tensors = [
        base._extract_pair_tensors(
            model,
            pair,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        for pair in target_pairs
    ]
    targets_by_id = {
        pair.pair_id: tensors
        for pair, tensors in zip(target_pairs, target_tensors, strict=True)
    }
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

    target_reference = target_tensors[0]
    target_reference_pair = target_pairs[0]

    def render(current: Any) -> list[Any]:
        return [
            base._inference(
                current,
                source,
                target_reference,
                seed=base.SEED + index,
                torch=torch,
                device=device,
            )
            .detach()
            .cpu()
            for index, source in enumerate(evaluation_tensors)
        ]

    base_outputs = render(model)
    control_base = method._load_xvc(arguments, XVC, device)
    control = PeftModel.from_pretrained(
        control_base, str(arguments.control_adapter), is_trainable=False
    )
    control_outputs = render(control)
    del control, control_base
    torch.cuda.empty_cache()

    selected_rows = {
        (str(row["pair_id"]), str(row["donor_id"])): row
        for row in audit["rows"]
        if row.get("selected")
    }
    selected_tensors: dict[tuple[str, str], dict[str, Any]] = {}
    for key, row in selected_rows.items():
        pair_id, donor_id = key
        source_path = arguments.pseudo_root / pair_id / f"source-{donor_id}-16k.wav"
        source = base.RenderSource(
            pair_id=f"{pair_id}-{donor_id}",
            display_text=f"filtered generated source {pair_id} via {donor_id}",
            source_path=source_path,
        )
        extracted = base._extract_render_source(
            model,
            source,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        target_tensor = targets_by_id[pair_id]
        selected_tensors[key] = {
            "source_wav": extracted["source_wav"],
            "semantic_tokens": extracted["semantic_tokens"],
            "target_wav": target_tensor["target_wav"],
            "ssl_feat": target_tensor["ssl_feat"],
        }
        if base.sha256_file(source_path) != row["source_sha256"]:
            raise FilteredPairError("selected source changed during extraction")

    schedule = [
        (str(row["pair_id"]), str(row["donor_id"]))
        for row in audit["selection"]["schedule"]
    ]
    scope = horizon.lora_scope(arguments.inventory, "control69")
    target_modules = list(scope["target_modules"])
    trained = get_peft_model(
        model,
        LoraConfig(
            r=8,
            lora_alpha=8,
            lora_dropout=0.0,
            bias="none",
            use_dora=False,
            use_rslora=False,
            target_modules=target_modules,
        ),
    )
    observed = getattr(trained, "targeted_module_names", None)
    if not isinstance(observed, (list, tuple)) or set(observed) != set(
        target_modules
    ):
        raise FilteredPairError("control69 target set drifted")
    trainable = base._set_adapter_training_only(trained)
    if sum(parameter.numel() for parameter in trainable) != int(
        scope["trainable_parameter_count"]
    ):
        raise FilteredPairError("control69 trainable parameter count drifted")
    optimizer = torch.optim.AdamW(trainable, lr=base.LEARNING_RATE)
    losses: list[float] = []
    for key in schedule:
        base._set_adapter_training_only(trained)
        optimizer.zero_grad(set_to_none=True)
        batch = base._gpu_batch(selected_tensors[key], torch=torch, device=device)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            loss, numeric = base._composite_loss(trained, batch, torch)
        loss.backward()
        gradient_norm = torch.nn.utils.clip_grad_norm_(
            trainable, base.GRADIENT_CLIP_NORM
        )
        if not math.isfinite(float(gradient_norm.detach().cpu())):
            raise FilteredPairError("X-VC gradient norm is non-finite")
        optimizer.step()
        losses.append(numeric)
    if len(losses) != TOTAL_UPDATES:
        raise FilteredPairError("filtered-pair update count drifted")
    adapter_dir = arguments.work_dir / "adapter-1044"
    trained.save_pretrained(adapter_dir, safe_serialization=True)
    candidate_outputs = render(trained)

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    listener_rows: list[dict[str, object]] = []
    for index, (item, pair) in enumerate(
        zip(evaluation["items"], evaluation_pairs, strict=True)
    ):
        row_root = staging / f"{index:02d}-{item['id']}"
        row_root.mkdir()
        shutil.copyfile(pair.source_path, row_root / "00-source-reference.wav")
        shutil.copyfile(
            target_reference_pair.target_path, row_root / "01-target-reference.wav"
        )
        hashes = {
            "base": base._write_float_wav(
                row_root / "10-xvc-base.wav", base_outputs[index], sample_rate
            ),
            "cv12-control69": base._write_float_wav(
                row_root / "20-xvc-cv12-control69.wav",
                control_outputs[index],
                sample_rate,
            ),
            "cv12-content-filtered6x2": base._write_float_wav(
                row_root / "30-xvc-content-filtered6x2.wav",
                candidate_outputs[index],
                sample_rate,
            ),
        }
        method._write_json(
            row_root / "index.json", listening_index(item, hashes=hashes)
        )
        listener_rows.append({"source_id": item["id"], "hashes": hashes})

    result = {
        "schema_version": 1,
        "kind": "liveconv-exp060-xvc-content-filtered-pairs-result/v1",
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": (
            "Does rejecting content-corrupt pseudo sources improve X-VC at fixed "
            "target exposure and optimizer updates?"
        ),
        "independent_variable": (
            "all twelve pseudo donors once versus best six content-preserving "
            "pseudo donors twice per target"
        ),
        "fixed": {
            "target_voice": "Amitaro runrun",
            "target_text_count": method.PAIR_COUNT,
            "target_exposures_per_text": 12,
            "optimizer_updates": TOTAL_UPDATES,
            "lora_scope": "control69",
            "learning_rate": base.LEARNING_RATE,
            "gradient_clip_norm": base.GRADIENT_CLIP_NORM,
            "target_wav_cond": "zeros",
            "loss": "pinned X-VC composite generative loss",
        },
        "selection_audit_sha256": audit["audit_sha256"],
        "selected_unique_pairs": len(selected_tensors),
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "listener_rows": listener_rows,
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
                "updates": len(losses),
                "selected_unique_pairs": len(selected_tensors),
                "evaluation_rows": len(evaluation_pairs),
                "listener_dir": str(arguments.listener_dir),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--selection-audit", type=Path, required=True)
    value.add_argument("--pseudo-root", type=Path, required=True)
    value.add_argument("--donors", type=Path, required=True)
    value.add_argument("--evaluation-set", type=Path, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--pair-root", type=Path, required=True)
    value.add_argument("--control-adapter", type=Path, required=True)
    value.add_argument("--xvc-source-root", type=Path, required=True)
    value.add_argument("--xvc-config", type=Path, required=True)
    value.add_argument("--checkpoint", type=Path, required=True)
    value.add_argument(
        "--inventory",
        type=Path,
        default=REPO_ROOT
        / "artifacts"
        / "exp007"
        / "phase0-inputs-v1"
        / "inventory.json",
    )
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    value.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    value.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        _, evaluation, targets, audit = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "targets": len(targets),
                        "selected_unique_pairs": sum(
                            bool(row.get("selected")) for row in audit["rows"]
                        ),
                        "updates": len(audit["selection"]["schedule"]),
                        "evaluation_rows": len(evaluation["items"]),
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, evaluation, targets, audit)
    except FilteredPairError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
