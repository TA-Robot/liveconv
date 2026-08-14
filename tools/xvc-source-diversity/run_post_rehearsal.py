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
from prepare_hard_negative_curriculum import (  # noqa: E402
    EXPECTED_COMPOSITION as HARD_EXPECTED_DOMAINS,
)
from prepare_hard_negative_curriculum import (  # noqa: E402
    OUTPUT_KIND as HARD_OUTPUT_KIND,
)
from prepare_jsut_retention_curriculum import (  # noqa: E402
    EXPECTED_COMPOSITION as JSUT_EXPECTED_DOMAINS,
)
from prepare_jsut_retention_curriculum import (  # noqa: E402
    OUTPUT_KIND as JSUT_RETENTION_OUTPUT_KIND,
)
from prepare_selective_retention_curriculum import (  # noqa: E402
    OUTPUT_KIND as SELECTIVE_OUTPUT_KIND,
)
from prepare_selective_retention_curriculum import (  # noqa: E402
    REPAIR_TARGET,
    RETENTION_TARGET,
)

CANDIDATE_ID = "cv12-clean-post-rehearsal170"
RESULT_KIND = "liveconv-exp141-xvc-clean-post-rehearsal-result/v1"
LEARNING_RATE = 1e-4
FULL_CONVERTER_TARGET = "full-converter"
LORA69_TARGET = "lora69"
CONVERTER_PREFIX = "acoustic_converter"
EXPECTED_CONVERTER_PARAMETERS = 42_357_760
CONVERTER_CHECKPOINT_KIND = "liveconv-xvc-merged-control69-converter/v1"
GENERATIVE_OBJECTIVE = "generative-only"
REAL_REFERENCE_ADVERSARIAL_OBJECTIVE = "real-reference-adversarial"
SEQUENTIAL_OPTIMIZER = "sequential"
PCGRAD_PAIRED_OPTIMIZER = "pcgrad-hard-easy-paired"
EMA_IMPLEMENTATION = "ema-pytorch-0.7.7-defaults-adapter-equivalent"
EMA_BETA = 0.9999
EMA_UPDATE_AFTER_STEP = 100
EMA_UPDATE_EVERY = 10
EMA_INV_GAMMA = 1.0
EMA_POWER = 2.0 / 3.0
EMA_MIN_VALUE = 0.0
PARAMETER_ANCHOR_COEFFICIENT = 1.0
PARAMETER_ANCHOR_IMPLEMENTATION = "l2-sp-control69-trainable-parameters/v1"


class PostRehearsalError(RuntimeError):
    """The bounded clean post-adaptation rehearsal cannot safely continue."""


