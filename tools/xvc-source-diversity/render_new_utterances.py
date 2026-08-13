#!/usr/bin/env python3
"""Render EXP-039 on same external speakers saying new utterances."""

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
for import_root in (TOOL_ROOT, HUMAN_TOOL_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import listen_now as base  # noqa: E402
import run as method  # noqa: E402
import run_breadth as breadth  # noqa: E402
import screen  # noqa: E402

KIND = "liveconv-exp039-commonvoice-same-speaker-new-utterances/v1"
EXPANDED_KIND = "liveconv-exp055-commonvoice-local-unused/v1"
HADOU_KIND = "liveconv-exp060-hadou-clean-heldout/v1"
EXPECTED_ROWS = 12
EXPECTED_SPEAKERS = 6
EXPANDED_ROWS = 33
EXPANDED_SPEAKERS = 33
HADOU_ROWS = 31
HADOU_SPEAKERS = 1
TARGET_ID = "EMOTION100_003"
TARGET_SHA256 = "76f5a4a9b989ed692a55343a7681623fa4f18e354ca04026f022e3e449195ca2"


class NewUtteranceError(RuntimeError):
    """The bounded EXP-039 evaluation cannot safely continue."""


def candidate_policy(kind: str) -> dict[str, str]:
    if kind == "speaker7":
        return {
            "experiment_id": "EXP-039",
            "variant_id": "cv12-speaker7",
            "display_name": "EXP-038 / CV12 / speaker-conditioned AdaLN only",
            "result_kind": "liveconv-exp039-xvc-new-utterance-result/v1",
            "question": (
                "Does speaker7 generalize to new utterances from heldout speakers?"
            ),
        }
    if kind == "reconstruction20":
        return {
            "experiment_id": "EXP-041",
            "variant_id": "cv12-reconstruction20",
            "display_name": (
                "EXP-040 / CV12 / 80% standard + 20% Amitaro reconstruction"
            ),
            "result_kind": "liveconv-exp041-xvc-reconstruction20-new-utterance/v1",
            "question": (
                "Does reconstruction20 generalize to new utterances from heldout "
                "speakers?"
            ),
        }
    if kind == "aligned-conditions":
        return {
            "experiment_id": "EXP-045",
            "variant_id": "cv12-aligned-conditions",
            "display_name": (
                "EXP-044 / CV12 / alignment-preserving varied conditions"
            ),
            "result_kind": "liveconv-exp045-xvc-aligned-new-utterance/v1",
            "question": (
                "Does aligned-condition augmentation generalize to new utterances "
                "from heldout speakers?"
            ),
        }
    if kind == "authentic-anchor":
        return {
            "experiment_id": "EXP-047",
            "variant_id": "cv11-authentic1",
            "display_name": (
                "EXP-046 / eleven synthetic donors + one authentic source"
            ),
            "result_kind": "liveconv-exp047-xvc-authentic-new-utterance/v1",
            "question": (
                "Does authentic-anchor training generalize to new utterances "
                "from heldout speakers?"
            ),
        }
    if kind == "semantic2x":
        return {
            "experiment_id": "EXP-050",
            "variant_id": "cv12-semantic2x",
            "display_name": "EXP-049 / CV12 / semantic SSL loss 2x",
            "result_kind": "liveconv-exp050-xvc-semantic2x-new-utterance/v1",
            "question": (
                "Does semantic2x preserve content on new utterances from "
                "heldout speakers?"
            ),
        }
    if kind == "source36":
        return {
            "experiment_id": "EXP-053",
            "variant_id": "cv12-source36",
            "display_name": "EXP-052 / CV12 / source-path-only LoRA",
            "result_kind": "liveconv-exp053-xvc-source36-new-utterance/v1",
            "question": (
                "Does source36 preserve content on new utterances from heldout "
                "speakers?"
            ),
        }
    if kind == "target275":
        return {
            "experiment_id": "EXP-056",
            "variant_id": "cv12-target275",
            "display_name": "EXP-055 / 275 target texts / fixed 1,044 updates",
            "result_kind": "liveconv-exp056-xvc-target275-new-utterance/v1",
            "question": (
                "Does target275 preserve content on changed utterances from "
                "heldout speakers?"
            ),
        }
    if kind == "target275-expanded":
        return {
            "experiment_id": "EXP-058",
            "variant_id": "cv12-target275",
            "display_name": "EXP-055 / 275 target texts / fixed 1,044 updates",
            "result_kind": "liveconv-exp058-xvc-target275-expanded-sentences/v1",
            "question": (
                "Does target275 preserve content on all 33 locally unused "
                "Common Voice utterances?"
            ),
        }
    if kind == "content-filtered6x2":
        return {
            "experiment_id": "EXP-061",
            "variant_id": "cv12-content-filtered6x2",
            "display_name": (
                "EXP-060 / best 6 pseudo donors x 2 / fixed 1,044 updates"
            ),
            "result_kind": "liveconv-exp061-xvc-filtered-new-utterance/v1",
            "question": (
                "Does pseudo-source content filtering preserve changed utterances?"
            ),
        }
    if kind == "content-filtered6x2-hadou":
        return {
            "experiment_id": "EXP-063",
            "variant_id": "cv12-content-filtered6x2",
            "display_name": (
                "EXP-060 / best 6 pseudo donors x 2 / fixed 1,044 updates"
            ),
            "result_kind": "liveconv-exp063-xvc-filtered-hadou-result/v1",
            "question": (
                "Does pseudo-source content filtering preserve clean Hadou "
                "heldout sentences?"
            ),
        }
    raise NewUtteranceError(f"unknown candidate kind: {kind}")


def load_evaluation(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NewUtteranceError("evaluation set is not valid JSON") from error
    items = value.get("items") if isinstance(value, dict) else None
    source = value.get("source") if isinstance(value, dict) else None
    kind = value.get("kind") if isinstance(value, dict) else None
    expected_rows = {
        EXPANDED_KIND: EXPANDED_ROWS,
        HADOU_KIND: HADOU_ROWS,
    }.get(kind, EXPECTED_ROWS)
    expected_speakers = {
        EXPANDED_KIND: EXPANDED_SPEAKERS,
        HADOU_KIND: HADOU_SPEAKERS,
    }.get(kind, EXPECTED_SPEAKERS)
    if (
        not isinstance(value, dict)
        or kind not in {KIND, EXPANDED_KIND, HADOU_KIND}
        or not isinstance(source, dict)
        or source.get("license")
        != ("CC-BY-4.0" if kind == HADOU_KIND else "CC0-1.0")
        or not isinstance(items, list)
        or len(items) != expected_rows
    ):
        raise NewUtteranceError("evaluation schema drifted")
    identifiers: set[str] = set()
    filenames: set[str] = set()
    clients: set[str] = set()
    for item in items:
        identifier = item.get("id") if isinstance(item, dict) else None
        filename = item.get("filename") if isinstance(item, dict) else None
        client = item.get("client_id_sha256") if isinstance(item, dict) else None
        transcript = item.get("source_transcript") if isinstance(item, dict) else None
        normalized = (
            screen.normalize_japanese(transcript)
            if isinstance(transcript, str)
            else ""
        )
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in identifiers
            or not isinstance(filename, str)
            or Path(filename).name != filename
            or filename in filenames
            or not base._is_sha256(item.get("sha256"))
            or not base._is_sha256(client)
            or not isinstance(item.get("text"), str)
            or not item["text"]
            or not isinstance(item.get("duration_seconds"), (int, float))
            or float(item["duration_seconds"]) <= 0.0
        ):
            raise NewUtteranceError("evaluation row identity drifted")
        if kind == KIND and (
            len(normalized) < 7
            or item.get("source_normalized_characters") != len(normalized)
            or item.get("window_policy") != "first-2.4s-right-pad-if-short"
            or item.get("group") != "same-speaker-second-utterance"
        ):
            raise NewUtteranceError("changed-utterance row identity drifted")
        if kind == EXPANDED_KIND and (
            item.get("group") != "commonvoice-local-unused"
            or item.get("down_votes") != 0
        ):
            raise NewUtteranceError("expanded-evaluation row identity drifted")
        if kind == HADOU_KIND and (
            item.get("group") != "hadou-clean-heldout"
            or item.get("window_policy")
            != "first-endpoint-complete-2.4s-right-pad-if-short"
            or not isinstance(item.get("full_utterance_audit_cer"), (int, float))
            or float(item["full_utterance_audit_cer"]) > 0.15
        ):
            raise NewUtteranceError("Hadou evaluation row identity drifted")
        identifiers.add(identifier)
        filenames.add(filename)
        clients.add(client)
    if len(clients) != expected_speakers:
        raise NewUtteranceError("evaluation speaker count drifted")
    return value


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], list[tuple[str, Path, str]]]:
    evaluation = load_evaluation(arguments.evaluation_set)
    original = breadth._load_manifest(
        arguments.original_evaluation,
        kind=breadth.EVALUATION_KIND,
        count=breadth.EVALUATION_COUNT,
    )
    donors = breadth._load_manifest(
        arguments.donors, kind=breadth.DONOR_KIND, count=breadth.DONOR_COUNT
    )
    original_clients = {item["client_id_sha256"] for item in original["items"]}
    donor_clients = {item["client_id_sha256"] for item in donors["items"]}
    clients = {item["client_id_sha256"] for item in evaluation["items"]}
    original_files = {item["filename"] for item in original["items"]}
    donor_files = {item["filename"] for item in donors["items"]}
    if evaluation["kind"] == KIND:
        if not clients < original_clients or clients & donor_clients:
            raise NewUtteranceError("evaluation speaker binding drifted")
    elif evaluation["kind"] == EXPANDED_KIND and any(
        item["filename"] in original_files | donor_files
        for item in evaluation["items"]
    ):
        raise NewUtteranceError("expanded evaluation filename binding drifted")
    for item in evaluation["items"]:
        path = arguments.source_root / item["filename"]
        if (
            item["filename"] in original_files
            or path.is_symlink()
            or not path.is_file()
            or base.sha256_file(path) != item["sha256"]
        ):
            raise NewUtteranceError(f"new utterance drifted: {item['filename']}")
    targets = method.target_inventory(arguments.pair_root)
    if {row[0]: row[2] for row in targets}.get(TARGET_ID) != TARGET_SHA256:
        raise NewUtteranceError("target reference identity drifted")
    for label, adapter in (
        ("EXP-035 control", arguments.control_adapter),
        ("method candidate", arguments.candidate_adapter),
    ):
        if adapter.is_symlink() or not (
            adapter / "adapter_model.safetensors"
        ).is_file():
            raise NewUtteranceError(f"{label} adapter is unavailable")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-039 work directory",
    )
    base._require_new_output(
        arguments.listener_dir,
        REPO_ROOT / "artifacts" / "ms3" / "listening",
        "EXP-039 listener directory",
    )
    return evaluation, targets


