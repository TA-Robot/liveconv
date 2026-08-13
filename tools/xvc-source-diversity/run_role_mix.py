#!/usr/bin/env python3
"""Train EXP-036 with X-VC's official standard/reconstruction/reversed mix."""

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
import listen_now_horizon as horizon  # noqa: E402
import render_commonvoice as external  # noqa: E402
import run as method  # noqa: E402
import run_breadth as breadth  # noqa: E402

PREDECESSOR_COMMIT = "01b2b247be79a534f567701caf4777dfa5476c10"
PREDECESSOR_INVENTORY_SHA256 = (
    "e909e465ae5b49fb2be67dded797acf13895acd7f2ddd77c570cea8acdba9cd0"
)
ROLE_COUNTS = {"standard": 418, "reconstruction": 208, "reversed": 418}
ROLE_CYCLE = ("standard", "reversed", "reconstruction", "standard", "reversed")
RECONSTRUCTION_COUNTS = {"standard": 835, "reconstruction": 209}
REAL_RECONSTRUCTION_COUNTS = {
    "standard": 835,
    "real-donor-reconstruction": 209,
}
RECONSTRUCTION_CYCLE = (
    "standard",
    "standard",
    "reconstruction",
    "standard",
    "standard",
)
SOURCE_CONDITION_CYCLE = (
    {"kind": "clean"},
    {"kind": "noise", "snr_db": 20.0},
    {"kind": "clean"},
    {"kind": "tempo", "factor": 1.2},
    {"kind": "clean"},
    {"kind": "pitch", "factor": 1.189207115},
    {"kind": "clean"},
    {"kind": "leading-silence", "milliseconds": 300},
    {"kind": "clean"},
    {"kind": "clean"},
)
SOURCE_CONDITION_COUNTS = {
    "clean": 626,
    "noise": 105,
    "tempo": 105,
    "pitch": 104,
    "leading-silence": 104,
}
STANDARD_LOSS_WEIGHTS = {
    "mse_loss": 1000.0,
    "vq_loss": 1.0,
    "mel_loss": 15.0,
    "sim_mse_loss": 10.0,
}
TOTAL_UPDATES = breadth.TOTAL_UPDATES
SPEAKER7_TARGETS = tuple(
    [
        f"acoustic_converter.transformer_blocks.{index}.attn_norm_x.linear"
        for index in range(6)
    ]
    + ["acoustic_converter.norm_out.linear"]
)
SPEAKER7_TRAINABLE_PARAMETERS = 166_400
SOURCE36_TRAINABLE_PARAMETERS = 442_368
OUTPUT2_TARGETS = (
    "acoustic_converter.norm_out.linear",
    "acoustic_converter.proj_out",
)
OUTPUT2_TRAINABLE_PARAMETERS = 22_016


class RoleMixError(RuntimeError):
    """The bounded EXP-036 role-mix pilot cannot safely continue."""


def role_schedule(count: int = TOTAL_UPDATES) -> list[str]:
    """Return an interleaved exact 40/20/40 schedule for 1,044 updates."""
    if count != TOTAL_UPDATES:
        raise RoleMixError("role schedule update count drifted")
    repeats, remainder = divmod(count, len(ROLE_CYCLE))
    tail = ("standard", "reversed", "standard", "reversed")
    if remainder != len(tail):
        raise RoleMixError("role schedule tail drifted")
    schedule = list(ROLE_CYCLE) * repeats + list(tail)
    if Counter(schedule) != ROLE_COUNTS:
        raise RoleMixError("role schedule proportions drifted")
    return schedule


def training_modes(policy: str) -> list[str]:
    if policy == "role-mix":
        return role_schedule()
    if policy == "all-standard":
        return ["standard"] * TOTAL_UPDATES
    if policy in {
        "source-augmentation",
        "paired-augmentation",
        "authentic-anchor",
        "semantic2x",
    }:
        return ["standard"] * TOTAL_UPDATES
    if policy == "standard-reconstruction":
        repeats, remainder = divmod(TOTAL_UPDATES, len(RECONSTRUCTION_CYCLE))
        tail = ("standard", "standard", "reconstruction", "standard")
        if remainder != len(tail):
            raise RoleMixError("reconstruction schedule tail drifted")
        schedule = list(RECONSTRUCTION_CYCLE) * repeats + list(tail)
        if Counter(schedule) != RECONSTRUCTION_COUNTS:
            raise RoleMixError("reconstruction schedule proportions drifted")
        return schedule
    if policy == "real-reconstruction20":
        repeats, remainder = divmod(TOTAL_UPDATES, len(RECONSTRUCTION_CYCLE))
        tail = ("standard", "standard", "real-donor-reconstruction", "standard")
        if remainder != len(tail):
            raise RoleMixError("real-reconstruction schedule tail drifted")
        cycle = (
            "standard",
            "standard",
            "real-donor-reconstruction",
            "standard",
            "standard",
        )
        schedule = list(cycle) * repeats + list(tail)
        if Counter(schedule) != REAL_RECONSTRUCTION_COUNTS:
            raise RoleMixError("real-reconstruction schedule proportions drifted")
        return schedule
    raise RoleMixError(f"unknown training policy: {policy}")


