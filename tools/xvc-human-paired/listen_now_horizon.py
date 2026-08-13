#!/usr/bin/env python3
"""Run an EXP-026 human-pair X-VC training-horizon listen-now comparison.

The run repeats the EXP-025 four-epoch arm as an exact deterministic control,
or the completed EXP-026 twelve-epoch arm for the extended plan, then changes
only training duration. It publishes plain labels on the fixed listener and
never opens a heldout target. The result is operator screening material, not
promote or product evidence.
"""

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

import listen_now as base

CHECKPOINT_EPOCHS = (4, 8, 12)
EXTENDED_CHECKPOINT_EPOCHS = (12, 18, 24)
ALLOWED_CHECKPOINT_EPOCHS = (CHECKPOINT_EPOCHS, EXTENDED_CHECKPOINT_EPOCHS)
FINAL_EPOCH = CHECKPOINT_EPOCHS[-1]
TOTAL_UPDATES = base.EXPECTED_TRAIN_PAIRS * FINAL_EPOCH
CONTROL69_TARGET_COUNT = 69
CONTROL69_TRAINABLE_PARAMETERS = 835_584
CONTROL69_TARGET_NAME_LIST_SHA256 = (
    "61652c6faf760d655f5c35d169980b158eb79a46eb3fb781db6b0ebb3bfc4860"
)
EXPECTED_BASE_HASHES = {
    "EMOTION100_002": (
        "5d0197ebbb21b61b35ec5924b3a06027e709a20a28ce4a7cdff4aa17fab70740"
    ),
    "EMOTION100_004": (
        "0085803cf464eb597c41986fa7aa57f817a3c54c5ef8b26141366d89cd025c85"
    ),
    "EMOTION100_017": (
        "a1ab62f396b5bf3c33afdde1bb74d41362b53b84da484dbe82c0a753c43f7010"
    ),
}
EXPECTED_EPOCH4_HASHES = {
    "EMOTION100_002": (
        "0eb32c54d3f67b6ef09dbd75378d7515aa10a4e2346f36c25c14c72f7f4b0a43"
    ),
    "EMOTION100_004": (
        "fefada2ccb0e0b4515fb3075847d200b5a0764a3137a7d62739fcd9ff02fb0b7"
    ),
    "EMOTION100_017": (
        "4a1cf0a0363fcaf81633226881e03896c3051064db8437f0fa083d60a987ba55"
    ),
}
EXPECTED_EPOCH12_HASHES = {
    "EMOTION100_002": (
        "7d5aa1917f6833ce4190060a81fe0d76368bf978574ded444b8bd3193cbe3e83"
    ),
    "EMOTION100_004": (
        "3c0e471d2368cc9e9cda12d953688f56443ef9bad6c53c37dfd61d4cec51b6af"
    ),
    "EMOTION100_017": (
        "968d43157cff15c316252d229394f9a6528412018e9c7996297b78da9b1fd9ed"
    ),
}


def listening_index(
    source: base.RenderSource,
    *,
    target_reference_id: str,
    hashes: Mapping[int, str],
    checkpoint_epochs: Sequence[int] = CHECKPOINT_EPOCHS,
    scope_name: str = "expanded79",
) -> dict[str, object]:
    variants: list[dict[str, object]] = [
        {
            "variant_id": "xvc-base",
            "display_name": "X-VC base / human input / adapterなし",
            "display_order": 1,
            "output_file": "10-xvc-base.wav",
            "status": "passed",
            "profile_id": "xvc.base.human-listen-now",
            "family_id": "x-vc",
            "output_sha256": hashes[0],
        }
    ]
    for order, epoch in enumerate(checkpoint_epochs, start=2):
        updates = epoch * base.EXPECTED_TRAIN_PAIRS
        variants.append(
            {
                "variant_id": f"xvc-human87-epoch{epoch:02d}",
                "display_name": (
                    "X-VC / 人間whole-short 87ペア / "
                    f"{scope_name} / {epoch} epochs / {updates} updates"
                ),
                "display_order": order,
                "output_file": f"{order}0-xvc-human87-e{epoch:02d}.wav",
                "status": "passed",
                "profile_id": (
                    f"xvc.exp026.human87.{scope_name}.e{epoch:02d}.listen-now"
                ),
                "family_id": "x-vc",
                "output_sha256": hashes[epoch],
            }
        )
    return {
        "schema_version": 1,
        "run_kind": "EXP-026 human87 X-VC horizon listen-now",
        "status": "completed-listen-now-unselected",
        "source_file": (
            f"Hadou public source-only / {source.pair_id} / {source.display_text}"
        ),
        "source_output_file": "00-source-reference.wav",
        "target_reference_output_file": "01-target-reference.wav",
        "reference_audio": [
            {
                "kind": "source",
                "label": f"Hadou source / {source.pair_id}",
                "output_file": "00-source-reference.wav",
                "excluded_from_preference": True,
            },
            {
                "kind": "target",
                "label": (
                    "Amitaro runrun train-role reference / "
                    f"{target_reference_id}"
                ),
                "output_file": "01-target-reference.wav",
                "excluded_from_preference": True,
            },
        ],
        "variants": variants,
    }


