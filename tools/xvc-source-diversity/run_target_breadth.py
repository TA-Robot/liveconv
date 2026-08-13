#!/usr/bin/env python3
"""Train EXP-055 with broader authorized Amitaro target-text coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import time
import zipfile
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
import listen_now_horizon as horizon  # noqa: E402
import render_commonvoice as external  # noqa: E402
import run as method  # noqa: E402

DONOR_KIND = "liveconv-exp035-commonvoice-donors/v1"
EVALUATION_KIND = "liveconv-exp035-commonvoice-external-evaluation/v1"
DONOR_COUNT = 12
EVALUATION_COUNT = 7
TRAIN_TARGET_COUNT = 275
FOUR_EXPOSURE_TARGETS = 219
TOTAL_UPDATES = 1_044
TARGET_ID_DIGEST = (
    "75f6b6431cde5c7af6dcd783a45eb08e01c4f24c728f0185b42e08b447ce9811"
)
SCHEDULE_DIGEST = (
    "c69200c9ccacccde1e29272f1d9affacf466ee0a694905c84cbe7e1243e71b16"
)
MAX_ADMISSION_DISTANCE = 0.375


class TargetBreadthError(RuntimeError):
    """The bounded EXP-055 target-text-breadth pilot cannot safely continue."""


def _load_manifest(path: Path, *, kind: str, count: int) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TargetBreadthError(
            f"manifest is not valid JSON: {path.name}"
        ) from error
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
        raise TargetBreadthError(f"manifest schema drifted: {path.name}")
    ids: set[str] = set()
    clients: set[str] = set()
    files: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise TargetBreadthError(f"manifest row is malformed: {path.name}")
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
            raise TargetBreadthError(
                f"manifest row identity drifted: {path.name}"
            )
        ids.add(identifier)
        clients.add(client)
        files.add(filename)
    return value


def training_schedule(
    target_ids: Sequence[str], donor_ids: Sequence[str]
) -> list[tuple[str, str]]:
    if len(target_ids) != TRAIN_TARGET_COUNT or len(set(target_ids)) != len(
        target_ids
    ):
        raise TargetBreadthError("target schedule drifted")
    if len(donor_ids) != DONOR_COUNT or len(set(donor_ids)) != DONOR_COUNT:
        raise TargetBreadthError("donor schedule drifted")
    schedule: list[tuple[str, str]] = []
    donor_index = 0
    for target_index, target_id in enumerate(target_ids):
        exposures = 4 if target_index < FOUR_EXPOSURE_TARGETS else 3
        for _ in range(exposures):
            schedule.append((target_id, donor_ids[donor_index % DONOR_COUNT]))
            donor_index += 1
    observed = Counter(donor for _, donor in schedule)
    if (
        len(schedule) != TOTAL_UPDATES
        or set(observed.values()) != {TOTAL_UPDATES // DONOR_COUNT}
    ):
        raise TargetBreadthError("training update schedule drifted")
    return schedule


def _load_target_rows(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TargetBreadthError("target manifest is not valid JSON") from error
    if not isinstance(value, dict):
        raise TargetBreadthError("target manifest schema drifted")
    manifest_sha256, rows = base._manifest_rows(value)
    train_rows = [row for row in rows if row.get("split") == "train"]
    if (
        manifest_sha256 != base.EXPECTED_MANIFEST_SHA256
        or len(rows) != 424
        or len(train_rows) != 334
    ):
        raise TargetBreadthError("target manifest identity drifted")
    return value, train_rows


def eligible_target_rows(
    rows: Sequence[Mapping[str, Any]], target_archive: Path
) -> list[dict[str, Any]]:
    if target_archive.is_symlink() or not target_archive.is_file():
        raise TargetBreadthError("Amitaro target archive is unavailable")
    if base.sha256_file(target_archive) != base.EXPECTED_TARGET_ARCHIVE_SHA256:
        raise TargetBreadthError("Amitaro target archive identity drifted")
    selected: list[dict[str, Any]] = []
    with zipfile.ZipFile(target_archive) as archive:
        for row in rows:
            pair_id = base._pair_id_from_value(row, "EXP-055 train row")
            locator, expected_hash = base._wav_locator(
                row, "target_wav", pair_id
            )
            payload = base._archive_wav(
                archive, locator, f"Amitaro target {pair_id}"
            )
            base._assert_wav_hash(payload, expected_hash, "Amitaro target")
            pcm = base._parse_pcm16_wav(payload, f"Amitaro target {pair_id}")
            start, stop = base.endpoint_complete_speech(pcm, base.SAMPLE_RATE_48K)
            if stop - start >= base.MIN_TARGET_SPEECH_SAMPLES:
                selected.append(dict(row))
    identifiers = [str(row["utterance_id"]) for row in selected]
    digest = hashlib.sha256(
        ("\n".join(identifiers) + "\n").encode("ascii")
    ).hexdigest()
    if len(selected) != TRAIN_TARGET_COUNT or digest != TARGET_ID_DIGEST:
        raise TargetBreadthError("eligible target-text inventory drifted")
    return selected


def materialize_target_windows(
    rows: Sequence[Mapping[str, Any]],
    *,
    target_archive: Path,
    output_root: Path,
) -> list[base.MaterializedPair]:
    output_root.mkdir()
    pairs: list[base.MaterializedPair] = []
    with zipfile.ZipFile(target_archive) as archive:
        for row in rows:
            pair_id = base._pair_id_from_value(row, "EXP-055 train row")
            locator, expected_hash = base._wav_locator(
                row, "target_wav", pair_id
            )
            payload = base._archive_wav(
                archive, locator, f"Amitaro target {pair_id}"
            )
            base._assert_wav_hash(payload, expected_hash, "Amitaro target")
            pcm = base._parse_pcm16_wav(payload, f"Amitaro target {pair_id}")
            start, stop = base.endpoint_complete_speech(pcm, base.SAMPLE_RATE_48K)
            active = pcm[start : min(stop, start + base.WINDOW_48K)]
            window = base._right_pad(active, base.WINDOW_48K)
            pair_root = output_root / pair_id
            pair_root.mkdir()
            target_path = pair_root / "target-48k.wav"
            base._write_pcm16(target_path, window)
            digest = base.sha256_file(target_path)
            pairs.append(
                base.MaterializedPair(
                    pair_id, target_path, target_path, digest, digest
                )
            )
    if len(pairs) != TRAIN_TARGET_COUNT:
        raise TargetBreadthError("materialized target count drifted")
    return pairs


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    donors = _load_manifest(arguments.donors, kind=DONOR_KIND, count=DONOR_COUNT)
    evaluation = _load_manifest(
        arguments.evaluation_set, kind=EVALUATION_KIND, count=EVALUATION_COUNT
    )
    donor_clients = {item["client_id_sha256"] for item in donors["items"]}
    evaluation_clients = {
        item["client_id_sha256"] for item in evaluation["items"]
    }
    if donor_clients & evaluation_clients:
        raise TargetBreadthError(
            "training donors overlap external evaluation speakers"
        )
    for item in [*donors["items"], *evaluation["items"]]:
        path = arguments.source_root / item["filename"]
        if (
            path.is_symlink()
            or not path.is_file()
            or base.sha256_file(path) != item["sha256"]
        ):
            raise TargetBreadthError(
                f"Common Voice input drifted: {item['filename']}"
            )
    target_manifest, train_rows = _load_target_rows(arguments.target_manifest)
    targets = eligible_target_rows(train_rows, arguments.target_archive)
    schedule = training_schedule(
        [str(row["utterance_id"]) for row in targets],
        [item["id"] for item in donors["items"]],
    )
    schedule_digest = hashlib.sha256(
        "".join(f"{target} {donor}\n" for target, donor in schedule).encode("ascii")
    ).hexdigest()
    if schedule_digest != SCHEDULE_DIGEST:
        raise TargetBreadthError("bound training schedule drifted")
    if (
        arguments.control_adapter.is_symlink()
        or not (arguments.control_adapter / "adapter_model.safetensors").is_file()
    ):
        raise TargetBreadthError("EXP-035 control adapter is unavailable")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-055 work directory",
    )
    base._require_new_output(
        arguments.listener_dir,
        REPO_ROOT / "artifacts" / "ms3" / "listening",
        "EXP-055 listener directory",
    )
    return donors, evaluation, target_manifest, targets


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
    item: Mapping[str, Any], *, hashes: Mapping[str, str]
) -> dict[str, object]:
    variants = (
        ("base", "X-VC base", "10-xvc-base.wav", 1),
        (
            "cv12-control69",
            "EXP-035 / 87 target texts / 12 donors / 1,044 updates",
            "20-xvc-cv12-control69.wav",
            2,
        ),
        (
            "cv12-target275",
            "EXP-055 / 275 target texts / 12 donors / 1,044 updates",
            "30-xvc-cv12-target275.wav",
            3,
        ),
    )
    return {
        "schema_version": 1,
        "run_kind": "EXP-055 X-VC target-text-breadth external evaluation",
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
                "profile_id": f"xvc.exp055.{variant_id}.listen-now",
                "family_id": "x-vc",
                "output_sha256": hashes[variant_id],
            }
            for variant_id, display_name, filename, order in variants
        ],
    }


def run(
    arguments: argparse.Namespace,
    donors: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    target_manifest: Mapping[str, Any],
    target_rows: list[dict[str, Any]],
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise TargetBreadthError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise TargetBreadthError("EXP-055 requires the explicit gpu0 lease")
    started = time.monotonic()
    arguments.work_dir.mkdir()
    donor_root = arguments.work_dir / "donor-references"
    evaluation_root = arguments.work_dir / "evaluation-sources"
    pseudo_root = arguments.work_dir / "generated-source-pairs"
    for path in (donor_root, evaluation_root, pseudo_root):
        path.mkdir()
    target_pairs = materialize_target_windows(
        target_rows,
        target_archive=arguments.target_archive,
        output_root=arguments.work_dir / "target-windows",
    )

    import torch
    from peft import LoraConfig, PeftModel, get_peft_model

    if not torch.cuda.is_available():
        raise TargetBreadthError("CUDA is unavailable")
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

    schedule = training_schedule(
        [pair.pair_id for pair in target_pairs],
        [pair.pair_id for pair in donor_pairs],
    )
    target_by_id = dict(
        zip(
            [pair.pair_id for pair in target_pairs], target_tensors, strict=True
        )
    )
    donor_by_id = dict(
        zip([pair.pair_id for pair in donor_pairs], donor_tensors, strict=True)
    )
    generated_tensors: list[dict[str, Any]] = []
    generated_inventory: list[dict[str, str]] = []
    for update_index, (target_id, donor_id) in enumerate(schedule):
        target_tensor = target_by_id[target_id]
        donor_tensor = donor_by_id[donor_id]
        pair_root = pseudo_root / target_id
        pair_root.mkdir(exist_ok=True)
        output = base._inference(
            model,
            target_tensor,
            donor_tensor,
            seed=base.SEED + update_index,
            torch=torch,
            device=device,
        )
        output_path = pair_root / f"source-{update_index:04d}-{donor_id}-16k.wav"
        digest = base._write_float_wav(output_path, output, sample_rate)
        with torch.inference_mode():
            features = model.semantic_encoder.extract_and_encode(output.squeeze(1))
        tokens = features.get("speech_tokens")
        if tokens is None or tokens[:, : base.SEMANTIC_FRAMES].shape != (
            1,
            base.SEMANTIC_FRAMES,
        ):
            raise TargetBreadthError("generated semantic feature shape drifted")
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
                "target_id": target_id,
                "donor_id": donor_id,
                "source_sha256": digest,
            }
        )
    if len(generated_tensors) != TOTAL_UPDATES:
        raise TargetBreadthError("generated pair count drifted")

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
        raise TargetBreadthError("control69 target set drifted")
    trainable = base._set_adapter_training_only(trained)
    if sum(parameter.numel() for parameter in trainable) != int(
        scope["trainable_parameter_count"]
    ):
        raise TargetBreadthError("control69 trainable parameter count drifted")
    optimizer = torch.optim.AdamW(trainable, lr=base.LEARNING_RATE)
    losses: list[float] = []
    for tensors in generated_tensors:
        base._set_adapter_training_only(trained)
        optimizer.zero_grad(set_to_none=True)
        batch = base._gpu_batch(tensors, torch=torch, device=device)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            loss, numeric = base._composite_loss(trained, batch, torch)
        loss.backward()
        gradient_norm = torch.nn.utils.clip_grad_norm_(
            trainable, base.GRADIENT_CLIP_NORM
        )
        if not math.isfinite(float(gradient_norm.detach().cpu())):
            raise TargetBreadthError("X-VC gradient norm is non-finite")
        optimizer.step()
        losses.append(numeric)
    if len(losses) != TOTAL_UPDATES:
        raise TargetBreadthError("EXP-055 update count drifted")
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
            "cv12-target275": base._write_float_wav(
                row_root / "30-xvc-cv12-target275.wav",
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
        "kind": "liveconv-exp055-xvc-target-text-breadth-result/v1",
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": (
            "Does broader authorized target-text coverage improve X-VC "
            "generalization at fixed updates and donor pool?"
        ),
        "independent_variable": (
            "eligible Amitaro target texts: 87 complete-short prefixes versus "
            "275 first-active windows; 1,044 updates and 12-donor pool fixed"
        ),
        "fixed": {
            "target_voice": "Amitaro runrun",
            "target_text_count": TRAIN_TARGET_COUNT,
            "target_exposures_per_text": {
                "three": TRAIN_TARGET_COUNT - FOUR_EXPOSURE_TARGETS,
                "four": FOUR_EXPOSURE_TARGETS,
            },
            "optimizer_updates": TOTAL_UPDATES,
            "lora_scope": "control69",
            "learning_rate": base.LEARNING_RATE,
            "gradient_clip_norm": base.GRADIENT_CLIP_NORM,
            "target_wav_cond": "zeros",
            "loss": "pinned X-VC composite generative loss",
        },
        "donor_manifest_sha256": base.sha256_file(arguments.donors),
        "target_manifest_sha256": base.sha256_file(arguments.target_manifest),
        "target_archive_sha256": base.sha256_file(arguments.target_archive),
        "target_id_digest": TARGET_ID_DIGEST,
        "training_schedule_sha256": SCHEDULE_DIGEST,
        "evaluation_set_sha256": base.sha256_file(arguments.evaluation_set),
        "donor_count": len(donor_pairs),
        "external_evaluation_speaker_count": len(evaluation_pairs),
        "generated_pair_count": len(generated_tensors),
        "generated_inventory_sha256": method._canonical_sha256(generated_inventory),
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
                "donors": len(donor_pairs),
                "training_targets": len(target_pairs),
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
    parser.add_argument("--donors", type=Path, required=True)
    parser.add_argument("--evaluation-set", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--target-manifest", type=Path, required=True)
    parser.add_argument("--target-archive", type=Path, required=True)
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
        donors, evaluation, target_manifest, targets = validate_inputs(arguments)
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
        return run(arguments, donors, evaluation, target_manifest, targets)
    except (
        base.ListenNowError,
        TargetBreadthError,
        external.ExternalEvaluationError,
        method.SourceDiversityError,
        OSError,
        ValueError,
    ) as error:
        print(f"exp055-target-breadth-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
