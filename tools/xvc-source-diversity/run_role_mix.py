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
REAL_TEACHER_SEMANTIC_COUNTS = {
    "standard": 835,
    "real-donor-teacher-semantic": 209,
}
REAL_TEACHER_BREADTH_POLICY = "real-teacher-breadth48"
REAL_TEACHER_OUTPUT_POLICY = "real-teacher-output48"
REAL_TEACHER_POOL_KIND = "liveconv-exp114-commonvoice-teacher48/v1"
REAL_TEACHER_POOL_GROUP = "commonvoice-teacher-train-disjoint"
REAL_TEACHER_POOL_COUNT = 48
FRESH48_KIND = "liveconv-exp112-commonvoice-fresh48/v1"
FRESH48_GROUP = "commonvoice-fresh-disjoint"
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
DENOISE_CONDITION_CYCLE = (
    {"kind": "clean"},
    {"kind": "noise", "snr_db": 20.0},
)
DENOISE_CONDITION_COUNTS = {"clean": 522, "noise": 522}
TOKEN_HOLD_CYCLE = ("clean", "hold5")
TOKEN_HOLD_COUNTS = {"clean": 522, "hold5": 522}
TOKEN_HOLD_BLOCK_SIZE = 5
FRAME_CONDITION_REFERENCE_ID = "EMOTION100_009"
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
DECODER_FINAL_MODULES = (
    "acoustic_decoder.model.4",
    "acoustic_decoder.model.5",
    "acoustic_decoder.model.6",
)
DECODER_FINAL_TRAINABLE_PARAMETERS = 297_890


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
        "source-semantic",
        "denoise-semantic",
        "cross-target-condition",
        "semantic-token-hold",
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
    if policy in {"real-teacher-semantic20", REAL_TEACHER_BREADTH_POLICY}:
        repeats, remainder = divmod(TOTAL_UPDATES, len(RECONSTRUCTION_CYCLE))
        tail = (
            "standard",
            "standard",
            "real-donor-teacher-semantic",
            "standard",
        )
        if remainder != len(tail):
            raise RoleMixError("real-teacher-semantic schedule tail drifted")
        cycle = (
            "standard",
            "standard",
            "real-donor-teacher-semantic",
            "standard",
            "standard",
        )
        schedule = list(cycle) * repeats + list(tail)
        if Counter(schedule) != REAL_TEACHER_SEMANTIC_COUNTS:
            raise RoleMixError("real-teacher-semantic proportions drifted")
        return schedule
    if policy == REAL_TEACHER_OUTPUT_POLICY:
        repeats, remainder = divmod(TOTAL_UPDATES, len(RECONSTRUCTION_CYCLE))
        tail = (
            "standard",
            "standard",
            "real-donor-teacher-output",
            "standard",
        )
        cycle = (
            "standard",
            "standard",
            "real-donor-teacher-output",
            "standard",
            "standard",
        )
        schedule = list(cycle) * repeats + list(tail)
        if remainder != len(tail) or Counter(schedule) != {
            "standard": 835,
            "real-donor-teacher-output": 209,
        }:
            raise RoleMixError("real-teacher-output proportions drifted")
        return schedule
    raise RoleMixError(f"unknown training policy: {policy}")


def real_teacher_pool_schedule(
    policy: str, pool_size: int
) -> list[int | None]:
    if policy not in {REAL_TEACHER_BREADTH_POLICY, REAL_TEACHER_OUTPUT_POLICY}:
        return [None] * TOTAL_UPDATES
    if pool_size != REAL_TEACHER_POOL_COUNT:
        raise RoleMixError("real-teacher pool size drifted")
    schedule: list[int | None] = []
    teacher_index = 0
    teacher_role = (
        "real-donor-teacher-output"
        if policy == REAL_TEACHER_OUTPUT_POLICY
        else "real-donor-teacher-semantic"
    )
    for role in training_modes(policy):
        if role == teacher_role:
            schedule.append(teacher_index % pool_size)
            teacher_index += 1
        else:
            schedule.append(None)
    counts = Counter(index for index in schedule if index is not None)
    if (
        len(schedule) != TOTAL_UPDATES
        or teacher_index != REAL_TEACHER_SEMANTIC_COUNTS[
            "real-donor-teacher-semantic"
        ]
        or sorted(counts.values()) != [4] * 31 + [5] * 17
    ):
        raise RoleMixError("real-teacher pool schedule drifted")
    return schedule