def assert_epoch4_control(
    source_id: str, *, base_sha256: str, epoch4_sha256: str
) -> None:
    if EXPECTED_BASE_HASHES.get(source_id) != base_sha256:
        raise base.ListenNowError(
            f"EXP-026 base control drifted for {source_id}"
        )
    if EXPECTED_EPOCH4_HASHES.get(source_id) != epoch4_sha256:
        raise base.ListenNowError(
            f"EXP-026 epoch-4 control drifted for {source_id}"
        )


def assert_extended_control(
    source_id: str, *, base_sha256: str, epoch12_sha256: str
) -> None:
    if EXPECTED_BASE_HASHES.get(source_id) != base_sha256:
        raise base.ListenNowError(
            f"EXP-026 extended base control drifted for {source_id}"
        )
    if EXPECTED_EPOCH12_HASHES.get(source_id) != epoch12_sha256:
        raise base.ListenNowError(
            f"EXP-026 extended epoch-12 control drifted for {source_id}"
        )


def assert_base_control(source_id: str, *, base_sha256: str) -> None:
    if EXPECTED_BASE_HASHES.get(source_id) != base_sha256:
        raise base.ListenNowError(f"EXP-026 base control drifted for {source_id}")


def parse_checkpoint_epochs(value: str) -> tuple[int, ...]:
    try:
        epochs = tuple(int(item) for item in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "checkpoint epochs must be comma-separated integers"
        ) from error
    if epochs not in ALLOWED_CHECKPOINT_EPOCHS:
        allowed = " or ".join(
            ",".join(str(epoch) for epoch in plan)
            for plan in ALLOWED_CHECKPOINT_EPOCHS
        )
        raise argparse.ArgumentTypeError(f"checkpoint epochs must be {allowed}")
    return epochs


def lora_scope(inventory_path: Path, scope_name: str) -> dict[str, object]:
    expanded = base.expanded79_scope(inventory_path)
    if scope_name == "expanded79":
        return expanded
    if scope_name != "control69":
        raise base.ListenNowError("LoRA scope must be control69 or expanded79")
    targets = [
        name
        for name in expanded["target_modules"]
        if ".attn." in name or ".ff_c." in name or ".ff_x." in name
    ]
    if (
        len(targets) != CONTROL69_TARGET_COUNT
        or base._canonical_sha256(targets) != CONTROL69_TARGET_NAME_LIST_SHA256
    ):
        raise base.ListenNowError("control69 LoRA scope drifted")
    return {
        "target_modules": targets,
        "trainable_parameter_count": CONTROL69_TRAINABLE_PARAMETERS,
    }


