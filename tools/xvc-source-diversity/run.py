#!/usr/bin/env python3
"""Run the EXP-033 X-VC generated-source-diversity listen-now pilot.

The pilot holds target text exposure, optimizer updates, LoRA topology, learning
rate, loss, and target voice fixed against the completed human87 control69-e12
run.  It changes only source construction: each of the 87 Amitaro targets is
converted to three JVS donor voices with the immutable base X-VC, then the 261
generated same-content pairs are trained for four epochs (1,044 updates).

Outputs are machine-screening and later listening material.  They cannot select
or promote a voice without operator hearing.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

TOOL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOL_ROOT.parents[1]
HUMAN_TOOL_ROOT = REPO_ROOT / "tools" / "xvc-human-paired"
if str(HUMAN_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(HUMAN_TOOL_ROOT))

import listen_now as base  # noqa: E402
import listen_now_horizon as horizon  # noqa: E402

KIND = "liveconv-exp033-xvc-source-diversity-evaluation/v1"
PAIR_COUNT = 87
DONOR_COUNT = 3
EPOCHS = 4
TOTAL_UPDATES = PAIR_COUNT * DONOR_COUNT * EPOCHS
TARGET_INVENTORY_SHA256 = (
    "d0e2ba669b459c3e617eca80651c1b020dab20bfb852fcb2d390583e88e70af5"
)
EXPECTED_GROUP_COUNTS = {
    "clean-cross-speaker": 6,
    "tempo": 1,
    "pitch": 1,
    "noise": 1,
    "leading-silence": 1,
}
EXPECTED_JVS_HASHES = {
    "jvs001.wav": "ad812d499e23ff37929402915cdf8d3034b6bc602b8471bb6a504d5432c19869",
    "jvs002.wav": "40298305cd0b063143ad5e5a7623f2a49d3c846aa6f535adfe682c19b7abbffd",
    "jvs003.wav": "b538f57686020e37cb82cfeda8dc7c369c4ffb174510a70344b7523fce0fb774",
}


class SourceDiversityError(RuntimeError):
    """The bounded EXP-033 pilot cannot safely continue."""


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SourceDiversityError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def load_evaluation_set(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceDiversityError("evaluation set is not valid JSON") from error
    if not isinstance(value, dict) or value.get("kind") != KIND:
        raise SourceDiversityError("evaluation set kind drifted")
    items = value.get("items")
    if not isinstance(items, list) or len(items) != sum(EXPECTED_GROUP_COUNTS.values()):
        raise SourceDiversityError("evaluation set must contain exactly ten rows")
    identifiers: set[str] = set()
    groups: Counter[str] = Counter()
    for item in items:
        if not isinstance(item, dict):
            raise SourceDiversityError("evaluation row must be an object")
        identifier = item.get("id")
        group = item.get("group")
        source_set = item.get("source_set")
        filename = item.get("filename")
        sha256 = item.get("sha256")
        transform = item.get("transform")
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in identifiers
            or group not in EXPECTED_GROUP_COUNTS
            or source_set not in {"jvs", "hadou-heldout"}
            or not isinstance(filename, str)
            or Path(filename).name != filename
            or not base._is_sha256(sha256)
            or not isinstance(transform, dict)
            or transform.get("kind")
            not in {"clean", "tempo", "pitch", "noise", "leading-silence"}
        ):
            raise SourceDiversityError("evaluation row schema or identity drifted")
        identifiers.add(identifier)
        groups[str(group)] += 1
    if dict(groups) != EXPECTED_GROUP_COUNTS:
        raise SourceDiversityError("evaluation group coverage drifted")
    return value


def target_inventory(pair_root: Path) -> list[tuple[str, Path, str]]:
    if pair_root.is_symlink() or not pair_root.is_dir():
        raise SourceDiversityError("human87 pair root is unavailable")
    rows: list[tuple[str, Path, str]] = []
    lines: list[str] = []
    for pair_dir in sorted(pair_root.iterdir(), key=lambda path: path.name):
        if pair_dir.is_symlink() or not pair_dir.is_dir():
            raise SourceDiversityError("human87 pair root contains a non-directory")
        target = pair_dir / "target-48k.wav"
        if target.is_symlink() or not target.is_file():
            raise SourceDiversityError(f"missing target for {pair_dir.name}")
        digest = base.sha256_file(target)
        rows.append((pair_dir.name, target, digest))
        lines.append(f"{pair_dir.name} {digest}\n")
    inventory_digest = hashlib.sha256("".join(lines).encode("ascii")).hexdigest()
    if len(rows) != PAIR_COUNT or inventory_digest != TARGET_INVENTORY_SHA256:
        raise SourceDiversityError("human87 target inventory drifted")
    return rows


def training_schedule(
    pair_ids: Sequence[str], donor_ids: Sequence[str]
) -> list[tuple[str, str]]:
    if len(pair_ids) != PAIR_COUNT or len(set(pair_ids)) != PAIR_COUNT:
        raise SourceDiversityError("training pair IDs drifted")
    if tuple(donor_ids) != ("jvs001", "jvs002", "jvs003"):
        raise SourceDiversityError("training donor IDs drifted")
    one_epoch = [(pair_id, donor_id) for pair_id in pair_ids for donor_id in donor_ids]
    schedule = one_epoch * EPOCHS
    if len(schedule) != TOTAL_UPDATES:
        raise SourceDiversityError("training update count drifted")
    return schedule


def _source_path(
    item: Mapping[str, object], *, jvs_root: Path, heldout_root: Path
) -> Path:
    root = jvs_root if item["source_set"] == "jvs" else heldout_root
    path = root / str(item["filename"])
    if path.is_symlink() or not path.is_file():
        raise SourceDiversityError(f"evaluation source is unavailable: {path.name}")
    if base.sha256_file(path) != item["sha256"]:
        raise SourceDiversityError(f"evaluation source hash drifted: {path.name}")
    return path


def _validate_xvc(arguments: argparse.Namespace) -> None:
    if arguments.xvc_source_root.is_symlink() or not arguments.xvc_source_root.is_dir():
        raise SourceDiversityError("X-VC source root is unavailable")
    revision = base._git_output(
        ["git", "-C", str(arguments.xvc_source_root), "rev-parse", "HEAD"],
        "X-VC revision",
    )
    dirty = base._git_output(
        [
            "git",
            "-C",
            str(arguments.xvc_source_root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        "X-VC worktree",
    )
    if revision != base.EXPECTED_XVC_REVISION or dirty:
        raise SourceDiversityError("X-VC source revision or worktree drifted")
    if base.sha256_file(arguments.xvc_config) != base.EXPECTED_XVC_CONFIG_SHA256:
        raise SourceDiversityError("X-VC config identity drifted")
    if (
        arguments.checkpoint.is_symlink()
        or not arguments.checkpoint.is_file()
        or arguments.checkpoint.stat().st_size != base.EXPECTED_CHECKPOINT_BYTES
    ):
        raise SourceDiversityError("X-VC checkpoint identity drifted")
    base.ffmpeg_rubberband_identity()
    horizon.lora_scope(arguments.inventory, "control69")


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], list[tuple[str, Path, str]]]:
    evaluation = load_evaluation_set(arguments.evaluation_set)
    targets = target_inventory(arguments.pair_root)
    for filename, digest in EXPECTED_JVS_HASHES.items():
        path = arguments.jvs_root / filename
        if path.is_symlink() or not path.is_file() or base.sha256_file(path) != digest:
            raise SourceDiversityError(f"JVS donor identity drifted: {filename}")
    for item in evaluation["items"]:
        _source_path(
            item, jvs_root=arguments.jvs_root, heldout_root=arguments.heldout_root
        )
    if (
        arguments.legacy_adapter.is_symlink()
        or not (arguments.legacy_adapter / "adapter_model.safetensors").is_file()
    ):
        raise SourceDiversityError("legacy control69-e12 adapter is unavailable")
    _validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-033 work directory",
    )
    base._require_new_output(
        arguments.listener_dir,
        REPO_ROOT / "artifacts" / "ms3" / "listening",
        "EXP-033 listener directory",
    )
    training_schedule([row[0] for row in targets], ["jvs001", "jvs002", "jvs003"])
    return evaluation, targets


def _model_window(
    path: Path, *, process_audio: Any, config: Mapping[str, object]
) -> np.ndarray:
    return base._model_audio(path, process_audio, config)


def _write_model_window(path: Path, values: np.ndarray) -> None:
    pcm = (np.clip(values, -1.0, 1.0) * 32767.0).round().astype("<i2")
    base._write_pcm16(path, pcm, rate=16_000)


def transform_window(
    source: Path,
    transform: Mapping[str, object],
    *,
    destination: Path,
    process_audio: Any,
    config: Mapping[str, object],
    seed: int,
) -> None:
    kind = transform["kind"]
    prepared = source
    temporary = destination.with_suffix(".transform.wav")
    if kind in {"tempo", "pitch"}:
        amount = float(transform["factor"])
        filter_name = "tempo" if kind == "tempo" else "pitch"
        try:
            subprocess.run(
                [
                    str(base.PINNED_FFMPEG),
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(source),
                    "-af",
                    f"rubberband={filter_name}={amount:.9f}",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    str(temporary),
                ],
                check=True,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise SourceDiversityError(f"failed to apply {kind} transform") from error
        prepared = temporary
    values = _model_window(prepared, process_audio=process_audio, config=config)
    if temporary.exists():
        temporary.unlink()
    if kind == "noise":
        snr_db = float(transform["snr_db"])
        rms = float(np.sqrt(np.mean(np.square(values), dtype=np.float64)))
        rng = np.random.default_rng(seed)
        noise = rng.standard_normal(values.shape).astype(np.float32)
        noise_rms = float(np.sqrt(np.mean(np.square(noise), dtype=np.float64)))
        if rms <= 0.0 or noise_rms <= 0.0:
            raise SourceDiversityError(
                "cannot add deterministic noise to silent source"
            )
        values = values + noise * np.float32(
            rms / (10.0 ** (snr_db / 20.0)) / noise_rms
        )
    elif kind == "leading-silence":
        samples = int(round(float(transform["milliseconds"]) * 16.0))
        if samples <= 0 or samples >= base.MODEL_SAMPLES:
            raise SourceDiversityError("leading silence duration is invalid")
        values = np.concatenate((np.zeros(samples, dtype=np.float32), values))[
            : base.MODEL_SAMPLES
        ]
    _write_model_window(destination, values)


def materialize_evaluation_sources(
    evaluation: Mapping[str, Any],
    *,
    output_root: Path,
    jvs_root: Path,
    heldout_root: Path,
    process_audio: Any,
    config: Mapping[str, object],
) -> list[base.RenderSource]:
    output_root.mkdir(parents=True)
    rendered: list[base.RenderSource] = []
    for index, item in enumerate(evaluation["items"]):
        source = _source_path(item, jvs_root=jvs_root, heldout_root=heldout_root)
        destination = output_root / f"{index:02d}-{item['id']}.wav"
        transform_window(
            source,
            item["transform"],
            destination=destination,
            process_audio=process_audio,
            config=config,
            seed=base.SEED + index,
        )
        rendered.append(
            base.RenderSource(
                pair_id=str(item["id"]),
                display_text=f"{item['corpus']} / {item['group']} / {item['label']}",
                source_path=destination,
            )
        )
    return rendered


def listening_index(
    source: base.RenderSource,
    *,
    target_reference_id: str,
    hashes: Mapping[str, str],
) -> dict[str, object]:
    variants = [
        ("base", "X-VC base", "10-xvc-base.wav", 1),
        (
            "human87-control69-e12",
            "旧X-VC再学習 / Hadou 1話者 human87 / control69 / 1,044 updates",
            "20-xvc-human87-control69-e12.wav",
            2,
        ),
        (
            "jvs3-generated-pairs",
            "新X-VC再学習 / JVS 3話者生成ペア261 / control69 / 1,044 updates",
            "30-xvc-jvs3-generated-pairs.wav",
            3,
        ),
    ]
    return {
        "schema_version": 1,
        "run_kind": "EXP-033 X-VC generated-source-diversity listen-now",
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
                "profile_id": f"xvc.exp033.{variant_id}.listen-now",
                "family_id": "x-vc",
                "output_sha256": hashes[variant_id],
            }
            for variant_id, display_name, filename, order in variants
        ],
    }


def _load_xvc(arguments: argparse.Namespace, XVC: Any, device: Any) -> Any:
    return XVC.load_from_checkpoint(
        str(arguments.xvc_config), str(arguments.checkpoint), device, ema_load=False
    )


def run(
    arguments: argparse.Namespace,
    evaluation: Mapping[str, Any],
    target_rows: list[tuple[str, Path, str]],
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise SourceDiversityError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise SourceDiversityError("EXP-033 requires the explicit gpu0 lease")

    started = time.monotonic()
    arguments.work_dir.mkdir()
    pseudo_root = arguments.work_dir / "generated-source-pairs"
    pseudo_root.mkdir()

    import torch
    from peft import LoraConfig, PeftModel, get_peft_model

    if not torch.cuda.is_available():
        raise SourceDiversityError("CUDA is unavailable")
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
    model = _load_xvc(arguments, XVC, device)
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
    donor_pairs = [
        base.MaterializedPair(
            donor_id,
            arguments.jvs_root / f"{donor_id}.wav",
            arguments.jvs_root / f"{donor_id}.wav",
            EXPECTED_JVS_HASHES[f"{donor_id}.wav"],
            EXPECTED_JVS_HASHES[f"{donor_id}.wav"],
        )
        for donor_id in ("jvs001", "jvs002", "jvs003")
    ]
    donor_tensors = [
        base._extract_pair_tensors(
            model,
            pair,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        for pair in donor_pairs
    ]
    eval_sources = materialize_evaluation_sources(
        evaluation,
        output_root=arguments.work_dir / "evaluation-sources",
        jvs_root=arguments.jvs_root,
        heldout_root=arguments.heldout_root,
        process_audio=process_audio,
        config=config,
    )
    eval_tensors = [
        base._extract_render_source(
            model,
            source,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        for source in eval_sources
    ]
    target_reference = target_tensors[0]
    target_reference_pair = target_pairs[0]
    base_outputs = [
        base._inference(
            model,
            source,
            target_reference,
            seed=base.SEED + index,
            torch=torch,
            device=device,
        )
        .detach()
        .cpu()
        for index, source in enumerate(eval_tensors)
    ]

    generated_tensors: list[dict[str, Any]] = []
    generated_inventory: list[dict[str, object]] = []
    for pair_index, (pair, target_tensor) in enumerate(
        zip(target_pairs, target_tensors, strict=True)
    ):
        pair_dir = pseudo_root / pair.pair_id
        pair_dir.mkdir()
        for donor_index, (donor_pair, donor_tensor) in enumerate(
            zip(donor_pairs, donor_tensors, strict=True)
        ):
            output = base._inference(
                model,
                target_tensor,
                donor_tensor,
                seed=base.SEED + pair_index * DONOR_COUNT + donor_index,
                torch=torch,
                device=device,
            )
            output_path = pair_dir / f"source-{donor_pair.pair_id}-16k.wav"
            digest = base._write_float_wav(output_path, output, sample_rate)
            source = base.RenderSource(
                pair_id=f"{pair.pair_id}-{donor_pair.pair_id}",
                display_text=(
                    f"generated source {pair.pair_id} via {donor_pair.pair_id}"
                ),
                source_path=output_path,
            )
            extracted = base._extract_render_source(
                model,
                source,
                process_audio=process_audio,
                config=config,
                torch=torch,
                device=device,
            )
            generated_tensors.append(
                {
                    "source_wav": extracted["source_wav"],
                    "semantic_tokens": extracted["semantic_tokens"],
                    "target_wav": target_tensor["target_wav"],
                    "ssl_feat": target_tensor["ssl_feat"],
                }
            )
            generated_inventory.append(
                {
                    "pair_id": pair.pair_id,
                    "donor_id": donor_pair.pair_id,
                    "source_sha256": digest,
                }
            )
    if len(generated_tensors) != PAIR_COUNT * DONOR_COUNT:
        raise SourceDiversityError("generated pair count drifted")

    legacy_base = _load_xvc(arguments, XVC, device)
    legacy_model = PeftModel.from_pretrained(
        legacy_base, str(arguments.legacy_adapter), is_trainable=False
    )
    legacy_outputs = [
        base._inference(
            legacy_model,
            source,
            target_reference,
            seed=base.SEED + index,
            torch=torch,
            device=device,
        )
        .detach()
        .cpu()
        for index, source in enumerate(eval_tensors)
    ]
    del legacy_model, legacy_base
    torch.cuda.empty_cache()

    scope = horizon.lora_scope(arguments.inventory, "control69")
    targets = list(scope["target_modules"])
    trained = get_peft_model(
        model,
        LoraConfig(
            r=8,
            lora_alpha=8,
            lora_dropout=0.0,
            bias="none",
            use_dora=False,
            use_rslora=False,
            target_modules=targets,
        ),
    )
    observed = getattr(trained, "targeted_module_names", None)
    if not isinstance(observed, (list, tuple)) or set(observed) != set(targets):
        raise SourceDiversityError("control69 target set drifted")
    trainable = base._set_adapter_training_only(trained)
    if sum(parameter.numel() for parameter in trainable) != int(
        scope["trainable_parameter_count"]
    ):
        raise SourceDiversityError("control69 trainable parameter count drifted")
    optimizer = torch.optim.AdamW(trainable, lr=base.LEARNING_RATE)
    losses: list[float] = []
    for _epoch in range(EPOCHS):
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
                raise SourceDiversityError("X-VC gradient norm is non-finite")
            optimizer.step()
            losses.append(numeric)
    if len(losses) != TOTAL_UPDATES:
        raise SourceDiversityError("EXP-033 update count drifted")
    adapter_dir = arguments.work_dir / "adapter-1044"
    trained.save_pretrained(adapter_dir, safe_serialization=True)
    adapted_outputs = [
        base._inference(
            trained,
            source,
            target_reference,
            seed=base.SEED + index,
            torch=torch,
            device=device,
        )
        .detach()
        .cpu()
        for index, source in enumerate(eval_tensors)
    ]

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    listener_rows: list[dict[str, object]] = []
    for index, source in enumerate(eval_sources):
        row_dir = staging / f"{index:02d}-{source.pair_id}"
        row_dir.mkdir()
        shutil.copyfile(source.source_path, row_dir / "00-source-reference.wav")
        shutil.copyfile(
            target_reference_pair.target_path, row_dir / "01-target-reference.wav"
        )
        hashes = {
            "base": base._write_float_wav(
                row_dir / "10-xvc-base.wav", base_outputs[index], sample_rate
            ),
            "human87-control69-e12": base._write_float_wav(
                row_dir / "20-xvc-human87-control69-e12.wav",
                legacy_outputs[index],
                sample_rate,
            ),
            "jvs3-generated-pairs": base._write_float_wav(
                row_dir / "30-xvc-jvs3-generated-pairs.wav",
                adapted_outputs[index],
                sample_rate,
            ),
        }
        _write_json(
            row_dir / "index.json",
            listening_index(
                source,
                target_reference_id=target_reference_pair.pair_id,
                hashes=hashes,
            ),
        )
        listener_rows.append(
            {
                "source_id": source.pair_id,
                "group": evaluation["items"][index]["group"],
                "hashes": hashes,
            }
        )

    receipt = {
        "schema_version": 1,
        "kind": "liveconv-exp033-xvc-source-diversity-result/v1",
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": (
            "Does generated same-content source-speaker diversity improve X-VC "
            "robustness at fixed target exposure and 1,044 updates?"
        ),
        "independent_variable": (
            "source construction: one real Hadou speaker versus three "
            "base-X-VC-generated JVS donor voices"
        ),
        "fixed": {
            "target_voice": "Amitaro runrun",
            "target_text_count": PAIR_COUNT,
            "target_exposures_per_text": 12,
            "optimizer_updates": TOTAL_UPDATES,
            "lora_scope": "control69",
            "learning_rate": base.LEARNING_RATE,
            "gradient_clip_norm": base.GRADIENT_CLIP_NORM,
            "target_wav_cond": "zeros",
        },
        "generated_pair_count": len(generated_tensors),
        "generated_inventory_sha256": _canonical_sha256(generated_inventory),
        "evaluation_set_sha256": base.sha256_file(arguments.evaluation_set),
        "evaluation_rows": listener_rows,
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "machine_screen_boundary": (
            "content/corruption and repetition only; not naturalness, similarity, "
            "or a winner"
        ),
        "claims": {
            "promoted": False,
            "route_qualified": False,
            "product_selected": False,
            "perceptual_winner": False,
        },
    }
    _write_json(arguments.work_dir / "result.json", receipt)
    staging.rename(arguments.listener_dir)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "listener_dir": str(arguments.listener_dir),
                "updates": len(losses),
                "evaluation_rows": len(listener_rows),
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
    parser.add_argument("--legacy-adapter", type=Path, required=True)
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
                        "training_targets": len(targets),
                        "generated_pairs": len(targets) * DONOR_COUNT,
                        "updates": TOTAL_UPDATES,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, evaluation, targets)
    except (base.ListenNowError, SourceDiversityError, OSError, ValueError) as error:
        print(f"exp033-source-diversity-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