def source_condition_schedule(policy: str) -> list[dict[str, object]]:
    if policy == "denoise-semantic":
        repeats, remainder = divmod(TOTAL_UPDATES, len(DENOISE_CONDITION_CYCLE))
        schedule = [dict(item) for item in DENOISE_CONDITION_CYCLE] * repeats
        schedule.extend(dict(item) for item in DENOISE_CONDITION_CYCLE[:remainder])
        observed = Counter(item["kind"] for item in schedule)
        if len(schedule) != TOTAL_UPDATES or observed != DENOISE_CONDITION_COUNTS:
            raise RoleMixError("denoise-condition schedule drifted")
        return schedule
    if policy not in {"source-augmentation", "paired-augmentation"}:
        return [{"kind": "clean"} for _ in range(TOTAL_UPDATES)]
    repeats, remainder = divmod(TOTAL_UPDATES, len(SOURCE_CONDITION_CYCLE))
    schedule = [dict(item) for item in SOURCE_CONDITION_CYCLE] * repeats
    schedule.extend(dict(item) for item in SOURCE_CONDITION_CYCLE[:remainder])
    observed = Counter(item["kind"] for item in schedule)
    if len(schedule) != TOTAL_UPDATES or observed != SOURCE_CONDITION_COUNTS:
        raise RoleMixError("source-condition schedule proportions drifted")
    return schedule


def semantic_token_schedule(policy: str) -> list[str]:
    if policy != "semantic-token-hold":
        return ["clean"] * TOTAL_UPDATES
    repeats, remainder = divmod(TOTAL_UPDATES, len(TOKEN_HOLD_CYCLE))
    schedule = list(TOKEN_HOLD_CYCLE) * repeats + list(
        TOKEN_HOLD_CYCLE[:remainder]
    )
    if Counter(schedule) != TOKEN_HOLD_COUNTS:
        raise RoleMixError("semantic-token hold schedule drifted")
    return schedule


def held_token_values(
    values: Sequence[int], block_size: int = TOKEN_HOLD_BLOCK_SIZE
) -> list[int]:
    if len(values) != base.SEMANTIC_FRAMES:
        raise RoleMixError("semantic-token hold input length drifted")
    if block_size <= 1 or base.SEMANTIC_FRAMES % block_size:
        raise RoleMixError("semantic-token hold block size drifted")
    return [
        int(values[start])
        for start in range(0, base.SEMANTIC_FRAMES, block_size)
        for _ in range(block_size)
    ]


def hold_semantic_tokens(tokens: Any, block_size: int = TOKEN_HOLD_BLOCK_SIZE) -> Any:
    if tuple(tokens.shape) != (1, base.SEMANTIC_FRAMES):
        raise RoleMixError("semantic-token hold input shape drifted")
    values = held_token_values(tokens.reshape(-1).tolist(), block_size)
    return tokens.new_tensor(values).reshape(1, base.SEMANTIC_FRAMES)


def target_condition_kind(policy: str, source_kind: str) -> str:
    if policy != "paired-augmentation" or source_kind in {"clean", "noise"}:
        return "clean"
    if source_kind not in {"tempo", "pitch", "leading-silence"}:
        raise RoleMixError(f"unknown source condition: {source_kind}")
    return source_kind


