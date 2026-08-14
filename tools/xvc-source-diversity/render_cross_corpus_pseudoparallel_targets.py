#!/usr/bin/env python3
"""Render source-aligned control69 targets for the cross-corpus X-VC pilot."""

from __future__ import annotations

import argparse
import json
import os
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
import run as method  # noqa: E402
from prepare_clean_post_rehearsal import load_json  # noqa: E402
from prepare_cross_corpus_unpaired_curriculum import (  # noqa: E402
    EXPECTED_COMPOSITION,
    EXPECTED_ROWS,
)
from prepare_cross_corpus_unpaired_curriculum import (  # noqa: E402
    OUTPUT_KIND as SOURCE_KIND,
)
from prepare_src4vc_cross_corpus_curriculum import (  # noqa: E402
    EXPECTED_COMPOSITION as SRC4VC_EXPECTED_COMPOSITION,
)
from prepare_src4vc_cross_corpus_curriculum import (  # noqa: E402
    OUTPUT_KIND as SRC4VC_SOURCE_KIND,
)

OUTPUT_KIND = "liveconv-exp238-cross-corpus-control69-pseudoparallel-inputs/v1"
RESULT_KIND = "liveconv-exp238-cross-corpus-control69-target-render/v1"
SRC4VC_OUTPUT_KIND = (
    "liveconv-exp244-src4vc-cross-corpus-control69-pseudoparallel-inputs/v1"
)
SRC4VC_RESULT_KIND = "liveconv-exp244-src4vc-control69-target-render/v1"
LEARNING_TARGET = "source-aligned-control69-plus-real-target-adversarial"


class PseudoparallelTargetError(RuntimeError):
    """The bounded source-aligned target render cannot continue safely."""


def source_policy(kind: object) -> dict[str, Any]:
    if kind == SOURCE_KIND:
        return {
            "source_kind": SOURCE_KIND,
            "composition": EXPECTED_COMPOSITION,
            "output_kind": OUTPUT_KIND,
            "result_kind": RESULT_KIND,
            "experiment_id": "EXP-238",
            "selection": (
                "exact EXP-213 source order and Amitaro target assignment; target "
                "WAV is the frozen control69 conversion of the same source"
            ),
            "question": (
                "Does removing the unrelated-content target contradiction through "
                "source-aligned control69 supervision improve X-VC retraining?"
            ),
        }
    if kind == SRC4VC_SOURCE_KIND:
        return {
            "source_kind": SRC4VC_SOURCE_KIND,
            "composition": SRC4VC_EXPECTED_COMPOSITION,
            "output_kind": SRC4VC_OUTPUT_KIND,
            "result_kind": SRC4VC_RESULT_KIND,
            "experiment_id": "EXP-244",
            "selection": (
                "exact EXP-244 source order and predecessor Amitaro target "
                "assignment; target WAV is the frozen control69 conversion of the "
                "same source"
            ),
            "question": (
                "Does replacing only JSUT85 with 85 distinct SRC4VC smartphone "
                "speakers improve the fixed pseudoparallel X-VC retraining method?"
            ),
        }
    raise PseudoparallelTargetError("cross-corpus source identity drifted")


def pair(identifier: str, path: Path, digest: str) -> base.MaterializedPair:
    return base.MaterializedPair(identifier, path, path, digest, digest)


