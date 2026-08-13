#!/usr/bin/env python3
"""Render EXP-033 adapters on six frozen Common Voice unseen speakers."""

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
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
if str(HUMAN_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(HUMAN_TOOL_ROOT))

import listen_now as base  # noqa: E402
import run as method  # noqa: E402

KIND = "liveconv-exp034-commonvoice25-ja-unseen/v1"
EXPECTED_ROWS = 6
TARGET_REFERENCE_SHA256 = (
    "76f5a4a9b989ed692a55343a7681623fa4f18e354ca04026f022e3e449195ca2"
)


class ExternalEvaluationError(RuntimeError):
    """The external generalization render cannot safely continue."""


def load_inputs(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExternalEvaluationError(
            "Common Voice inputs are not valid JSON"
        ) from error
    if not isinstance(value, dict) or value.get("kind") != KIND:
        raise ExternalEvaluationError("Common Voice input kind drifted")
    source = value.get("source")
    items = value.get("items")
    if (
        not isinstance(source, dict)
        or source.get("license") != "CC0-1.0"
        or not isinstance(items, list)
        or len(items) != EXPECTED_ROWS
    ):
        raise ExternalEvaluationError("Common Voice source or row count drifted")
    ids: set[str] = set()
    clients: set[str] = set()
    files: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ExternalEvaluationError("Common Voice row must be an object")
        identifier = item.get("id")
        client = item.get("client_id_sha256")
        filename = item.get("filename")
        if (
            not isinstance(identifier, str)
            or identifier in ids
            or not base._is_sha256(client)
            or client in clients
            or not isinstance(filename, str)
            or Path(filename).name != filename
            or filename in files
            or not base._is_sha256(item.get("sha256"))
            or not isinstance(item.get("text"), str)
            or not item["text"]
            or item.get("group") != "commonvoice-unseen-speaker"
            or item.get("down_votes") != 0
        ):
            raise ExternalEvaluationError("Common Voice row schema drifted")
        ids.add(identifier)
        clients.add(client)
        files.add(filename)
    return value


def validate_inputs(arguments: argparse.Namespace) -> dict[str, Any]:
    inputs = load_inputs(arguments.inputs)
    for item in inputs["items"]:
        path = arguments.source_root / item["filename"]
        if (
            path.is_symlink()
            or not path.is_file()
            or base.sha256_file(path) != item["sha256"]
        ):
            raise ExternalEvaluationError(
                f"Common Voice file drifted: {item['filename']}"
            )
    if (
        arguments.target_reference.is_symlink()
        or not arguments.target_reference.is_file()
        or base.sha256_file(arguments.target_reference) != TARGET_REFERENCE_SHA256
    ):
        raise ExternalEvaluationError("target reference identity drifted")
    for label, adapter in (
        ("legacy", arguments.legacy_adapter),
        ("new", arguments.new_adapter),
    ):
        if (
            adapter.is_symlink()
            or not (adapter / "adapter_model.safetensors").is_file()
        ):
            raise ExternalEvaluationError(f"{label} adapter is unavailable")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-034 work directory",
    )
    base._require_new_output(
        arguments.listener_dir,
        REPO_ROOT / "artifacts" / "ms3" / "listening",
        "EXP-034 listener directory",
    )
    return inputs


def listening_index(
    item: Mapping[str, object],
    *,
    hashes: Mapping[str, str],
) -> dict[str, object]:
    variants = [
        ("base", "X-VC base", "10-xvc-base.wav", 1),
        (
            "human87-control69-e12",
            "旧X-VC再学習 / Hadou 1話者 human87 / 1,044 updates",
            "20-xvc-human87-control69-e12.wav",
            2,
        ),
        (
            "jvs3-generated-pairs",
            "新X-VC再学習 / JVS 3話者生成pair / 1,044 updates",
            "30-xvc-jvs3-generated-pairs.wav",
            3,
        ),
    ]
    return {
        "schema_version": 1,
        "run_kind": "EXP-034 Common Voice unseen-speaker X-VC evaluation",
        "status": "completed-listen-now-unselected",
        "source_file": (
            f"Common Voice 25.0 / {item['age']} / {item['gender']} / {item['text']}"
        ),
        "source_output_file": "00-source-reference.wav",
        "target_reference_output_file": "01-target-reference.wav",
        "reference_audio": [
            {
                "kind": "source",
                "label": f"Common Voice / {item['text']}",
                "output_file": "00-source-reference.wav",
                "excluded_from_preference": True,
            },
            {
                "kind": "target",
                "label": "Amitaro runrun / EMOTION100_003",
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
                "profile_id": f"xvc.exp034.{variant_id}.listen-now",
                "family_id": "x-vc",
                "output_sha256": hashes[variant_id],
            }
            for variant_id, display_name, filename, order in variants
        ],
    }