def frame_condition_target_index(
    policy: str, target_index: int, target_count: int
) -> int | None:
    if policy != "cross-target-condition":
        return None
    if target_count < 2 or not 0 <= target_index < target_count:
        raise RoleMixError("cross-target frame-condition index drifted")
    return (target_index + 1) % target_count


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
    if name == "decoder-final":
        expanded = horizon.lora_scope(inventory, "expanded79")
        if "acoustic_converter.proj_out" not in expanded["target_modules"]:
            raise RoleMixError("decoder-final serialization sentinel drifted")
        return {
            "target_modules": ["acoustic_converter.proj_out"],
            "modules_to_save": list(DECODER_FINAL_MODULES),
            "trainable_parameter_count": DECODER_FINAL_TRAINABLE_PARAMETERS,
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
        arguments.training_policy == REAL_TEACHER_OUTPUT_POLICY
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-116",
            "slug": "exp116",
            "candidate_id": "cv12-real-teacher-output48",
            "candidate_name": (
                "EXP-116 / 20% frozen-base full-output teacher / 48 speakers"
            ),
            "run_kind": "EXP-116 X-VC full-output teacher evaluation",
            "result_kind": "liveconv-exp116-xvc-real-teacher-output48/v1",
            "question": (
                "Does full converted-output distillation on real Japanese "
                "sources prevent the waveform failures left by semantic-only "
                "teacher rehearsal?"
            ),
            "independent_variable": (
                "teacher target on the same 209 train48 positions: semantic-only "
                "frozen-base prediction versus the frozen base's complete "
                "Amitaro-conditioned converted waveform with standard semantic, "
                "speaker, mel, and VQ losses; data, 835 standard rows, total "
                "updates, control69, LR, seed, and zero frame condition stay fixed"
            ),
        }
    if (
        arguments.training_policy == REAL_TEACHER_BREADTH_POLICY
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-114",
            "slug": "exp114",
            "candidate_id": "cv12-real-teacher-breadth48",
            "candidate_name": (
                "EXP-114 / 20% semantic teacher / 48 real source speakers"
            ),
            "run_kind": "EXP-114 X-VC real-teacher breadth evaluation",
            "result_kind": "liveconv-exp114-xvc-real-teacher-breadth48/v1",
            "question": (
                "Does increasing only the real semantic-teacher source pool "
                "from 12 to 48 speakers improve fresh-speaker generalization?"
            ),
            "independent_variable": (
                "real semantic-teacher source diversity: 12 EXP-035 donors "
                "versus 48 training-only Common Voice speakers across the same "
                "209 teacher positions; the 835 standard rows, total updates, "
                "teacher objective, target voice, control69, LR, seed, zero "
                "frame condition, and loss weights stay fixed"
            ),
        }
    if (
        arguments.training_policy == "real-teacher-semantic20"
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-106",
            "slug": "exp106",
            "candidate_id": "cv12-real-teacher-semantic20",
            "candidate_name": (
                "EXP-106 / 80% target conversion + 20% real-source teacher semantic"
            ),
            "run_kind": "EXP-106 X-VC real-source teacher-semantic evaluation",
            "result_kind": "liveconv-exp106-xvc-real-teacher-semantic-result/v1",
            "question": (
                "Can frozen-base semantic rehearsal on real Japanese donor inputs "
                "preserve off-distribution content without teaching donor identity?"
            ),
            "independent_variable": (
                "training method: 835 standard generated-source-to-Amitaro updates "
                "plus 209 real Common Voice source rows supervised only by the "
                "frozen base model's semantic prediction under the Amitaro target "
                "speaker; total updates, real donors and 80/20 positions from "
                "EXP-072, target-specific rows, control69, LR, seed, zero frame "
                "condition, and standard loss weights stay fixed"
            ),
        }
    if (
        arguments.training_policy == "semantic-token-hold"
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-100",
            "slug": "exp100",
            "candidate_id": "cv12-semantic-token-hold",
            "candidate_name": (
                "EXP-100 / CV12 / alternating clean and 5-frame-held tokens"
            ),
            "run_kind": "EXP-100 X-VC semantic-token hold evaluation",
            "result_kind": "liveconv-exp100-xvc-semantic-token-hold-result/v1",
            "question": (
                "Does deterministic semantic-token collapse during retraining "
                "make X-VC use its acoustic path without harming clean content?"
            ),
            "independent_variable": (
                "semantic token input: 522 clean versus 522 rows where each "
                "five-frame block repeats its first token; source waveform, "
                "target waveform/speaker/semantic objectives, data identities, "
                "control69, LR, seed, zero condition, and 1,044 updates stay fixed"
            ),
        }
    if (
        arguments.training_policy == "cross-target-condition"
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-094",
            "slug": "exp094",
            "candidate_id": "cv12-cross-target-condition",
            "candidate_name": (
                "EXP-094 / CV12 / same-speaker cross-utterance frame condition"
            ),
            "run_kind": "EXP-094 X-VC cross-target-condition evaluation",
            "result_kind": "liveconv-exp094-xvc-cross-target-condition-result/v1",
            "question": (
                "Does training and inference with a same-speaker, different-"
                "utterance frame condition stabilize X-VC content and waveform "
                "generation compared with the always-zero condition contract?"
            ),
            "independent_variable": (
                "target_wav_cond contract: zeros versus deterministic next-"
                "Amitaro-utterance waveform for every training target and fixed "
                f"{FRAME_CONDITION_REFERENCE_ID} at inference; generated source/"
                "target pairs, target speaker path, semantic target, loss weights, "
                "control69, LR, seed, and 1,044 updates stay fixed"
            ),
            "conditioned_inference": True,
        }
    if (
        arguments.training_policy == "denoise-semantic"
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-087",
            "slug": "exp087",
            "candidate_id": "cv12-denoise-semantic",
            "candidate_name": (
                "EXP-087 / CV12 / clean-noise denoising semantic consistency"
            ),
            "run_kind": "EXP-087 X-VC denoising-semantic evaluation",
            "result_kind": "liveconv-exp087-xvc-denoise-semantic-result/v1",
            "question": (
                "Does clean-source semantic supervision recover content from "
                "noise-corrupted X-VC inputs without harming clean speech?"
            ),
            "independent_variable": (
                "denoising semantic consistency: alternate 522 clean and 522 "
                "noise20 source waveforms/tokens while supervising semantic MSE "
                "with the corresponding clean-source hidden states; target "
                "waveform/speaker, loss weights, data identities, control69, LR, "
                "seed, zero condition, and 1,044 updates stay fixed"
            ),
        }
    if (
        arguments.training_policy == "source-semantic"
        and arguments.lora_scope == "control69"
    ):
        return {
            "experiment_id": "EXP-081",
            "slug": "exp081",
            "candidate_id": "cv12-source-semantic",
            "candidate_name": (
                "EXP-081 / CV12 / source-hidden semantic supervision"
            ),
            "run_kind": "EXP-081 X-VC source-semantic evaluation",
            "result_kind": "liveconv-exp081-xvc-source-semantic-result/v1",
            "question": (
                "Does supervising the semantic decoder with source hidden states "
                "preserve unseen input content better than target-hidden supervision?"
            ),
            "independent_variable": (
                "semantic MSE target: target-voice Whisper hidden states versus "
                "generated-source Whisper hidden states; target waveform, target "
                "speaker, loss weights, data, control69 scope, LR, seed, zero "
                "condition, and 1,044 updates stay fixed"
            ),
        }
    if (
        arguments.training_policy == "all-standard"
        and arguments.lora_scope == "decoder-final"
    ):
        return {
            "experiment_id": "EXP-077",
            "slug": "exp077",
            "candidate_id": "cv12-decoder-final",
            "candidate_name": "EXP-077 / CV12 / final waveform decoder stage",
            "run_kind": "EXP-077 X-VC final decoder-stage evaluation",
            "result_kind": "liveconv-exp077-xvc-decoder-final-result/v1",
            "question": (
                "Can adapting only the final waveform upsampling stage improve "
                "the decoder path without changing converter content modules?"
            ),
            "independent_variable": (
                "trainable function: control69 converter LoRA versus 297,890 full "
                "parameters in acoustic_decoder.model.4--6; data, generative loss, "
                "LR, seed, condition, and 1,044 updates stay fixed"
            ),
        }
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
    semantic_target: str = "reference",
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
    if role in {
        "real-donor-teacher-semantic",
        "real-donor-teacher-output",
    }:
        if real_donor is None:
            raise RoleMixError("real donor tensors are required for teacher rehearsal")
        return {
            "source_wav": real_donor["source_wav"],
            "semantic_tokens": real_donor["semantic_tokens"],
            "target_wav": target["target_wav"],
            "ssl_feat": target["ssl_feat"],
        }
    if role == "standard":
        source, reference = generated, target
    elif role == "reconstruction":
        source = reference = target
    elif role == "reversed":
        source, reference = target, generated
    else:
        raise RoleMixError(f"unknown role assignment: {role}")
    if semantic_target not in {"reference", "source"}:
        raise RoleMixError(f"unknown semantic target: {semantic_target}")
    return {
        "source_wav": source["source_wav"],
        "semantic_tokens": source["semantic_tokens"],
        "target_wav": reference["target_wav"],
        "ssl_feat": (
            source["ssl_feat"]
            if semantic_target == "source"
            else reference["ssl_feat"]
        ),
    }