def source_condition_schedule(policy: str) -> list[dict[str, object]]:
    if policy not in {"source-augmentation", "paired-augmentation"}:
        return [{"kind": "clean"} for _ in range(TOTAL_UPDATES)]
    repeats, remainder = divmod(TOTAL_UPDATES, len(SOURCE_CONDITION_CYCLE))
    schedule = [dict(item) for item in SOURCE_CONDITION_CYCLE] * repeats
    schedule.extend(dict(item) for item in SOURCE_CONDITION_CYCLE[:remainder])
    observed = Counter(item["kind"] for item in schedule)
    if len(schedule) != TOTAL_UPDATES or observed != SOURCE_CONDITION_COUNTS:
        raise RoleMixError("source-condition schedule proportions drifted")
    return schedule


def target_condition_kind(policy: str, source_kind: str) -> str:
    if policy != "paired-augmentation" or source_kind in {"clean", "noise"}:
        return "clean"
    if source_kind not in {"tempo", "pitch", "leading-silence"}:
        raise RoleMixError(f"unknown source condition: {source_kind}")
    return source_kind


def uses_authentic_anchor(policy: str, donor_index: int) -> bool:
    return policy == "authentic-anchor" and donor_index == 0


def training_loss_weights(policy: str) -> dict[str, float]:
    weights = dict(STANDARD_LOSS_WEIGHTS)
    if policy == "semantic2x":
        weights["mse_loss"] = 2000.0
    return weights


def authentic_pairs(
    pair_root: Path, targets: Sequence[tuple[str, Path, str]]
) -> list[base.MaterializedPair]:
    pairs: list[base.MaterializedPair] = []
    for pair_id, target_path, target_digest in targets:
        source_path = pair_root / pair_id / "source-48k.wav"
        if source_path.is_symlink() or not source_path.is_file():
            raise RoleMixError(f"authentic source is unavailable: {pair_id}")
        pairs.append(
            base.MaterializedPair(
                pair_id,
                source_path,
                target_path,
                base.sha256_file(source_path),
                target_digest,
            )
        )
    if len(pairs) != method.PAIR_COUNT:
        raise RoleMixError("authentic source count drifted")
    return pairs


def training_scope(inventory: Path, name: str) -> dict[str, object]:
    if name == "control69":
        return horizon.lora_scope(inventory, name)
    if name == "source36":
        expanded = horizon.lora_scope(inventory, "expanded79")
        observed = tuple(
            item
            for item in expanded["target_modules"]
            if (
                (
                    ".attn." in item
                    and item.endswith((".to_q", ".to_k", ".to_v", ".to_out.0"))
                )
                or ".ff_x." in item
            )
        )
        if len(observed) != 36:
            raise RoleMixError("source36 target topology drifted")
        return {
            "target_modules": list(observed),
            "trainable_parameter_count": SOURCE36_TRAINABLE_PARAMETERS,
        }
    if name == "output2":
        expanded = horizon.lora_scope(inventory, "expanded79")
        observed = tuple(
            item for item in expanded["target_modules"] if item in OUTPUT2_TARGETS
        )
        if observed != OUTPUT2_TARGETS:
            raise RoleMixError("output2 target topology drifted")
        return {
            "target_modules": list(observed),
            "trainable_parameter_count": OUTPUT2_TRAINABLE_PARAMETERS,
        }
    if name != "speaker7":
        raise RoleMixError(f"unknown LoRA scope: {name}")
    expanded = horizon.lora_scope(inventory, "expanded79")
    observed = tuple(
        item for item in expanded["target_modules"] if item in SPEAKER7_TARGETS
    )
    if observed != SPEAKER7_TARGETS:
        raise RoleMixError("speaker7 target topology drifted")
    return {
        "target_modules": list(observed),
        "trainable_parameter_count": SPEAKER7_TRAINABLE_PARAMETERS,
    }