def source_pool(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Freeze one admitted source order and its real target assignment."""

    items = manifest.get("items")
    policy = source_policy(manifest.get("kind"))
    if (
        manifest.get("composition") != policy["composition"]
        or not isinstance(items, list)
        or len(items) != EXPECTED_ROWS
    ):
        raise PseudoparallelTargetError("cross-corpus source identity drifted")
    rows: list[dict[str, Any]] = []
    ids: set[str] = set()
    domains: Counter[str] = Counter()
    for position, item in enumerate(items):
        if not isinstance(item, dict):
            raise PseudoparallelTargetError("cross-corpus source row drifted")
        identifier = item.get("id")
        teacher_id = item.get("teacher_id")
        source_file = item.get("source_file")
        target_file = item.get("target_file")
        target_id = item.get("target_id")
        if (
            not isinstance(identifier, str)
            or identifier in ids
            or not isinstance(teacher_id, str)
            or not isinstance(source_file, str)
            or Path(source_file).is_absolute()
            or ".." in Path(source_file).parts
            or not base._is_sha256(item.get("source_sha256"))
            or not isinstance(target_id, str)
            or not isinstance(target_file, str)
            or Path(target_file).is_absolute()
            or ".." in Path(target_file).parts
            or not base._is_sha256(item.get("target_sha256"))
            or item.get("source_root") != "diverse-work"
            or item.get("target_root") != "diverse-work"
            or item.get("learning_target")
            != "source-content-plus-unpaired-target-identity"
        ):
            raise PseudoparallelTargetError("cross-corpus source row drifted")
        ids.add(identifier)
        domains[str(item.get("domain"))] += 1
        rows.append(
            {
                "position": position,
                "id": identifier,
                "teacher_id": teacher_id,
                "domain": item.get("domain"),
                "source_manifest_id": item.get("source_manifest_id"),
                "source_text": item.get("source_text"),
                "source_file": source_file,
                "source_sha256": item["source_sha256"],
                "target_id": target_id,
                "target_text": item.get("target_text"),
                "real_target_file": target_file,
                "real_target_sha256": item["target_sha256"],
            }
        )
    if dict(domains) != policy["composition"]:
        raise PseudoparallelTargetError("cross-corpus composition drifted")
    return {
        "schema_version": 1,
        "kind": policy["source_kind"],
        "composition": policy["composition"],
        "items": rows,
    }


def curriculum(
    pool: Mapping[str, Any], output_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Bind every source to its same-content frozen-control69 target WAV."""

    policy = source_policy(pool.get("kind"))
    if pool.get("composition") != policy["composition"]:
        raise PseudoparallelTargetError("pseudoparallel pool identity drifted")
    if len(output_rows) != EXPECTED_ROWS:
        raise PseudoparallelTargetError("pseudoparallel output count drifted")
    output_by_position = {int(row["position"]): row for row in output_rows}
    if set(output_by_position) != set(range(EXPECTED_ROWS)):
        raise PseudoparallelTargetError("pseudoparallel output order drifted")
    items: list[dict[str, Any]] = []
    domains: Counter[str] = Counter()
    for source in pool["items"]:
        position = int(source["position"])
        rendered = output_by_position[position]
        if (
            rendered.get("teacher_id") != source["teacher_id"]
            or rendered.get("target_id") != source["target_id"]
            or not base._is_sha256(rendered.get("output_sha256"))
        ):
            raise PseudoparallelTargetError("pseudoparallel output identity drifted")
        target_file = str(rendered.get("target_file"))
        if (
            Path(target_file).is_absolute()
            or ".." in Path(target_file).parts
            or not target_file.startswith("control-outputs/")
        ):
            raise PseudoparallelTargetError("pseudoparallel target path drifted")
        domain = str(source["domain"])
        domains[domain] += 1
        items.append(
            {
                "id": source["id"],
                "teacher_id": source["teacher_id"],
                "domain": domain,
                "source_manifest_id": source["source_manifest_id"],
                "source_text": source["source_text"],
                "source_root": "source-work",
                "source_file": source["source_file"],
                "source_sha256": source["source_sha256"],
                "source_relative_distance": 0.0,
                "target_id": source["target_id"],
                "target_text": source["source_text"],
                "target_root": "diverse-work",
                "target_file": target_file,
                "target_sha256": rendered["output_sha256"],
                "learning_target": LEARNING_TARGET,
                "real_target_text": source["target_text"],
                "real_target_root": "source-work",
                "real_target_file": source["real_target_file"],
                "real_target_sha256": source["real_target_sha256"],
            }
        )
    if dict(domains) != policy["composition"]:
        raise PseudoparallelTargetError("pseudoparallel composition drifted")
    return {
        "schema_version": 1,
        "kind": policy["output_kind"],
        "selection": policy["selection"],
        "learning_target_counts": {LEARNING_TARGET: EXPECTED_ROWS},
        "composition": policy["composition"],
        "items": items,
    }


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], list[tuple[str, Path, str]]]:
    pool = source_pool(load_json(arguments.source_manifest))
    if arguments.source_root.is_symlink() or not arguments.source_root.is_dir():
        raise PseudoparallelTargetError("cross-corpus source root is unavailable")
    for row in pool["items"]:
        for label, filename, digest in (
            ("source", row["source_file"], row["source_sha256"]),
            ("real target", row["real_target_file"], row["real_target_sha256"]),
        ):
            audio = arguments.source_root / str(filename)
            if (
                audio.is_symlink()
                or not audio.is_file()
                or base.sha256_file(audio) != digest
            ):
                raise PseudoparallelTargetError(
                    f"cross-corpus {label} audio drifted: {row['teacher_id']}"
                )
    targets = method.target_inventory(arguments.pair_root)
    if (
        arguments.control_adapter.is_symlink()
        or not (arguments.control_adapter / "adapter_model.safetensors").is_file()
    ):
        raise PseudoparallelTargetError("control69 adapter is unavailable")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        f"{source_policy(pool['kind'])['experiment_id']} work directory",
    )
    return pool, targets