def teacher_semantic_target(
    model: Any,
    tensors: Mapping[str, Any],
    *,
    torch: Any,
    device: Any,
) -> Any:
    """Freeze the base prediction for one real-source, target-speaker row."""
    batch = base._gpu_batch(tensors, torch=torch, device=device)
    model.eval()
    with torch.inference_mode(), torch.autocast(
        device_type="cuda", dtype=torch.bfloat16
    ):
        outputs = model(dict(batch))
    prediction = outputs.get("pred") if isinstance(outputs, dict) else None
    if (
        prediction is None
        or prediction.shape != batch["ssl_feat"].shape
        or not bool(torch.isfinite(prediction).all())
    ):
        raise RoleMixError("frozen teacher semantic prediction drifted")
    return prediction.detach().cpu().to(torch.float32).contiguous()


def teacher_output_targets(
    model: Any,
    real_donor: Mapping[str, Any],
    target: Mapping[str, Any],
    *,
    seed: int,
    torch: Any,
    device: Any,
) -> dict[str, Any]:
    """Freeze one complete base conversion as a paired distillation target."""
    waveform = base._inference(
        model,
        real_donor,
        target,
        seed=seed,
        torch=torch,
        device=device,
    )
    with torch.inference_mode():
        features = model.semantic_encoder.extract_and_encode(waveform.squeeze(1))
    hidden = features.get("whisper_hidden_states_50hz")
    if (
        hidden is None
        or hidden[..., : base.TARGET_HIDDEN_FRAMES].shape[-1]
        != base.TARGET_HIDDEN_FRAMES
        or not bool(torch.isfinite(hidden).all())
    ):
        raise RoleMixError("full-output teacher semantic target drifted")
    return {
        "source_wav": real_donor["source_wav"],
        "semantic_tokens": real_donor["semantic_tokens"],
        "target_wav": waveform.detach().cpu().to(torch.float32).contiguous(),
        "ssl_feat": hidden[..., : base.TARGET_HIDDEN_FRAMES]
        .detach()
        .cpu()
        .to(torch.float32)
        .contiguous(),
    }