def experiment_policy(arguments: argparse.Namespace) -> dict[str, Any]:
    if (
        arguments.training_policy == "real-reconstruction20"
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-072",
            "slug": "exp072",
            "candidate_id": "cv12-real-reconstruction20",
            "candidate_name": (
                "EXP-072 / 80% Amitaro conversion + 20% real donor rehearsal"
            ),
            "run_kind": "EXP-072 X-VC real-speech rehearsal evaluation",
            "result_kind": "liveconv-exp072-xvc-real-rehearsal-result/v1",
            "question": (
                "Does real Common Voice self-reconstruction rehearsal reduce "
                "content forgetting while retaining target-voice conversion?"
            ),
            "independent_variable": (
                "training data role: all 1,044 generated-source-to-Amitaro updates "
                "versus 835 such updates plus 209 self-reconstructions of the "
                "twelve real Common Voice donor windows; total updates, scope, "
                "loss, LR, seed, condition, and evaluation stay fixed"
            ),
        }
    if (
        arguments.training_policy == "all-standard"
        and arguments.lora_scope == "output2"
    ):
        return {
            "experiment_id": "EXP-068",
            "slug": "exp068",
            "candidate_id": "cv12-output2",
            "candidate_name": (
                "EXP-068 / CV12 / decoder-interface output2 LoRA / 1,044 updates"
            ),
            "run_kind": "EXP-068 X-VC decoder-interface scope evaluation",
            "result_kind": "liveconv-exp068-xvc-decoder-interface-result/v1",
            "question": (
                "Does adapting only X-VC's final speaker-conditioned normalization "
                "and decoder-facing projection produce a viable hearing candidate?"
            ),
            "independent_variable": (
                "LoRA target: control69 joint attention/FFN linears versus only "
                "the final norm_out.linear and decoder-facing proj_out; data, loss, "
                "LR, roles, seed, target, condition, and updates stay fixed"
            ),
        }
    if arguments.training_policy == "role-mix" and arguments.lora_scope == "control69":
        return {
            "experiment_id": "EXP-036",
            "slug": "exp036",
            "candidate_id": "cv12-role-mix",
            "candidate_name": (
                "EXP-036 / CV12 / standard-reconstruction-reversed / 1,044 updates"
            ),
            "run_kind": "EXP-036 X-VC role-mix external evaluation",
            "result_kind": "liveconv-exp036-xvc-role-mix-result/v1",
            "question": "Does official role mixing beat all-standard fine-tuning?",
            "independent_variable": (
                "training role assignment: all-standard versus 418 standard, "
                "208 reconstruction, and 418 reversed updates"
            ),
        }
    if (
        arguments.training_policy == "all-standard"
        and arguments.lora_scope == "speaker7"
    ):
        return {
            "experiment_id": "EXP-038",
            "slug": "exp038",
            "candidate_id": "cv12-speaker7",
            "candidate_name": (
                "EXP-038 / CV12 / speaker-conditioning-only LoRA / 1,044 updates"
            ),
            "run_kind": "EXP-038 X-VC speaker7 external evaluation",
            "result_kind": "liveconv-exp038-xvc-speaker7-result/v1",
            "question": (
                "Does speaker-conditioning-only LoRA preserve external content "
                "better than control69?"
            ),
            "independent_variable": (
                "LoRA scope: 69 attention/FFN linears versus seven speaker-conditioned "
                "AdaLN linears"
            ),
        }
    if (
        arguments.training_policy == "standard-reconstruction"
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-040",
            "slug": "exp040",
            "candidate_id": "cv12-reconstruction20",
            "candidate_name": (
                "EXP-040 / CV12 / 80% standard + 20% Amitaro reconstruction"
            ),
            "run_kind": "EXP-040 X-VC target-preserving reconstruction evaluation",
            "result_kind": "liveconv-exp040-xvc-reconstruction20-result/v1",
            "question": (
                "Does target-preserving reconstruction regularize control69 "
                "without reversed donor-target dilution?"
            ),
            "independent_variable": (
                "training roles: all-standard versus 835 standard and 209 "
                "same-target reconstruction updates, with zero reversed updates"
            ),
        }
    if (
        arguments.training_policy == "source-augmentation"
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-043",
            "slug": "exp043",
            "candidate_id": "cv12-source-conditions",
            "candidate_name": (
                "EXP-043 / CV12 / 60% clean + 40% source-condition augmentation"
            ),
            "run_kind": "EXP-043 X-VC source-condition augmentation evaluation",
            "result_kind": "liveconv-exp043-xvc-source-condition-result/v1",
            "question": (
                "Does source-side audio-condition augmentation improve X-VC "
                "robustness without corrupting clean unseen speech?"
            ),
            "independent_variable": (
                "source acoustics: all-clean versus deterministic 626 clean, "
                "105 noise20, 105 tempo1.2, 104 pitch+3, and 104 leading300ms "
                "updates; target audio and all optimizer settings stay fixed"
            ),
        }
    if (
        arguments.training_policy == "paired-augmentation"
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-044",
            "slug": "exp044",
            "candidate_id": "cv12-aligned-conditions",
            "candidate_name": (
                "EXP-044 / CV12 / alignment-preserving source conditions"
            ),
            "run_kind": "EXP-044 X-VC aligned-condition evaluation",
            "result_kind": "liveconv-exp044-xvc-aligned-condition-result/v1",
            "question": (
                "Does alignment-preserving paired augmentation improve X-VC "
                "robustness without corrupting clean unseen speech?"
            ),
            "independent_variable": (
                "supervision alignment: tempo, pitch, and leading silence are "
                "applied to both pseudo-source and clean target while noise is "
                "source-only; the 626/418 schedule and optimizer controls match "
                "the rejected source-only augmentation"
            ),
        }
    if (
        arguments.training_policy == "authentic-anchor"
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-046",
            "slug": "exp046",
            "candidate_id": "cv11-authentic1",
            "candidate_name": (
                "EXP-046 / eleven synthetic donors + one authentic source"
            ),
            "run_kind": "EXP-046 X-VC authentic-anchor evaluation",
            "result_kind": "liveconv-exp046-xvc-authentic-anchor-result/v1",
            "question": (
                "Does one authentic aligned source per target anchor synthetic "
                "donor diversity without losing external generalization?"
            ),
            "independent_variable": (
                "source construction: twelve synthetic donor exposures versus "
                "eleven synthetic exposures plus one authentic Hadou source per "
                "Amitaro target; target exposure and optimizer controls stay fixed"
            ),
        }
    if (
        arguments.training_policy == "semantic2x"
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-049",
            "slug": "exp049",
            "candidate_id": "cv12-semantic2x",
            "candidate_name": "EXP-049 / CV12 / semantic SSL loss 2x",
            "run_kind": "EXP-049 X-VC semantic-loss evaluation",
            "result_kind": "liveconv-exp049-xvc-semantic2x-result/v1",
            "question": (
                "Does doubling semantic SSL reconstruction weight preserve "
                "external content without weakening waveform or speaker losses?"
            ),
            "independent_variable": (
                "loss weight: mse_loss 1000 to 2000; mel 15, speaker 10, VQ 1, "
                "data, target, roles, scope, LR, seed, and updates stay fixed"
            ),
        }
    if (
        arguments.training_policy == "all-standard"
        and arguments.lora_scope == "source36"
    ):
        return {
            "experiment_id": "EXP-052",
            "slug": "exp052",
            "candidate_id": "cv12-source36",
            "candidate_name": "EXP-052 / CV12 / source-path-only LoRA",
            "run_kind": "EXP-052 X-VC source-path scope evaluation",
            "result_kind": "liveconv-exp052-xvc-source36-result/v1",
            "question": (
                "Does excluding input-invariant zero-condition modules improve "
                "content generalization while retaining source-path adaptation?"
            ),
            "independent_variable": (
                "LoRA target: control69 joint source/frame attention+FFN versus "
                "36 source x-branch attention+FFN linears; data, loss, LR, roles, "
                "seed, target, condition, and updates stay fixed"
            ),
        }
    raise RoleMixError("unsupported training-policy and LoRA-scope combination")


