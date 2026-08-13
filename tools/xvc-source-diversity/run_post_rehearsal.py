#!/usr/bin/env python3
"""Run one clean teacher pass after the frozen control69 X-VC adaptation."""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
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
import run as method  # noqa: E402
import run_breadth as breadth  # noqa: E402
import run_role_mix as role_mix  # noqa: E402
from prepare_clean_post_rehearsal import (  # noqa: E402
    EXPECTED_DOMAINS,
    EXPECTED_ROWS,
    OUTPUT_KIND,
    load_json,
    sha256_file,
)

CANDIDATE_ID = "cv12-clean-post-rehearsal170"
RESULT_KIND = "liveconv-exp141-xvc-clean-post-rehearsal-result/v1"
LEARNING_RATE = 1e-4


class PostRehearsalError(RuntimeError):
    """The bounded clean post-adaptation rehearsal cannot safely continue."""


def load_manifest(path: Path, source_work: Path) -> dict[str, Any]:
    value = load_json(path)
    items = value.get("items")
    if (
        value.get("kind") != OUTPUT_KIND
        or value.get("composition") != EXPECTED_DOMAINS
        or not isinstance(items, list)
        or len(items) != EXPECTED_ROWS
    ):
        raise PostRehearsalError("clean rehearsal manifest drifted")
    ids: set[str] = set()
    teachers: set[str] = set()
    domains: Counter[str] = Counter()
    for item in items:
        if not isinstance(item, dict):
            raise PostRehearsalError("clean rehearsal row is malformed")
        identifier = item.get("id")
        teacher_id = item.get("teacher_id")
        source_file = item.get("source_file")
        target_file = item.get("target_file")
        if (
            not isinstance(identifier, str)
            or identifier in ids
            or not isinstance(teacher_id, str)
            or teacher_id in teachers
            or not isinstance(source_file, str)
            or not isinstance(target_file, str)
            or Path(source_file).is_absolute()
            or Path(target_file).is_absolute()
            or ".." in Path(source_file).parts
            or ".." in Path(target_file).parts
            or not base._is_sha256(item.get("source_sha256"))
            or not base._is_sha256(item.get("target_sha256"))
            or not isinstance(item.get("source_relative_distance"), (int, float))
            or float(item["source_relative_distance"]) >= 0.5
        ):
            raise PostRehearsalError("clean rehearsal identity drifted")
        for filename, digest in (
            (source_file, item["source_sha256"]),
            (target_file, item["target_sha256"]),
        ):
            audio = source_work / filename
            if (
                audio.is_symlink()
                or not audio.is_file()
                or sha256_file(audio) != digest
            ):
                raise PostRehearsalError(f"clean teacher audio drifted: {identifier}")
        ids.add(identifier)
        teachers.add(teacher_id)
        domains[str(item.get("domain"))] += 1
    if dict(domains) != EXPECTED_DOMAINS:
        raise PostRehearsalError("clean rehearsal composition drifted")
    return value


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, Path, str]]]:
    manifest = load_manifest(arguments.training_manifest, arguments.source_work)
    evaluation = breadth._load_manifest(
        arguments.evaluation_set,
        kind=breadth.EVALUATION_KIND,
        count=breadth.EVALUATION_COUNT,
    )
    for item in evaluation["items"]:
        source = arguments.source_root / item["filename"]
        if (
            source.is_symlink()
            or not source.is_file()
            or sha256_file(source) != item["sha256"]
        ):
            raise PostRehearsalError(f"external source drifted: {item['id']}")
    targets = method.target_inventory(arguments.pair_root)
    if arguments.control_adapter.is_symlink() or not (
        arguments.control_adapter / "adapter_model.safetensors"
    ).is_file():
        raise PostRehearsalError("control69 adapter is unavailable")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-141 work directory",
    )
    if not arguments.smoke:
        base._require_new_output(
            arguments.listener_dir,
            REPO_ROOT / "artifacts" / "ms3" / "listening",
            "EXP-141 listener directory",
        )
    return manifest, evaluation, targets


def _pair(identifier: str, path: Path, digest: str) -> base.MaterializedPair:
    return base.MaterializedPair(identifier, path, path, digest, digest)