def listening_policy(
    manifest_kind: str = OUTPUT_KIND,
    trainable_target: str = LORA69_TARGET,
    training_objective: str = GENERATIVE_OBJECTIVE,
    use_adapter_ema: bool = False,
    optimizer_mode: str = SEQUENTIAL_OPTIMIZER,
    parameter_anchor: bool = False,
) -> dict[str, str]:
    """Return the complete shared-listener identity for the admitted method."""

    if parameter_anchor:
        if (
            manifest_kind != SELECTIVE_OUTPUT_KIND
            or trainable_target != LORA69_TARGET
            or training_objective != REAL_REFERENCE_ADVERSARIAL_OBJECTIVE
            or not use_adapter_ema
            or optimizer_mode != SEQUENTIAL_OPTIMIZER
        ):
            raise PostRehearsalError(
                "parameter anchor is admitted only for the exact EXP-163 baseline"
            )
        return {
            "slug": "exp181",
            "candidate_id": "cv12-selective-real-adversarial-anchor-ema170",
            "candidate_name": (
                "EXP-181 / selective real-adversarial / control69 anchor / EMA"
            ),
            "run_kind": "EXP-181 X-VC parameter-anchor external evaluation",
            "result_kind": "liveconv-exp181-xvc-parameter-anchor-ema/v1",
            "question": (
                "Can a light control69 parameter anchor retain EXP-163's repair "
                "signal while reducing tempo and ordinary-content forgetting?"
            ),
            "independent_variable": (
                "only a coefficient-1 L2-SP penalty around the immutable control69 "
                "LoRA69 initialization is added to EXP-163; its hard85/easy85 "
                "curriculum, real-reference adversarial objective, 170 sequential "
                "updates, LR, AdamW, clip, scope, zero condition, and upstream EMA "
                "schedule stay fixed"
            ),
        }
    if optimizer_mode == PCGRAD_PAIRED_OPTIMIZER:
        if (
            manifest_kind != SELECTIVE_OUTPUT_KIND
            or trainable_target != LORA69_TARGET
            or training_objective != GENERATIVE_OBJECTIVE
            or use_adapter_ema
        ):
            raise PostRehearsalError(
                "paired PCGrad is admitted only for selective generative LoRA69"
            )
        return {
            "slug": "exp176",
            "candidate_id": "cv12-selective-pcgrad85",
            "candidate_name": "EXP-176 / paired hard-retention PCGrad",
            "run_kind": "EXP-176 X-VC paired PCGrad external evaluation",
            "result_kind": "liveconv-exp176-xvc-paired-pcgrad/v1",
            "question": (
                "Can gradient-conflict surgery preserve normal behavior while "
                "repairing the frozen control69 hard failures?"
            ),
            "independent_variable": (
                "only optimizer gradient composition changes from EXP-150: each "
                "unchanged adjacent hard/easy pair is evaluated at one shared "
                "parameter state, conflicting task-gradient components are "
                "projected away, and the resulting gradients are summed into 85 "
                "pair steps; all 170 sources and targets, initialization, loss, "
                "LR, clip, LoRA69 scope, target references, and zero frame "
                "condition stay fixed"
            ),
        }
    if optimizer_mode != SEQUENTIAL_OPTIMIZER:
        raise PostRehearsalError("unknown optimizer mode")
    if use_adapter_ema:
        if (
            manifest_kind not in {SELECTIVE_OUTPUT_KIND, JSUT_RETENTION_OUTPUT_KIND}
            or trainable_target != LORA69_TARGET
            or training_objective != REAL_REFERENCE_ADVERSARIAL_OBJECTIVE
        ):
            raise PostRehearsalError(
                "adapter EMA is admitted only for selective real-adversarial LoRA69"
            )
        if manifest_kind == JSUT_RETENTION_OUTPUT_KIND:
            return {
                "slug": "exp171",
                "candidate_id": "cv12-jsut-retention-real-adversarial-ema170",
                "candidate_name": ("EXP-171 / JSUT retention + real-adversarial + EMA"),
                "run_kind": "EXP-171 X-VC JSUT retention external evaluation",
                "result_kind": "liveconv-exp171-xvc-jsut-retention-ema/v1",
                "question": (
                    "Does category-balanced Japanese retention data improve the "
                    "surviving EXP-163 method across independent frozen gates?"
                ),
                "independent_variable": (
                    "only the easy85 retention source and frozen control69 target "
                    "domain changes from EXP-163 Common Voice/Hadou/JVS rows to "
                    "precommitted category-balanced JSUT; hard85, target IDs, "
                    "updates, scope, objective, optimizer, clip, condition, and "
                    "upstream EMA remain fixed"
                ),
            }
        return {
            "slug": "exp163",
            "candidate_id": "cv12-selective-real-adversarial-ema170",
            "candidate_name": ("EXP-163 / selective real-adversarial / upstream EMA"),
            "run_kind": "EXP-163 X-VC upstream-EMA external evaluation",
            "result_kind": "liveconv-exp163-xvc-real-adversarial-ema/v1",
            "question": (
                "Does restoring upstream-configured EMA retain ordinary gains "
                "without the final online adapter's fresh collapse?"
            ),
            "independent_variable": (
                "reported adapter state changes from EXP-158's final online "
                "LoRA69 parameters to the equivalent trainable-parameter EMA "
                "using pinned ema-pytorch 0.7.7 defaults; data, objective, "
                "initialization, optimizer steps, LR, clip, scope, and condition "
                "stay fixed"
            ),
        }
    if training_objective == REAL_REFERENCE_ADVERSARIAL_OBJECTIVE:
        if manifest_kind != SELECTIVE_OUTPUT_KIND or trainable_target != LORA69_TARGET:
            raise PostRehearsalError(
                "real-reference adversarial is admitted only for selective LoRA69"
            )
        return {
            "slug": "exp158",
            "candidate_id": "cv12-selective-retention-real-adversarial170",
            "candidate_name": (
                "EXP-158 / selective retention + real-reference adversarial"
            ),
            "run_kind": "EXP-158 X-VC real-reference adversarial evaluation",
            "result_kind": "liveconv-exp158-xvc-real-reference-adversarial/v1",
            "question": (
                "Can real-reference waveform adversarial and feature matching "
                "suppress collapse while selective targets retain normal behavior?"
            ),
            "independent_variable": (
                "objective adds the pretrained X-VC waveform discriminator and "
                "feature matching, whose real side uses the authorized original "
                "Amitaro target waveform; the exact EXP-150 curriculum, synthetic "
                "repair/retention generative targets, initialization, LR, clip, "
                "LoRA69 scope, update count, and zero frame condition stay fixed"
            ),
        }
    if training_objective != GENERATIVE_OBJECTIVE:
        raise PostRehearsalError("unknown training objective")
    if trainable_target == FULL_CONVERTER_TARGET:
        if manifest_kind != SELECTIVE_OUTPUT_KIND:
            raise PostRehearsalError(
                "full converter is admitted only for selective retention"
            )
        return {
            "slug": "exp154",
            "candidate_id": "cv12-selective-retention-full-converter170",
            "candidate_name": (
                "EXP-154 / selective retention / full acoustic converter"
            ),
            "run_kind": "EXP-154 X-VC full-converter retention evaluation",
            "result_kind": "liveconv-exp154-xvc-full-converter-retention/v1",
            "question": (
                "Can a merged-control69 full acoustic converter generalize "
                "selective hard repair while retaining normal behavior?"
            ),
            "independent_variable": (
                "trainable target changes from control69's 69 LoRA modules to "
                "all acoustic-converter parameters; the exact EXP-150 selective "
                "curriculum, learning targets, initialization function, loss, LR, "
                "clip, target references, update count, and zero frame condition "
                "stay fixed"
            ),
        }
    if trainable_target != LORA69_TARGET:
        raise PostRehearsalError("unknown trainable target")
    if manifest_kind == SELECTIVE_OUTPUT_KIND:
        return {
            "slug": "exp150",
            "candidate_id": "cv12-selective-retention170",
            "candidate_name": (
                "EXP-150 / hard repair + control69 retention distillation"
            ),
            "run_kind": "EXP-150 X-VC selective retention evaluation",
            "result_kind": "liveconv-exp150-xvc-selective-retention/v1",
            "question": (
                "Can base-teacher repair on training-only failures coexist with "
                "control69 retention targets on normal rows?"
            ),
            "independent_variable": (
                "same EXP-146 85-hard/85-easy schedule, but easy rows change "
                "from base-X-VC teacher targets to their frozen non-gross "
                "control69 outputs; initialization, hard targets, loss, LR, "
                "clip, scope, target references, and zero frame condition stay fixed"
            ),
        }
    if manifest_kind == HARD_OUTPUT_KIND:
        return {
            "slug": "exp146",
            "candidate_id": "cv12-hard-negative-curriculum170",
            "candidate_name": (
                "EXP-146 / control69 + failure-triggered 50/50 curriculum"
            ),
            "run_kind": "EXP-146 X-VC hard-negative curriculum evaluation",
            "result_kind": "liveconv-exp146-xvc-hard-negative-curriculum/v1",
            "question": (
                "Does training-only failure-triggered sampling repair control69 "
                "collapse without broad heldout regression?"
            ),
            "independent_variable": (
                "same 170 clean base-teacher updates, resampled from one-pass "
                "coverage to alternating 85 control-hard and 85 domain-stratified "
                "easy positions; initialization, loss, LR, clip, scope, target, "
                "and zero frame condition stay fixed"
            ),
        }
    if manifest_kind != OUTPUT_KIND:
        raise PostRehearsalError("unknown post-rehearsal manifest kind")
    return {
        "slug": "exp141",
        "candidate_id": CANDIDATE_ID,
        "candidate_name": (
            "EXP-141 / control69 + one clean unique teacher rehearsal pass"
        ),
        "run_kind": "EXP-141 X-VC clean post-rehearsal external evaluation",
        "result_kind": RESULT_KIND,
        "question": (
            "Does a clean post-adaptation teacher pass retain control69 while "
            "reducing off-distribution corruption?"
        ),
        "independent_variable": (
            "optimization sequence: fresh-base mixed 835 standard + 209 "
            "unfiltered teacher updates versus frozen control69 initialization "
            "followed by one pass over 170 unique, non-gross teacher outputs "
            "with fixed source-relative distance < 0.5 admission"
        ),
    }