def training_loss(
    model: Any,
    batch: Mapping[str, Any],
    role: str,
    *,
    torch: Any,
) -> tuple[Any, float]:
    """Use semantic-only distillation on the bounded real-source teacher rows."""
    if role != "real-donor-teacher-semantic":
        return base._composite_loss(model, batch, torch)
    outputs = model(dict(batch))
    prediction = outputs.get("pred") if isinstance(outputs, dict) else None
    if prediction is None or not bool(torch.isfinite(prediction).all()):
        raise RoleMixError("teacher-semantic training output is malformed")
    semantic = model.compute_mse_loss(prediction, batch["ssl_feat"])
    loss = STANDARD_LOSS_WEIGHTS["mse_loss"] * semantic
    if not bool(torch.isfinite(loss)):
        raise RoleMixError("teacher-semantic loss is non-finite")
    return loss, float(loss.detach().cpu())


def conditioned_inference(
    model: Any,
    source: Mapping[str, Any],
    reference: Mapping[str, Any],
    frame_condition: Mapping[str, Any],
    *,
    seed: int,
    torch: Any,
    device: Any,
) -> Any:
    index = device.index
    if index is None:
        raise RoleMixError("conditioned render requires numbered cuda:0")
    batch = {
        "source_wav": source["source_wav"].to(device=device, dtype=torch.float32),
        "target_wav": reference["target_wav"].to(
            device=device, dtype=torch.float32
        ),
        "target_wav_cond": frame_condition["target_wav"].to(
            device=device, dtype=torch.float32
        ),
        "semantic_tokens": source["semantic_tokens"].to(
            device=device, dtype=torch.int64
        ),
        "ssl_feat": reference["ssl_feat"].to(device=device, dtype=torch.float32),
    }
    model.eval()
    with torch.random.fork_rng(devices=[index], enabled=True), torch.no_grad():
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        rendered = model.inference(batch).get("recons")
    if (
        rendered is None
        or rendered.shape != (1, 1, base.MODEL_SAMPLES)
        or not bool(torch.isfinite(rendered).all())
    ):
        raise RoleMixError("conditioned render is not finite 2.4-second mono")
    return rendered


def _set_scope_training_only(model: Any, scope: Mapping[str, object]) -> list[Any]:
    modules = tuple(str(item) for item in scope.get("modules_to_save", []))
    if not modules:
        return base._set_adapter_training_only(model)
    model.eval()
    trainable: list[Any] = []
    for name, parameter in model.named_parameters():
        selected = ".modules_to_save.default." in name and any(
            f".{module}." in name for module in modules
        )
        parameter.requires_grad_(selected)
        if selected:
            trainable.append(parameter)
    if sum(parameter.numel() for parameter in trainable) != int(
        scope["trainable_parameter_count"]
    ):
        raise RoleMixError("decoder-final trainable parameter count drifted")
    return trainable


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


def _load_fixed_commonvoice_pool(
    path: Path, *, kind: str, group: str, count: int
) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RoleMixError("fixed Common Voice pool is not valid JSON") from error
    items = value.get("items") if isinstance(value, dict) else None
    source = value.get("source") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or value.get("kind") != kind
        or not isinstance(source, dict)
        or source.get("license") != "CC0-1.0"
        or not isinstance(items, list)
        or len(items) != count
    ):
        raise RoleMixError("fixed Common Voice pool schema drifted")
    ids: set[str] = set()
    files: set[str] = set()
    clients: set[str] = set()
    for item in items:
        identifier = item.get("id") if isinstance(item, dict) else None
        filename = item.get("filename") if isinstance(item, dict) else None
        client = item.get("client_id_sha256") if isinstance(item, dict) else None
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in ids
            or not isinstance(filename, str)
            or Path(filename).name != filename
            or filename in files
            or not base._is_sha256(item.get("sha256"))
            or not base._is_sha256(client)
            or client in clients
            or item.get("group") != group
            or not isinstance(item.get("source_transcript"), str)
            or not item["source_transcript"]
            or item.get("down_votes") != 0
            or not isinstance(item.get("up_votes"), int)
            or int(item["up_votes"]) < 2
        ):
            raise RoleMixError("fixed Common Voice pool row drifted")
        ids.add(identifier)
        files.add(filename)
        clients.add(client)
    return value


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[tuple[str, Path, str]],
    dict[str, Any],
    dict[str, Any] | None,
]:
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

    teacher_pool: dict[str, Any] | None = None
    if arguments.training_policy in {
        REAL_TEACHER_BREADTH_POLICY,
        REAL_TEACHER_OUTPUT_POLICY,
    }:
        if (
            arguments.real_teacher_manifest is None
            or arguments.real_teacher_root is None
            or arguments.frozen_fresh_evaluation is None
        ):
            raise RoleMixError("real-teacher breadth inputs are required")
        teacher_pool = _load_fixed_commonvoice_pool(
            arguments.real_teacher_manifest,
            kind=REAL_TEACHER_POOL_KIND,
            group=REAL_TEACHER_POOL_GROUP,
            count=REAL_TEACHER_POOL_COUNT,
        )
        fresh = _load_fixed_commonvoice_pool(
            arguments.frozen_fresh_evaluation,
            kind=FRESH48_KIND,
            group=FRESH48_GROUP,
            count=REAL_TEACHER_POOL_COUNT,
        )
        teacher_clients = {
            item["client_id_sha256"] for item in teacher_pool["items"]
        }
        frozen_clients = {item["client_id_sha256"] for item in fresh["items"]}
        if teacher_clients & (donor_clients | evaluation_clients | frozen_clients):
            raise RoleMixError("real-teacher pool overlaps frozen speakers")
        for item in teacher_pool["items"]:
            path = arguments.real_teacher_root / item["filename"]
            if (
                path.is_symlink()
                or not path.is_file()
                or base.sha256_file(path) != item["sha256"]
            ):
                raise RoleMixError(
                    f"real-teacher Common Voice input drifted: {item['filename']}"
                )

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
    real_teacher_pool_schedule(
        arguments.training_policy,
        len(teacher_pool["items"]) if teacher_pool is not None else 0,
    )
    return donors, evaluation, targets, predecessor, teacher_pool


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