def run(arguments: argparse.Namespace, inputs: Mapping[str, Any]) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise ExternalEvaluationError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise ExternalEvaluationError("EXP-034 requires the explicit gpu0 lease")
    started = time.monotonic()
    arguments.work_dir.mkdir()
    source_output = arguments.work_dir / "sources"
    source_output.mkdir()

    import torch
    from peft import PeftModel

    if not torch.cuda.is_available():
        raise ExternalEvaluationError("CUDA is unavailable")
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
        str(arguments.xvc_config), str(arguments.checkpoint), device, ema_load=False
    )
    target_pair = base.MaterializedPair(
        "EMOTION100_003",
        arguments.target_reference,
        arguments.target_reference,
        TARGET_REFERENCE_SHA256,
        TARGET_REFERENCE_SHA256,
    )
    target_tensor = base._extract_pair_tensors(
        model,
        target_pair,
        process_audio=process_audio,
        config=config,
        torch=torch,
        device=device,
    )
    sources: list[base.RenderSource] = []
    for item in inputs["items"]:
        values = base._model_audio(
            arguments.source_root / item["filename"], process_audio, config
        )
        path = source_output / f"{item['id']}.wav"
        method._write_model_window(path, values)
        sources.append(
            base.RenderSource(
                pair_id=str(item["id"]),
                display_text=f"Common Voice / {item['text']}",
                source_path=path,
            )
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
        ("human87-control69-e12", arguments.legacy_adapter),
        ("jvs3-generated-pairs", arguments.new_adapter),
    ):
        adapted_base = XVC.load_from_checkpoint(
            str(arguments.xvc_config),
            str(arguments.checkpoint),
            device,
            ema_load=False,
        )
        adapted = PeftModel.from_pretrained(
            adapted_base, str(adapter), is_trainable=False
        )
        outputs[label] = render(adapted)
        del adapted, adapted_base
        torch.cuda.empty_cache()

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    listener_rows: list[dict[str, object]] = []
    for index, (item, source) in enumerate(zip(inputs["items"], sources, strict=True)):
        row_dir = staging / f"{index:02d}-{item['id']}"
        row_dir.mkdir()
        shutil.copyfile(source.source_path, row_dir / "00-source-reference.wav")
        shutil.copyfile(arguments.target_reference, row_dir / "01-target-reference.wav")
        hashes = {
            "base": base._write_float_wav(
                row_dir / "10-xvc-base.wav", outputs["base"][index], sample_rate
            ),
            "human87-control69-e12": base._write_float_wav(
                row_dir / "20-xvc-human87-control69-e12.wav",
                outputs["human87-control69-e12"][index],
                sample_rate,
            ),
            "jvs3-generated-pairs": base._write_float_wav(
                row_dir / "30-xvc-jvs3-generated-pairs.wav",
                outputs["jvs3-generated-pairs"][index],
                sample_rate,
            ),
        }
        method._write_json(row_dir / "index.json", listening_index(item, hashes=hashes))
        listener_rows.append({"source_id": item["id"], "hashes": hashes})

    result = {
        "schema_version": 1,
        "kind": "liveconv-exp034-commonvoice-generalization-result/v1",
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": "Does EXP-033 generalize beyond its three JVS donor speakers?",
        "input_manifest_sha256": base.sha256_file(arguments.inputs),
        "speaker_count": len(sources),
        "training_update_count": 0,
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
                "listener_dir": str(arguments.listener_dir),
                "speaker_count": len(sources),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--target-reference", type=Path, required=True)
    parser.add_argument("--legacy-adapter", type=Path, required=True)
    parser.add_argument("--new-adapter", type=Path, required=True)
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
        inputs = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "speaker_count": len(inputs["items"]),
                        "training_updates": 0,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, inputs)
    except (base.ListenNowError, ExternalEvaluationError, OSError, ValueError) as error:
        print(f"exp034-commonvoice-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