def assigned_tensors(
    target: Mapping[str, Any],
    generated: Mapping[str, Any],
    role: str,
    *,
    real_donor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assign waveform and feature roles using the upstream role semantics."""
    if role == "real-donor-reconstruction":
        if real_donor is None:
            raise RoleMixError("real donor tensors are required for rehearsal")
        return {
            "source_wav": real_donor["source_wav"],
            "semantic_tokens": real_donor["semantic_tokens"],
            "target_wav": real_donor["target_wav"],
            "ssl_feat": real_donor["ssl_feat"],
        }
    if role == "standard":
        source, reference = generated, target
    elif role == "reconstruction":
        source = reference = target
    elif role == "reversed":
        source, reference = target, generated
    else:
        raise RoleMixError(f"unknown role assignment: {role}")
    return {
        "source_wav": source["source_wav"],
        "semantic_tokens": source["semantic_tokens"],
        "target_wav": reference["target_wav"],
        "ssl_feat": reference["ssl_feat"],
    }


def _load_predecessor(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RoleMixError("EXP-035 result is not valid JSON") from error
    expected = {
        "kind": "liveconv-exp035-xvc-donor-breadth-result/v1",
        "status": "completed-listen-now-unselected",
        "git_commit": PREDECESSOR_COMMIT,
        "generated_pair_count": TOTAL_UPDATES,
        "generated_inventory_sha256": PREDECESSOR_INVENTORY_SHA256,
    }
    if not isinstance(value, dict) or any(
        value.get(key) != item for key, item in expected.items()
    ):
        raise RoleMixError("EXP-035 result identity drifted")
    return value


def _pseudo_path(root: Path, target_id: str, donor_id: str) -> Path:
    return root / target_id / f"source-{donor_id}-16k.wav"


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, Path, str]], dict[str, Any]]:
    donors = breadth._load_manifest(
        arguments.donors, kind=breadth.DONOR_KIND, count=breadth.DONOR_COUNT
    )
    evaluation = breadth._load_manifest(
        arguments.evaluation_set,
        kind=breadth.EVALUATION_KIND,
        count=breadth.EVALUATION_COUNT,
    )
    donor_clients = {item["client_id_sha256"] for item in donors["items"]}
    evaluation_clients = {item["client_id_sha256"] for item in evaluation["items"]}
    if donor_clients & evaluation_clients:
        raise RoleMixError("training donors overlap external evaluation speakers")
    for item in [*donors["items"], *evaluation["items"]]:
        path = arguments.source_root / item["filename"]
        if (
            path.is_symlink()
            or not path.is_file()
            or base.sha256_file(path) != item["sha256"]
        ):
            raise RoleMixError(f"Common Voice input drifted: {item['filename']}")

    targets = method.target_inventory(arguments.pair_root)
    breadth.training_schedule(
        [row[0] for row in targets], [item["id"] for item in donors["items"]]
    )
    predecessor = _load_predecessor(arguments.predecessor_result)
    if (
        predecessor.get("donor_manifest_sha256") != base.sha256_file(arguments.donors)
        or predecessor.get("evaluation_set_sha256")
        != base.sha256_file(arguments.evaluation_set)
    ):
        raise RoleMixError("EXP-035 manifest binding drifted")
    if (
        arguments.predecessor_pseudo_root.is_symlink()
        or not arguments.predecessor_pseudo_root.is_dir()
    ):
        raise RoleMixError("EXP-035 pseudo-source root is unavailable")
    inventory: list[dict[str, str]] = []
    for target_id, _target, _digest in targets:
        for donor in donors["items"]:
            path = _pseudo_path(
                arguments.predecessor_pseudo_root, target_id, donor["id"]
            )
            if path.is_symlink() or not path.is_file():
                raise RoleMixError(f"EXP-035 pseudo source is unavailable: {path.name}")
            inventory.append(
                {
                    "target_id": target_id,
                    "donor_id": donor["id"],
                    "source_sha256": base.sha256_file(path),
                }
            )
    if (
        len(inventory) != TOTAL_UPDATES
        or method._canonical_sha256(inventory) != PREDECESSOR_INVENTORY_SHA256
    ):
        raise RoleMixError("EXP-035 pseudo-source inventory drifted")
    if arguments.control_adapter.is_symlink() or not (
        arguments.control_adapter / "adapter_model.safetensors"
    ).is_file():
        raise RoleMixError("EXP-035 all-standard adapter is unavailable")
    experiment_policy(arguments)
    training_modes(arguments.training_policy)
    training_scope(arguments.inventory, arguments.lora_scope)
    if arguments.training_policy == "authentic-anchor":
        authentic_pairs(arguments.pair_root, targets)
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-036 work directory",
    )
    base._require_new_output(
        arguments.listener_dir,
        REPO_ROOT / "artifacts" / "ms3" / "listening",
        "EXP-036 listener directory",
    )
    return donors, evaluation, targets, predecessor


def listening_index(
    item: Mapping[str, Any],
    *,
    hashes: Mapping[str, str],
    policy: Mapping[str, Any],
) -> dict[str, object]:
    variants = (
        ("base", "X-VC base", "10-xvc-base.wav", 1),
        (
            "cv12-standard",
            "EXP-035 / CV12 / all-standard / 1,044 updates",
            "20-xvc-cv12-standard.wav",
            2,
        ),
        (
            policy["candidate_id"],
            policy["candidate_name"],
            "30-xvc-candidate.wav",
            3,
        ),
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
                "profile_id": f"xvc.{policy['slug']}.{variant_id}.listen-now",
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
    target_rows: list[tuple[str, Path, str]],
    predecessor: Mapping[str, Any],
) -> int:
    policy = experiment_policy(arguments)
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise RoleMixError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise RoleMixError(
            f"{policy['experiment_id']} requires the explicit gpu0 lease"
        )
    started = time.monotonic()
    arguments.work_dir.mkdir()
    donor_root = arguments.work_dir / "donor-references"
    evaluation_root = arguments.work_dir / "evaluation-sources"
    regenerated_root = arguments.work_dir / "verified-generated-source-pairs"
    for path in (donor_root, evaluation_root, regenerated_root):
        path.mkdir()

    import torch
    from peft import LoraConfig, PeftModel, get_peft_model

    if not torch.cuda.is_available():
        raise RoleMixError("CUDA is unavailable")
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
    observed_loss_weights = {
        key: float(value)
        for key, value in model.loss_config["loss_weights"].items()
    }
    if observed_loss_weights != STANDARD_LOSS_WEIGHTS:
        raise RoleMixError("upstream X-VC loss weights drifted")
    loss_weights = training_loss_weights(arguments.training_policy)
    model.loss_config["loss_weights"] = dict(loss_weights)

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
    anchor_pairs = (
        authentic_pairs(arguments.pair_root, target_rows)
        if arguments.training_policy == "authentic-anchor"
        else []
    )
    anchor_tensors = [
        base._extract_pair_tensors(
            model,
            pair,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        for pair in anchor_pairs
    ]
    donor_pairs: list[base.MaterializedPair] = []
    donor_tensors: list[dict[str, Any]] = []
    for item in donors["items"]:
        pair, tensors = breadth._reference_tensor(
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

    modes = training_modes(arguments.training_policy)
    source_conditions = source_condition_schedule(arguments.training_policy)
    training_rows: list[dict[str, Any]] = []
    generated_inventory: list[dict[str, str]] = []
    training_source_inventory: list[dict[str, object]] = []
    training_target_inventory: list[dict[str, object]] = []
    aligned_target_cache: dict[tuple[str, str], tuple[dict[str, Any], str]] = {}
    row_index = 0
    for target_index, (target_pair, target_tensor) in enumerate(
        zip(target_pairs, target_tensors, strict=True)
    ):
        pair_root = regenerated_root / target_pair.pair_id
        pair_root.mkdir()
        for donor_index, (donor_pair, donor_tensor) in enumerate(
            zip(donor_pairs, donor_tensors, strict=True)
        ):
            output = base._inference(
                model,
                target_tensor,
                donor_tensor,
                seed=base.SEED + target_index * breadth.DONOR_COUNT + donor_index,
                torch=torch,
                device=device,
            )
            output_path = pair_root / f"source-{donor_pair.pair_id}-16k.wav"
            digest = base._write_float_wav(output_path, output, sample_rate)
            predecessor_path = _pseudo_path(
                arguments.predecessor_pseudo_root,
                target_pair.pair_id,
                donor_pair.pair_id,
            )
            if digest != base.sha256_file(predecessor_path):
                raise RoleMixError("generated source no longer reproduces EXP-035")
            condition = source_conditions[row_index]
            condition_kind = str(condition["kind"])
            training_source = output
            training_source_path = output_path
            authentic_row = uses_authentic_anchor(
                arguments.training_policy, donor_index
            )
            authentic_tensor = (
                anchor_tensors[target_index] if authentic_row else None
            )
            if authentic_row:
                training_source = authentic_tensor["source_wav"].to(
                    device=device, dtype=torch.float32
                )
                training_source_path = anchor_pairs[target_index].source_path
            if condition_kind != "clean":
                training_source_path = (
                    pair_root
                    / f"train-{donor_pair.pair_id}-{condition_kind}-16k.wav"
                )
                method.transform_window(
                    output_path,
                    condition,
                    destination=training_source_path,
                    process_audio=process_audio,
                    config=config,
                    seed=base.SEED + row_index,
                )
                values = method._model_window(
                    training_source_path,
                    process_audio=process_audio,
                    config=config,
                )
                training_source = (
                    torch.from_numpy(values)
                    .reshape(1, 1, -1)
                    .to(device=device, dtype=torch.float32)
                )
            target_condition = target_condition_kind(
                arguments.training_policy, condition_kind
            )
            training_target = target_tensor
            target_source_digest = target_pair.target_sha256
            if target_condition != "clean":
                cache_key = (target_pair.pair_id, target_condition)
                cached = aligned_target_cache.get(cache_key)
                if cached is None:
                    clean_target_path = pair_root / "target-clean-window-16k.wav"
                    if not clean_target_path.exists():
                        base._write_float_wav(
                            clean_target_path,
                            target_tensor["target_wav"],
                            sample_rate,
                        )
                    aligned_target_path = (
                        pair_root / f"target-{target_condition}-16k.wav"
                    )
                    method.transform_window(
                        clean_target_path,
                        condition,
                        destination=aligned_target_path,
                        process_audio=process_audio,
                        config=config,
                        seed=base.SEED + row_index,
                    )
                    target_source_digest = base.sha256_file(aligned_target_path)
                    aligned_pair = base.MaterializedPair(
                        f"{target_pair.pair_id}-{target_condition}",
                        aligned_target_path,
                        aligned_target_path,
                        target_source_digest,
                        target_source_digest,
                    )
                    training_target = base._extract_pair_tensors(
                        model,
                        aligned_pair,
                        process_audio=process_audio,
                        config=config,
                        torch=torch,
                        device=device,
                    )
                    aligned_target_cache[cache_key] = (
                        training_target,
                        target_source_digest,
                    )
                else:
                    training_target, target_source_digest = cached
            if authentic_tensor is None:
                with torch.inference_mode():
                    features = model.semantic_encoder.extract_and_encode(
                        training_source.squeeze(1)
                    )
                tokens = features.get("speech_tokens")
                hidden = features.get("whisper_hidden_states_50hz")
            else:
                tokens = authentic_tensor["semantic_tokens"].to(device=device)
                hidden = target_tensor["ssl_feat"].to(device=device)
            if (
                tokens is None
                or hidden is None
                or tokens[:, : base.SEMANTIC_FRAMES].shape
                != (1, base.SEMANTIC_FRAMES)
                or hidden[..., : base.TARGET_HIDDEN_FRAMES].shape[-1]
                != base.TARGET_HIDDEN_FRAMES
            ):
                raise RoleMixError("generated semantic feature shape drifted")
            generated = {
                "source_wav": training_source.detach()
                .cpu()
                .to(torch.float32)
                .contiguous(),
                "semantic_tokens": tokens[:, : base.SEMANTIC_FRAMES]
                .detach()
                .cpu()
                .to(torch.int64)
                .contiguous(),
                "target_wav": output.detach().cpu().to(torch.float32).contiguous(),
                "ssl_feat": hidden[..., : base.TARGET_HIDDEN_FRAMES]
                .detach()
                .cpu()
                .to(torch.float32)
                .contiguous(),
            }
            training_rows.append(
                assigned_tensors(
                    training_target,
                    generated,
                    modes[row_index],
                    real_donor=donor_tensor,
                )
            )
            generated_inventory.append(
                {
                    "target_id": target_pair.pair_id,
                    "donor_id": donor_pair.pair_id,
                    "source_sha256": digest,
                }
            )
            training_source_inventory.append(
                {
                    "target_id": target_pair.pair_id,
                    "donor_id": donor_pair.pair_id,
                    "condition": condition,
                    "authentic_anchor": authentic_row,
                    "source_sha256": base.sha256_file(training_source_path),
                }
            )
            training_target_inventory.append(
                {
                    "target_id": target_pair.pair_id,
                    "condition": target_condition,
                    "target_sha256": target_source_digest,
                }
            )
            row_index += 1
    if (
        len(training_rows) != TOTAL_UPDATES
        or method._canonical_sha256(generated_inventory)
        != PREDECESSOR_INVENTORY_SHA256
    ):
        raise RoleMixError("regenerated EXP-035 pair inventory drifted")

    scope = training_scope(arguments.inventory, arguments.lora_scope)
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
    if not isinstance(observed, (list, tuple)) or set(observed) != set(target_modules):
        raise RoleMixError(f"{arguments.lora_scope} target set drifted")
    trainable = base._set_adapter_training_only(trained)
    if sum(parameter.numel() for parameter in trainable) != int(
        scope["trainable_parameter_count"]
    ):
        raise RoleMixError(
            f"{arguments.lora_scope} trainable parameter count drifted"
        )
    optimizer = torch.optim.AdamW(trainable, lr=base.LEARNING_RATE)
    losses: list[float] = []
    observed_role_counts = dict(Counter(modes))
    loss_by_role: dict[str, list[float]] = {
        role: [] for role in observed_role_counts
    }
    for role, tensors in zip(modes, training_rows, strict=True):
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
            raise RoleMixError("X-VC gradient norm is non-finite")
        optimizer.step()
        losses.append(numeric)
        loss_by_role[role].append(numeric)
    if len(losses) != TOTAL_UPDATES:
        raise RoleMixError(f"{policy['experiment_id']} update count drifted")
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
            "predecessor_git_commit": predecessor["git_commit"],
            "generated_inventory_sha256": PREDECESSOR_INVENTORY_SHA256,
            "target_voice": "Amitaro runrun",
            "target_text_count": method.PAIR_COUNT,
            "target_exposures_per_text": breadth.DONOR_COUNT,
            "optimizer_updates": TOTAL_UPDATES,
            "lora_scope": arguments.lora_scope,
            "learning_rate": base.LEARNING_RATE,
            "gradient_clip_norm": base.GRADIENT_CLIP_NORM,
            "target_wav_cond": "zeros",
            "loss_weights": loss_weights,
        },
        "role_counts": observed_role_counts,
        "role_schedule_sha256": method._canonical_sha256(modes),
        "source_condition_counts": dict(
            Counter(item["kind"] for item in source_conditions)
        ),
        "source_condition_schedule_sha256": method._canonical_sha256(
            source_conditions
        ),
        "training_source_inventory_sha256": method._canonical_sha256(
            training_source_inventory
        ),
        "target_condition_counts": dict(
            Counter(item["condition"] for item in training_target_inventory)
        ),
        "training_target_inventory_sha256": method._canonical_sha256(
            training_target_inventory
        ),
        "authentic_anchor_count": sum(
            bool(item["authentic_anchor"]) for item in training_source_inventory
        ),
        "authentic_pair_inventory_sha256": (
            method._canonical_sha256(
                [
                    {
                        "pair_id": pair.pair_id,
                        "source_sha256": pair.source_sha256,
                        "target_sha256": pair.target_sha256,
                    }
                    for pair in anchor_pairs
                ]
            )
            if anchor_pairs
            else None
        ),
        "donor_manifest_sha256": base.sha256_file(arguments.donors),
        "evaluation_set_sha256": base.sha256_file(arguments.evaluation_set),
        "generated_pair_count": len(training_rows),
        "generated_inventory_sha256": method._canonical_sha256(generated_inventory),
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "loss_by_role_first_last": {
            role: {"first": values[0], "last": values[-1]}
            for role, values in loss_by_role.items()
        },
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "listener_rows": listener_rows,
        "machine_screen_boundary": (
            "content/corruption and repetition only; not naturalness, similarity, "
            "or a winner"
        ),
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
                "role_counts": observed_role_counts,
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
        "--training-policy",
        choices=(
            "role-mix",
            "all-standard",
            "standard-reconstruction",
            "source-augmentation",
            "paired-augmentation",
            "authentic-anchor",
            "semantic2x",
            "real-reconstruction20",
        ),
        default="role-mix",
    )
    parser.add_argument(
        "--lora-scope",
        choices=("control69", "speaker7", "source36", "output2"),
        default="control69",
    )
    parser.add_argument("--donors", type=Path, required=True)
    parser.add_argument("--evaluation-set", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--predecessor-result", type=Path, required=True)
    parser.add_argument("--predecessor-pseudo-root", type=Path, required=True)
    parser.add_argument("--control-adapter", type=Path, required=True)
    parser.add_argument("--xvc-source-root", type=Path, required=True)
    parser.add_argument("--xvc-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
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
        donors, evaluation, targets, predecessor = validate_inputs(arguments)
        if arguments.check:
            modes = training_modes(arguments.training_policy)
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "donors": len(donors["items"]),
                        "evaluation_rows": len(evaluation["items"]),
                        "training_targets": len(targets),
                        "generated_pairs": TOTAL_UPDATES,
                        "updates": TOTAL_UPDATES,
                        "role_counts": dict(Counter(modes)),
                        "source_condition_counts": dict(
                            Counter(
                                item["kind"]
                                for item in source_condition_schedule(
                                    arguments.training_policy
                                )
                            )
                        ),
                        "target_condition_counts": dict(
                            Counter(
                                target_condition_kind(
                                    arguments.training_policy, str(item["kind"])
                                )
                                for item in source_condition_schedule(
                                    arguments.training_policy
                                )
                            )
                        ),
                        "authentic_anchor_count": (
                            method.PAIR_COUNT
                            if arguments.training_policy == "authentic-anchor"
                            else 0
                        ),
                        "loss_weights": training_loss_weights(
                            arguments.training_policy
                        ),
                        "lora_scope": arguments.lora_scope,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, donors, evaluation, targets, predecessor)
    except (
        base.ListenNowError,
        breadth.BreadthError,
        external.ExternalEvaluationError,
        method.SourceDiversityError,
        RoleMixError,
        OSError,
        ValueError,
    ) as error:
        print(f"exp036-role-mix-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
