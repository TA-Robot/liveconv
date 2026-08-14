#!/usr/bin/env python3
"""Render the frozen-control69 teacher side of EXP-325/326.

The CPU preparation step owns SRC4VC acquisition, the two-utterance speaker
identity, and the ordered real-Amitaro assignment.  This module deliberately
does not choose any of those things.  It validates the prepared 170-row pool,
runs the ordinary frozen control69 converter once per source, and writes the
complete curriculum consumed by both matched training arms.

``--check`` validates manifests and every source/real-target hash without
importing the model or touching CUDA.  A normal run is the only path that
imports X-VC and creates teacher WAVs.  ``--resume-existing`` is a narrow
crash-recovery path: it accepts only the exact complete 170-WAV inventory and
finishes the manifests without rerendering those WAVs.
"""

from __future__ import annotations

import argparse
import json
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
import run as method  # noqa: E402
from prepare_clean_post_rehearsal import load_json, sha256_file  # noqa: E402
from prepare_exp325_src4vc_two_utterance import (  # noqa: E402
    OUTPUT_KIND as POOL_KIND,
)


EXP238_KIND = "liveconv-exp238-cross-corpus-control69-pseudoparallel-inputs/v1"
OUTPUT_KIND = "liveconv-exp325-exp326-xvc-src4vc-two-utterance-inputs/v1"
RESULT_KIND = "liveconv-exp325-exp326-xvc-src4vc-two-utterance-target-render/v1"
LEARNING_TARGET = "source-aligned-control69-plus-real-target-adversarial"

EXPECTED_ROWS = 170
EXPECTED_SPEAKERS = 85
EXPECTED_UTTERANCES_PER_SPEAKER = 2
BASE_COMPOSITION = {
    "commonvoice-unpaired": 48,
    "jsut-unpaired": 85,
    "jvs-unpaired": 3,
    "hadou-unpaired": 34,
}