def run_teacher_output_smoke(
    arguments: argparse.Namespace,
    teacher_pool: Mapping[str, Any] | None,
    target_rows: list[tuple[str, Path, str]],
) -> int:
    """Run one full-output teacher row through LoRA backward without saving it."""
    if (
        arguments.training_policy != REAL_TEACHER_OUTPUT_POLICY
        or teacher_pool is None
        or arguments.real_teacher_root is None
    ):
        raise RoleMixError("full-output smoke requires EXP-116 inputs")
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise RoleMixError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise RoleMixError("EXP-116 smoke requires the explicit gpu0 lease")
    arguments.work_dir.mkdir()
    reference_root = arguments.work_dir / "teacher-reference"
    reference_root.mkdir()

    import torch
    from peft import LoraConfig, get_peft_model

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
    model = method._load_xvc(arguments, XVC, device)
    base._initialize_loss(model, arguments.xvc_config)
    target_id, target_path, target_digest = target_rows[0]
    target_pair = base.MaterializedPair(
        target_id, target_path, target_path, target_digest, target_digest
    )
    target = base._extract_pair_tensors(
        model,
        target_pair,
        process_audio=process_audio,
        config=config,
        torch=torch,
        device=device,
    )
    _teacher_pair, real_donor = breadth._reference_tensor(
        model,
        teacher_pool["items"][0],
        source_root=arguments.real_teacher_root,
        output_root=reference_root,
        process_audio=process_audio,
        config=config,
        torch=torch,
        device=device,
    )
    tensors = teacher_output_targets(
        model,
        real_donor,
        target,
        seed=base.SEED + TOTAL_UPDATES,
        torch=torch,
        device=device,
    )
    scope = training_scope(arguments.inventory, arguments.lora_scope)
    trained = get_peft_model(
        model,
        LoraConfig(
            r=8,
            lora_alpha=8,
            lora_dropout=0.0,
            bias="none",
            use_dora=False,
            use_rslora=False,
            target_modules=list(scope["target_modules"]),
        ),
    )
    trainable = _set_scope_training_only(trained, scope)
    batch = base._gpu_batch(tensors, torch=torch, device=device)
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        loss, numeric = training_loss(
            trained, batch, "real-donor-teacher-output", torch=torch
        )
    loss.backward()
    gradient_norm = torch.nn.utils.clip_grad_norm_(
        trainable, base.GRADIENT_CLIP_NORM
    )
    if not math.isfinite(float(gradient_norm.detach().cpu())):
        raise RoleMixError("full-output smoke gradient is non-finite")
    print(
        json.dumps(
            {
                "status": "smoked-one-full-output-row",
                "loss": numeric,
                "gradient_norm": float(gradient_norm.detach().cpu()),
                "target_samples": int(tensors["target_wav"].numel()),
                "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
            },
            sort_keys=True,
        )
    )
    return 0


