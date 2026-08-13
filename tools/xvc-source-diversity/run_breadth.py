#!/usr/bin/env python3
"""Train fixed-data X-VC donor-breadth and waveform-adversarial pilots."""

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

import listen_now as base  # noqa: E402
import listen_now_horizon as horizon  # noqa: E402
import render_commonvoice as external  # noqa: E402
import run as method  # noqa: E402

DONOR_KIND = "liveconv-exp035-commonvoice-donors/v1"
EVALUATION_KIND = "liveconv-exp035-commonvoice-external-evaluation/v1"
DONOR_COUNT = 12
EVALUATION_COUNT = 7
TOTAL_UPDATES = method.PAIR_COUNT * DONOR_COUNT
MAX_ADMISSION_DISTANCE = 0.375
GENERATIVE_OBJECTIVE = "generative-only"
ADVERSARIAL_OBJECTIVE = "upstream-adversarial"
EXP035_CONTROL_ADAPTER_SHA256 = (
    "2cd08900b8992877158ef16f5963706a0ac909d076d139288dcd5d7c66825e7f"
)
EXP035_GENERATED_INVENTORY_SHA256 = (
    "e909e465ae5b49fb2be67dded797acf13895acd7f2ddd77c570cea8acdba9cd0"
)


class BreadthError(RuntimeError):
    """The bounded EXP-035 donor-breadth pilot cannot safely continue."""


def training_policy(objective: str) -> dict[str, Any]:
    if objective == GENERATIVE_OBJECTIVE:
        return {
            "experiment_id": "EXP-035",
            "result_kind": "liveconv-exp035-xvc-donor-breadth-result/v1",
            "run_kind": "EXP-035 X-VC donor-breadth external evaluation",
            "question": (
                "Does twelve-donor breadth beat three donors at fixed exposure?"
            ),
            "independent_variable": (
                "generated-source donor pool: 3 distinct speakers repeated four "
                "times versus 12 distinct speakers in one pass"
            ),
            "control": (
                "jvs3-generated-pairs",
                "EXP-033 / JVS 3 donor x 4 epochs / 1,044 updates",
                "20-xvc-jvs3-generated-pairs.wav",
            ),
            "candidate": (
                "cv12-generated-pairs",
                "EXP-035 / Common Voice 12 donor x 1 epoch / 1,044 updates",
                "30-xvc-cv12-generated-pairs.wav",
            ),
            "loss": "pinned X-VC composite generative loss",
        }
    if objective == ADVERSARIAL_OBJECTIVE:
        return {
            "experiment_id": "EXP-064",
            "result_kind": "liveconv-exp064-xvc-wave-adversarial-result/v1",
            "run_kind": "EXP-064 X-VC waveform-adversarial external evaluation",
            "question": (
                "Does restoring X-VC's pretrained waveform-adversarial objective "
                "produce a viable fixed-data listening candidate?"
            ),
            "independent_variable": (
                "training objective: composite generative loss only versus the same "
                "loss plus pretrained waveform adversarial and feature matching"
            ),
            "control": (
                "cv12-control69",
                "EXP-035 / CV12 / generative-only control69",
                "20-xvc-cv12-control69.wav",
            ),
            "candidate": (
                "cv12-wave-adversarial",
                "EXP-064 / CV12 / pretrained waveform adversarial",
                "30-xvc-cv12-wave-adversarial.wav",
            ),
            "loss": (
                "pinned X-VC composite generative + pretrained waveform "
                "adversarial + feature matching"
            ),
        }
    raise BreadthError(f"unknown training objective: {objective}")


def _load_manifest(path: Path, *, kind: str, count: int) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BreadthError(f"manifest is not valid JSON: {path.name}") from error
    items = value.get("items") if isinstance(value, dict) else None
    source = value.get("source") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or value.get("kind") != kind
        or not isinstance(items, list)
        or len(items) != count
        or not isinstance(source, dict)
        or source.get("license") != "CC0-1.0"
    ):
        raise BreadthError(f"manifest schema drifted: {path.name}")
    ids: set[str] = set()
    clients: set[str] = set()
    files: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise BreadthError(f"manifest row is malformed: {path.name}")
        identifier = item.get("id")
        client = item.get("client_id_sha256")
        filename = item.get("filename")
        distance = item.get("known_text_distance")
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in ids
            or not base._is_sha256(client)
            or client in clients
            or not isinstance(filename, str)
            or Path(filename).name != filename
            or filename in files
            or not base._is_sha256(item.get("sha256"))
            or not isinstance(item.get("text"), str)
            or not isinstance(item.get("source_transcript"), str)
            or not isinstance(distance, (int, float))
            or isinstance(distance, bool)
            or not 0.0 <= float(distance) <= MAX_ADMISSION_DISTANCE
        ):
            raise BreadthError(f"manifest row identity drifted: {path.name}")
        ids.add(identifier)
        clients.add(client)
        files.add(filename)
    return value