def _batch_from_item(
    model: Any,
    item: Mapping[str, Any],
    *,
    source_work: Path,
    process_audio: Any,
    config: Mapping[str, Any],
    torch: Any,
    device: Any,
) -> dict[str, Any]:
    source_path = source_work / str(item["source_file"])
    target_path = source_work / str(item["target_file"])
    source = base._extract_pair_tensors(
        model,
        _pair(str(item["teacher_id"]), source_path, str(item["source_sha256"])),
        process_audio=process_audio,
        config=config,
        torch=torch,
        device=device,
    )
    target = base._extract_pair_tensors(
        model,
        _pair(str(item["target_id"]), target_path, str(item["target_sha256"])),
        process_audio=process_audio,
        config=config,
        torch=torch,
        device=device,
    )
    return {
        "source_wav": source["source_wav"],
        "semantic_tokens": source["semantic_tokens"],
        "target_wav": target["target_wav"],
        "ssl_feat": target["ssl_feat"],
    }


def run(
    arguments: argparse.Namespace,
    manifest: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    target_rows: list[tuple[str, Path, str]],
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise PostRehearsalError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise PostRehearsalError("EXP-141 requires the explicit gpu0 lease")
    started = time.monotonic()
    arguments.work_dir.mkdir()

    import torch
    from peft import PeftModel

    if not torch.cuda.is_available():
        raise PostRehearsalError("CUDA is unavailable")
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
    if {
        key: float(value) for key, value in model.loss_config["loss_weights"].items()
    } != role_mix.STANDARD_LOSS_WEIGHTS:
        raise PostRehearsalError("upstream X-VC loss weights drifted")

    trained = PeftModel.from_pretrained(
        model, str(arguments.control_adapter), is_trainable=True
    )
    scope = role_mix.training_scope(arguments.inventory, "control69")
    trainable = role_mix._set_scope_training_only(trained, scope)
    expected_trainable = role_mix.expected_trainable_parameter_count(
        scope, "standard"
    )
    if sum(parameter.numel() for parameter in trainable) != expected_trainable:
        raise PostRehearsalError("control69 trainable parameter count drifted")
    optimizer = torch.optim.AdamW(trainable, lr=LEARNING_RATE)
    losses: list[float] = []
    rows = manifest["items"][:1] if arguments.smoke else manifest["items"]
    for item in rows:
        role_mix._set_scope_training_only(trained, scope)
        tensors = _batch_from_item(
            trained,
            item,
            source_work=arguments.source_work,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        optimizer.zero_grad(set_to_none=True)
        batch = base._gpu_batch(tensors, torch=torch, device=device)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            loss, numeric = role_mix.training_loss(
                trained,
                batch,
                "real-donor-teacher-output",
                torch=torch,
                teacher_loss="standard",
            )
        loss.backward()
        gradient_norm = torch.nn.utils.clip_grad_norm_(
            trainable, base.GRADIENT_CLIP_NORM
        )
        if not math.isfinite(float(gradient_norm.detach().cpu())):
            raise PostRehearsalError("post-rehearsal gradient norm is non-finite")
        if not arguments.smoke:
            optimizer.step()
        losses.append(numeric)
    if arguments.smoke:
        print(
            json.dumps(
                {
                    "status": "smoked-control69-clean-post-rehearsal",
                    "loss": losses[0],
                    "gradient_norm": float(gradient_norm.detach().cpu()),
                    "trainable_parameters": expected_trainable,
                    "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
                },
                sort_keys=True,
            )
        )
        return 0
    if len(losses) != EXPECTED_ROWS:
        raise PostRehearsalError("post-rehearsal update count drifted")
    adapter_dir = arguments.work_dir / f"adapter-{EXPECTED_ROWS}"
    trained.save_pretrained(adapter_dir, safe_serialization=True)

    target_id, target_path, target_digest = target_rows[0]
    target = base._extract_pair_tensors(
        trained,
        _pair(target_id, target_path, target_digest),
        process_audio=process_audio,
        config=config,
        torch=torch,
        device=device,
    )
    evaluation_root = arguments.work_dir / "evaluation-sources"
    evaluation_root.mkdir()
    evaluation_pairs: list[base.MaterializedPair] = []
    evaluation_tensors: list[dict[str, Any]] = []
    for item in evaluation["items"]:
        pair, tensors = breadth._reference_tensor(
            trained,
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

    def render(current: Any) -> list[Any]:
        return [
            base._inference(
                current,
                source,
                target,
                seed=base.SEED + index,
                torch=torch,
                device=device,
            )
            .detach()
            .cpu()
            for index, source in enumerate(evaluation_tensors)
        ]

    candidate_outputs = render(trained)
    control_base = method._load_xvc(arguments, XVC, device)
    control = PeftModel.from_pretrained(
        control_base, str(arguments.control_adapter), is_trainable=False
    )
    control_outputs = render(control)
    del control, control_base
    torch.cuda.empty_cache()
    plain_base = method._load_xvc(arguments, XVC, device)
    base_outputs = render(plain_base)
    del plain_base
    torch.cuda.empty_cache()

    policy = {
        "candidate_id": CANDIDATE_ID,
        "candidate_name": (
            "EXP-141 / control69 + one clean unique teacher rehearsal pass"
        ),
        "run_kind": "EXP-141 X-VC clean post-rehearsal external evaluation",
        "question": (
            "Does a clean post-adaptation teacher pass retain control69 while "
            "reducing off-distribution corruption?"
        ),
    }
    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    listener_rows: list[dict[str, Any]] = []
    for index, (item, pair) in enumerate(
        zip(evaluation["items"], evaluation_pairs, strict=True)
    ):
        row_root = staging / f"{index:02d}-{item['id']}"
        row_root.mkdir()
        shutil.copyfile(pair.source_path, row_root / "00-source-reference.wav")
        shutil.copyfile(target_path, row_root / "01-target-reference.wav")
        hashes = {
            "base": base._write_float_wav(
                row_root / "10-xvc-base.wav", base_outputs[index], sample_rate
            ),
            "cv12-standard": base._write_float_wav(
                row_root / "20-xvc-cv12-standard.wav",
                control_outputs[index],
                sample_rate,
            ),
            CANDIDATE_ID: base._write_float_wav(
                row_root / "30-xvc-candidate.wav",
                candidate_outputs[index],
                sample_rate,
            ),
        }
        method._write_json(
            row_root / "index.json",
            role_mix.listening_index(item, hashes=hashes, policy=policy),
        )
        listener_rows.append({"source_id": item["id"], "hashes": hashes})
    staging.rename(arguments.listener_dir)
    result = {
        "schema_version": 1,
        "kind": RESULT_KIND,
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": policy["question"],
        "independent_variable": (
            "optimization sequence: fresh-base mixed 835 standard + 209 unfiltered "
            "teacher updates versus frozen control69 initialization followed by "
            "one pass over 170 unique, non-gross teacher outputs with fixed "
            "source-relative distance < 0.5 admission"
        ),
        "training_manifest_sha256": sha256_file(arguments.training_manifest),
        "source_result_sha256": sha256_file(arguments.source_work / "result.json"),
        "control_adapter": str(arguments.control_adapter),
        "updates": len(losses),
        "role_counts": {"real-donor-teacher-output": len(losses)},
        "composition": EXPECTED_DOMAINS,
        "learning_rate": LEARNING_RATE,
        "gradient_clip_norm": base.GRADIENT_CLIP_NORM,
        "trainable_parameters": expected_trainable,
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "evaluation_set_sha256": sha256_file(arguments.evaluation_set),
        "listener_rows": listener_rows,
        "boundary": (
            "Auxiliary content/corruption screening only; not naturalness, target "
            "identity, a keeper, or promotion"
        ),
        "claims": {
            "perceptual_winner": False,
            "promoted": False,
            "route_qualified": False,
        },
    }
    method._write_json(arguments.work_dir / "result.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "updates": len(losses),
                "listener_dir": str(arguments.listener_dir),
            },
            sort_keys=True,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--smoke", action="store_true")
    value.add_argument("--training-manifest", type=Path, required=True)
    value.add_argument("--source-work", type=Path, required=True)
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
        default=REPO_ROOT / "artifacts/exp007/phase0-inputs-v1/inventory.json",
    )
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    value.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    value.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        manifest, evaluation, targets = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "training_rows": len(manifest["items"]),
                        "composition": EXPECTED_DOMAINS,
                        "evaluation_rows": len(evaluation["items"]),
                        "initialization": "EXP-035-control69",
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, manifest, evaluation, targets)
    except (
        PostRehearsalError,
        base.ListenNowError,
        breadth.BreadthError,
        external.ExternalEvaluationError,
        method.SourceDiversityError,
        role_mix.RoleMixError,
        OSError,
        ValueError,
    ) as error:
        print(f"exp141-post-rehearsal-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