class Src4vcRenderError(RuntimeError):
    """The bounded EXP-325 teacher render cannot continue safely."""


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _relative(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise Src4vcRenderError(f"{label} path is malformed")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise Src4vcRenderError(f"{label} path escapes its root")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or Path(value).name != value:
        raise Src4vcRenderError(f"{label} identity is malformed")
    return value


def _validate_audio(path: Path, digest: object, label: str) -> None:
    if path.is_symlink() or not path.is_file() or not _is_sha256(digest):
        raise Src4vcRenderError(f"{label} audio is unavailable")
    if sha256_file(path) != digest:
        raise Src4vcRenderError(f"{label} audio hash drifted")


def _position(row: Mapping[str, Any], label: str) -> int:
    value = row.get("position")
    if value is None:
        value = row.get("curriculum_position")
    if isinstance(value, bool) or not isinstance(value, int):
        raise Src4vcRenderError(f"{label} position is malformed")
    return value


def base_rows(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Validate the EXP-238 rows used solely as the target-order authority."""

    items = value.get("items")
    if (
        value.get("kind") != EXP238_KIND
        or value.get("composition") != BASE_COMPOSITION
        or not isinstance(items, list)
        or len(items) != EXPECTED_ROWS
        or not all(isinstance(item, dict) for item in items)
    ):
        raise Src4vcRenderError("EXP-238 curriculum identity drifted")
    output: list[dict[str, Any]] = []
    ids: set[str] = set()
    teachers: set[str] = set()
    for index, item in enumerate(items):
        identifier = _identifier(item.get("id"), f"EXP-238 row {index}")
        teacher_id = _identifier(item.get("teacher_id"), f"EXP-238 row {index}")
        if identifier in ids or teacher_id in teachers:
            raise Src4vcRenderError("EXP-238 row identities are not unique")
        for key in ("source_file", "target_file", "real_target_file"):
            _relative(item.get(key), f"EXP-238 {key}")
        for key in ("source_sha256", "target_sha256", "real_target_sha256"):
            if not _is_sha256(item.get(key)):
                raise Src4vcRenderError(f"EXP-238 {key} drifted")
        if (
            item.get("source_root") != "source-work"
            or item.get("target_root") != "diverse-work"
            or item.get("real_target_root") != "source-work"
            or item.get("learning_target") != LEARNING_TARGET
        ):
            raise Src4vcRenderError("EXP-238 source/target root contract drifted")
        ids.add(identifier)
        teachers.add(teacher_id)
        output.append(dict(item))
    return output


def source_pool(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the exact 85-speaker x two-utterance prepared pool."""

    items = value.get("items")
    if (
        value.get("kind") != POOL_KIND
        or value.get("composition")
        != {"src4vc-smartphone-unpaired": EXPECTED_ROWS}
        or not isinstance(items, list)
        or len(items) != EXPECTED_ROWS
        or not all(isinstance(item, dict) for item in items)
    ):
        raise Src4vcRenderError("EXP-325 pool identity drifted")

    ids: set[str] = set()
    teachers: set[str] = set()
    sources: set[str] = set()
    speaker_rows: dict[str, list[dict[str, Any]]] = {}
    output: list[dict[str, Any]] = []
    for expected_position, item in enumerate(items):
        label = f"EXP-325 row {expected_position}"
        position = _position(item, label)
        if position != expected_position:
            raise Src4vcRenderError("EXP-325 pool order drifted")
        identifier = _identifier(item.get("id"), label)
        teacher_id = _identifier(item.get("teacher_id"), label)
        if identifier in ids or teacher_id in teachers:
            raise Src4vcRenderError("EXP-325 row identities are not unique")
        source_file = _relative(item.get("source_file"), f"{label} source")
        if source_file in sources:
            raise Src4vcRenderError("EXP-325 source files are not unique")
        for key in ("real_target_file",):
            _relative(item.get(key), f"{label} {key}")
        for key in ("source_sha256", "real_target_sha256"):
            if not _is_sha256(item.get(key)):
                raise Src4vcRenderError(f"{label} {key} drifted")
        speaker = item.get("source_speaker_id")
        if not isinstance(speaker, str) or not speaker:
            raise Src4vcRenderError(f"{label} source speaker identity is malformed")
        utterance = item.get("source_utterance_index")
        if utterance is None:
            utterance = item.get("utterance_index")
        if (
            isinstance(utterance, bool)
            or not isinstance(utterance, int)
            or utterance not in {0, 1}
        ):
            raise Src4vcRenderError(f"{label} utterance index is malformed")
        if (
            item.get("domain") != "src4vc-smartphone-unpaired"
            or item.get("source_root") != "source-work"
            or item.get("real_target_root") != "source-work"
            or item.get("learning_target") != LEARNING_TARGET
            or not _identifier(item.get("target_id"), f"{label} target")
            or not isinstance(item.get("source_text"), str)
            or not item["source_text"]
            or not isinstance(item.get("target_text"), str)
            or item.get("target_text") != item.get("source_text")
            or not isinstance(item.get("real_target_text"), str)
            or not item["real_target_text"]
        ):
            raise Src4vcRenderError(f"{label} pool row contract drifted")
        row = dict(item)
        row["position"] = position
        row["source_utterance_index"] = utterance
        ids.add(identifier)
        teachers.add(teacher_id)
        sources.add(source_file)
        speaker_rows.setdefault(speaker, []).append(row)
        output.append(row)

    if len(speaker_rows) != EXPECTED_SPEAKERS or any(
        len(rows) != EXPECTED_UTTERANCES_PER_SPEAKER for rows in speaker_rows.values()
    ):
        raise Src4vcRenderError("EXP-325 speaker composition drifted")
    if any(
        {int(row["source_utterance_index"]) for row in rows} != {0, 1}
        for rows in speaker_rows.values()
    ):
        raise Src4vcRenderError("EXP-325 utterance pair coverage drifted")
    return {
        "schema_version": 1,
        "kind": POOL_KIND,
        "composition": {"src4vc-smartphone-unpaired": EXPECTED_ROWS},
        "speaker_count": EXPECTED_SPEAKERS,
        "items": output,
    }


def _copy_verified(source: Path, destination: Path, digest: str, label: str) -> None:
    _validate_audio(source, digest, label)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise Src4vcRenderError(f"render output already exists: {destination}")
    shutil.copyfile(source, destination)
    if sha256_file(destination) != digest:
        raise Src4vcRenderError(f"{label} copied hash drifted")


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pool = source_pool(load_json(arguments.pool))
    exp238 = load_json(arguments.exp238_curriculum)
    exp238_rows = base_rows(exp238)
    if arguments.source_work.is_symlink() or not arguments.source_work.is_dir():
        raise Src4vcRenderError("source-work is unavailable")

    for position, row in enumerate(pool["items"]):
        _validate_audio(
            arguments.source_work / str(row["source_file"]),
            row["source_sha256"],
            f"EXP-325 source {position}",
        )
        _validate_audio(
            arguments.source_work / str(row["real_target_file"]),
            row["real_target_sha256"],
            f"EXP-325 real target {position}",
        )
        reference = exp238_rows[position]
        for key in ("target_id", "real_target_root", "real_target_file", "real_target_sha256"):
            if row.get(key) != reference.get(key):
                raise Src4vcRenderError(
                    f"EXP-325 ordered real target assignment drifted: {position}"
                )
        if row.get("real_target_text") != reference.get("real_target_text"):
            raise Src4vcRenderError(
                f"EXP-325 ordered real target text drifted: {position}"
            )

    if arguments.control_adapter.is_symlink() or not (
        arguments.control_adapter / "adapter_model.safetensors"
    ).is_file():
        raise Src4vcRenderError("frozen control69 adapter is unavailable")
    if (
        not arguments.resume_existing
        and (arguments.output_diverse_work.exists() or arguments.output_diverse_work.is_symlink())
    ):
        raise Src4vcRenderError("EXP-325 diverse-work output already exists")
    return pool, exp238


def _pair(identifier: str, path: Path, digest: str) -> base.MaterializedPair:
    return base.MaterializedPair(identifier, path, path, digest, digest)


def _build_curriculum(
    exp238: Mapping[str, Any],
    pool: Mapping[str, Any],
    rendered: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    reference_rows = base_rows(exp238)
    pool_rows = pool["items"]
    if not isinstance(pool_rows, list) or len(pool_rows) != EXPECTED_ROWS:
        raise Src4vcRenderError("EXP-325 pool row count drifted")
    if len(rendered) != EXPECTED_ROWS:
        raise Src4vcRenderError("EXP-325 rendered row count drifted")
    rendered_by_position: dict[int, Mapping[str, Any]] = {}
    for row in rendered:
        position = _position(row, "EXP-325 rendered row")
        if position in rendered_by_position or not 0 <= position < EXPECTED_ROWS:
            raise Src4vcRenderError("EXP-325 rendered order drifted")
        rendered_by_position[position] = row
    if set(rendered_by_position) != set(range(EXPECTED_ROWS)):
        raise Src4vcRenderError("EXP-325 rendered coverage drifted")

    output_rows: list[dict[str, Any]] = []
    for position, source in enumerate(pool_rows):
        reference = reference_rows[position]
        for key in (
            "target_id",
            "real_target_root",
            "real_target_file",
            "real_target_sha256",
        ):
            if source.get(key) != reference.get(key):
                raise Src4vcRenderError(
                    f"EXP-325 ordered real target assignment drifted: {position}"
                )
        if source.get("real_target_text") != reference.get("real_target_text"):
            raise Src4vcRenderError(
                f"EXP-325 ordered real target text drifted: {position}"
            )
        rendered_row = rendered_by_position[position]
        if (
            rendered_row.get("teacher_id") != source.get("teacher_id")
            or rendered_row.get("target_id") != source.get("target_id")
            or not _is_sha256(rendered_row.get("output_sha256"))
        ):
            raise Src4vcRenderError(f"EXP-325 rendered source identity drifted: {position}")
        target_file = _relative(rendered_row.get("target_file"), "EXP-325 target")
        if not target_file.startswith("control-outputs/"):
            raise Src4vcRenderError("EXP-325 target output path drifted")
        item = dict(source)
        item.update(
            {
                "target_file": target_file,
                "target_sha256": rendered_row["output_sha256"],
                "target_root": "diverse-work",
                "target_text": item["source_text"],
                "source_relative_distance": 0.0,
                "output_position": position,
            }
        )
        output_rows.append(item)
    counts = dict(Counter(str(row.get("domain")) for row in output_rows))
    if counts != {"src4vc-smartphone-unpaired": EXPECTED_ROWS}:
        raise Src4vcRenderError("EXP-325 composition drifted")
    speaker_counts = Counter(str(row["source_speaker_id"]) for row in output_rows)
    if len(speaker_counts) != EXPECTED_SPEAKERS or set(speaker_counts.values()) != {2}:
        raise Src4vcRenderError("EXP-325 speaker composition drifted")
    return {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "selection": (
                "exact prepared SRC4VC two-utterance pool: 85 explicit speakers x "
                "utterance indices 0 and 1"
            ),
            "target": (
                "frozen control69 same-content teachers with the exact ordered "
                "EXP-238 real Amitaro discriminator references"
            ),
            "shared_by": "EXP-325 ordinary lane and EXP-326 source-speaker-adversary lane",
            "boundary": "training-only target preparation; no naturalness, keeper, or winner claim",
        },
        "composition": counts,
        "speaker_count": EXPECTED_SPEAKERS,
        "learning_target_counts": dict(
            Counter(str(row.get("learning_target")) for row in output_rows)
        ),
        "items": output_rows,
    }


def _create_output_root(path: Path) -> Path:
    if path.exists() or path.is_symlink():
        raise Src4vcRenderError("EXP-325 diverse-work output already exists")
    path.mkdir(parents=True)
    control_outputs = path / "control-outputs"
    control_outputs.mkdir()
    return control_outputs


def _output_path(
    output_diverse_work: Path, position: int, item: Mapping[str, Any]
) -> Path:
    return (
        output_diverse_work
        / "control-outputs"
        / f"src4vc-{position:03d}-{item['id']}-16k.wav"
    )


def _existing_output_rows(
    output_diverse_work: Path, pool: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Recover only an exact, complete render left before manifest commit."""

    control_root = output_diverse_work / "control-outputs"
    if (
        output_diverse_work.is_symlink()
        or not output_diverse_work.is_dir()
        or control_root.is_symlink()
        or not control_root.is_dir()
    ):
        raise Src4vcRenderError("EXP-325 resumable output root is unavailable")
    if (output_diverse_work / "curriculum.json").exists() or (
        output_diverse_work / "result.json"
    ).exists():
        raise Src4vcRenderError("EXP-325 resume requires an unfinalized render")

    expected_paths = {
        _output_path(output_diverse_work, position, item)
        for position, item in enumerate(pool["items"])
    }
    actual_paths = set(control_root.glob("*.wav"))
    if actual_paths != expected_paths:
        raise Src4vcRenderError("EXP-325 resumable WAV inventory drifted")

    output_rows: list[dict[str, Any]] = []
    for position, item in enumerate(pool["items"]):
        output_path = _output_path(output_diverse_work, position, item)
        teacher_hash = sha256_file(output_path)
        _validate_audio(output_path, teacher_hash, f"EXP-325 teacher {position}")
        output_rows.append(
            {
                "position": position,
                "teacher_id": item["teacher_id"],
                "target_id": item["target_id"],
                "target_file": output_path.relative_to(output_diverse_work).as_posix(),
                "output_sha256": teacher_hash,
            }
        )
    return output_rows


def run(
    arguments: argparse.Namespace,
    pool: Mapping[str, Any],
    exp238: Mapping[str, Any],
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise Src4vcRenderError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise Src4vcRenderError("EXP-325 requires the explicit gpu0 lease")
    started = time.monotonic()
    resumed_existing = bool(arguments.resume_existing)
    if resumed_existing:
        output_rows = _existing_output_rows(arguments.output_diverse_work, pool)
        peak_gpu_bytes = 0
    else:
        import torch
        from peft import PeftModel

        if not torch.cuda.is_available():
            raise Src4vcRenderError("CUDA is unavailable")
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
        output_root = _create_output_root(arguments.output_diverse_work)
        output_rows = []
        for position, item in enumerate(pool["items"]):
            source_path = arguments.source_work / str(item["source_file"])
            source = base._extract_pair_tensors(
                control,
                _pair(
                    str(item["teacher_id"]),
                    source_path,
                    str(item["source_sha256"]),
                ),
                process_audio=process_audio,
                config=config,
                torch=torch,
                device=device,
            )
            target_id = str(item["target_id"])
            if target_id not in target_cache:
                target_path = arguments.source_work / str(item["real_target_file"])
                target_cache[target_id] = base._extract_pair_tensors(
                    control,
                    _pair(target_id, target_path, str(item["real_target_sha256"])),
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
                    seed=base.SEED + position,
                    torch=torch,
                    device=device,
                )
                .detach()
                .cpu()
            )
            output_path = _output_path(arguments.output_diverse_work, position, item)
            teacher_hash = base._write_float_wav(output_path, waveform, sample_rate)
            _validate_audio(output_path, teacher_hash, f"EXP-325 teacher {position}")
            output_rows.append(
                {
                    "position": position,
                    "teacher_id": item["teacher_id"],
                    "target_id": target_id,
                    "target_file": output_path.relative_to(
                        arguments.output_diverse_work
                    ).as_posix(),
                    "output_sha256": teacher_hash,
                }
            )
        peak_gpu_bytes = int(torch.cuda.max_memory_allocated(device))
    curriculum = _build_curriculum(exp238, pool, output_rows)
    curriculum_path = arguments.output_diverse_work / "curriculum.json"
    curriculum_path.write_text(
        json.dumps(curriculum, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = {
        "schema_version": 1,
        "kind": RESULT_KIND,
        "status": "completed-training-only-target-render",
        "rows": output_rows,
        "source_pool_sha256": sha256_file(arguments.pool),
        "exp238_curriculum_sha256": sha256_file(arguments.exp238_curriculum),
        "curriculum_sha256": sha256_file(curriculum_path),
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": peak_gpu_bytes,
        "resumed_existing_outputs": resumed_existing,
        "boundary": "new training-target preparation only; no listener, winner, or promotion claim",
    }
    (arguments.output_diverse_work / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
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
    value.add_argument("--resume-existing", action="store_true")
    value.add_argument("--pool", type=Path, required=True)
    value.add_argument("--source-work", type=Path, required=True)
    value.add_argument("--exp238-curriculum", type=Path, required=True)
    value.add_argument("--output-diverse-work", type=Path, required=True)
    value.add_argument("--control-adapter", type=Path, required=True)
    value.add_argument("--xvc-source-root", type=Path, required=True)
    value.add_argument("--xvc-config", type=Path, required=True)
    value.add_argument("--checkpoint", type=Path, required=True)
    value.add_argument(
        "--inventory",
        type=Path,
        default=REPO_ROOT / "artifacts/exp007/phase0-inputs-v1/inventory.json",
    )
    value.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    value.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        pool, exp238 = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "rows": EXPECTED_ROWS,
                        "speakers": EXPECTED_SPEAKERS,
                        "utterances_per_speaker": EXPECTED_UTTERANCES_PER_SPEAKER,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, pool, exp238)
    except (
        Src4vcRenderError,
        base.ListenNowError,
        method.SourceDiversityError,
        OSError,
        ValueError,
        KeyError,
    ) as error:
        print(f"exp325-src4vc-render-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