def training_schedule(
    target_ids: Sequence[str], donor_ids: Sequence[str]
) -> list[tuple[str, str]]:
    if len(target_ids) != method.PAIR_COUNT or len(set(target_ids)) != len(target_ids):
        raise BreadthError("target schedule drifted")
    if len(donor_ids) != DONOR_COUNT or len(set(donor_ids)) != DONOR_COUNT:
        raise BreadthError("donor schedule drifted")
    schedule = [
        (target_id, donor_id)
        for target_id in target_ids
        for donor_id in donor_ids
    ]
    if len(schedule) != TOTAL_UPDATES:
        raise BreadthError("training update count drifted")
    return schedule


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, Path, str]]]:
    donors = _load_manifest(arguments.donors, kind=DONOR_KIND, count=DONOR_COUNT)
    evaluation = _load_manifest(
        arguments.evaluation_set, kind=EVALUATION_KIND, count=EVALUATION_COUNT
    )
    donor_clients = {item["client_id_sha256"] for item in donors["items"]}
    evaluation_clients = {
        item["client_id_sha256"] for item in evaluation["items"]
    }
    if donor_clients & evaluation_clients:
        raise BreadthError("training donors overlap external evaluation speakers")
    for item in [*donors["items"], *evaluation["items"]]:
        path = arguments.source_root / item["filename"]
        if (
            path.is_symlink()
            or not path.is_file()
            or base.sha256_file(path) != item["sha256"]
        ):
            raise BreadthError(f"Common Voice input drifted: {item['filename']}")
    targets = method.target_inventory(arguments.pair_root)
    training_schedule(
        [row[0] for row in targets], [item["id"] for item in donors["items"]]
    )
    if (
        arguments.control_adapter.is_symlink()
        or not (arguments.control_adapter / "adapter_model.safetensors").is_file()
    ):
        raise BreadthError("EXP-033 control adapter is unavailable")
    if arguments.training_objective == ADVERSARIAL_OBJECTIVE and base.sha256_file(
        arguments.control_adapter / "adapter_model.safetensors"
    ) != EXP035_CONTROL_ADAPTER_SHA256:
        raise BreadthError("EXP-035 generative-only control adapter drifted")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-035 work directory",
    )
    base._require_new_output(
        arguments.listener_dir,
        REPO_ROOT / "artifacts" / "ms3" / "listening",
        "EXP-035 listener directory",
    )
    return donors, evaluation, targets


def _reference_tensor(
    model: Any,
    item: Mapping[str, Any],
    *,
    source_root: Path,
    output_root: Path,
    process_audio: Any,
    config: Mapping[str, object],
    torch: Any,
    device: Any,
) -> tuple[base.MaterializedPair, dict[str, Any]]:
    values = external.padded_model_audio(
        source_root / str(item["filename"]), process_audio, config
    )
    output = output_root / f"{item['id']}.wav"
    method._write_model_window(output, values)
    digest = base.sha256_file(output)
    pair = base.MaterializedPair(str(item["id"]), output, output, digest, digest)
    tensors = base._extract_pair_tensors(
        model,
        pair,
        process_audio=process_audio,
        config=config,
        torch=torch,
        device=device,
    )
    return pair, tensors