def run(
    arguments: argparse.Namespace,
    manifest: Mapping[str, Any],
    rows: list[dict[str, Any]],
) -> int:
    del manifest
    checkpoint_epochs = arguments.checkpoint_epochs
    final_epoch = checkpoint_epochs[-1]
    total_updates = base.EXPECTED_TRAIN_PAIRS * final_epoch
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise base.ListenNowError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise base.ListenNowError("EXP-026 requires the explicit gpu0 lease")

    started = time.monotonic()
    arguments.work_dir.mkdir()
    materialized = base._materialize_training_pairs(
        rows,
        source_root=arguments.source_root,
        target_archive=arguments.target_archive,
        output_root=arguments.work_dir / "train-pairs",
    )
    render_sources = base._materialize_render_sources(
        rows,
        source_root=arguments.source_root,
        output_root=arguments.work_dir / "render-sources",
    )

    import torch
    from peft import LoraConfig, get_peft_model

    if not torch.cuda.is_available():
        raise base.ListenNowError("CUDA is unavailable")
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
    model = XVC.load_from_checkpoint(
        str(arguments.xvc_config),
        str(arguments.checkpoint),
        device,
        ema_load=False,
    )
    base._initialize_loss(model, arguments.xvc_config)
    train_tensors = [
        base._extract_pair_tensors(
            model,
            pair,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        for pair in materialized
    ]
    render_tensors = [
        base._extract_render_source(
            model,
            source,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        for source in render_sources
    ]
    target_reference = train_tensors[0]
    target_reference_pair = materialized[0]
    outputs: dict[int, list[Any]] = {
        0: [
            base._inference(
                model,
                source,
                target_reference,
                seed=base.SEED + index,
                torch=torch,
                device=device,
            ).detach().cpu()
            for index, source in enumerate(render_tensors)
        ]
    }

    scope = lora_scope(arguments.inventory, arguments.lora_scope)
    targets = list(scope["target_modules"])
    model = get_peft_model(
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
    observed = getattr(model, "targeted_module_names", None)
    if not isinstance(observed, (list, tuple)) or set(observed) != set(targets):
        raise base.ListenNowError("PEFT target module set drifted")
    trainable = base._set_adapter_training_only(model)
    if sum(parameter.numel() for parameter in trainable) != int(
        scope["trainable_parameter_count"]
    ):
        raise base.ListenNowError("LoRA trainable parameter count drifted")
    optimizer = torch.optim.AdamW(trainable, lr=base.LEARNING_RATE)
    losses: list[float] = []
    for epoch in range(1, final_epoch + 1):
        for tensors in train_tensors:
            base._set_adapter_training_only(model)
            optimizer.zero_grad(set_to_none=True)
            batch = base._gpu_batch(tensors, torch=torch, device=device)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                loss, numeric = base._composite_loss(model, batch, torch)
            loss.backward()
            gradient_norm = torch.nn.utils.clip_grad_norm_(
                trainable, base.GRADIENT_CLIP_NORM
            )
            if not math.isfinite(float(gradient_norm.detach().cpu())):
                raise base.ListenNowError("X-VC gradient norm is non-finite")
            optimizer.step()
            losses.append(numeric)
        if epoch in checkpoint_epochs:
            updates = epoch * base.EXPECTED_TRAIN_PAIRS
            adapter_dir = arguments.work_dir / f"adapter-{updates:04d}"
            model.save_pretrained(adapter_dir, safe_serialization=True)
            outputs[epoch] = [
                base._inference(
                    model,
                    source,
                    target_reference,
                    seed=base.SEED + index,
                    torch=torch,
                    device=device,
                ).detach().cpu()
                for index, source in enumerate(render_tensors)
            ]
    if len(losses) != total_updates or set(outputs) != {0, *checkpoint_epochs}:
        raise base.ListenNowError("EXP-026 update or checkpoint count drifted")

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    listener_rows: list[dict[str, object]] = []
    for index, source in enumerate(render_sources, start=1):
        row_dir = staging / f"{index:02d}-{source.pair_id}"
        row_dir.mkdir()
        shutil.copyfile(source.source_path, row_dir / "00-source-reference.wav")
        shutil.copyfile(
            target_reference_pair.target_path, row_dir / "01-target-reference.wav"
        )
        hashes: dict[int, str] = {
            0: base._write_float_wav(
                row_dir / "10-xvc-base.wav", outputs[0][index - 1], sample_rate
            )
        }
        for order, epoch in enumerate(checkpoint_epochs, start=2):
            hashes[epoch] = base._write_float_wav(
                row_dir / f"{order}0-xvc-human87-e{epoch:02d}.wav",
                outputs[epoch][index - 1],
                sample_rate,
            )
        if (
            arguments.lora_scope == "expanded79"
            and checkpoint_epochs == CHECKPOINT_EPOCHS
        ):
            assert_epoch4_control(
                source.pair_id,
                base_sha256=hashes[0],
                epoch4_sha256=hashes[4],
            )
        elif arguments.lora_scope == "expanded79":
            assert_extended_control(
                source.pair_id,
                base_sha256=hashes[0],
                epoch12_sha256=hashes[12],
            )
        else:
            assert_base_control(source.pair_id, base_sha256=hashes[0])
        base._write_json(
            row_dir / "index.json",
            listening_index(
                source,
                target_reference_id=target_reference_pair.pair_id,
                hashes=hashes,
                checkpoint_epochs=checkpoint_epochs,
                scope_name=arguments.lora_scope,
            ),
        )
        listener_rows.append(
            {
                "source_id": source.pair_id,
                "hashes_by_epoch": {str(key): value for key, value in hashes.items()},
            }
        )

    receipt = {
        "schema_version": 1,
        "kind": "liveconv-exp026-human87-horizon-listen-now-result",
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": (
            "Does extending the exact human87 trajectory across epochs "
            f"{', '.join(str(epoch) for epoch in checkpoint_epochs)} audibly "
            "improve X-VC?"
        ),
        "train_pair_count": len(materialized),
        "lora_scope": arguments.lora_scope,
        "lora_target_count": len(targets),
        "checkpoint_epochs": list(checkpoint_epochs),
        "updates": len(losses),
        "learning_rate": base.LEARNING_RATE,
        "gradient_clip_norm": base.GRADIENT_CLIP_NORM,
        "loss_first": losses[0],
        "loss_at_checkpoints": {
            str(epoch): losses[epoch * base.EXPECTED_TRAIN_PAIRS - 1]
            for epoch in checkpoint_epochs
        },
        "render_sources": listener_rows,
        "target_reference_id": target_reference_pair.pair_id,
        "heldout_target_access_count": 0,
        "control_epoch": (
            checkpoint_epochs[0] if arguments.lora_scope == "expanded79" else None
        ),
        "control_epoch_reproduced": arguments.lora_scope == "expanded79",
        "epoch4_control_reproduced": (
            arguments.lora_scope == "expanded79"
            and checkpoint_epochs == CHECKPOINT_EPOCHS
        ),
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "claims": {
            "promoted": False,
            "route_qualified": False,
            "product_selected": False,
            "serious_334_36_54_adaptation": False,
        },
    }
    base._write_json(arguments.work_dir / "listen-now-result.json", receipt)
    staging.rename(arguments.listener_dir)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "listener_dir": str(arguments.listener_dir),
                "updates": len(losses),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--target-archive", type=Path, required=True)
    parser.add_argument("--xvc-source-root", type=Path, required=True)
    parser.add_argument("--xvc-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=(
            base.REPO_ROOT
            / "artifacts"
            / "exp007"
            / "phase0-inputs-v1"
            / "inventory.json"
        ),
    )
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--listener-dir", type=Path, required=True)
    parser.add_argument(
        "--checkpoint-epochs",
        type=parse_checkpoint_epochs,
        default=CHECKPOINT_EPOCHS,
        metavar="EPOCHS",
        help="exactly 4,8,12 or 12,18,24",
    )
    parser.add_argument(
        "--lora-scope",
        choices=("expanded79", "control69"),
        default="expanded79",
    )
    parser.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    parser.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        manifest, rows = base.validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "manifest_sha256": manifest["manifest_sha256"],
                        "row_count": len(rows),
                        "expected_train_pair_count": base.EXPECTED_TRAIN_PAIRS,
                        "checkpoint_epochs": list(arguments.checkpoint_epochs),
                        "lora_scope": arguments.lora_scope,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, manifest, rows)
    except base.ListenNowError as error:
        print(f"listen-now horizon failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