def listening_index(
    item: Mapping[str, Any],
    *,
    hashes: Mapping[str, str],
    policy: Mapping[str, str],
) -> dict[str, object]:
    source_name = (
        "Hadou ITA"
        if item["group"] == "hadou-clean-heldout"
        else "Common Voice 25.0"
    )
    variants = (
        ("base", "X-VC base", "10-xvc-base.wav", 1),
        (
            "cv12-control69",
            "EXP-035 / CV12 / content attention-FFN control69",
            "20-xvc-cv12-control69.wav",
            2,
        ),
        (
            policy["variant_id"],
            policy["display_name"],
            "30-xvc-candidate.wav",
            3,
        ),
    )
    return {
        "schema_version": 1,
        "run_kind": f"{policy['experiment_id']} X-VC heldout evaluation",
        "status": "completed-listen-now-unselected",
        "source_file": f"{source_name} / {item['duration_seconds']} s / {item['text']}",
        "source_output_file": "00-source-reference.wav",
        "target_reference_output_file": "01-target-reference.wav",
        "reference_audio": [
            {
                "kind": "source",
                "label": (
                    "first 2.4 s / source ASR: "
                    f"{item.get('source_transcript', 'computed in machine screen')}"
                ),
                "output_file": "00-source-reference.wav",
                "excluded_from_preference": True,
            },
            {
                "kind": "target",
                "label": f"Amitaro runrun / {TARGET_ID}",
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
                    f"xvc.{policy['experiment_id'].lower()}.{variant_id}.listen-now"
                ),
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
) -> int:
    policy = candidate_policy(arguments.candidate_kind)
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise NewUtteranceError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise NewUtteranceError("EXP-039 requires the explicit gpu0 lease")
    started = time.monotonic()
    arguments.work_dir.mkdir()
    evaluation_root = arguments.work_dir / "evaluation-sources"
    evaluation_root.mkdir()

    import torch
    from peft import PeftModel

    if not torch.cuda.is_available():
        raise NewUtteranceError("CUDA is unavailable")
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
    by_id = {pair_id: (path, digest) for pair_id, path, digest in target_rows}
    target_path, target_digest = by_id[TARGET_ID]
    target_pair = base.MaterializedPair(
        TARGET_ID, target_path, target_path, target_digest, target_digest
    )
    target_tensor = base._extract_pair_tensors(
        model,
        target_pair,
        process_audio=process_audio,
        config=config,
        torch=torch,
        device=device,
    )
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
            for index, source in enumerate(evaluation_tensors)
        ]

    outputs = {"base": render(model)}
    for label, adapter in (
        ("cv12-control69", arguments.control_adapter),
        (policy["variant_id"], arguments.candidate_adapter),
    ):
        adapted_base = method._load_xvc(arguments, XVC, device)
        adapted = PeftModel.from_pretrained(
            adapted_base, str(adapter), is_trainable=False
        )
        outputs[label] = render(adapted)
        del adapted, adapted_base
        torch.cuda.empty_cache()

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    listener_rows: list[dict[str, object]] = []
    for index, (item, pair) in enumerate(
        zip(evaluation["items"], evaluation_pairs, strict=True)
    ):
        row_root = staging / f"{index:02d}-{item['id']}"
        row_root.mkdir()
        shutil.copyfile(pair.source_path, row_root / "00-source-reference.wav")
        shutil.copyfile(target_pair.target_path, row_root / "01-target-reference.wav")
        hashes = {
            "base": base._write_float_wav(
                row_root / "10-xvc-base.wav", outputs["base"][index], sample_rate
            ),
            "cv12-control69": base._write_float_wav(
                row_root / "20-xvc-cv12-control69.wav",
                outputs["cv12-control69"][index],
                sample_rate,
            ),
            policy["variant_id"]: base._write_float_wav(
                row_root / "30-xvc-candidate.wav",
                outputs[policy["variant_id"]][index],
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
        "training_update_count": 0,
        "evaluation_set_sha256": base.sha256_file(arguments.evaluation_set),
        "evaluation_rows": listener_rows,
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
        "--candidate-kind",
        choices=(
            "speaker7",
            "reconstruction20",
            "aligned-conditions",
            "authentic-anchor",
            "semantic2x",
            "source36",
            "target275",
            "target275-expanded",
            "content-filtered6x2",
            "content-filtered6x2-hadou",
        ),
        default="speaker7",
    )
    parser.add_argument("--evaluation-set", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--control-adapter", type=Path, required=True)
    parser.add_argument("--candidate-adapter", type=Path, required=True)
    parser.add_argument("--xvc-source-root", type=Path, required=True)
    parser.add_argument("--xvc-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--donors",
        type=Path,
        default=REPO_ROOT / "experiments" / "EXP-035-xvc-donor-breadth" / "donors.json",
    )
    parser.add_argument(
        "--original-evaluation",
        type=Path,
        default=(
            REPO_ROOT
            / "experiments"
            / "EXP-035-xvc-donor-breadth"
            / "external-evaluation.json"
        ),
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=(
            REPO_ROOT
            / "artifacts"
            / "exp007"
            / "phase0-inputs-v1"
            / "inventory.json"
        ),
    )
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--listener-dir", type=Path, required=True)
    parser.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    parser.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        candidate_policy(arguments.candidate_kind)
        evaluation, targets = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "evaluation_rows": len(evaluation["items"]),
                        "evaluation_speakers": len(
                            {item["client_id_sha256"] for item in evaluation["items"]}
                        ),
                        "training_updates": 0,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, evaluation, targets)
    except (
        base.ListenNowError,
        breadth.BreadthError,
        method.SourceDiversityError,
        NewUtteranceError,
        OSError,
        ValueError,
    ) as error:
        print(f"exp039-new-utterance-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