def listening_index(
    item: Mapping[str, Any],
    *,
    hashes: Mapping[str, str],
    policy: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    policy = training_policy(GENERATIVE_OBJECTIVE) if policy is None else policy
    control_id, control_name, control_filename = policy["control"]
    candidate_id, candidate_name, candidate_filename = policy["candidate"]
    variants = (
        ("base", "X-VC base", "10-xvc-base.wav", 1),
        (control_id, control_name, control_filename, 2),
        (candidate_id, candidate_name, candidate_filename, 3),
    )
    return {
        "schema_version": 1,
        "run_kind": policy["run_kind"],
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
                "profile_id": (
                    f"xvc.{str(policy['experiment_id']).lower()}."
                    f"{variant_id}.listen-now"
                ),
                "family_id": "x-vc",
                "output_sha256": hashes[variant_id],
            }
            for variant_id, display_name, filename, order in variants
        ],
    }


def _load_pretrained_discriminator(
    arguments: argparse.Namespace,
    config: Mapping[str, Any],
    *,
    torch: Any,
    device: Any,
) -> tuple[Any, Any]:
    import hydra

    discriminator_config = config["model"]["discriminator"]
    discriminator = hydra.utils.instantiate(discriminator_config)
    checkpoint = torch.load(
        arguments.checkpoint,
        map_location="cpu",
        weights_only=False,
        mmap=True,
    )
    state = checkpoint.get("discriminator") if isinstance(checkpoint, dict) else None
    if not isinstance(state, dict) or len(state) != 324:
        raise BreadthError("pretrained X-VC discriminator state drifted")
    discriminator.load_state_dict(state, strict=True)
    del checkpoint, state
    discriminator.to(device).train()
    parameters = list(discriminator.parameters())
    if not parameters or not all(parameter.requires_grad for parameter in parameters):
        raise BreadthError("pretrained X-VC discriminator is not trainable")
    optimizer_config = discriminator_config["optim_conf"]
    optimizer = torch.optim.AdamW(
        parameters,
        lr=float(optimizer_config["lr"]),
        betas=tuple(float(value) for value in optimizer_config["betas"]),
    )
    return discriminator, optimizer


def _finite_loss(value: Any, *, torch: Any, label: str) -> Any:
    if value is None or not bool(torch.isfinite(value)):
        raise BreadthError(f"{label} is non-finite")
    return value


def _adversarial_update(
    trained: Any,
    discriminator: Any,
    generator_optimizer: Any,
    discriminator_optimizer: Any,
    trainable: Sequence[Any],
    batch: Mapping[str, Any],
    *,
    torch: Any,
) -> dict[str, float]:
    base._set_adapter_training_only(trained)
    discriminator.train()
    generator_optimizer.zero_grad(set_to_none=True)
    discriminator_optimizer.zero_grad(set_to_none=True)

    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        outputs = trained(dict(batch))
        reconstruction = outputs.get("recons") if isinstance(outputs, dict) else None
        if reconstruction is None or not bool(torch.isfinite(reconstruction).all()):
            raise BreadthError("X-VC adversarial reconstruction is malformed")
        outputs["audios"] = batch["target_wav"][..., : reconstruction.shape[-1]]
        discriminator_losses = discriminator.discriminative_loss(outputs)
        discriminator_loss = _finite_loss(
            discriminator_losses.get("loss"),
            torch=torch,
            label="X-VC discriminator loss",
        )
    discriminator_loss.backward()
    discriminator_norm = torch.nn.utils.clip_grad_norm_(
        discriminator.parameters(), base.GRADIENT_CLIP_NORM
    )
    if not math.isfinite(float(discriminator_norm.detach().cpu())):
        raise BreadthError("X-VC discriminator gradient norm is non-finite")
    discriminator_optimizer.step()

    for parameter in discriminator.parameters():
        parameter.requires_grad_(False)
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        generator_losses = trained.generative_loss(outputs)
        adversarial_losses = discriminator.adversarial_loss(outputs)
        generator_loss = _finite_loss(
            generator_losses.get("loss"),
            torch=torch,
            label="X-VC generative loss",
        )
        adversarial_loss = _finite_loss(
            adversarial_losses.get("loss"),
            torch=torch,
            label="X-VC adversarial loss",
        )
        total_loss = generator_loss + adversarial_loss
    total_loss.backward()
    generator_norm = torch.nn.utils.clip_grad_norm_(
        trainable, base.GRADIENT_CLIP_NORM
    )
    if not math.isfinite(float(generator_norm.detach().cpu())):
        raise BreadthError("X-VC generator gradient norm is non-finite")
    generator_optimizer.step()
    for parameter in discriminator.parameters():
        parameter.requires_grad_(True)

    return {
        "total": float(total_loss.detach().cpu()),
        "generative": float(generator_loss.detach().cpu()),
        "discriminator": float(discriminator_loss.detach().cpu()),
        "adversarial_generator": float(adversarial_losses["adv_gen_loss"]),
        "adversarial_feature": float(adversarial_losses["adv_feat_loss"]),
    }