def run(
    arguments: argparse.Namespace,
    donors: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    target_rows: list[tuple[str, Path, str]],
    predecessor: Mapping[str, Any],
    teacher_pool: Mapping[str, Any] | None,
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
    teacher_root = arguments.work_dir / "teacher-references"
    evaluation_root = arguments.work_dir / "evaluation-sources"
    regenerated_root = arguments.work_dir / "verified-generated-source-pairs"
    roots = [donor_root, evaluation_root, regenerated_root]
    if teacher_pool is not None:
        roots.append(teacher_root)
    for path in roots:
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
    teacher_pairs: list[base.MaterializedPair] = []
    teacher_tensors: list[dict[str, Any]] = []
    if teacher_pool is not None:
        if arguments.real_teacher_root is None:
            raise RoleMixError("real-teacher source root is unavailable")
        for item in teacher_pool["items"]:
            pair, tensors = breadth._reference_tensor(
                model,
                item,
                source_root=arguments.real_teacher_root,
                output_root=teacher_root,
                process_audio=process_audio,
                config=config,
                torch=torch,
                device=device,
            )
            teacher_pairs.append(pair)
            teacher_tensors.append(tensors)
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
    target_by_id = {
        pair.pair_id: tensor
        for pair, tensor in zip(target_pairs, target_tensors, strict=True)
    }
    if FRAME_CONDITION_REFERENCE_ID not in target_by_id:
        raise RoleMixError("fixed frame-condition reference is unavailable")
    frame_condition_reference = target_by_id[FRAME_CONDITION_REFERENCE_ID]

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
    teacher_pool_indices = real_teacher_pool_schedule(
        arguments.training_policy, len(teacher_tensors)
    )
    source_conditions = source_condition_schedule(arguments.training_policy)
    token_conditions = semantic_token_schedule(arguments.training_policy)
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
                    clean_features = (
                        model.semantic_encoder.extract_and_encode(output.squeeze(1))
                        if arguments.training_policy == "denoise-semantic"
                        and condition_kind != "clean"
                        else features
                    )
                tokens = features.get("speech_tokens")
                hidden = clean_features.get("whisper_hidden_states_50hz")
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
            semantic_tokens = (
                tokens[:, : base.SEMANTIC_FRAMES]
                .detach()
                .cpu()
                .to(torch.int64)
                .contiguous()
            )
            token_condition = token_conditions[row_index]
            if token_condition == "hold5":
                semantic_tokens = hold_semantic_tokens(semantic_tokens)
            elif token_condition != "clean":
                raise RoleMixError("semantic-token condition drifted")
            generated = {
                "source_wav": training_source.detach()
                .cpu()
                .to(torch.float32)
                .contiguous(),
                "semantic_tokens": semantic_tokens,
                "target_wav": output.detach().cpu().to(torch.float32).contiguous(),
                "ssl_feat": hidden[..., : base.TARGET_HIDDEN_FRAMES]
                .detach()
                .cpu()
                .to(torch.float32)
                .contiguous(),
            }
            teacher_pool_index = teacher_pool_indices[row_index]
            selected_real_donor = (
                teacher_tensors[teacher_pool_index]
                if teacher_pool_index is not None
                else donor_tensor
            )
            assigned = assigned_tensors(
                training_target,
                generated,
                modes[row_index],
                real_donor=selected_real_donor,
                semantic_target=(
                    "source"
                    if arguments.training_policy
                    in {"source-semantic", "denoise-semantic"}
                    else "reference"
                ),
            )
            if modes[row_index] == "real-donor-teacher-semantic":
                assigned["ssl_feat"] = teacher_semantic_target(
                    model,
                    assigned,
                    torch=torch,
                    device=device,
                )
            if modes[row_index] == "real-donor-teacher-output":
                assigned = teacher_output_targets(
                    model,
                    selected_real_donor,
                    training_target,
                    seed=base.SEED + TOTAL_UPDATES + row_index,
                    torch=torch,
                    device=device,
                )
                teacher_output_name = (
                    "teacher-output-"
                    f"{teacher_pairs[teacher_pool_index].pair_id}-16k.wav"
                )
                target_source_digest = base._write_float_wav(
                    pair_root / teacher_output_name,
                    assigned["target_wav"],
                    sample_rate,
                )
            frame_condition_index = frame_condition_target_index(
                arguments.training_policy, target_index, len(target_tensors)
            )
            frame_condition_pair = None
            if frame_condition_index is not None:
                frame_condition_pair = target_pairs[frame_condition_index]
                assigned["target_wav_cond"] = target_tensors[
                    frame_condition_index
                ]["target_wav"]
            training_rows.append(assigned)
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
                    "semantic_token_condition": token_condition,
                    "authentic_anchor": authentic_row,
                    "real_teacher_id": (
                        teacher_pairs[teacher_pool_index].pair_id
                        if teacher_pool_index is not None
                        else None
                    ),
                    "source_sha256": base.sha256_file(training_source_path),
                }
            )
            training_target_inventory.append(
                {
                    "target_id": target_pair.pair_id,
                    "condition": target_condition,
                    "target_sha256": target_source_digest,
                    "frame_condition_target_id": (
                        frame_condition_pair.pair_id if frame_condition_pair else None
                    ),
                    "frame_condition_target_sha256": (
                        frame_condition_pair.target_sha256
                        if frame_condition_pair
                        else None
                    ),
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
    lora_options: dict[str, Any] = {}
    if scope.get("modules_to_save"):
        lora_options["modules_to_save"] = list(scope["modules_to_save"])
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
            **lora_options,
        ),
    )
    observed = getattr(trained, "targeted_module_names", None)
    if not isinstance(observed, (list, tuple)) or set(observed) != set(target_modules):
        raise RoleMixError(f"{arguments.lora_scope} target set drifted")
    trainable = _set_scope_training_only(trained, scope)
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
        _set_scope_training_only(trained, scope)
        optimizer.zero_grad(set_to_none=True)
        batch = base._gpu_batch(tensors, torch=torch, device=device)
        if "target_wav_cond" in tensors:
            batch["target_wav_cond"] = tensors["target_wav_cond"].to(
                device=device, dtype=torch.float32
            )
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            loss, numeric = training_loss(trained, batch, role, torch=torch)
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
    candidate_outputs = (
        [
            conditioned_inference(
                trained,
                source,
                target_reference,
                frame_condition_reference,
                seed=base.SEED + index,
                torch=torch,
                device=device,
            )
            .detach()
            .cpu()
            for index, source in enumerate(evaluation_tensors)
        ]
        if policy.get("conditioned_inference")
        else render(trained)
    )

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
            "target_wav_cond": (
                "same-speaker-next-utterance-training/fixed-"
                f"{FRAME_CONDITION_REFERENCE_ID}-inference"
                if arguments.training_policy == "cross-target-condition"
                else "zeros"
            ),
            "semantic_supervision": (
                "frozen_base_full_converted_output_on_real_donor_rows"
                if arguments.training_policy == REAL_TEACHER_OUTPUT_POLICY
                else (
                    "frozen_base_semantic_prediction_on_real_donor_rows"
                    if arguments.training_policy
                    in {"real-teacher-semantic20", REAL_TEACHER_BREADTH_POLICY}
                    else (
                    "clean_source_whisper_hidden_states_50hz"
                    if arguments.training_policy == "denoise-semantic"
                    else (
                        "source_whisper_hidden_states_50hz"
                        if arguments.training_policy == "source-semantic"
                        else "target_whisper_hidden_states_50hz"
                    )
                    )
                )
            ),
            "loss_weights": loss_weights,
            "real_teacher_pool_count": len(teacher_tensors),
            "real_teacher_manifest_sha256": (
                base.sha256_file(arguments.real_teacher_manifest)
                if teacher_pool is not None
                and arguments.real_teacher_manifest is not None
                else None
            ),
        },
        "role_counts": observed_role_counts,
        "role_schedule_sha256": method._canonical_sha256(modes),
        "source_condition_counts": dict(
            Counter(item["kind"] for item in source_conditions)
        ),
        "source_condition_schedule_sha256": method._canonical_sha256(
            source_conditions
        ),
        "semantic_token_condition_counts": dict(Counter(token_conditions)),
        "semantic_token_condition_schedule_sha256": method._canonical_sha256(
            token_conditions
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
    parser.add_argument("--smoke-teacher-output", action="store_true")
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
            "source-semantic",
            "denoise-semantic",
            "cross-target-condition",
            "semantic-token-hold",
            "real-teacher-semantic20",
            REAL_TEACHER_BREADTH_POLICY,
            REAL_TEACHER_OUTPUT_POLICY,
            "real-reconstruction20",
        ),
        default="role-mix",
    )
    parser.add_argument(
        "--lora-scope",
        choices=("control69", "speaker7", "source36", "output2", "decoder-final"),
        default="control69",
    )
    parser.add_argument("--donors", type=Path, required=True)
    parser.add_argument("--evaluation-set", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--real-teacher-manifest", type=Path)
    parser.add_argument("--real-teacher-root", type=Path)
    parser.add_argument("--frozen-fresh-evaluation", type=Path)
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
        donors, evaluation, targets, predecessor, teacher_pool = validate_inputs(
            arguments
        )
        if arguments.smoke_teacher_output:
            return run_teacher_output_smoke(arguments, teacher_pool, targets)
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
                        "real_teacher_pool_rows": (
                            len(teacher_pool["items"])
                            if teacher_pool is not None
                            else 0
                        ),
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
                        "semantic_token_condition_counts": dict(
                            Counter(
                                semantic_token_schedule(arguments.training_policy)
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
                        "semantic_supervision": (
                            "frozen_base_full_converted_output_on_real_donor_rows"
                            if arguments.training_policy
                            == REAL_TEACHER_OUTPUT_POLICY
                            else (
                                "frozen_base_semantic_prediction_on_real_donor_rows"
                                if arguments.training_policy
                                in {
                                    "real-teacher-semantic20",
                                    REAL_TEACHER_BREADTH_POLICY,
                                }
                                else (
                                "clean_source_whisper_hidden_states_50hz"
                                if arguments.training_policy == "denoise-semantic"
                                else (
                                    "source_whisper_hidden_states_50hz"
                                    if arguments.training_policy == "source-semantic"
                                    else "target_whisper_hidden_states_50hz"
                                )
                                )
                            )
                        ),
                        "frame_condition_rows": sum(
                            frame_condition_target_index(
                                arguments.training_policy, index, len(targets)
                            )
                            is not None
                            for index in range(len(targets))
                        )
                        * len(donors["items"]),
                        "lora_scope": arguments.lora_scope,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(
            arguments, donors, evaluation, targets, predecessor, teacher_pool
        )
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