def load_manifest(
    path: Path,
    source_work: Path,
    control_work: Path | None = None,
    diverse_work: Path | None = None,
) -> dict[str, Any]:
    value = load_json(path)
    items = value.get("items")
    kind = value.get("kind")
    if kind == JSUT_RETENTION_OUTPUT_KIND:
        expected_domains = JSUT_EXPECTED_DOMAINS
    elif kind in {HARD_OUTPUT_KIND, SELECTIVE_OUTPUT_KIND}:
        expected_domains = HARD_EXPECTED_DOMAINS
    else:
        expected_domains = EXPECTED_DOMAINS
    if (
        kind
        not in {
            OUTPUT_KIND,
            HARD_OUTPUT_KIND,
            SELECTIVE_OUTPUT_KIND,
            JSUT_RETENTION_OUTPUT_KIND,
        }
        or value.get("composition") != expected_domains
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
            or (kind == OUTPUT_KIND and teacher_id in teachers)
            or not isinstance(source_file, str)
            or not isinstance(target_file, str)
            or Path(source_file).is_absolute()
            or Path(target_file).is_absolute()
            or ".." in Path(source_file).parts
            or ".." in Path(target_file).parts
            or not base._is_sha256(item.get("source_sha256"))
            or not base._is_sha256(item.get("target_sha256"))
            or not isinstance(item.get("source_relative_distance"), (int, float))
            or (
                kind != JSUT_RETENTION_OUTPUT_KIND
                and float(item["source_relative_distance"]) >= 0.5
            )
        ):
            raise PostRehearsalError("clean rehearsal identity drifted")
        if kind in {
            HARD_OUTPUT_KIND,
            SELECTIVE_OUTPUT_KIND,
            JSUT_RETENTION_OUTPUT_KIND,
        } and (
            item.get("curriculum_role") not in {"hard", "easy"}
            or not isinstance(item.get("source_manifest_id"), str)
        ):
            raise PostRehearsalError("hard curriculum identity drifted")
        source_root = (
            diverse_work if item.get("source_root") == "diverse-work" else source_work
        )
        if source_root is None:
            raise PostRehearsalError("diverse retention work is required")
        target_root = source_work
        if kind in {SELECTIVE_OUTPUT_KIND, JSUT_RETENTION_OUTPUT_KIND}:
            learning_target = item.get("learning_target")
            base_target_file = item.get("base_teacher_target_file")
            expected_target = (
                REPAIR_TARGET
                if item.get("curriculum_role") == "hard"
                else RETENTION_TARGET
            )
            expected_root = "source-work"
            if learning_target == RETENTION_TARGET:
                expected_root = (
                    "diverse-work"
                    if kind == JSUT_RETENTION_OUTPUT_KIND
                    else "control-work"
                )
            requires_base_target = (
                kind == SELECTIVE_OUTPUT_KIND or learning_target == REPAIR_TARGET
            )
            if (
                learning_target != expected_target
                or item.get("target_root") != expected_root
            ):
                raise PostRehearsalError("selective learning-target identity drifted")
            if requires_base_target:
                if (
                    not base._is_sha256(item.get("base_teacher_target_sha256"))
                    or not isinstance(base_target_file, str)
                    or Path(base_target_file).is_absolute()
                    or ".." in Path(base_target_file).parts
                ):
                    raise PostRehearsalError("selective base-target identity drifted")
                base_target = source_work / base_target_file
                if (
                    base_target.is_symlink()
                    or not base_target.is_file()
                    or sha256_file(base_target) != item["base_teacher_target_sha256"]
                ):
                    raise PostRehearsalError("base repair target drifted")
            if learning_target == RETENTION_TARGET:
                target_root = (
                    diverse_work if kind == JSUT_RETENTION_OUTPUT_KIND else control_work
                )
                if target_root is None:
                    raise PostRehearsalError("retention work is required")
        for audio, digest in (
            (source_root / source_file, item["source_sha256"]),
            (target_root / target_file, item["target_sha256"]),
        ):
            if (
                audio.is_symlink()
                or not audio.is_file()
                or sha256_file(audio) != digest
            ):
                raise PostRehearsalError(f"clean teacher audio drifted: {identifier}")
        ids.add(identifier)
        teachers.add(teacher_id)
        domains[str(item.get("domain"))] += 1
    if dict(domains) != expected_domains:
        raise PostRehearsalError("clean rehearsal composition drifted")
    return value


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, Path, str]]]:
    manifest = load_manifest(
        arguments.training_manifest,
        arguments.source_work,
        arguments.control_work,
        arguments.diverse_work,
    )
    listening_policy(
        str(manifest["kind"]),
        arguments.trainable_target,
        arguments.training_objective,
        arguments.adapter_ema,
        arguments.optimizer_mode,
        arguments.parameter_anchor,
    )
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
    if (
        arguments.control_adapter.is_symlink()
        or not (arguments.control_adapter / "adapter_model.safetensors").is_file()
    ):
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
    control_work: Path | None,
    diverse_work: Path | None,
    process_audio: Any,
    config: Mapping[str, Any],
    torch: Any,
    device: Any,
) -> dict[str, Any]:
    source_root = (
        diverse_work if item.get("source_root") == "diverse-work" else source_work
    )
    if source_root is None:
        raise PostRehearsalError("diverse retention work is required")
    source_path = source_root / str(item["source_file"])
    target_root = source_work
    if item.get("target_root") == "control-work":
        target_root = control_work
    elif item.get("target_root") == "diverse-work":
        target_root = diverse_work
    if target_root is None:
        raise PostRehearsalError("control retention work is required")
    target_path = target_root / str(item["target_file"])
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