def run(
    arguments: argparse.Namespace,
    donors: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    target_rows: list[tuple[str, Path, str]],
) -> int:
    policy = training_policy(arguments.training_objective)
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise BreadthError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise BreadthError(
            f"{policy['experiment_id']} requires the explicit gpu0 lease"
        )
    started = time.monotonic()
    arguments.work_dir.mkdir()
    donor_root = arguments.work_dir / "donor-references"
    evaluation_root = arguments.work_dir / "evaluation-sources"
    pseudo_root = arguments.work_dir / "generated-source-pairs"
    for path in (donor_root, evaluation_root, pseudo_root):
        path.mkdir()

    import torch
    from peft import LoraConfig, PeftModel, get_peft_model

    if not torch.cuda.is_available():
        raise BreadthError("CUDA is unavailable")
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
    donor_pairs: list[base.MaterializedPair] = []
    donor_tensors: list[dict[str, Any]] = []
    for item in donors["items"]:
        pair, tensors = _reference_tensor(
            model,
            item,
            source_root=arguments.source_root,
            output_root=donor_root,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        donor_pairs.append(pair)
        donor_tensors.append(tensors)

    evaluation_pairs: list[base.MaterializedPair] = []
    evaluation_tensors: list[dict[str, Any]] = []
    for item in evaluation["items"]:
        pair, tensors = _reference_tensor(
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

    generated_tensors: list[dict[str, Any]] = []
    generated_inventory: list[dict[str, str]] = []
    for target_index, (target_pair, target_tensor) in enumerate(
        zip(target_pairs, target_tensors, strict=True)
    ):
        pair_root = pseudo_root / target_pair.pair_id
        pair_root.mkdir()
        for donor_index, (donor_pair, donor_tensor) in enumerate(
            zip(donor_pairs, donor_tensors, strict=True)
        ):
            output = base._inference(
                model,
                target_tensor,
                donor_tensor,
                seed=base.SEED + target_index * DONOR_COUNT + donor_index,
                torch=torch,
                device=device,
            )
            output_path = pair_root / f"source-{donor_pair.pair_id}-16k.wav"
            digest = base._write_float_wav(output_path, output, sample_rate)
            with torch.inference_mode():
                features = model.semantic_encoder.extract_and_encode(output.squeeze(1))
            tokens = features.get("speech_tokens")
            if tokens is None or tokens[:, : base.SEMANTIC_FRAMES].shape != (
                1,
                base.SEMANTIC_FRAMES,
            ):
                raise BreadthError("generated semantic feature shape drifted")
            generated_tensors.append(
                {
                    "source_wav": output.detach().cpu().to(torch.float32).contiguous(),
                    "semantic_tokens": tokens[:, : base.SEMANTIC_FRAMES]
                    .detach()
                    .cpu()
                    .to(torch.int64)
                    .contiguous(),
                    "target_wav": target_tensor["target_wav"],
                    "ssl_feat": target_tensor["ssl_feat"],
                }
            )
            generated_inventory.append(
                {
                    "target_id": target_pair.pair_id,
                    "donor_id": donor_pair.pair_id,
                    "source_sha256": digest,
                }
            )
    if len(generated_tensors) != TOTAL_UPDATES:
        raise BreadthError("generated pair count drifted")
    generated_inventory_sha256 = method._canonical_sha256(generated_inventory)
    if (
        arguments.training_objective == ADVERSARIAL_OBJECTIVE
        and generated_inventory_sha256 != EXP035_GENERATED_INVENTORY_SHA256
    ):
        raise BreadthError("EXP-035 generated training data drifted")

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
        raise BreadthError("control69 target set drifted")
    trainable = base._set_adapter_training_only(trained)
    if sum(parameter.numel() for parameter in trainable) != int(
        scope["trainable_parameter_count"]
    ):
        raise BreadthError("control69 trainable parameter count drifted")
    optimizer = torch.optim.AdamW(trainable, lr=base.LEARNING_RATE)
    losses: list[float] = []
    adversarial_metrics: list[dict[str, float]] = []
    discriminator = None
    discriminator_optimizer = None
    if arguments.training_objective == ADVERSARIAL_OBJECTIVE:
        discriminator, discriminator_optimizer = _load_pretrained_discriminator(
            arguments, config, torch=torch, device=device
        )
    for tensors in generated_tensors:
        batch = base._gpu_batch(tensors, torch=torch, device=device)
        if discriminator is not None and discriminator_optimizer is not None:
            metrics = _adversarial_update(
                trained,
                discriminator,
                optimizer,
                discriminator_optimizer,
                trainable,
                batch,
                torch=torch,
            )
            losses.append(metrics["total"])
            adversarial_metrics.append(metrics)
        else:
            base._set_adapter_training_only(trained)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                loss, numeric = base._composite_loss(trained, batch, torch)
            loss.backward()
            gradient_norm = torch.nn.utils.clip_grad_norm_(
                trainable, base.GRADIENT_CLIP_NORM
            )
            if not math.isfinite(float(gradient_norm.detach().cpu())):
                raise BreadthError("X-VC gradient norm is non-finite")
            optimizer.step()
            losses.append(numeric)
    if len(losses) != TOTAL_UPDATES:
        raise BreadthError(f"{policy['experiment_id']} update count drifted")
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
        control_id, _, control_filename = policy["control"]
        candidate_id, _, candidate_filename = policy["candidate"]
        hashes = {
            "base": base._write_float_wav(
                row_root / "10-xvc-base.wav", base_outputs[index], sample_rate
            ),
            control_id: base._write_float_wav(
                row_root / control_filename,
                control_outputs[index],
                sample_rate,
            ),
            candidate_id: base._write_float_wav(
                row_root / candidate_filename,
                candidate_outputs[index],
                sample_rate,
            ),
        }
        method._write_json(
            row_root / "index.json",
            listening_index(item, hashes=hashes, policy=policy),
        )
        listener_rows.append({"source_id": item["id"], "hashes": hashes})

    result = {
        "schema_version": 1,
        "kind": policy["result_kind"],
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": policy["question"],
        "independent_variable": policy["independent_variable"],
        "fixed": {
            "target_voice": "Amitaro runrun",
            "target_text_count": method.PAIR_COUNT,
            "target_exposures_per_text": DONOR_COUNT,
            "optimizer_updates": TOTAL_UPDATES,
            "lora_scope": "control69",
            "learning_rate": base.LEARNING_RATE,
            "gradient_clip_norm": base.GRADIENT_CLIP_NORM,
            "target_wav_cond": "zeros",
            "loss": policy["loss"],
        },
        "donor_manifest_sha256": base.sha256_file(arguments.donors),
        "evaluation_set_sha256": base.sha256_file(arguments.evaluation_set),
        "donor_count": len(donor_pairs),
        "external_evaluation_speaker_count": len(evaluation_pairs),
        "generated_pair_count": len(generated_tensors),
        "generated_inventory_sha256": generated_inventory_sha256,
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "adversarial_metrics": (
            {
                "updates": len(adversarial_metrics),
                "first": adversarial_metrics[0],
                "last": adversarial_metrics[-1],
            }
            if adversarial_metrics
            else None
        ),
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
                "donors": len(donor_pairs),
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
    parser.add_argument(
        "--training-objective",
        choices=(GENERATIVE_OBJECTIVE, ADVERSARIAL_OBJECTIVE),
        default=GENERATIVE_OBJECTIVE,
    )
    parser.add_argument("--donors", type=Path, required=True)
    parser.add_argument("--evaluation-set", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--control-adapter", type=Path, required=True)
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
        donors, evaluation, targets = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "donors": len(donors["items"]),
                        "evaluation_rows": len(evaluation["items"]),
                        "training_targets": len(targets),
                        "generated_pairs": TOTAL_UPDATES,
                        "updates": TOTAL_UPDATES,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, donors, evaluation, targets)
    except (
        base.ListenNowError,
        BreadthError,
        external.ExternalEvaluationError,
        method.SourceDiversityError,
        OSError,
        ValueError,
    ) as error:
        print(f"exp035-breadth-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