def run(
    arguments: argparse.Namespace,
    pool: Mapping[str, Any],
    target_rows: Sequence[tuple[str, Path, str]],
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise PseudoparallelTargetError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise PseudoparallelTargetError(
            f"{source_policy(pool['kind'])['experiment_id']} requires the explicit "
            "gpu0 lease"
        )
    started = time.monotonic()
    arguments.work_dir.mkdir()
    output_root = arguments.work_dir / "control-outputs"
    output_root.mkdir()

    import torch
    from peft import PeftModel

    if not torch.cuda.is_available():
        raise PseudoparallelTargetError("CUDA is unavailable")
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
    plain = method._load_xvc(arguments, XVC, device)
    control = PeftModel.from_pretrained(
        plain, str(arguments.control_adapter), is_trainable=False
    )
    target_cache: dict[str, dict[str, Any]] = {}
    output_rows: list[dict[str, Any]] = []
    for index, item in enumerate(pool["items"]):
        teacher_id = str(item["teacher_id"])
        target_id = str(item["target_id"])
        source_path = arguments.source_root / str(item["source_file"])
        source = base._extract_pair_tensors(
            control,
            pair(teacher_id, source_path, str(item["source_sha256"])),
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        if target_id not in target_cache:
            target_path = arguments.source_root / str(item["real_target_file"])
            target_digest = str(item["real_target_sha256"])
            target_cache[target_id] = base._extract_pair_tensors(
                control,
                pair(target_id, target_path, target_digest),
                process_audio=process_audio,
                config=config,
                torch=torch,
                device=device,
            )
        waveform = (
            base._inference(
                control,
                source,
                target_cache[target_id],
                seed=base.SEED + index,
                torch=torch,
                device=device,
            )
            .detach()
            .cpu()
        )
        output_path = output_root / f"{index:03d}-{teacher_id}-16k.wav"
        output_rows.append(
            {
                "position": index,
                "teacher_id": teacher_id,
                "target_id": target_id,
                "target_file": output_path.relative_to(arguments.work_dir).as_posix(),
                "output_sha256": base._write_float_wav(
                    output_path, waveform, sample_rate
                ),
            }
        )

    policy = source_policy(pool["kind"])
    manifest = curriculum(pool, output_rows)
    method._write_json(arguments.work_dir / "pool.json", pool)
    method._write_json(arguments.work_dir / "curriculum.json", manifest)
    result = {
        "schema_version": 1,
        "kind": policy["result_kind"],
        "status": "completed-training-only-target-render",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": policy["question"],
        "source_manifest_sha256": base.sha256_file(arguments.source_manifest),
        "control_adapter": str(arguments.control_adapter),
        "rows": output_rows,
        "composition": policy["composition"],
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "boundary": (
            "training-target preparation only; not evaluation, naturalness, "
            "target identity, a keeper, or promotion"
        ),
    }
    method._write_json(arguments.work_dir / "result.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "rows": len(output_rows),
                "elapsed_seconds": result["elapsed_seconds"],
                "peak_gpu_bytes": result["peak_gpu_bytes"],
            },
            sort_keys=True,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--source-manifest", type=Path, required=True)
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
    value.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    value.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        pool, targets = validate_inputs(arguments)
        if arguments.check:
            print(json.dumps({"status": "checked-no-cuda", "rows": EXPECTED_ROWS}))
            return 0
        return run(arguments, pool, targets)
    except (
        PseudoparallelTargetError,
        base.ListenNowError,
        method.SourceDiversityError,
        OSError,
        ValueError,
    ) as error:
        print(f"pseudoparallel-target-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