def _set_converter_training_only(model: Any) -> list[Any]:
    model.eval()
    converter = getattr(model, CONVERTER_PREFIX, None)
    if converter is None:
        raise PostRehearsalError("X-VC acoustic converter is unavailable")
    converter.train(True)
    trainable: list[Any] = []
    for name, parameter in model.named_parameters():
        selected = name.startswith(CONVERTER_PREFIX + ".")
        parameter.requires_grad_(selected)
        if selected:
            trainable.append(parameter)
    if (
        sum(parameter.numel() for parameter in trainable)
        != EXPECTED_CONVERTER_PARAMETERS
    ):
        raise PostRehearsalError("full converter parameter count drifted")
    return trainable


def _converter_snapshot(model: Any, torch: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for name, parameter in model.named_parameters():
        if not name.startswith(CONVERTER_PREFIX + "."):
            continue
        relative = name.removeprefix(CONVERTER_PREFIX + ".")
        value = parameter.detach().cpu().contiguous()
        if not bool(torch.isfinite(value).all()):
            raise PostRehearsalError(f"non-finite converter parameter: {relative}")
        snapshot[relative] = value
    if (
        sum(value.numel() for value in snapshot.values())
        != EXPECTED_CONVERTER_PARAMETERS
    ):
        raise PostRehearsalError("converter snapshot parameter count drifted")
    return snapshot


def save_converter_checkpoint(
    model: Any, directory: Path, torch: Any
) -> dict[str, Any]:
    from safetensors.torch import load_file, save_file

    directory.mkdir()
    weights = directory / "converter-parameters.safetensors"
    snapshot = _converter_snapshot(model, torch)
    save_file(
        snapshot,
        str(weights),
        metadata={"format": "merged_control69_converter_parameters_v1"},
    )
    reloaded = load_file(str(weights), device="cpu")
    if set(reloaded) != set(snapshot) or any(
        not torch.equal(reloaded[name], snapshot[name]) for name in snapshot
    ):
        raise PostRehearsalError("converter checkpoint serialization drifted")
    metadata = {
        "schema_version": 1,
        "kind": CONVERTER_CHECKPOINT_KIND,
        "initialization": "base-xvc-plus-merged-control69",
        "parameter_prefix": CONVERTER_PREFIX,
        "tensor_count": len(snapshot),
        "parameter_count": EXPECTED_CONVERTER_PARAMETERS,
        "weights_sha256": sha256_file(weights),
    }
    method._write_json(directory / "converter.json", metadata)
    return metadata


def load_converter_checkpoint(
    model: Any, directory: Path, *, torch: Any, device: Any
) -> dict[str, Any]:
    from safetensors.torch import load_file

    metadata_path = directory / "converter.json"
    weights = directory / "converter-parameters.safetensors"
    if (
        directory.is_symlink()
        or metadata_path.is_symlink()
        or weights.is_symlink()
        or not metadata_path.is_file()
        or not weights.is_file()
    ):
        raise PostRehearsalError("full converter checkpoint is unavailable")
    metadata = load_json(metadata_path)
    if (
        metadata.get("kind") != CONVERTER_CHECKPOINT_KIND
        or metadata.get("parameter_prefix") != CONVERTER_PREFIX
        or metadata.get("parameter_count") != EXPECTED_CONVERTER_PARAMETERS
        or metadata.get("weights_sha256") != sha256_file(weights)
    ):
        raise PostRehearsalError("full converter checkpoint identity drifted")
    stored = load_file(str(weights), device="cpu")
    destinations = {
        name.removeprefix(CONVERTER_PREFIX + "."): parameter
        for name, parameter in model.named_parameters()
        if name.startswith(CONVERTER_PREFIX + ".")
    }
    if (
        set(stored) != set(destinations)
        or sum(value.numel() for value in stored.values())
        != EXPECTED_CONVERTER_PARAMETERS
    ):
        raise PostRehearsalError("full converter tensor set drifted")
    with torch.no_grad():
        for name, value in stored.items():
            destination = destinations[name]
            if tuple(value.shape) != tuple(destination.shape):
                raise PostRehearsalError(f"converter shape drifted: {name}")
            destination.copy_(value.to(device=device, dtype=destination.dtype))
    actual = _converter_snapshot(model, torch)
    if any(not torch.equal(actual[name], stored[name]) for name in stored):
        raise PostRehearsalError("full converter checkpoint reload is not exact")
    return metadata


class AdapterEMA:
    """Exact ema-pytorch 0.7.7 default schedule over mutable adapter tensors."""

    def __init__(self, model: Any, torch: Any) -> None:
        self.torch = torch
        self.parameters = {
            name: parameter
            for name, parameter in model.named_parameters()
            if parameter.requires_grad and bool(torch.is_floating_point(parameter))
        }
        if not self.parameters:
            raise PostRehearsalError("adapter EMA has no mutable tensors")
        self.shadow = {
            name: parameter.detach().clone()
            for name, parameter in self.parameters.items()
        }
        self.step = 0
        self.initted = False
        self.copy_updates = 0
        self.moving_average_updates = 0
        self.last_decay = 0.0

    def _copy(self) -> None:
        with self.torch.no_grad():
            for name, parameter in self.parameters.items():
                self.shadow[name].copy_(parameter.detach())
        self.copy_updates += 1

    def update(self) -> None:
        current_step = self.step
        self.step += 1
        if not self.initted:
            self._copy()
            self.initted = True
            return
        if current_step % EMA_UPDATE_EVERY != 0:
            return
        if current_step <= EMA_UPDATE_AFTER_STEP:
            self._copy()
            return
        epoch = max(self.step - EMA_UPDATE_AFTER_STEP - 1, 0)
        decay = 1.0 - (1.0 + epoch / EMA_INV_GAMMA) ** (-EMA_POWER)
        decay = min(max(decay, EMA_MIN_VALUE), EMA_BETA)
        with self.torch.no_grad():
            for name, parameter in self.parameters.items():
                self.shadow[name].lerp_(parameter.detach(), 1.0 - decay)
        self.moving_average_updates += 1
        self.last_decay = decay

    def copy_to(self) -> None:
        with self.torch.no_grad():
            for name, parameter in self.parameters.items():
                parameter.copy_(self.shadow[name])

    def receipt(self) -> dict[str, Any]:
        return {
            "implementation": EMA_IMPLEMENTATION,
            "beta": EMA_BETA,
            "update_after_step": EMA_UPDATE_AFTER_STEP,
            "update_every": EMA_UPDATE_EVERY,
            "inv_gamma": EMA_INV_GAMMA,
            "power": EMA_POWER,
            "min_value": EMA_MIN_VALUE,
            "calls": self.step,
            "copy_updates": self.copy_updates,
            "moving_average_updates": self.moving_average_updates,
            "last_decay": self.last_decay,
            "tensor_count": len(self.shadow),
            "parameter_count": sum(value.numel() for value in self.shadow.values()),
        }


def smoke_rows(
    manifest: Mapping[str, Any],
    optimizer_mode: str = SEQUENTIAL_OPTIMIZER,
    parameter_anchor: bool = False,
) -> list[Mapping[str, Any]]:
    items = manifest["items"]
    if optimizer_mode == PCGRAD_PAIRED_OPTIMIZER:
        return items[:2]
    if parameter_anchor:
        return items[:2]
    if manifest.get("kind") != JSUT_RETENTION_OUTPUT_KIND:
        return items[:1]
    hard = next(item for item in items if item.get("curriculum_role") == "hard")
    easy = next(item for item in items if item.get("curriculum_role") == "easy")
    return [hard, easy]


def paired_hard_easy_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Validate and return the frozen selective curriculum as hard/easy pairs."""

    if len(rows) % 2:
        raise PostRehearsalError("paired PCGrad requires an even row count")
    pairs = []
    for offset in range(0, len(rows), 2):
        hard, easy = rows[offset : offset + 2]
        if (
            hard.get("curriculum_role") != "hard"
            or hard.get("learning_target") != REPAIR_TARGET
            or easy.get("curriculum_role") != "easy"
            or easy.get("learning_target") != RETENTION_TARGET
        ):
            raise PostRehearsalError(
                f"paired PCGrad role order drifted at rows {offset}/{offset + 1}"
            )
        pairs.append((hard, easy))
    return pairs


def project_conflicting_pair(
    hard_gradients: Sequence[Any],
    easy_gradients: Sequence[Any],
    *,
    torch: Any,
) -> tuple[list[Any], dict[str, float | bool]]:
    """Apply symmetric two-task PCGrad and return the summed update gradient."""

    if not hard_gradients or len(hard_gradients) != len(easy_gradients):
        raise PostRehearsalError("paired PCGrad gradient sets drifted")
    dot = sum(
        (hard * easy).sum()
        for hard, easy in zip(hard_gradients, easy_gradients, strict=True)
    )
    hard_norm_sq = sum(gradient.square().sum() for gradient in hard_gradients)
    easy_norm_sq = sum(gradient.square().sum() for gradient in easy_gradients)
    scalars = (dot, hard_norm_sq, easy_norm_sq)
    if any(not bool(torch.isfinite(value)) for value in scalars):
        raise PostRehearsalError("paired PCGrad geometry is non-finite")
    dot_value = float(dot.detach().cpu())
    hard_norm_value = float(hard_norm_sq.detach().cpu())
    easy_norm_value = float(easy_norm_sq.detach().cpu())
    denominator = math.sqrt(hard_norm_value * easy_norm_value)
    cosine = dot_value / denominator if denominator > 0.0 else 0.0
    conflict = dot_value < 0.0
    if conflict:
        if hard_norm_value == 0.0 or easy_norm_value == 0.0:
            raise PostRehearsalError("conflicting PCGrad task has zero norm")
        hard_scale = dot / easy_norm_sq
        easy_scale = dot / hard_norm_sq
        merged = [
            hard - hard_scale * easy + easy - easy_scale * hard
            for hard, easy in zip(hard_gradients, easy_gradients, strict=True)
        ]
    else:
        merged = [
            hard + easy
            for hard, easy in zip(hard_gradients, easy_gradients, strict=True)
        ]
    return merged, {
        "conflict": conflict,
        "dot": dot_value,
        "cosine": cosine,
        "hard_norm": math.sqrt(hard_norm_value),
        "easy_norm": math.sqrt(easy_norm_value),
    }


def parameter_anchor_regularizer(
    parameters: Sequence[Any],
    anchors: Sequence[Any],
    *,
    torch: Any,
    coefficient: float = PARAMETER_ANCHOR_COEFFICIENT,
) -> tuple[Any, dict[str, float]]:
    """Return a finite L2-SP loss around the immutable control69 parameters."""

    if (
        not parameters
        or len(parameters) != len(anchors)
        or not math.isfinite(coefficient)
        or coefficient <= 0.0
    ):
        raise PostRehearsalError("parameter anchor identity drifted")
    squared_distance = sum(
        (parameter.float() - anchor.float()).square().sum()
        for parameter, anchor in zip(parameters, anchors, strict=True)
    )
    loss = squared_distance * (0.5 * coefficient)
    if not bool(torch.isfinite(loss)):
        raise PostRehearsalError("parameter anchor loss is non-finite")
    return loss, {
        "parameter_anchor_loss": float(loss.detach().cpu()),
        "parameter_anchor_squared_distance": float(
            squared_distance.detach().cpu()
        ),
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
    policy = listening_policy(
        str(manifest["kind"]),
        arguments.trainable_target,
        arguments.training_objective,
        arguments.adapter_ema,
        arguments.optimizer_mode,
        arguments.parameter_anchor,
    )

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

    scope = role_mix.training_scope(arguments.inventory, "control69")
    if arguments.trainable_target == FULL_CONVERTER_TARGET:
        control = PeftModel.from_pretrained(
            model, str(arguments.control_adapter), is_trainable=False
        )
        trained = control.merge_and_unload(safe_merge=True)
        trainable = _set_converter_training_only(trained)
        expected_trainable = EXPECTED_CONVERTER_PARAMETERS
    else:
        trained = PeftModel.from_pretrained(
            model, str(arguments.control_adapter), is_trainable=True
        )
        trainable = role_mix._set_scope_training_only(trained, scope)
        expected_trainable = role_mix.expected_trainable_parameter_count(
            scope, "standard"
        )
    if sum(parameter.numel() for parameter in trainable) != expected_trainable:
        raise PostRehearsalError("control69 trainable parameter count drifted")
    optimizer = torch.optim.AdamW(trainable, lr=LEARNING_RATE)
    adapter_ema = AdapterEMA(trained, torch) if arguments.adapter_ema else None
    parameter_anchors = (
        [parameter.detach().clone() for parameter in trainable]
        if arguments.parameter_anchor
        else None
    )
    losses: list[float] = []
    adversarial_metrics: list[dict[str, float]] = []
    pcgrad_metrics: list[dict[str, float | bool]] = []
    optimizer_steps = 0
    rows = (
        smoke_rows(
            manifest,
            arguments.optimizer_mode,
            arguments.parameter_anchor,
        )
        if arguments.smoke
        else manifest["items"]
    )
    discriminator = None
    discriminator_optimizer = None
    realism_targets: dict[str, Any] = {}
    if arguments.training_objective == REAL_REFERENCE_ADVERSARIAL_OBJECTIVE:
        discriminator, discriminator_optimizer = breadth._load_pretrained_discriminator(
            arguments, config, torch=torch, device=device
        )
        target_by_id = {
            target_id: _pair(target_id, path, digest)
            for target_id, path, digest in target_rows
        }
        for target_id in {str(item["target_id"]) for item in rows}:
            pair = target_by_id.get(target_id)
            if pair is None:
                raise PostRehearsalError(
                    f"real adversarial target is unavailable: {target_id}"
                )
            realism_targets[target_id] = base._extract_pair_tensors(
                trained,
                pair,
                process_audio=process_audio,
                config=config,
                torch=torch,
                device=device,
            )["target_wav"]

    def batch_for(item: Mapping[str, Any]) -> Any:
        if arguments.trainable_target == FULL_CONVERTER_TARGET:
            _set_converter_training_only(trained)
        else:
            role_mix._set_scope_training_only(trained, scope)
        tensors = _batch_from_item(
            trained,
            item,
            source_work=arguments.source_work,
            control_work=arguments.control_work,
            diverse_work=arguments.diverse_work,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        return base._gpu_batch(tensors, torch=torch, device=device)

    if arguments.optimizer_mode == PCGRAD_PAIRED_OPTIMIZER:
        for hard_item, easy_item in paired_hard_easy_rows(rows):
            task_gradients: list[list[Any]] = []
            for item in (hard_item, easy_item):
                optimizer.zero_grad(set_to_none=True)
                batch = batch_for(item)
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                    loss, numeric = role_mix.training_loss(
                        trained,
                        batch,
                        "real-donor-teacher-output",
                        torch=torch,
                        teacher_loss="standard",
                    )
                gradients = torch.autograd.grad(
                    loss,
                    trainable,
                    allow_unused=True,
                )
                task_gradients.append(
                    [
                        gradient.detach()
                        if gradient is not None
                        else torch.zeros_like(parameter)
                        for parameter, gradient in zip(
                            trainable, gradients, strict=True
                        )
                    ]
                )
                losses.append(numeric)
            merged_gradients, metrics = project_conflicting_pair(
                task_gradients[0], task_gradients[1], torch=torch
            )
            pcgrad_metrics.append(metrics)
            optimizer.zero_grad(set_to_none=True)
            for parameter, gradient in zip(trainable, merged_gradients, strict=True):
                parameter.grad = gradient
            gradient_norm = torch.nn.utils.clip_grad_norm_(
                trainable, base.GRADIENT_CLIP_NORM
            )
            if not math.isfinite(float(gradient_norm.detach().cpu())):
                raise PostRehearsalError("paired PCGrad merged norm is non-finite")
            if not arguments.smoke:
                optimizer.step()
                optimizer_steps += 1
    else:
        for item in rows:
            batch = batch_for(item)
            if discriminator is not None and discriminator_optimizer is not None:
                metrics = breadth._adversarial_update(
                    trained,
                    discriminator,
                    optimizer,
                    discriminator_optimizer,
                    trainable,
                    batch,
                    torch=torch,
                    real_audios=realism_targets[str(item["target_id"])].to(
                        device=device, dtype=torch.float32
                    ),
                    generator_regularizer=(
                        (
                            lambda: parameter_anchor_regularizer(
                                trainable,
                                parameter_anchors,
                                torch=torch,
                            )
                        )
                        if parameter_anchors is not None
                        else None
                    ),
                )
                losses.append(metrics["total"])
                adversarial_metrics.append(metrics)
            else:
                optimizer.zero_grad(set_to_none=True)
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
                    raise PostRehearsalError(
                        "post-rehearsal gradient norm is non-finite"
                    )
                if not arguments.smoke:
                    optimizer.step()
                losses.append(numeric)
            if not arguments.smoke:
                optimizer_steps += 1
            if adapter_ema is not None:
                adapter_ema.update()
    if arguments.smoke:
        smoke = {
            "status": "smoked-control69-clean-post-rehearsal",
            "loss": losses[0],
            "trainable_parameters": expected_trainable,
            "training_objective": arguments.training_objective,
            "optimizer_mode": arguments.optimizer_mode,
            "parameter_anchor": arguments.parameter_anchor,
            "prospective_optimizer_steps": (
                1 if arguments.optimizer_mode == PCGRAD_PAIRED_OPTIMIZER else len(rows)
            ),
            "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        }
        if adversarial_metrics:
            smoke["adversarial_metrics"] = {
                "first": adversarial_metrics[0],
                "last": adversarial_metrics[-1],
            }
        else:
            smoke["gradient_norm"] = float(gradient_norm.detach().cpu())
        if adapter_ema is not None:
            smoke["adapter_ema"] = adapter_ema.receipt()
        if pcgrad_metrics:
            smoke["pcgrad"] = pcgrad_metrics[0]
        method._write_json(arguments.work_dir / "smoke.json", smoke)
        print(json.dumps(smoke, sort_keys=True))
        return 0
    if len(losses) != EXPECTED_ROWS:
        raise PostRehearsalError("post-rehearsal update count drifted")
    if arguments.trainable_target == FULL_CONVERTER_TARGET:
        checkpoint_metadata = save_converter_checkpoint(
            trained, arguments.work_dir / f"converter-{EXPECTED_ROWS}", torch
        )
    else:
        checkpoint_steps = (
            optimizer_steps
            if arguments.optimizer_mode == PCGRAD_PAIRED_OPTIMIZER
            else EXPECTED_ROWS
        )
        adapter_dir = arguments.work_dir / f"adapter-{checkpoint_steps}"
        if adapter_ema is not None:
            online_dir = arguments.work_dir / f"online-adapter-{EXPECTED_ROWS}"
            trained.save_pretrained(online_dir, safe_serialization=True)
            adapter_ema.copy_to()
        trained.save_pretrained(adapter_dir, safe_serialization=True)
        checkpoint_metadata = {
            "kind": "peft-adapter-ema" if adapter_ema is not None else "peft-adapter",
            "directory": adapter_dir.name,
            "online_directory": (
                f"online-adapter-{EXPECTED_ROWS}" if adapter_ema is not None else None
            ),
        }

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
            policy["candidate_id"]: base._write_float_wav(
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
        "kind": policy["result_kind"],
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": policy["question"],
        "independent_variable": policy["independent_variable"],
        "training_manifest_sha256": sha256_file(arguments.training_manifest),
        "source_result_sha256": sha256_file(arguments.source_work / "result.json"),
        "control_probe_result_sha256": (
            sha256_file(arguments.control_work / "result.json")
            if arguments.control_work is not None
            else None
        ),
        "control_adapter": str(arguments.control_adapter),
        "trainable_target": arguments.trainable_target,
        "training_objective": arguments.training_objective,
        "optimizer_mode": arguments.optimizer_mode,
        "parameter_anchor": (
            {
                "implementation": PARAMETER_ANCHOR_IMPLEMENTATION,
                "coefficient": PARAMETER_ANCHOR_COEFFICIENT,
                "reference": "immutable EXP-035 control69 trainable parameters",
                "first_loss": adversarial_metrics[0]["parameter_anchor_loss"],
                "last_loss": adversarial_metrics[-1]["parameter_anchor_loss"],
                "last_squared_distance": adversarial_metrics[-1][
                    "parameter_anchor_squared_distance"
                ],
            }
            if arguments.parameter_anchor
            else None
        ),
        "adapter_ema": adapter_ema.receipt() if adapter_ema is not None else None,
        "candidate_checkpoint": checkpoint_metadata,
        "optimizer_steps": optimizer_steps,
        "training_examples": len(losses),
        "updates": optimizer_steps,
        "role_counts": {"real-donor-teacher-output": len(losses)},
        "learning_target_counts": manifest.get(
            "learning_target_counts", {"base-teacher": len(losses)}
        ),
        "composition": manifest["composition"],
        "learning_rate": LEARNING_RATE,
        "gradient_clip_norm": base.GRADIENT_CLIP_NORM,
        "trainable_parameters": expected_trainable,
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "adversarial_metrics": (
            {
                "updates": len(adversarial_metrics),
                "first": adversarial_metrics[0],
                "last": adversarial_metrics[-1],
                "real_audio": "authorized-original-Amitaro-target",
                "generative_audio": "selective-repair-or-retention-target",
            }
            if adversarial_metrics
            else None
        ),
        "pcgrad_metrics": (
            {
                "pairs": len(pcgrad_metrics),
                "conflicts": sum(bool(item["conflict"]) for item in pcgrad_metrics),
                "cosine_min": min(float(item["cosine"]) for item in pcgrad_metrics),
                "cosine_mean": sum(float(item["cosine"]) for item in pcgrad_metrics)
                / len(pcgrad_metrics),
                "cosine_max": max(float(item["cosine"]) for item in pcgrad_metrics),
            }
            if pcgrad_metrics
            else None
        ),
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
                "optimizer_steps": optimizer_steps,
                "training_examples": len(losses),
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
    value.add_argument("--control-work", type=Path)
    value.add_argument("--diverse-work", type=Path)
    value.add_argument("--evaluation-set", type=Path, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--pair-root", type=Path, required=True)
    value.add_argument("--control-adapter", type=Path, required=True)
    value.add_argument(
        "--trainable-target",
        choices=(LORA69_TARGET, FULL_CONVERTER_TARGET),
        default=LORA69_TARGET,
    )
    value.add_argument(
        "--training-objective",
        choices=(GENERATIVE_OBJECTIVE, REAL_REFERENCE_ADVERSARIAL_OBJECTIVE),
        default=GENERATIVE_OBJECTIVE,
    )
    value.add_argument(
        "--optimizer-mode",
        choices=(SEQUENTIAL_OPTIMIZER, PCGRAD_PAIRED_OPTIMIZER),
        default=SEQUENTIAL_OPTIMIZER,
    )
    value.add_argument("--adapter-ema", action="store_true")
    value.add_argument("--parameter-anchor", action="store_true")
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
                        "composition": manifest["composition"],
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
