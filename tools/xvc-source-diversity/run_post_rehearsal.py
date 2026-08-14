#!/usr/bin/env python3
"""Run one clean teacher pass after the frozen control69 X-VC adaptation."""

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
import render_commonvoice as external  # noqa: E402
import run as method  # noqa: E402
import run_breadth as breadth  # noqa: E402
import run_role_mix as role_mix  # noqa: E402
from prepare_clean_post_rehearsal import (  # noqa: E402
    EXPECTED_DOMAINS,
    EXPECTED_ROWS,
    OUTPUT_KIND,
    load_json,
    sha256_file,
)
from prepare_commonvoice_retention_curriculum import (  # noqa: E402
    EXPECTED_COMPOSITION as COMMONVOICE_RETENTION_EXPECTED_DOMAINS,
)
from prepare_commonvoice_retention_curriculum import (  # noqa: E402
    OUTPUT_KIND as COMMONVOICE_RETENTION_OUTPUT_KIND,
)
from prepare_conditioned_retention_curriculum import (  # noqa: E402
    EXPECTED_COMPOSITION as CONDITIONED_RETENTION_EXPECTED_DOMAINS,
)
from prepare_conditioned_retention_curriculum import (  # noqa: E402
    OUTPUT_KIND as CONDITIONED_RETENTION_OUTPUT_KIND,
)
from prepare_cross_corpus_unpaired_curriculum import (  # noqa: E402
    EXPECTED_COMPOSITION as CROSS_CORPUS_UNPAIRED_EXPECTED_DOMAINS,
)
from prepare_cross_corpus_unpaired_curriculum import (  # noqa: E402
    OUTPUT_KIND as CROSS_CORPUS_UNPAIRED_OUTPUT_KIND,
)
from prepare_hard_negative_curriculum import (  # noqa: E402
    EXPECTED_COMPOSITION as HARD_EXPECTED_DOMAINS,
)
from prepare_hard_negative_curriculum import (  # noqa: E402
    OUTPUT_KIND as HARD_OUTPUT_KIND,
)
from prepare_jsut_retention_curriculum import (  # noqa: E402
    EXPECTED_COMPOSITION as JSUT_EXPECTED_DOMAINS,
)
from prepare_jsut_retention_curriculum import (  # noqa: E402
    OUTPUT_KIND as JSUT_RETENTION_OUTPUT_KIND,
)
from prepare_selective_retention_curriculum import (  # noqa: E402
    OUTPUT_KIND as SELECTIVE_OUTPUT_KIND,
)
from prepare_selective_retention_curriculum import (  # noqa: E402
    REPAIR_TARGET,
    RETENTION_TARGET,
)
from prepare_src4vc_cross_corpus_curriculum import (  # noqa: E402
    EXPECTED_COMPOSITION as SRC4VC_PSEUDOPARALLEL_EXPECTED_DOMAINS,
)
from prepare_unpaired_human_curriculum import (  # noqa: E402
    EXPECTED_COMPOSITION as UNPAIRED_HUMAN_EXPECTED_DOMAINS,
)
from prepare_unpaired_human_curriculum import (  # noqa: E402
    OUTPUT_KIND as UNPAIRED_HUMAN_OUTPUT_KIND,
)
from render_cross_corpus_pseudoparallel_targets import (  # noqa: E402
    EXPECTED_COMPOSITION as PSEUDOPARALLEL_EXPECTED_DOMAINS,
)
from render_cross_corpus_pseudoparallel_targets import (  # noqa: E402
    LEARNING_TARGET as PSEUDOPARALLEL_LEARNING_TARGET,
)
from render_cross_corpus_pseudoparallel_targets import (  # noqa: E402
    OUTPUT_KIND as PSEUDOPARALLEL_OUTPUT_KIND,
)
from render_cross_corpus_pseudoparallel_targets import (  # noqa: E402
    SRC4VC_OUTPUT_KIND as SRC4VC_PSEUDOPARALLEL_OUTPUT_KIND,
)

CANDIDATE_ID = "cv12-clean-post-rehearsal170"
RESULT_KIND = "liveconv-exp141-xvc-clean-post-rehearsal-result/v1"
LEARNING_RATE = 1e-4
FULL_CONVERTER_TARGET = "full-converter"
ACOUSTIC_ENCODER_TARGET = "acoustic-encoder"
LORA69_TARGET = "lora69"
SOURCE36_TARGET = "source36"
SPEAKER7_OVERLAY_TARGET = "speaker7-overlay"
CONVERTER_PREFIX = "acoustic_converter"
EXPECTED_CONVERTER_PARAMETERS = 42_357_760
CONVERTER_CHECKPOINT_KIND = "liveconv-xvc-merged-control69-converter/v1"
ACOUSTIC_ENCODER_PREFIX = "acoustic_encoder"
EXPECTED_ACOUSTIC_ENCODER_PARAMETERS = 21_521_536
ACOUSTIC_ENCODER_CHECKPOINT_KIND = "liveconv-xvc-merged-control69-acoustic-encoder/v1"
GENERATIVE_OBJECTIVE = "generative-only"
REAL_REFERENCE_ADVERSARIAL_OBJECTIVE = "real-reference-adversarial"
FACTORIZED_UNPAIRED_OBJECTIVE = "factorized-unpaired-human-adversarial"
OUTPUT_CYCLE_UNPAIRED_OBJECTIVE = "factorized-unpaired-human-output-cycle-adversarial"
CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE = (
    "factorized-unpaired-human-contrastive-output-cycle-adversarial"
)
DISCRETE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE = (
    "factorized-unpaired-human-discrete-output-cycle-adversarial"
)
SPEAKER_PATH_UNPAIRED_OBJECTIVE = "factorized-unpaired-human-speaker-path-adversarial"
PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE = "pseudoparallel-generative-real-adversarial"
PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE = (
    "pseudoparallel-generative-real-adversarial-output-speaker"
)
OUTPUT_CYCLE_CONTENT_WEIGHT = 1000.0
CONTRASTIVE_CONTENT_TEMPERATURE = 0.1
SEQUENTIAL_OPTIMIZER = "sequential"
PCGRAD_PAIRED_OPTIMIZER = "pcgrad-hard-easy-paired"
PCGRAD_CONTENT_VOICE_OPTIMIZER = "pcgrad-content-voice"
EMA_IMPLEMENTATION = "ema-pytorch-0.7.7-defaults-adapter-equivalent"
EMA_BETA = 0.9999
EMA_UPDATE_AFTER_STEP = 100
EMA_UPDATE_EVERY = 10
EMA_INV_GAMMA = 1.0
EMA_POWER = 2.0 / 3.0
EMA_MIN_VALUE = 0.0
PARAMETER_ANCHOR_COEFFICIENT = 1.0
PARAMETER_ANCHOR_IMPLEMENTATION = "l2-sp-control69-trainable-parameters/v1"
SOURCE_ACTIVITY_ENVELOPE_WEIGHT = 10.0
SOURCE_ACTIVITY_ENVELOPE_IMPLEMENTATION = (
    "normalized-abs-envelope-20ms-window-10ms-hop/v1"
)
OUTPUT_SPEAKER_IDENTITY_WEIGHT = 10.0
OUTPUT_SPEAKER_IDENTITY_IMPLEMENTATION = (
    "frozen-xvc-eres2net-final-waveform-cosine/v1"
)
DIVERSE_RETENTION_KINDS = {
    JSUT_RETENTION_OUTPUT_KIND,
    COMMONVOICE_RETENTION_OUTPUT_KIND,
    CONDITIONED_RETENTION_OUTPUT_KIND,
}
UNPAIRED_HUMAN_KINDS = {
    UNPAIRED_HUMAN_OUTPUT_KIND,
    CROSS_CORPUS_UNPAIRED_OUTPUT_KIND,
}
PSEUDOPARALLEL_KINDS = {
    PSEUDOPARALLEL_OUTPUT_KIND,
    SRC4VC_PSEUDOPARALLEL_OUTPUT_KIND,
}


class PostRehearsalError(RuntimeError):
    """The bounded clean post-adaptation rehearsal cannot safely continue."""


def listening_policy(
    manifest_kind: str = OUTPUT_KIND,
    trainable_target: str = LORA69_TARGET,
    training_objective: str = GENERATIVE_OBJECTIVE,
    use_adapter_ema: bool = False,
    optimizer_mode: str = SEQUENTIAL_OPTIMIZER,
    parameter_anchor: bool = False,
    source_activity_envelope: bool = False,
) -> dict[str, str]:
    """Return the complete shared-listener identity for the admitted method."""

    if (
        manifest_kind in PSEUDOPARALLEL_KINDS
        or training_objective
        in {
            PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
            PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
        }
    ):
        if (
            manifest_kind not in PSEUDOPARALLEL_KINDS
            or trainable_target != LORA69_TARGET
            or training_objective
            not in {
                PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
                PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
            }
            or not use_adapter_ema
            or optimizer_mode != SEQUENTIAL_OPTIMIZER
            or parameter_anchor
            or source_activity_envelope
        ):
            raise PostRehearsalError(
                "pseudoparallel supervision requires an exact admitted pilot"
            )
        if (
            manifest_kind == SRC4VC_PSEUDOPARALLEL_OUTPUT_KIND
            and training_objective == PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE
        ):
            raise PostRehearsalError(
                "output speaker identity requires the retained EXP-238 curriculum"
            )
        if manifest_kind == SRC4VC_PSEUDOPARALLEL_OUTPUT_KIND:
            return {
                "slug": "exp244",
                "candidate_id": ("src4vc85-pseudoparallel-real-adv-ema170"),
                "candidate_name": (
                    "EXP-244 / SRC4VC85 source substitution / "
                    "pseudoparallel / real-adversarial / EMA"
                ),
                "run_kind": "EXP-244 X-VC SRC4VC source-substitution evaluation",
                "result_kind": (
                    "liveconv-exp244-xvc-src4vc-pseudoparallel-real-adv-ema/v1"
                ),
                "question": (
                    "Does replacing only the JSUT85 source block with 85 distinct "
                    "SRC4VC smartphone speakers improve robust X-VC conversion?"
                ),
                "independent_variable": (
                    "relative to EXP-238, only the 85 single-speaker JSUT source "
                    "rows change to one RECITATION row from each of 85 distinct "
                    "SRC4VC smartphone speakers; CV48/JVS3/Hadou34, exact ordered "
                    "Amitaro references, frozen-control69 same-content targets, "
                    "control69 LoRA69 initialization, complete generative and real "
                    "adversarial losses, LR, sequential optimizer, 170 updates, "
                    "gradient clip, zero condition, and EMA remain fixed"
                ),
            }
        if training_objective == PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE:
            return {
                "slug": "exp252",
                "candidate_id": (
                    "cross-corpus170-pseudoparallel-output-speaker-ema170"
                ),
                "candidate_name": (
                    "EXP-252 / source-aligned targets / final-WAV speaker / EMA"
                ),
                "run_kind": "EXP-252 X-VC final-WAV speaker identity evaluation",
                "result_kind": (
                    "liveconv-exp252-xvc-pseudoparallel-output-speaker-ema/v1"
                ),
                "question": (
                    "Does direct final-WAV target-speaker supervision improve "
                    "X-VC identity without broad content corruption?"
                ),
                "independent_variable": (
                    "relative to EXP-238, add one weight-10 cosine loss between "
                    "the final converted waveform and the assigned real Amitaro "
                    "target in X-VC's frozen ERes2Net speaker space; the exact "
                    "CV48/JSUT85/JVS3/Hadou34 curriculum, source-aligned control69 "
                    "generative targets, real-wave discriminator target, internal "
                    "speaker predictor loss, LoRA69 initialization and scope, LR, "
                    "sequential optimizer, 170 updates, clip, zero condition, and "
                    "EMA remain fixed"
                ),
            }
        return {
            "slug": "exp238",
            "candidate_id": "cross-corpus170-pseudoparallel-real-adv-ema170",
            "candidate_name": (
                "EXP-238 / source-aligned control69 targets / real-adversarial / EMA"
            ),
            "run_kind": "EXP-238 X-VC pseudoparallel retraining evaluation",
            "result_kind": "liveconv-exp238-xvc-pseudoparallel-real-adv-ema/v1",
            "question": (
                "Does replacing unrelated-text target supervision with frozen "
                "control69 same-content targets improve broad X-VC retraining?"
            ),
            "independent_variable": (
                "the exact CV48/JSUT85/JVS3/Hadou34 sources and ordered Amitaro "
                "target references stay fixed, but each generative target changes "
                "from unrelated real target speech plus factorized content losses "
                "to the frozen control69 conversion of that same source under the "
                "assigned Amitaro reference; the original authorized Amitaro WAV "
                "remains only the real side of the unchanged adversarial/feature "
                "objective; control69 LoRA69 initialization, standard complete "
                "generative loss, 170 updates, LR, optimizer, clip, zero condition, "
                "discriminator update, and EMA remain fixed"
            ),
        }

    if source_activity_envelope:
        if (
            manifest_kind != COMMONVOICE_RETENTION_OUTPUT_KIND
            or trainable_target != LORA69_TARGET
            or training_objective != REAL_REFERENCE_ADVERSARIAL_OBJECTIVE
            or not use_adapter_ema
            or optimizer_mode != SEQUENTIAL_OPTIMIZER
            or parameter_anchor
        ):
            raise PostRehearsalError(
                "source activity envelope is admitted only for EXP-186"
            )
        return {
            "slug": "exp196",
            "candidate_id": (
                "cv12-commonvoice48-source-envelope-real-adversarial-ema170"
            ),
            "candidate_name": (
                "EXP-196 / Common Voice 48-speaker retention / source activity "
                "envelope / real-adversarial / EMA"
            ),
            "run_kind": "EXP-196 X-VC source-envelope retention evaluation",
            "result_kind": "liveconv-exp196-xvc-source-envelope-retention-ema/v1",
            "question": (
                "Can an explicit source speech-activity timing objective reduce "
                "tempo and leading-silence forgetting?"
            ),
            "independent_variable": (
                "only a fixed weight-10 L1 penalty between per-utterance-normalized "
                "20 ms/10 ms source and converted absolute-amplitude envelopes is "
                "added; EXP-186 data, targets, control69 LoRA69 initialization, "
                "real-reference adversarial objective, 170 updates, LR, optimizer, "
                "clip, zero condition, and upstream EMA remain fixed"
            ),
        }
    if parameter_anchor:
        if (
            manifest_kind != SELECTIVE_OUTPUT_KIND
            or trainable_target != LORA69_TARGET
            or training_objective != REAL_REFERENCE_ADVERSARIAL_OBJECTIVE
            or not use_adapter_ema
            or optimizer_mode != SEQUENTIAL_OPTIMIZER
        ):
            raise PostRehearsalError(
                "parameter anchor is admitted only for the exact EXP-163 baseline"
            )
        return {
            "slug": "exp181",
            "candidate_id": "cv12-selective-real-adversarial-anchor-ema170",
            "candidate_name": (
                "EXP-181 / selective real-adversarial / control69 anchor / EMA"
            ),
            "run_kind": "EXP-181 X-VC parameter-anchor external evaluation",
            "result_kind": "liveconv-exp181-xvc-parameter-anchor-ema/v1",
            "question": (
                "Can a light control69 parameter anchor retain EXP-163's repair "
                "signal while reducing tempo and ordinary-content forgetting?"
            ),
            "independent_variable": (
                "only a coefficient-1 L2-SP penalty around the immutable control69 "
                "LoRA69 initialization is added to EXP-163; its hard85/easy85 "
                "curriculum, real-reference adversarial objective, 170 sequential "
                "updates, LR, AdamW, clip, scope, zero condition, and upstream EMA "
                "schedule stay fixed"
            ),
        }
    if (
        trainable_target == SPEAKER7_OVERLAY_TARGET
        or training_objective == SPEAKER_PATH_UNPAIRED_OBJECTIVE
    ):
        if (
            manifest_kind != CROSS_CORPUS_UNPAIRED_OUTPUT_KIND
            or trainable_target != SPEAKER7_OVERLAY_TARGET
            or training_objective != SPEAKER_PATH_UNPAIRED_OBJECTIVE
            or not use_adapter_ema
            or optimizer_mode != SEQUENTIAL_OPTIMIZER
            or parameter_anchor
            or source_activity_envelope
        ):
            raise PostRehearsalError(
                "speaker-path overlay requires the exact EXP-233 pilot"
            )
        return {
            "slug": "exp233",
            "candidate_id": "control69-speaker7-real-voice-ema170",
            "candidate_name": "EXP-233 / control69 + speaker7 voice overlay / EMA",
            "run_kind": "EXP-233 X-VC speaker-path voice refinement evaluation",
            "result_kind": "liveconv-exp233-xvc-speaker7-voice-overlay-ema/v1",
            "question": (
                "Can a voice-only speaker-modulation overlay improve X-VC without "
                "retraining the content converter?"
            ),
            "independent_variable": (
                "merge the frozen control69 content converter into the base, then "
                "train a new rank-8 LoRA only on the seven speaker-conditioned "
                "AdaLN linears with the unchanged target-speaker plus real-wave "
                "adversarial/feature loss; the content-cycle loss and all 69 "
                "control69 content/condition LoRA paths are absent from the mutable "
                "graph; exact CV48/JSUT85/JVS3/Hadou34 rows, ordered Amitaro target "
                "multiset, 170 updates, LR, clip, zero condition, discriminator "
                "update, and EMA schedule remain fixed"
            ),
        }
    if optimizer_mode == PCGRAD_CONTENT_VOICE_OPTIMIZER:
        if (
            manifest_kind != CROSS_CORPUS_UNPAIRED_OUTPUT_KIND
            or trainable_target != LORA69_TARGET
            or training_objective != OUTPUT_CYCLE_UNPAIRED_OBJECTIVE
            or not use_adapter_ema
            or parameter_anchor
            or source_activity_envelope
        ):
            raise PostRehearsalError(
                "content/voice PCGrad requires the exact EXP-213 pilot"
            )
        return {
            "slug": "exp228",
            "candidate_id": "cross-corpus170-content-voice-pcgrad-ema170",
            "candidate_name": "EXP-228 / cross-corpus content-voice PCGrad / EMA",
            "run_kind": "EXP-228 X-VC content-voice PCGrad evaluation",
            "result_kind": "liveconv-exp228-xvc-content-voice-pcgrad-ema/v1",
            "question": (
                "Does projecting only conflicting content-versus-voice gradients "
                "retain EXP-213's Hadou/noise gain without its ordinary-JSUT cost?"
            ),
            "independent_variable": (
                "only per-row generator gradient composition changes from EXP-213: "
                "the unchanged weighted final-WAV Whisper MSE is one task and the "
                "unchanged target-speaker plus real-wave adversarial/feature loss is "
                "the other; negative-dot-product components are symmetrically "
                "projected before the same one optimizer step per row; exact "
                "CV48/JSUT85/JVS3/Hadou34 data, Amitaro targets, loss weights, "
                "control69 LoRA69 initialization, 170 updates, LR, clip, zero "
                "condition, discriminator update, and EMA remain fixed"
            ),
        }
    if optimizer_mode == PCGRAD_PAIRED_OPTIMIZER:
        if (
            manifest_kind != SELECTIVE_OUTPUT_KIND
            or trainable_target != LORA69_TARGET
            or training_objective != GENERATIVE_OBJECTIVE
            or use_adapter_ema
        ):
            raise PostRehearsalError(
                "paired PCGrad is admitted only for selective generative LoRA69"
            )
        return {
            "slug": "exp176",
            "candidate_id": "cv12-selective-pcgrad85",
            "candidate_name": "EXP-176 / paired hard-retention PCGrad",
            "run_kind": "EXP-176 X-VC paired PCGrad external evaluation",
            "result_kind": "liveconv-exp176-xvc-paired-pcgrad/v1",
            "question": (
                "Can gradient-conflict surgery preserve normal behavior while "
                "repairing the frozen control69 hard failures?"
            ),
            "independent_variable": (
                "only optimizer gradient composition changes from EXP-150: each "
                "unchanged adjacent hard/easy pair is evaluated at one shared "
                "parameter state, conflicting task-gradient components are "
                "projected away, and the resulting gradients are summed into 85 "
                "pair steps; all 170 sources and targets, initialization, loss, "
                "LR, clip, LoRA69 scope, target references, and zero frame "
                "condition stay fixed"
            ),
        }
    if optimizer_mode != SEQUENTIAL_OPTIMIZER:
        raise PostRehearsalError("unknown optimizer mode")
    if use_adapter_ema:
        if manifest_kind in UNPAIRED_HUMAN_KINDS:
            if (
                trainable_target != LORA69_TARGET
                or training_objective
                not in {
                    FACTORIZED_UNPAIRED_OBJECTIVE,
                    OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
                    CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
                    DISCRETE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
                }
                or optimizer_mode != SEQUENTIAL_OPTIMIZER
                or parameter_anchor
                or source_activity_envelope
            ):
                raise PostRehearsalError(
                    "unpaired human EMA requires the exact factorized LoRA69 pilot"
                )
            if manifest_kind == UNPAIRED_HUMAN_OUTPUT_KIND and training_objective in {
                CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
                DISCRETE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
            }:
                raise PostRehearsalError(
                    "contrastive output cycle requires the fixed cross-corpus data"
                )
            if (
                manifest_kind == CROSS_CORPUS_UNPAIRED_OUTPUT_KIND
                and training_objective
                not in {
                    OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
                    CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
                    DISCRETE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
                }
            ):
                raise PostRehearsalError(
                    "cross-corpus unpaired data requires a fixed output-cycle objective"
                )
            if (
                manifest_kind == CROSS_CORPUS_UNPAIRED_OUTPUT_KIND
                and training_objective == CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE
            ):
                return {
                    "slug": "exp218",
                    "candidate_id": ("cross-corpus170-contrastive-output-cycle-ema170"),
                    "candidate_name": (
                        "EXP-218 / cross-corpus contrastive output-cycle / EMA"
                    ),
                    "run_kind": ("EXP-218 X-VC contrastive output-cycle evaluation"),
                    "result_kind": (
                        "liveconv-exp218-xvc-contrastive-output-cycle-ema/v1"
                    ),
                    "question": (
                        "Can utterance-discriminative final-WAV content training "
                        "avoid the mean-content collapse path left by pointwise MSE?"
                    ),
                    "independent_variable": (
                        "only final-WAV content comparison changes from pointwise "
                        "Whisper-hidden MSE to two-way framewise cosine InfoNCE at "
                        "fixed temperature 0.1 against the next row in the frozen "
                        "mixed schedule; the exact CV48/JSUT85/JVS3/Hadou34 rows, "
                        "ordered Amitaro target multiset, target speaker loss, "
                        "real-wave adversarial objective, control69 LoRA69 "
                        "initialization, 170 updates, LR, optimizer, clip, zero "
                        "condition, and EMA stay fixed"
                    ),
                }
            if (
                manifest_kind == CROSS_CORPUS_UNPAIRED_OUTPUT_KIND
                and training_objective == DISCRETE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE
            ):
                return {
                    "slug": "exp223",
                    "candidate_id": ("cross-corpus170-discrete-output-cycle-ema170"),
                    "candidate_name": (
                        "EXP-223 / cross-corpus discrete output-cycle / EMA"
                    ),
                    "run_kind": ("EXP-223 X-VC discrete output-cycle evaluation"),
                    "result_kind": ("liveconv-exp223-xvc-discrete-output-cycle-ema/v1"),
                    "question": (
                        "Can direct frozen WhisperVQ token classification on the "
                        "final WAV preserve categorical content without MSE "
                        "averaging or arbitrary negatives?"
                    ),
                    "independent_variable": (
                        "only final-WAV content supervision changes from "
                        "source-versus-negative InfoNCE to normalized cross-entropy "
                        "over the frozen 16,384-entry WhisperVQ codebook using the "
                        "row's existing source semantic-token IDs; the exact "
                        "CV48/JSUT85/JVS3/Hadou34 rows, ordered Amitaro target "
                        "multiset, target speaker loss, real-wave adversarial "
                        "objective, control69 LoRA69 initialization, 170 updates, "
                        "LR, optimizer, clip, zero condition, and EMA stay fixed"
                    ),
                }
            if (
                manifest_kind == CROSS_CORPUS_UNPAIRED_OUTPUT_KIND
                and training_objective == OUTPUT_CYCLE_UNPAIRED_OBJECTIVE
            ):
                return {
                    "slug": "exp213",
                    "candidate_id": ("cross-corpus170-unpaired-output-cycle-ema170"),
                    "candidate_name": (
                        "EXP-213 / cross-corpus unpaired output-cycle / EMA"
                    ),
                    "run_kind": ("EXP-213 X-VC cross-corpus output-cycle evaluation"),
                    "result_kind": (
                        "liveconv-exp213-xvc-cross-corpus-output-cycle-ema/v1"
                    ),
                    "question": (
                        "Does replacing the Hadou-only source curriculum with a "
                        "fixed training-only CV/JSUT/JVS/Hadou mixture reduce "
                        "unknown-speaker collapse without losing broad stability?"
                    ),
                    "independent_variable": (
                        "only the 170-row source-side data distribution changes "
                        "from Hadou-only to all frozen training-only Common Voice "
                        "48, all disjoint JSUT85, all JVS3, and 34 spread Hadou "
                        "rows; the exact 170 unrelated Amitaro target-window "
                        "multiset, final-WAV weight-1000 frozen-Whisper content "
                        "cycle, target speaker loss, real-wave adversarial "
                        "objective, control69 LoRA69 initialization, updates, LR, "
                        "optimizer, clip, zero condition, and EMA stay fixed"
                    ),
                }
            if training_objective == OUTPUT_CYCLE_UNPAIRED_OBJECTIVE:
                return {
                    "slug": "exp208",
                    "candidate_id": "human170-unpaired-output-cycle-ema170",
                    "candidate_name": (
                        "EXP-208 / unpaired human output-cycle content / EMA"
                    ),
                    "run_kind": ("EXP-208 X-VC unpaired-human output-cycle evaluation"),
                    "result_kind": (
                        "liveconv-exp208-xvc-unpaired-human-output-cycle-ema/v1"
                    ),
                    "question": (
                        "Can frozen-Whisper content consistency on the final WAV "
                        "close the collapse path left by internal semantic loss?"
                    ),
                    "independent_variable": (
                        "only the content-supervision site changes from EXP-203's "
                        "internal semantic-decoder MSE to weight-1000 frame-aligned "
                        "MSE between source Whisper hidden states and the same "
                        "frozen Whisper encoder applied differentiably to the final "
                        "converted WAV; the 170 unpaired Hadou/Amitaro rows, target "
                        "speaker loss, real-wave adversarial objective, control69 "
                        "LoRA69 initialization, updates, LR, optimizer, clip, zero "
                        "frame condition, and EMA stay fixed"
                    ),
                }
            return {
                "slug": "exp203",
                "candidate_id": "human170-factorized-unpaired-ema170",
                "candidate_name": (
                    "EXP-203 / unpaired human content-identity factorization / EMA"
                ),
                "run_kind": "EXP-203 X-VC unpaired-human external evaluation",
                "result_kind": "liveconv-exp203-xvc-unpaired-human-factorized-ema/v1",
                "question": (
                    "Can alignment-free human source content plus unrelated real "
                    "target identity improve broad X-VC conversion stability?"
                ),
                "independent_variable": (
                    "replace aligned synthetic repair/retention targets with 170 "
                    "speech-active Hadou source windows spread across all 334 train "
                    "IDs; source Whisper content is supervised separately from an "
                    "unrelated-text Amitaro speaker target and real-wave adversarial "
                    "reference, with no waveform alignment, stretch, DTW, or target "
                    "content loss; control69 LoRA69 initialization, 170 updates, LR, "
                    "optimizer, clip, zero frame condition, and EMA stay fixed"
                ),
            }
        if trainable_target == ACOUSTIC_ENCODER_TARGET:
            if (
                manifest_kind != SELECTIVE_OUTPUT_KIND
                or training_objective != REAL_REFERENCE_ADVERSARIAL_OBJECTIVE
            ):
                raise PostRehearsalError(
                    "acoustic encoder EMA is admitted only for EXP-163 data"
                )
            return {
                "slug": "exp198",
                "candidate_id": (
                    "cv12-selective-acoustic-encoder-real-adversarial-ema170"
                ),
                "candidate_name": (
                    "EXP-198 / selective real-adversarial / acoustic encoder / EMA"
                ),
                "run_kind": "EXP-198 X-VC acoustic-encoder evaluation",
                "result_kind": (
                    "liveconv-exp198-xvc-acoustic-encoder-real-adversarial-ema/v1"
                ),
                "question": (
                    "Does adapting the frozen source acoustic representation "
                    "repair cross-condition timing/content residuals that "
                    "converter-only objectives did not?"
                ),
                "independent_variable": (
                    "only the mutable learning target moves from control69's "
                    "69 acoustic-converter LoRA modules to all 21,521,536 source "
                    "acoustic-encoder parameters after merging control69; the "
                    "exact EXP-163 CV/Hadou/JVS hard85/easy85 data, targets, "
                    "real-reference adversarial objective, 170 sequential "
                    "updates, LR, optimizer, clip, zero condition, and upstream "
                    "EMA schedule remain fixed"
                ),
            }
        if trainable_target == SOURCE36_TARGET:
            if (
                manifest_kind != COMMONVOICE_RETENTION_OUTPUT_KIND
                or training_objective != REAL_REFERENCE_ADVERSARIAL_OBJECTIVE
            ):
                raise PostRehearsalError(
                    "source36 EMA is admitted only for EXP-186 retention"
                )
            return {
                "slug": "exp194",
                "candidate_id": ("cv12-commonvoice48-source36-real-adversarial-ema170"),
                "candidate_name": (
                    "EXP-194 / Common Voice 48-speaker retention / "
                    "source36 / real-adversarial / EMA"
                ),
                "run_kind": "EXP-194 X-VC source36 retention evaluation",
                "result_kind": "liveconv-exp194-xvc-source36-retention-ema/v1",
                "question": (
                    "Can restricting EXP-186 updates to the source-side "
                    "attention and feed-forward path reduce forgetting?"
                ),
                "independent_variable": (
                    "only the mutable LoRA path changes from all 69 control69 "
                    "attention/condition/feed-forward modules to the contained "
                    "36 source-side attention and feed-forward modules; EXP-186 "
                    "hard85/easy85 data, 48 speakers, targets, initialization, "
                    "objective, 170 updates, LR, optimizer, clip, zero condition, "
                    "and upstream EMA remain fixed"
                ),
            }
        if (
            manifest_kind
            not in {
                SELECTIVE_OUTPUT_KIND,
                JSUT_RETENTION_OUTPUT_KIND,
                COMMONVOICE_RETENTION_OUTPUT_KIND,
                CONDITIONED_RETENTION_OUTPUT_KIND,
            }
            or trainable_target != LORA69_TARGET
            or training_objective != REAL_REFERENCE_ADVERSARIAL_OBJECTIVE
        ):
            raise PostRehearsalError(
                "adapter EMA is admitted only for selective real-adversarial LoRA69"
            )
        if manifest_kind == JSUT_RETENTION_OUTPUT_KIND:
            return {
                "slug": "exp171",
                "candidate_id": "cv12-jsut-retention-real-adversarial-ema170",
                "candidate_name": ("EXP-171 / JSUT retention + real-adversarial + EMA"),
                "run_kind": "EXP-171 X-VC JSUT retention external evaluation",
                "result_kind": "liveconv-exp171-xvc-jsut-retention-ema/v1",
                "question": (
                    "Does category-balanced Japanese retention data improve the "
                    "surviving EXP-163 method across independent frozen gates?"
                ),
                "independent_variable": (
                    "only the easy85 retention source and frozen control69 target "
                    "domain changes from EXP-163 Common Voice/Hadou/JVS rows to "
                    "precommitted category-balanced JSUT; hard85, target IDs, "
                    "updates, scope, objective, optimizer, clip, condition, and "
                    "upstream EMA remain fixed"
                ),
            }
        if manifest_kind == COMMONVOICE_RETENTION_OUTPUT_KIND:
            return {
                "slug": "exp186",
                "candidate_id": (
                    "cv12-commonvoice48-retention-real-adversarial-ema170"
                ),
                "candidate_name": (
                    "EXP-186 / Common Voice 48-speaker retention + "
                    "real-adversarial + EMA"
                ),
                "run_kind": (
                    "EXP-186 X-VC Common Voice 48-speaker retention external evaluation"
                ),
                "result_kind": ("liveconv-exp186-xvc-commonvoice48-retention-ema/v1"),
                "question": (
                    "Does speaker-balanced retention data improve the surviving "
                    "EXP-163 method across independent frozen gates?"
                ),
                "independent_variable": (
                    "only the easy85 retention source and frozen control69 target "
                    "data changes from EXP-163's mostly one-speaker Hadou mix to "
                    "85 balanced exposures from 48 precommitted Common Voice "
                    "speakers; hard85, target IDs, updates, scope, objective, "
                    "optimizer, clip, condition, and upstream EMA remain fixed"
                ),
            }
        if manifest_kind == CONDITIONED_RETENTION_OUTPUT_KIND:
            return {
                "slug": "exp191",
                "candidate_id": ("cv12-conditioned-retention-real-adversarial-ema170"),
                "candidate_name": (
                    "EXP-191 / condition-balanced control69 retention + "
                    "real-adversarial + EMA"
                ),
                "run_kind": "EXP-191 X-VC conditioned retention evaluation",
                "result_kind": "liveconv-exp191-xvc-conditioned-retention-ema/v1",
                "question": (
                    "Does control69 retention replay on conditioned real sources "
                    "preserve ordinary content while reducing route-condition "
                    "forgetting?"
                ),
                "independent_variable": (
                    "only EXP-186's easy85 source/teacher condition policy changes "
                    "from all-clean to 17 each clean, noise15, tempo1.1, pitch+2, "
                    "and leading150ms; each retention target is a frozen control69 "
                    "output from that conditioned source, while hard85, speaker "
                    "identities, target IDs, updates, scope, objective, optimizer, "
                    "clip, zero condition, and upstream EMA remain fixed"
                ),
            }
        return {
            "slug": "exp163",
            "candidate_id": "cv12-selective-real-adversarial-ema170",
            "candidate_name": ("EXP-163 / selective real-adversarial / upstream EMA"),
            "run_kind": "EXP-163 X-VC upstream-EMA external evaluation",
            "result_kind": "liveconv-exp163-xvc-real-adversarial-ema/v1",
            "question": (
                "Does restoring upstream-configured EMA retain ordinary gains "
                "without the final online adapter's fresh collapse?"
            ),
            "independent_variable": (
                "reported adapter state changes from EXP-158's final online "
                "LoRA69 parameters to the equivalent trainable-parameter EMA "
                "using pinned ema-pytorch 0.7.7 defaults; data, objective, "
                "initialization, optimizer steps, LR, clip, scope, and condition "
                "stay fixed"
            ),
        }
    if training_objective == REAL_REFERENCE_ADVERSARIAL_OBJECTIVE:
        if manifest_kind != SELECTIVE_OUTPUT_KIND or trainable_target != LORA69_TARGET:
            raise PostRehearsalError(
                "real-reference adversarial is admitted only for selective LoRA69"
            )
        return {
            "slug": "exp158",
            "candidate_id": "cv12-selective-retention-real-adversarial170",
            "candidate_name": (
                "EXP-158 / selective retention + real-reference adversarial"
            ),
            "run_kind": "EXP-158 X-VC real-reference adversarial evaluation",
            "result_kind": "liveconv-exp158-xvc-real-reference-adversarial/v1",
            "question": (
                "Can real-reference waveform adversarial and feature matching "
                "suppress collapse while selective targets retain normal behavior?"
            ),
            "independent_variable": (
                "objective adds the pretrained X-VC waveform discriminator and "
                "feature matching, whose real side uses the authorized original "
                "Amitaro target waveform; the exact EXP-150 curriculum, synthetic "
                "repair/retention generative targets, initialization, LR, clip, "
                "LoRA69 scope, update count, and zero frame condition stay fixed"
            ),
        }
    if training_objective != GENERATIVE_OBJECTIVE:
        raise PostRehearsalError("unknown training objective")
    if trainable_target == FULL_CONVERTER_TARGET:
        if manifest_kind != SELECTIVE_OUTPUT_KIND:
            raise PostRehearsalError(
                "full converter is admitted only for selective retention"
            )
        return {
            "slug": "exp154",
            "candidate_id": "cv12-selective-retention-full-converter170",
            "candidate_name": (
                "EXP-154 / selective retention / full acoustic converter"
            ),
            "run_kind": "EXP-154 X-VC full-converter retention evaluation",
            "result_kind": "liveconv-exp154-xvc-full-converter-retention/v1",
            "question": (
                "Can a merged-control69 full acoustic converter generalize "
                "selective hard repair while retaining normal behavior?"
            ),
            "independent_variable": (
                "trainable target changes from control69's 69 LoRA modules to "
                "all acoustic-converter parameters; the exact EXP-150 selective "
                "curriculum, learning targets, initialization function, loss, LR, "
                "clip, target references, update count, and zero frame condition "
                "stay fixed"
            ),
        }
    if trainable_target != LORA69_TARGET:
        raise PostRehearsalError("unknown trainable target")
    if manifest_kind == SELECTIVE_OUTPUT_KIND:
        return {
            "slug": "exp150",
            "candidate_id": "cv12-selective-retention170",
            "candidate_name": (
                "EXP-150 / hard repair + control69 retention distillation"
            ),
            "run_kind": "EXP-150 X-VC selective retention evaluation",
            "result_kind": "liveconv-exp150-xvc-selective-retention/v1",
            "question": (
                "Can base-teacher repair on training-only failures coexist with "
                "control69 retention targets on normal rows?"
            ),
            "independent_variable": (
                "same EXP-146 85-hard/85-easy schedule, but easy rows change "
                "from base-X-VC teacher targets to their frozen non-gross "
                "control69 outputs; initialization, hard targets, loss, LR, "
                "clip, scope, target references, and zero frame condition stay fixed"
            ),
        }
    if manifest_kind == HARD_OUTPUT_KIND:
        return {
            "slug": "exp146",
            "candidate_id": "cv12-hard-negative-curriculum170",
            "candidate_name": (
                "EXP-146 / control69 + failure-triggered 50/50 curriculum"
            ),
            "run_kind": "EXP-146 X-VC hard-negative curriculum evaluation",
            "result_kind": "liveconv-exp146-xvc-hard-negative-curriculum/v1",
            "question": (
                "Does training-only failure-triggered sampling repair control69 "
                "collapse without broad heldout regression?"
            ),
            "independent_variable": (
                "same 170 clean base-teacher updates, resampled from one-pass "
                "coverage to alternating 85 control-hard and 85 domain-stratified "
                "easy positions; initialization, loss, LR, clip, scope, target, "
                "and zero frame condition stay fixed"
            ),
        }
    if manifest_kind != OUTPUT_KIND:
        raise PostRehearsalError("unknown post-rehearsal manifest kind")
    return {
        "slug": "exp141",
        "candidate_id": CANDIDATE_ID,
        "candidate_name": (
            "EXP-141 / control69 + one clean unique teacher rehearsal pass"
        ),
        "run_kind": "EXP-141 X-VC clean post-rehearsal external evaluation",
        "result_kind": RESULT_KIND,
        "question": (
            "Does a clean post-adaptation teacher pass retain control69 while "
            "reducing off-distribution corruption?"
        ),
        "independent_variable": (
            "optimization sequence: fresh-base mixed 835 standard + 209 "
            "unfiltered teacher updates versus frozen control69 initialization "
            "followed by one pass over 170 unique, non-gross teacher outputs "
            "with fixed source-relative distance < 0.5 admission"
        ),
    }


def load_manifest(
    path: Path,
    source_work: Path,
    control_work: Path | None = None,
    diverse_work: Path | None = None,
) -> dict[str, Any]:
    value = load_json(path)
    items = value.get("items")
    kind = value.get("kind")
    if kind == JSUT_RETENTION_OUTPUT_KIND:
        expected_domains = JSUT_EXPECTED_DOMAINS
    elif kind == UNPAIRED_HUMAN_OUTPUT_KIND:
        expected_domains = UNPAIRED_HUMAN_EXPECTED_DOMAINS
    elif kind == CROSS_CORPUS_UNPAIRED_OUTPUT_KIND:
        expected_domains = CROSS_CORPUS_UNPAIRED_EXPECTED_DOMAINS
    elif kind == PSEUDOPARALLEL_OUTPUT_KIND:
        expected_domains = PSEUDOPARALLEL_EXPECTED_DOMAINS
    elif kind == SRC4VC_PSEUDOPARALLEL_OUTPUT_KIND:
        expected_domains = SRC4VC_PSEUDOPARALLEL_EXPECTED_DOMAINS
    elif kind == COMMONVOICE_RETENTION_OUTPUT_KIND:
        expected_domains = COMMONVOICE_RETENTION_EXPECTED_DOMAINS
    elif kind == CONDITIONED_RETENTION_OUTPUT_KIND:
        expected_domains = CONDITIONED_RETENTION_EXPECTED_DOMAINS
    elif kind in {HARD_OUTPUT_KIND, SELECTIVE_OUTPUT_KIND}:
        expected_domains = HARD_EXPECTED_DOMAINS
    else:
        expected_domains = EXPECTED_DOMAINS
    if (
        kind
        not in {
            OUTPUT_KIND,
            HARD_OUTPUT_KIND,
            SELECTIVE_OUTPUT_KIND,
            JSUT_RETENTION_OUTPUT_KIND,
            COMMONVOICE_RETENTION_OUTPUT_KIND,
            CONDITIONED_RETENTION_OUTPUT_KIND,
            UNPAIRED_HUMAN_OUTPUT_KIND,
            CROSS_CORPUS_UNPAIRED_OUTPUT_KIND,
            PSEUDOPARALLEL_OUTPUT_KIND,
            SRC4VC_PSEUDOPARALLEL_OUTPUT_KIND,
        }
        or value.get("composition") != expected_domains
        or not isinstance(items, list)
        or len(items) != EXPECTED_ROWS
    ):
        raise PostRehearsalError("clean rehearsal manifest drifted")
    ids: set[str] = set()
    teachers: set[str] = set()
    domains: Counter[str] = Counter()
    for item in items:
        if not isinstance(item, dict):
            raise PostRehearsalError("clean rehearsal row is malformed")
        identifier = item.get("id")
        teacher_id = item.get("teacher_id")
        source_file = item.get("source_file")
        target_file = item.get("target_file")
        if (
            not isinstance(identifier, str)
            or identifier in ids
            or not isinstance(teacher_id, str)
            or (kind == OUTPUT_KIND and teacher_id in teachers)
            or not isinstance(source_file, str)
            or not isinstance(target_file, str)
            or Path(source_file).is_absolute()
            or Path(target_file).is_absolute()
            or ".." in Path(source_file).parts
            or ".." in Path(target_file).parts
            or not base._is_sha256(item.get("source_sha256"))
            or not base._is_sha256(item.get("target_sha256"))
            or not isinstance(item.get("source_relative_distance"), (int, float))
            or (
                kind not in DIVERSE_RETENTION_KINDS
                and float(item["source_relative_distance"]) >= 0.5
            )
        ):
            raise PostRehearsalError("clean rehearsal identity drifted")
        if kind in {
            HARD_OUTPUT_KIND,
            SELECTIVE_OUTPUT_KIND,
            JSUT_RETENTION_OUTPUT_KIND,
            COMMONVOICE_RETENTION_OUTPUT_KIND,
            CONDITIONED_RETENTION_OUTPUT_KIND,
        } and (
            item.get("curriculum_role") not in {"hard", "easy"}
            or not isinstance(item.get("source_manifest_id"), str)
        ):
            raise PostRehearsalError("hard curriculum identity drifted")
        source_root = (
            diverse_work if item.get("source_root") == "diverse-work" else source_work
        )
        if source_root is None:
            raise PostRehearsalError("diverse retention work is required")
        target_root = source_work
        if kind in UNPAIRED_HUMAN_KINDS:
            if (
                item.get("source_root") != "diverse-work"
                or item.get("target_root") != "diverse-work"
                or item.get("learning_target")
                != "source-content-plus-unpaired-target-identity"
            ):
                raise PostRehearsalError("unpaired human target identity drifted")
            target_root = diverse_work
            if target_root is None:
                raise PostRehearsalError("unpaired human work is required")
        if kind in PSEUDOPARALLEL_KINDS:
            real_target_file = item.get("real_target_file")
            if (
                item.get("source_root") != "source-work"
                or item.get("target_root") != "diverse-work"
                or item.get("learning_target") != PSEUDOPARALLEL_LEARNING_TARGET
                or item.get("target_text") != item.get("source_text")
                or item.get("real_target_root") != "source-work"
                or not isinstance(real_target_file, str)
                or Path(real_target_file).is_absolute()
                or ".." in Path(real_target_file).parts
                or not base._is_sha256(item.get("real_target_sha256"))
            ):
                raise PostRehearsalError(
                    "pseudoparallel learning-target identity drifted"
                )
            target_root = diverse_work
            if target_root is None:
                raise PostRehearsalError("pseudoparallel target work is required")
            real_target = source_work / real_target_file
            if (
                real_target.is_symlink()
                or not real_target.is_file()
                or sha256_file(real_target) != item["real_target_sha256"]
            ):
                raise PostRehearsalError("pseudoparallel real target drifted")
        if kind in {
            SELECTIVE_OUTPUT_KIND,
            JSUT_RETENTION_OUTPUT_KIND,
            COMMONVOICE_RETENTION_OUTPUT_KIND,
            CONDITIONED_RETENTION_OUTPUT_KIND,
        }:
            learning_target = item.get("learning_target")
            base_target_file = item.get("base_teacher_target_file")
            expected_target = (
                REPAIR_TARGET
                if item.get("curriculum_role") == "hard"
                else RETENTION_TARGET
            )
            expected_root = "source-work"
            if learning_target == RETENTION_TARGET:
                expected_root = (
                    "diverse-work"
                    if kind in DIVERSE_RETENTION_KINDS
                    else "control-work"
                )
            requires_base_target = (
                kind == SELECTIVE_OUTPUT_KIND or learning_target == REPAIR_TARGET
            )
            if (
                learning_target != expected_target
                or item.get("target_root") != expected_root
            ):
                raise PostRehearsalError("selective learning-target identity drifted")
            if requires_base_target:
                if (
                    not base._is_sha256(item.get("base_teacher_target_sha256"))
                    or not isinstance(base_target_file, str)
                    or Path(base_target_file).is_absolute()
                    or ".." in Path(base_target_file).parts
                ):
                    raise PostRehearsalError("selective base-target identity drifted")
                base_target = source_work / base_target_file
                if (
                    base_target.is_symlink()
                    or not base_target.is_file()
                    or sha256_file(base_target) != item["base_teacher_target_sha256"]
                ):
                    raise PostRehearsalError("base repair target drifted")
            if learning_target == RETENTION_TARGET:
                target_root = (
                    diverse_work if kind in DIVERSE_RETENTION_KINDS else control_work
                )
                if target_root is None:
                    raise PostRehearsalError("retention work is required")
        for audio, digest in (
            (source_root / source_file, item["source_sha256"]),
            (target_root / target_file, item["target_sha256"]),
        ):
            if (
                audio.is_symlink()
                or not audio.is_file()
                or sha256_file(audio) != digest
            ):
                raise PostRehearsalError(f"clean teacher audio drifted: {identifier}")
        ids.add(identifier)
        teachers.add(teacher_id)
        domains[str(item.get("domain"))] += 1
    if dict(domains) != expected_domains:
        raise PostRehearsalError("clean rehearsal composition drifted")
    return value


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, Path, str]]]:
    manifest = load_manifest(
        arguments.training_manifest,
        arguments.source_work,
        arguments.control_work,
        arguments.diverse_work,
    )
    listening_policy(
        str(manifest["kind"]),
        arguments.trainable_target,
        arguments.training_objective,
        arguments.adapter_ema,
        arguments.optimizer_mode,
        arguments.parameter_anchor,
        arguments.source_activity_envelope,
    )
    evaluation = breadth._load_manifest(
        arguments.evaluation_set,
        kind=breadth.EVALUATION_KIND,
        count=breadth.EVALUATION_COUNT,
    )
    for item in evaluation["items"]:
        source = arguments.source_root / item["filename"]
        if (
            source.is_symlink()
            or not source.is_file()
            or sha256_file(source) != item["sha256"]
        ):
            raise PostRehearsalError(f"external source drifted: {item['id']}")
    targets = method.target_inventory(arguments.pair_root)
    if (
        arguments.control_adapter.is_symlink()
        or not (arguments.control_adapter / "adapter_model.safetensors").is_file()
    ):
        raise PostRehearsalError("control69 adapter is unavailable")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-141 work directory",
    )
    if not arguments.smoke:
        base._require_new_output(
            arguments.listener_dir,
            REPO_ROOT / "artifacts" / "ms3" / "listening",
            "EXP-141 listener directory",
        )
    return manifest, evaluation, targets


def _pair(identifier: str, path: Path, digest: str) -> base.MaterializedPair:
    return base.MaterializedPair(identifier, path, path, digest, digest)


def _batch_from_item(
    model: Any,
    item: Mapping[str, Any],
    *,
    source_work: Path,
    control_work: Path | None,
    diverse_work: Path | None,
    process_audio: Any,
    config: Mapping[str, Any],
    torch: Any,
    device: Any,
    factorized_unpaired: bool = False,
) -> dict[str, Any]:
    source_root = (
        diverse_work if item.get("source_root") == "diverse-work" else source_work
    )
    if source_root is None:
        raise PostRehearsalError("diverse retention work is required")
    source_path = source_root / str(item["source_file"])
    target_root = source_work
    if item.get("target_root") == "control-work":
        target_root = control_work
    elif item.get("target_root") == "diverse-work":
        target_root = diverse_work
    if target_root is None:
        raise PostRehearsalError("control retention work is required")
    target_path = target_root / str(item["target_file"])
    source = base._extract_pair_tensors(
        model,
        _pair(str(item["teacher_id"]), source_path, str(item["source_sha256"])),
        process_audio=process_audio,
        config=config,
        torch=torch,
        device=device,
    )
    target = base._extract_pair_tensors(
        model,
        _pair(str(item["target_id"]), target_path, str(item["target_sha256"])),
        process_audio=process_audio,
        config=config,
        torch=torch,
        device=device,
    )
    return {
        "source_wav": source["source_wav"],
        "semantic_tokens": source["semantic_tokens"],
        "target_wav": target["target_wav"],
        "ssl_feat": (source["ssl_feat"] if factorized_unpaired else target["ssl_feat"]),
    }


def factorized_unpaired_generator_loss(
    outputs: Mapping[str, Any], batch: Mapping[str, Any], *, torch: Any
) -> dict[str, Any]:
    """Keep source content while target identity is learned without alignment."""
    prediction = outputs.get("pred")
    predicted_speaker = outputs.get("pred_sim_feat")
    target_speaker = outputs.get("sim_feat")
    if (
        prediction is None
        or predicted_speaker is None
        or target_speaker is None
        or prediction.shape != batch["ssl_feat"].shape
    ):
        raise PostRehearsalError("factorized human output shape drifted")
    semantic = torch.nn.functional.mse_loss(prediction, batch["ssl_feat"])
    speaker = torch.nn.functional.mse_loss(predicted_speaker, target_speaker)
    loss = (
        role_mix.STANDARD_LOSS_WEIGHTS["mse_loss"] * semantic
        + role_mix.STANDARD_LOSS_WEIGHTS["sim_mse_loss"] * speaker
    )
    if not bool(torch.isfinite(loss)):
        raise PostRehearsalError("factorized human loss is non-finite")
    return {"loss": loss, "semantic": semantic, "speaker": speaker}


def speaker_path_unpaired_generator_loss(
    outputs: Mapping[str, Any], _batch: Mapping[str, Any], *, torch: Any
) -> dict[str, Any]:
    """Train only target-voice prediction on the frozen content converter."""
    predicted_speaker = outputs.get("pred_sim_feat")
    target_speaker = outputs.get("sim_feat")
    if predicted_speaker is None or target_speaker is None:
        raise PostRehearsalError("speaker-path output shape drifted")
    speaker = torch.nn.functional.mse_loss(predicted_speaker, target_speaker)
    loss = role_mix.STANDARD_LOSS_WEIGHTS["sim_mse_loss"] * speaker
    if not bool(torch.isfinite(loss)):
        raise PostRehearsalError("speaker-path voice loss is non-finite")
    return {"loss": loss, "speaker": speaker}


def differentiable_whisper_hidden_states(
    semantic_encoder: Any, waveform: Any, *, torch: Any
) -> Any:
    """Reproduce Whisper's torch log-mel frontend without detaching the WAV."""
    if waveform.ndim != 3 or waveform.shape[1] != 1:
        raise PostRehearsalError("output-cycle waveform shape drifted")
    feature_extractor = getattr(semantic_encoder, "feature_extractor", None)
    encoder = getattr(semantic_encoder, "encoder", None)
    if feature_extractor is None or encoder is None:
        raise PostRehearsalError("output-cycle Whisper encoder is unavailable")
    n_fft = int(getattr(feature_extractor, "n_fft", 0))
    hop_length = int(getattr(feature_extractor, "hop_length", 0))
    mel_values = getattr(feature_extractor, "mel_filters", None)
    if n_fft <= 0 or hop_length <= 0 or mel_values is None:
        raise PostRehearsalError("output-cycle Whisper frontend drifted")

    audio = waveform.squeeze(1).float()
    window = torch.hann_window(n_fft, device=audio.device, dtype=audio.dtype)
    spectrum = torch.stft(
        audio,
        n_fft,
        hop_length,
        window=window,
        return_complex=True,
    )
    magnitudes = spectrum[..., :-1].abs().square()
    mel_filters = torch.as_tensor(
        mel_values,
        device=audio.device,
        dtype=magnitudes.dtype,
    )
    if mel_filters.ndim != 2 or mel_filters.shape[0] != magnitudes.shape[-2]:
        raise PostRehearsalError("output-cycle Whisper mel bank drifted")
    mel_spec = mel_filters.transpose(0, 1) @ magnitudes
    log_spec = torch.clamp(mel_spec, min=1e-10).log10()
    maximum = log_spec.amax(dim=(-2, -1), keepdim=True)
    log_spec = torch.maximum(log_spec, maximum - 8.0)
    log_spec = (log_spec + 4.0) / 4.0
    attention_mask = torch.ones(
        (log_spec.shape[0], log_spec.shape[-1]),
        device=log_spec.device,
        dtype=torch.int32,
    )
    encoded = encoder(input_features=log_spec, attention_mask=attention_mask)
    hidden = getattr(encoded, "whisper_hidden_states_50hz", None)
    if hidden is None or not bool(torch.isfinite(hidden).all()):
        raise PostRehearsalError("output-cycle Whisper hidden state is malformed")
    return hidden


def output_cycle_unpaired_generator_loss(
    outputs: Mapping[str, Any],
    batch: Mapping[str, Any],
    *,
    semantic_encoder: Any,
    torch: Any,
) -> dict[str, Any]:
    """Bind source content to the final converted waveform, not an internal head."""
    reconstruction = outputs.get("recons")
    predicted_speaker = outputs.get("pred_sim_feat")
    target_speaker = outputs.get("sim_feat")
    target_hidden = batch.get("ssl_feat")
    if (
        reconstruction is None
        or predicted_speaker is None
        or target_speaker is None
        or target_hidden is None
    ):
        raise PostRehearsalError("output-cycle human output shape drifted")
    cycle_hidden = differentiable_whisper_hidden_states(
        semantic_encoder, reconstruction, torch=torch
    )
    if cycle_hidden.shape != target_hidden.shape:
        raise PostRehearsalError("output-cycle content shape drifted")
    content = torch.nn.functional.mse_loss(cycle_hidden, target_hidden)
    speaker = torch.nn.functional.mse_loss(predicted_speaker, target_speaker)
    loss = (
        OUTPUT_CYCLE_CONTENT_WEIGHT * content
        + role_mix.STANDARD_LOSS_WEIGHTS["sim_mse_loss"] * speaker
    )
    if not bool(torch.isfinite(loss)):
        raise PostRehearsalError("output-cycle human loss is non-finite")
    return {"loss": loss, "output_cycle_content": content, "speaker": speaker}


def contrastive_output_cycle_unpaired_generator_loss(
    outputs: Mapping[str, Any],
    batch: Mapping[str, Any],
    *,
    semantic_encoder: Any,
    torch: Any,
) -> dict[str, Any]:
    """Make the final WAV identify its source content against another utterance."""
    reconstruction = outputs.get("recons")
    predicted_speaker = outputs.get("pred_sim_feat")
    target_speaker = outputs.get("sim_feat")
    positive_hidden = batch.get("ssl_feat")
    negative_hidden = batch.get("negative_ssl_feat")
    if (
        reconstruction is None
        or predicted_speaker is None
        or target_speaker is None
        or positive_hidden is None
        or negative_hidden is None
        or positive_hidden.shape != negative_hidden.shape
    ):
        raise PostRehearsalError("contrastive output-cycle shape drifted")
    cycle_hidden = differentiable_whisper_hidden_states(
        semantic_encoder, reconstruction, torch=torch
    )
    if cycle_hidden.shape != positive_hidden.shape:
        raise PostRehearsalError("contrastive output-cycle content shape drifted")
    positive_cosine = torch.nn.functional.cosine_similarity(
        cycle_hidden.float(), positive_hidden.float(), dim=-1
    ).mean()
    negative_cosine = torch.nn.functional.cosine_similarity(
        cycle_hidden.float(), negative_hidden.float(), dim=-1
    ).mean()
    logits = torch.stack((positive_cosine, negative_cosine), dim=0).reshape(1, 2)
    logits = logits / CONTRASTIVE_CONTENT_TEMPERATURE
    labels = torch.zeros((1,), device=logits.device, dtype=torch.long)
    content = torch.nn.functional.cross_entropy(logits, labels)
    speaker = torch.nn.functional.mse_loss(predicted_speaker, target_speaker)
    loss = (
        OUTPUT_CYCLE_CONTENT_WEIGHT * content
        + role_mix.STANDARD_LOSS_WEIGHTS["sim_mse_loss"] * speaker
    )
    if not bool(torch.isfinite(loss)):
        raise PostRehearsalError("contrastive output-cycle loss is non-finite")
    return {
        "loss": loss,
        "output_cycle_contrastive_content": content,
        "positive_cosine": positive_cosine,
        "negative_cosine": negative_cosine,
        "speaker": speaker,
    }


def differentiable_whisper_token_logits(
    semantic_encoder: Any, hidden_states_50hz: Any, *, torch: Any
) -> Any:
    """Map differentiable 50 Hz Whisper states to the frozen VQ vocabulary."""
    encoder = getattr(semantic_encoder, "encoder", None)
    pooling = getattr(encoder, "pooling_layer", None)
    codebook = getattr(encoder, "codebook", None)
    codebook_weight = getattr(codebook, "weight", None)
    if (
        encoder is None
        or pooling is None
        or codebook_weight is None
        or hidden_states_50hz.ndim != 3
        or codebook_weight.ndim != 2
        or codebook_weight.shape[0] != 16_384
        or codebook_weight.shape[1] != hidden_states_50hz.shape[1]
    ):
        raise PostRehearsalError("discrete output-cycle codebook drifted")
    # WhisperVQ exposes its saved pre-pooling states as [batch, channel, time].
    # Keep that official channel-first boundary through Pool1d and transpose only
    # for the token-classification view below.
    pooled = pooling(hidden_states_50hz).transpose(1, 2)
    flat = pooled.float().reshape(-1, pooled.shape[-1])
    frozen_codebook = codebook_weight.detach().float()
    distances = (
        flat.square().sum(dim=1, keepdim=True)
        + frozen_codebook.square().sum(dim=1).unsqueeze(0)
        - 2.0 * flat @ frozen_codebook.transpose(0, 1)
    )
    logits = -distances.reshape(
        pooled.shape[0], pooled.shape[1], frozen_codebook.shape[0]
    )
    if not bool(torch.isfinite(logits).all()):
        raise PostRehearsalError("discrete output-cycle logits are non-finite")
    return logits


def discrete_output_cycle_unpaired_generator_loss(
    outputs: Mapping[str, Any],
    batch: Mapping[str, Any],
    *,
    semantic_encoder: Any,
    torch: Any,
) -> dict[str, Any]:
    """Classify source WhisperVQ tokens directly from the final converted WAV."""
    reconstruction = outputs.get("recons")
    predicted_speaker = outputs.get("pred_sim_feat")
    target_speaker = outputs.get("sim_feat")
    target_tokens = batch.get("semantic_tokens")
    if (
        reconstruction is None
        or predicted_speaker is None
        or target_speaker is None
        or target_tokens is None
        or target_tokens.ndim != 2
        or target_tokens.dtype != torch.long
    ):
        raise PostRehearsalError("discrete output-cycle shape drifted")
    hidden_states = differentiable_whisper_hidden_states(
        semantic_encoder, reconstruction, torch=torch
    )
    logits = differentiable_whisper_token_logits(
        semantic_encoder, hidden_states, torch=torch
    )
    if logits.shape[:2] != target_tokens.shape:
        raise PostRehearsalError("discrete output-cycle token shape drifted")
    vocabulary_size = logits.shape[-1]
    cross_entropy = torch.nn.functional.cross_entropy(
        logits.reshape(-1, vocabulary_size), target_tokens.reshape(-1)
    )
    content = cross_entropy / math.log(float(vocabulary_size))
    speaker = torch.nn.functional.mse_loss(predicted_speaker, target_speaker)
    loss = (
        OUTPUT_CYCLE_CONTENT_WEIGHT * content
        + role_mix.STANDARD_LOSS_WEIGHTS["sim_mse_loss"] * speaker
    )
    if not bool(torch.isfinite(loss)):
        raise PostRehearsalError("discrete output-cycle loss is non-finite")
    with torch.no_grad():
        accuracy = (logits.argmax(dim=-1) == target_tokens).float().mean()
    return {
        "loss": loss,
        "output_cycle_discrete_content": content,
        "output_cycle_token_cross_entropy": cross_entropy,
        "output_cycle_token_accuracy": accuracy,
        "speaker": speaker,
    }


def validate_output_cycle_frontend(
    semantic_encoder: Any,
    source_waveform: Any,
    expected_hidden: Any,
    *,
    torch: Any,
    maximum_tolerance: float = 1e-3,
) -> dict[str, float]:
    """Prove the differentiable frontend matches X-VC's detached helper."""
    with torch.no_grad():
        actual = differentiable_whisper_hidden_states(
            semantic_encoder, source_waveform, torch=torch
        )
    if actual.shape != expected_hidden.shape:
        raise PostRehearsalError("output-cycle frontend equivalence shape drifted")
    distance = (actual.float() - expected_hidden.float()).abs()
    maximum = float(distance.max().cpu())
    mean = float(distance.mean().cpu())
    if not math.isfinite(maximum) or maximum > maximum_tolerance:
        raise PostRehearsalError(
            f"output-cycle frontend mismatch: maximum={maximum:.8f}"
        )
    return {
        "maximum_absolute_hidden_difference": maximum,
        "mean_absolute_hidden_difference": mean,
        "maximum_tolerance": maximum_tolerance,
    }


def source_receipt_identities(
    manifest_kind: str, source_work: Path, training_manifest: Path
) -> dict[str, str | None]:
    """Bind either a predecessor result or the standalone human curriculum."""
    if manifest_kind in UNPAIRED_HUMAN_KINDS | PSEUDOPARALLEL_KINDS:
        return {
            "source_result_sha256": None,
            "unpaired_human_curriculum_sha256": sha256_file(training_manifest),
        }
    return {
        "source_result_sha256": sha256_file(source_work / "result.json"),
        "unpaired_human_curriculum_sha256": None,
    }


def _set_converter_training_only(model: Any) -> list[Any]:
    model.eval()
    converter = getattr(model, CONVERTER_PREFIX, None)
    if converter is None:
        raise PostRehearsalError("X-VC acoustic converter is unavailable")
    converter.train(True)
    trainable: list[Any] = []
    for name, parameter in model.named_parameters():
        selected = name.startswith(CONVERTER_PREFIX + ".")
        parameter.requires_grad_(selected)
        if selected:
            trainable.append(parameter)
    if (
        sum(parameter.numel() for parameter in trainable)
        != EXPECTED_CONVERTER_PARAMETERS
    ):
        raise PostRehearsalError("full converter parameter count drifted")
    return trainable


def _set_acoustic_encoder_training_only(model: Any) -> list[Any]:
    model.eval()
    encoder = getattr(model, ACOUSTIC_ENCODER_PREFIX, None)
    if encoder is None:
        raise PostRehearsalError("X-VC acoustic encoder is unavailable")
    encoder.train(True)
    trainable: list[Any] = []
    for name, parameter in model.named_parameters():
        selected = name.startswith(ACOUSTIC_ENCODER_PREFIX + ".")
        parameter.requires_grad_(selected)
        if selected:
            trainable.append(parameter)
    if (
        sum(parameter.numel() for parameter in trainable)
        != EXPECTED_ACOUSTIC_ENCODER_PARAMETERS
    ):
        raise PostRehearsalError("acoustic encoder parameter count drifted")
    return trainable


def _set_existing_adapter_scope_training_only(
    model: Any, scope: Mapping[str, object]
) -> list[Any]:
    """Restrict an already-loaded control69 adapter to one contained scope."""

    targets = tuple(str(item) for item in scope.get("target_modules", []))
    if not targets:
        raise PostRehearsalError("adapter scope has no target modules")
    model.eval()
    active = 0
    for name, module in model.named_modules():
        selected = (".lora_A" in name or ".lora_B" in name) and any(
            f".{target}." in f".{name}." for target in targets
        )
        if selected:
            module.train(True)
            active += 1
    trainable: list[Any] = []
    for name, parameter in model.named_parameters():
        selected = (".lora_A." in name or ".lora_B." in name) and any(
            f".{target}." in f".{name}." for target in targets
        )
        parameter.requires_grad_(selected)
        if selected:
            trainable.append(parameter)
    expected = int(scope["trainable_parameter_count"])
    if active == 0 or sum(parameter.numel() for parameter in trainable) != expected:
        raise PostRehearsalError("existing adapter scope topology drifted")
    return trainable


def _converter_snapshot(model: Any, torch: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for name, parameter in model.named_parameters():
        if not name.startswith(CONVERTER_PREFIX + "."):
            continue
        relative = name.removeprefix(CONVERTER_PREFIX + ".")
        value = parameter.detach().cpu().contiguous()
        if not bool(torch.isfinite(value).all()):
            raise PostRehearsalError(f"non-finite converter parameter: {relative}")
        snapshot[relative] = value
    if (
        sum(value.numel() for value in snapshot.values())
        != EXPECTED_CONVERTER_PARAMETERS
    ):
        raise PostRehearsalError("converter snapshot parameter count drifted")
    return snapshot


def save_converter_checkpoint(
    model: Any, directory: Path, torch: Any
) -> dict[str, Any]:
    from safetensors.torch import load_file, save_file

    directory.mkdir()
    weights = directory / "converter-parameters.safetensors"
    snapshot = _converter_snapshot(model, torch)
    save_file(
        snapshot,
        str(weights),
        metadata={"format": "merged_control69_converter_parameters_v1"},
    )
    reloaded = load_file(str(weights), device="cpu")
    if set(reloaded) != set(snapshot) or any(
        not torch.equal(reloaded[name], snapshot[name]) for name in snapshot
    ):
        raise PostRehearsalError("converter checkpoint serialization drifted")
    metadata = {
        "schema_version": 1,
        "kind": CONVERTER_CHECKPOINT_KIND,
        "initialization": "base-xvc-plus-merged-control69",
        "parameter_prefix": CONVERTER_PREFIX,
        "tensor_count": len(snapshot),
        "parameter_count": EXPECTED_CONVERTER_PARAMETERS,
        "weights_sha256": sha256_file(weights),
    }
    method._write_json(directory / "converter.json", metadata)
    return metadata


def load_converter_checkpoint(
    model: Any, directory: Path, *, torch: Any, device: Any
) -> dict[str, Any]:
    from safetensors.torch import load_file

    metadata_path = directory / "converter.json"
    weights = directory / "converter-parameters.safetensors"
    if (
        directory.is_symlink()
        or metadata_path.is_symlink()
        or weights.is_symlink()
        or not metadata_path.is_file()
        or not weights.is_file()
    ):
        raise PostRehearsalError("full converter checkpoint is unavailable")
    metadata = load_json(metadata_path)
    if (
        metadata.get("kind") != CONVERTER_CHECKPOINT_KIND
        or metadata.get("parameter_prefix") != CONVERTER_PREFIX
        or metadata.get("parameter_count") != EXPECTED_CONVERTER_PARAMETERS
        or metadata.get("weights_sha256") != sha256_file(weights)
    ):
        raise PostRehearsalError("full converter checkpoint identity drifted")
    stored = load_file(str(weights), device="cpu")
    destinations = {
        name.removeprefix(CONVERTER_PREFIX + "."): parameter
        for name, parameter in model.named_parameters()
        if name.startswith(CONVERTER_PREFIX + ".")
    }
    if (
        set(stored) != set(destinations)
        or sum(value.numel() for value in stored.values())
        != EXPECTED_CONVERTER_PARAMETERS
    ):
        raise PostRehearsalError("full converter tensor set drifted")
    with torch.no_grad():
        for name, value in stored.items():
            destination = destinations[name]
            if tuple(value.shape) != tuple(destination.shape):
                raise PostRehearsalError(f"converter shape drifted: {name}")
            destination.copy_(value.to(device=device, dtype=destination.dtype))
    actual = _converter_snapshot(model, torch)
    if any(not torch.equal(actual[name], stored[name]) for name in stored):
        raise PostRehearsalError("full converter checkpoint reload is not exact")
    return metadata


def _acoustic_encoder_snapshot(model: Any, torch: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for name, parameter in model.named_parameters():
        if not name.startswith(ACOUSTIC_ENCODER_PREFIX + "."):
            continue
        relative = name.removeprefix(ACOUSTIC_ENCODER_PREFIX + ".")
        value = parameter.detach().cpu().contiguous()
        if not bool(torch.isfinite(value).all()):
            raise PostRehearsalError(
                f"non-finite acoustic encoder parameter: {relative}"
            )
        snapshot[relative] = value
    if (
        sum(value.numel() for value in snapshot.values())
        != EXPECTED_ACOUSTIC_ENCODER_PARAMETERS
    ):
        raise PostRehearsalError("acoustic encoder snapshot count drifted")
    return snapshot


def save_acoustic_encoder_checkpoint(
    model: Any, directory: Path, torch: Any
) -> dict[str, Any]:
    from safetensors.torch import load_file, save_file

    directory.mkdir()
    weights = directory / "acoustic-encoder-parameters.safetensors"
    snapshot = _acoustic_encoder_snapshot(model, torch)
    save_file(
        snapshot,
        str(weights),
        metadata={"format": "merged_control69_acoustic_encoder_parameters_v1"},
    )
    reloaded = load_file(str(weights), device="cpu")
    if set(reloaded) != set(snapshot) or any(
        not torch.equal(reloaded[name], snapshot[name]) for name in snapshot
    ):
        raise PostRehearsalError("acoustic encoder serialization drifted")
    metadata = {
        "schema_version": 1,
        "kind": ACOUSTIC_ENCODER_CHECKPOINT_KIND,
        "initialization": "base-xvc-plus-merged-control69",
        "parameter_prefix": ACOUSTIC_ENCODER_PREFIX,
        "tensor_count": len(snapshot),
        "parameter_count": EXPECTED_ACOUSTIC_ENCODER_PARAMETERS,
        "weights_sha256": sha256_file(weights),
    }
    method._write_json(directory / "acoustic-encoder.json", metadata)
    return metadata


def load_acoustic_encoder_checkpoint(
    model: Any, directory: Path, *, torch: Any, device: Any
) -> dict[str, Any]:
    from safetensors.torch import load_file

    metadata_path = directory / "acoustic-encoder.json"
    weights = directory / "acoustic-encoder-parameters.safetensors"
    if (
        directory.is_symlink()
        or metadata_path.is_symlink()
        or weights.is_symlink()
        or not metadata_path.is_file()
        or not weights.is_file()
    ):
        raise PostRehearsalError("acoustic encoder checkpoint is unavailable")
    metadata = load_json(metadata_path)
    if (
        metadata.get("kind") != ACOUSTIC_ENCODER_CHECKPOINT_KIND
        or metadata.get("parameter_prefix") != ACOUSTIC_ENCODER_PREFIX
        or metadata.get("parameter_count") != EXPECTED_ACOUSTIC_ENCODER_PARAMETERS
        or metadata.get("weights_sha256") != sha256_file(weights)
    ):
        raise PostRehearsalError("acoustic encoder checkpoint identity drifted")
    stored = load_file(str(weights), device="cpu")
    destinations = {
        name.removeprefix(ACOUSTIC_ENCODER_PREFIX + "."): parameter
        for name, parameter in model.named_parameters()
        if name.startswith(ACOUSTIC_ENCODER_PREFIX + ".")
    }
    if (
        set(stored) != set(destinations)
        or sum(value.numel() for value in stored.values())
        != EXPECTED_ACOUSTIC_ENCODER_PARAMETERS
    ):
        raise PostRehearsalError("acoustic encoder tensor set drifted")
    with torch.no_grad():
        for name, value in stored.items():
            destination = destinations[name]
            if tuple(value.shape) != tuple(destination.shape):
                raise PostRehearsalError(f"acoustic encoder shape drifted: {name}")
            destination.copy_(value.to(device=device, dtype=destination.dtype))
    actual = _acoustic_encoder_snapshot(model, torch)
    if any(not torch.equal(actual[name], stored[name]) for name in stored):
        raise PostRehearsalError("acoustic encoder checkpoint reload is not exact")
    return metadata


class AdapterEMA:
    """Exact ema-pytorch 0.7.7 default schedule over mutable adapter tensors."""

    def __init__(self, model: Any, torch: Any) -> None:
        self.torch = torch
        self.parameters = {
            name: parameter
            for name, parameter in model.named_parameters()
            if parameter.requires_grad and bool(torch.is_floating_point(parameter))
        }
        if not self.parameters:
            raise PostRehearsalError("adapter EMA has no mutable tensors")
        self.shadow = {
            name: parameter.detach().clone()
            for name, parameter in self.parameters.items()
        }
        self.step = 0
        self.initted = False
        self.copy_updates = 0
        self.moving_average_updates = 0
        self.last_decay = 0.0

    def _copy(self) -> None:
        with self.torch.no_grad():
            for name, parameter in self.parameters.items():
                self.shadow[name].copy_(parameter.detach())
        self.copy_updates += 1

    def update(self) -> None:
        current_step = self.step
        self.step += 1
        if not self.initted:
            self._copy()
            self.initted = True
            return
        if current_step % EMA_UPDATE_EVERY != 0:
            return
        if current_step <= EMA_UPDATE_AFTER_STEP:
            self._copy()
            return
        epoch = max(self.step - EMA_UPDATE_AFTER_STEP - 1, 0)
        decay = 1.0 - (1.0 + epoch / EMA_INV_GAMMA) ** (-EMA_POWER)
        decay = min(max(decay, EMA_MIN_VALUE), EMA_BETA)
        with self.torch.no_grad():
            for name, parameter in self.parameters.items():
                self.shadow[name].lerp_(parameter.detach(), 1.0 - decay)
        self.moving_average_updates += 1
        self.last_decay = decay

    def copy_to(self) -> None:
        with self.torch.no_grad():
            for name, parameter in self.parameters.items():
                parameter.copy_(self.shadow[name])

    def receipt(self) -> dict[str, Any]:
        return {
            "implementation": EMA_IMPLEMENTATION,
            "beta": EMA_BETA,
            "update_after_step": EMA_UPDATE_AFTER_STEP,
            "update_every": EMA_UPDATE_EVERY,
            "inv_gamma": EMA_INV_GAMMA,
            "power": EMA_POWER,
            "min_value": EMA_MIN_VALUE,
            "calls": self.step,
            "copy_updates": self.copy_updates,
            "moving_average_updates": self.moving_average_updates,
            "last_decay": self.last_decay,
            "tensor_count": len(self.shadow),
            "parameter_count": sum(value.numel() for value in self.shadow.values()),
        }


def smoke_rows(
    manifest: Mapping[str, Any],
    optimizer_mode: str = SEQUENTIAL_OPTIMIZER,
    parameter_anchor: bool = False,
    require_hard_easy: bool = False,
) -> list[Mapping[str, Any]]:
    items = manifest["items"]
    if optimizer_mode == PCGRAD_PAIRED_OPTIMIZER:
        return items[:2]
    if parameter_anchor:
        return items[:2]
    if manifest.get("kind") in UNPAIRED_HUMAN_KINDS | PSEUDOPARALLEL_KINDS:
        return items[:2]
    if manifest.get("kind") not in DIVERSE_RETENTION_KINDS and not require_hard_easy:
        return items[:1]
    hard = next(item for item in items if item.get("curriculum_role") == "hard")
    easy = next(item for item in items if item.get("curriculum_role") == "easy")
    return [hard, easy]


def paired_hard_easy_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Validate and return the frozen selective curriculum as hard/easy pairs."""

    if len(rows) % 2:
        raise PostRehearsalError("paired PCGrad requires an even row count")
    pairs = []
    for offset in range(0, len(rows), 2):
        hard, easy = rows[offset : offset + 2]
        if (
            hard.get("curriculum_role") != "hard"
            or hard.get("learning_target") != REPAIR_TARGET
            or easy.get("curriculum_role") != "easy"
            or easy.get("learning_target") != RETENTION_TARGET
        ):
            raise PostRehearsalError(
                f"paired PCGrad role order drifted at rows {offset}/{offset + 1}"
            )
        pairs.append((hard, easy))
    return pairs


def project_conflicting_pair(
    hard_gradients: Sequence[Any],
    easy_gradients: Sequence[Any],
    *,
    torch: Any,
) -> tuple[list[Any], dict[str, float | bool]]:
    """Apply symmetric two-task PCGrad and return the summed update gradient."""

    if not hard_gradients or len(hard_gradients) != len(easy_gradients):
        raise PostRehearsalError("paired PCGrad gradient sets drifted")
    dot = sum(
        (hard * easy).sum()
        for hard, easy in zip(hard_gradients, easy_gradients, strict=True)
    )
    hard_norm_sq = sum(gradient.square().sum() for gradient in hard_gradients)
    easy_norm_sq = sum(gradient.square().sum() for gradient in easy_gradients)
    scalars = (dot, hard_norm_sq, easy_norm_sq)
    if any(not bool(torch.isfinite(value)) for value in scalars):
        raise PostRehearsalError("paired PCGrad geometry is non-finite")
    dot_value = float(dot.detach().cpu())
    hard_norm_value = float(hard_norm_sq.detach().cpu())
    easy_norm_value = float(easy_norm_sq.detach().cpu())
    denominator = math.sqrt(hard_norm_value * easy_norm_value)
    cosine = dot_value / denominator if denominator > 0.0 else 0.0
    conflict = dot_value < 0.0
    if conflict:
        if hard_norm_value == 0.0 or easy_norm_value == 0.0:
            raise PostRehearsalError("conflicting PCGrad task has zero norm")
        hard_scale = dot / easy_norm_sq
        easy_scale = dot / hard_norm_sq
        merged = [
            hard - hard_scale * easy + easy - easy_scale * hard
            for hard, easy in zip(hard_gradients, easy_gradients, strict=True)
        ]
    else:
        merged = [
            hard + easy
            for hard, easy in zip(hard_gradients, easy_gradients, strict=True)
        ]
    return merged, {
        "conflict": conflict,
        "dot": dot_value,
        "cosine": cosine,
        "hard_norm": math.sqrt(hard_norm_value),
        "easy_norm": math.sqrt(easy_norm_value),
    }


def content_voice_task_losses(
    generator_losses: Mapping[str, Any], adversarial_loss: Any, *, torch: Any
) -> tuple[Any, Any]:
    """Split EXP-213's unchanged generator loss into content and voice tasks."""
    generator_loss = generator_losses.get("loss")
    content = generator_losses.get("output_cycle_content")
    speaker = generator_losses.get("speaker")
    if generator_loss is None or content is None or speaker is None:
        raise PostRehearsalError("content/voice PCGrad loss boundary drifted")
    content_task = OUTPUT_CYCLE_CONTENT_WEIGHT * content
    voice_task = (
        role_mix.STANDARD_LOSS_WEIGHTS["sim_mse_loss"] * speaker + adversarial_loss
    )
    total = content_task + voice_task
    expected = generator_loss + adversarial_loss
    if (
        not bool(torch.isfinite(total))
        or not bool(torch.isfinite(expected))
        or not bool(torch.allclose(total, expected, rtol=1e-5, atol=1e-5))
    ):
        raise PostRehearsalError("content/voice PCGrad task sum drifted")
    return content_task, voice_task


def content_voice_pcgrad_adversarial_update(
    trained: Any,
    discriminator: Any,
    generator_optimizer: Any,
    discriminator_optimizer: Any,
    trainable: Sequence[Any],
    batch: Mapping[str, Any],
    *,
    torch: Any,
) -> tuple[dict[str, float], dict[str, float | bool]]:
    """Run one unchanged EXP-213 update with content/voice gradient surgery."""
    base._set_adapter_training_only(trained)
    discriminator.train()
    generator_optimizer.zero_grad(set_to_none=True)
    discriminator_optimizer.zero_grad(set_to_none=True)
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        outputs = trained(dict(batch))
        reconstruction = outputs.get("recons") if isinstance(outputs, dict) else None
        if reconstruction is None or not bool(torch.isfinite(reconstruction).all()):
            raise PostRehearsalError("content/voice PCGrad reconstruction is malformed")
        discriminator_real = batch["target_wav"][..., : reconstruction.shape[-1]]
        outputs["audios"] = discriminator_real
        discriminator_losses = discriminator.discriminative_loss(outputs)
        discriminator_loss = breadth._finite_loss(
            discriminator_losses.get("loss"),
            torch=torch,
            label="X-VC discriminator loss",
        )
    discriminator_loss.backward()
    discriminator_norm = torch.nn.utils.clip_grad_norm_(
        discriminator.parameters(), base.GRADIENT_CLIP_NORM
    )
    if not math.isfinite(float(discriminator_norm.detach().cpu())):
        raise PostRehearsalError(
            "content/voice PCGrad discriminator norm is non-finite"
        )
    discriminator_optimizer.step()

    for parameter in discriminator.parameters():
        parameter.requires_grad_(False)
    try:
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            outputs["audios"] = batch["target_wav"][..., : reconstruction.shape[-1]]
            generator_losses = output_cycle_unpaired_generator_loss(
                outputs,
                batch,
                semantic_encoder=trained.semantic_encoder,
                torch=torch,
            )
            outputs["audios"] = discriminator_real
            adversarial_losses = discriminator.adversarial_loss(outputs)
            adversarial_loss = breadth._finite_loss(
                adversarial_losses.get("loss"),
                torch=torch,
                label="X-VC adversarial loss",
            )
            content_task, voice_task = content_voice_task_losses(
                generator_losses, adversarial_loss, torch=torch
            )
            total_loss = content_task + voice_task
        task_gradients: list[list[Any]] = []
        for task_index, task_loss in enumerate((content_task, voice_task)):
            gradients = torch.autograd.grad(
                task_loss,
                trainable,
                retain_graph=task_index == 0,
                allow_unused=True,
            )
            task_gradients.append(
                [
                    gradient.detach()
                    if gradient is not None
                    else torch.zeros_like(parameter)
                    for parameter, gradient in zip(trainable, gradients, strict=True)
                ]
            )
        merged_gradients, raw_geometry = project_conflicting_pair(
            task_gradients[0], task_gradients[1], torch=torch
        )
        geometry = {
            "conflict": raw_geometry["conflict"],
            "dot": raw_geometry["dot"],
            "cosine": raw_geometry["cosine"],
            "content_norm": raw_geometry["hard_norm"],
            "voice_norm": raw_geometry["easy_norm"],
        }
        generator_optimizer.zero_grad(set_to_none=True)
        for parameter, gradient in zip(trainable, merged_gradients, strict=True):
            parameter.grad = gradient
        generator_norm = torch.nn.utils.clip_grad_norm_(
            trainable, base.GRADIENT_CLIP_NORM
        )
        if not math.isfinite(float(generator_norm.detach().cpu())):
            raise PostRehearsalError(
                "content/voice PCGrad generator norm is non-finite"
            )
        generator_optimizer.step()
    finally:
        for parameter in discriminator.parameters():
            parameter.requires_grad_(True)

    metrics = {
        "total": float(total_loss.detach().cpu()),
        "generative": float(generator_losses["loss"].detach().cpu()),
        "discriminator": float(discriminator_loss.detach().cpu()),
        "adversarial_generator": float(adversarial_losses["adv_gen_loss"]),
        "adversarial_feature": float(adversarial_losses["adv_feat_loss"]),
        "generator_output_cycle_content": float(
            generator_losses["output_cycle_content"].detach().cpu()
        ),
        "generator_speaker": float(generator_losses["speaker"].detach().cpu()),
    }
    return metrics, geometry


def parameter_anchor_regularizer(
    parameters: Sequence[Any],
    anchors: Sequence[Any],
    *,
    torch: Any,
    coefficient: float = PARAMETER_ANCHOR_COEFFICIENT,
) -> tuple[Any, dict[str, float]]:
    """Return a finite L2-SP loss around the immutable control69 parameters."""

    if (
        not parameters
        or len(parameters) != len(anchors)
        or not math.isfinite(coefficient)
        or coefficient <= 0.0
    ):
        raise PostRehearsalError("parameter anchor identity drifted")
    squared_distance = sum(
        (parameter.float() - anchor.float()).square().sum()
        for parameter, anchor in zip(parameters, anchors, strict=True)
    )
    loss = squared_distance * (0.5 * coefficient)
    if not bool(torch.isfinite(loss)):
        raise PostRehearsalError("parameter anchor loss is non-finite")
    return loss, {
        "parameter_anchor_loss": float(loss.detach().cpu()),
        "parameter_anchor_squared_distance": float(squared_distance.detach().cpu()),
    }


def source_activity_envelope_regularizer(
    reconstruction: Any,
    batch: Mapping[str, Any],
    *,
    torch: Any,
    weight: float = SOURCE_ACTIVITY_ENVELOPE_WEIGHT,
) -> tuple[Any, dict[str, float]]:
    """Preserve source speech-activity timing without matching source timbre."""

    source = batch.get("source_wav")
    if (
        source is None
        or reconstruction.ndim != 3
        or source.ndim != 3
        or reconstruction.shape[:2] != source.shape[:2]
        or reconstruction.shape[-1] > source.shape[-1]
        or weight <= 0.0
    ):
        raise PostRehearsalError("source activity envelope identity drifted")
    source = source[..., : reconstruction.shape[-1]].float()
    converted = reconstruction.float()
    source_envelope = torch.nn.functional.avg_pool1d(
        source.abs(), kernel_size=320, stride=160
    )
    converted_envelope = torch.nn.functional.avg_pool1d(
        converted.abs(), kernel_size=320, stride=160
    )
    epsilon = 1e-4
    source_envelope = source_envelope / source_envelope.mean(
        dim=-1, keepdim=True
    ).clamp_min(epsilon)
    converted_envelope = converted_envelope / converted_envelope.mean(
        dim=-1, keepdim=True
    ).clamp_min(epsilon)
    distance = torch.nn.functional.l1_loss(converted_envelope, source_envelope)
    loss = distance * weight
    if not bool(torch.isfinite(loss)):
        raise PostRehearsalError("source activity envelope loss is non-finite")
    return loss, {
        "source_activity_envelope_distance": float(distance.detach().cpu()),
        "source_activity_envelope_loss": float(loss.detach().cpu()),
    }


def differentiable_xvc_speaker_embedding(
    speaker_encoder: Any,
    waveform: Any,
    *,
    torch: Any,
) -> Any:
    """Run X-VC's frozen ERes2Net without its evaluation-time detach."""
    extractor = getattr(speaker_encoder, "feat_extractor", None)
    model = getattr(speaker_encoder, "model", None)
    if (
        extractor is None
        or model is None
        or waveform.ndim != 3
        or waveform.shape[1] != 1
    ):
        raise PostRehearsalError("output speaker identity encoder is unavailable")
    with torch.autocast(device_type="cuda", enabled=False):
        mono = waveform.squeeze(1).float()
        features = torch.stack([extractor(item) for item in mono])
        embedding, _latent = model(features)
        embedding = torch.nn.functional.normalize(embedding.float(), dim=-1)
    if embedding.ndim != 2 or not bool(torch.isfinite(embedding).all()):
        raise PostRehearsalError("output speaker identity embedding is malformed")
    return embedding


def output_speaker_identity_regularizer(
    reconstruction: Any,
    target_waveform: Any,
    *,
    speaker_encoder: Any,
    torch: Any,
    weight: float = OUTPUT_SPEAKER_IDENTITY_WEIGHT,
) -> tuple[Any, dict[str, float]]:
    """Pull the final converted WAV toward the real target speaker embedding."""
    if not math.isfinite(weight) or weight <= 0.0:
        raise PostRehearsalError("output speaker identity weight is invalid")
    output_embedding = differentiable_xvc_speaker_embedding(
        speaker_encoder, reconstruction, torch=torch
    )
    target_waveform = target_waveform.to(
        device=reconstruction.device, dtype=torch.float32
    )
    with torch.no_grad():
        target_embedding = differentiable_xvc_speaker_embedding(
            speaker_encoder, target_waveform, torch=torch
        )
    if output_embedding.shape != target_embedding.shape:
        raise PostRehearsalError("output speaker identity shape drifted")
    similarity = torch.nn.functional.cosine_similarity(
        output_embedding, target_embedding, dim=-1
    ).mean()
    distance = 1.0 - similarity
    loss = weight * distance
    if not bool(torch.isfinite(loss)):
        raise PostRehearsalError("output speaker identity loss is non-finite")
    return loss, {
        "output_speaker_identity_similarity": float(similarity.detach().cpu()),
        "output_speaker_identity_distance": float(distance.detach().cpu()),
        "output_speaker_identity_loss": float(loss.detach().cpu()),
    }


def run(
    arguments: argparse.Namespace,
    manifest: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    target_rows: list[tuple[str, Path, str]],
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise PostRehearsalError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise PostRehearsalError("EXP-141 requires the explicit gpu0 lease")
    started = time.monotonic()
    arguments.work_dir.mkdir()
    policy = listening_policy(
        str(manifest["kind"]),
        arguments.trainable_target,
        arguments.training_objective,
        arguments.adapter_ema,
        arguments.optimizer_mode,
        arguments.parameter_anchor,
        arguments.source_activity_envelope,
    )

    import torch
    from peft import LoraConfig, PeftModel, get_peft_model

    if not torch.cuda.is_available():
        raise PostRehearsalError("CUDA is unavailable")
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
    if {
        key: float(value) for key, value in model.loss_config["loss_weights"].items()
    } != role_mix.STANDARD_LOSS_WEIGHTS:
        raise PostRehearsalError("upstream X-VC loss weights drifted")

    scope_name = (
        "speaker7"
        if arguments.trainable_target == SPEAKER7_OVERLAY_TARGET
        else "source36"
        if arguments.trainable_target == SOURCE36_TARGET
        else "control69"
    )
    scope = role_mix.training_scope(arguments.inventory, scope_name)
    if arguments.trainable_target in {
        FULL_CONVERTER_TARGET,
        ACOUSTIC_ENCODER_TARGET,
    }:
        control = PeftModel.from_pretrained(
            model, str(arguments.control_adapter), is_trainable=False
        )
        trained = control.merge_and_unload(safe_merge=True)
        if arguments.trainable_target == FULL_CONVERTER_TARGET:
            trainable = _set_converter_training_only(trained)
            expected_trainable = EXPECTED_CONVERTER_PARAMETERS
        else:
            trainable = _set_acoustic_encoder_training_only(trained)
            expected_trainable = EXPECTED_ACOUSTIC_ENCODER_PARAMETERS
    elif arguments.trainable_target == SPEAKER7_OVERLAY_TARGET:
        control = PeftModel.from_pretrained(
            model, str(arguments.control_adapter), is_trainable=False
        )
        merged = control.merge_and_unload(safe_merge=True)
        trained = get_peft_model(
            merged,
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
        trainable = role_mix._set_scope_training_only(trained, scope)
        expected_trainable = role_mix.expected_trainable_parameter_count(
            scope, "standard"
        )
    else:
        trained = PeftModel.from_pretrained(
            model, str(arguments.control_adapter), is_trainable=True
        )
        trainable = (
            _set_existing_adapter_scope_training_only(trained, scope)
            if arguments.trainable_target == SOURCE36_TARGET
            else role_mix._set_scope_training_only(trained, scope)
        )
        expected_trainable = role_mix.expected_trainable_parameter_count(
            scope, "standard"
        )
    if sum(parameter.numel() for parameter in trainable) != expected_trainable:
        raise PostRehearsalError("trainable parameter count drifted")
    optimizer = torch.optim.AdamW(trainable, lr=LEARNING_RATE)
    adapter_ema = AdapterEMA(trained, torch) if arguments.adapter_ema else None
    parameter_anchors = (
        [parameter.detach().clone() for parameter in trainable]
        if arguments.parameter_anchor
        else None
    )
    losses: list[float] = []
    adversarial_metrics: list[dict[str, float]] = []
    output_cycle_frontend_metrics: dict[str, float] | None = None
    pcgrad_metrics: list[dict[str, float | bool]] = []
    optimizer_steps = 0
    rows = (
        smoke_rows(
            manifest,
            arguments.optimizer_mode,
            arguments.parameter_anchor,
            arguments.trainable_target == ACOUSTIC_ENCODER_TARGET,
        )
        if arguments.smoke
        else manifest["items"]
    )
    discriminator = None
    discriminator_optimizer = None
    realism_targets: dict[str, Any] = {}
    if arguments.training_objective in {
        REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        FACTORIZED_UNPAIRED_OBJECTIVE,
        OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
        CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
        DISCRETE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
        SPEAKER_PATH_UNPAIRED_OBJECTIVE,
        PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
        PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
    }:
        discriminator, discriminator_optimizer = breadth._load_pretrained_discriminator(
            arguments, config, torch=torch, device=device
        )
        if arguments.training_objective in {
            REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
            PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
            PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
        }:
            target_by_id = {
                target_id: _pair(target_id, path, digest)
                for target_id, path, digest in target_rows
            }
            for item in rows:
                target_id = str(item["target_id"])
                if (
                    arguments.training_objective
                    in {
                        PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
                        PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
                    }
                ):
                    real_target = arguments.source_work / str(item["real_target_file"])
                    pair = _pair(
                        target_id,
                        real_target,
                        str(item["real_target_sha256"]),
                    )
                else:
                    pair = target_by_id.get(target_id)
                    if pair is None:
                        raise PostRehearsalError(
                            f"real adversarial target is unavailable: {target_id}"
                        )
                realism_targets[target_id] = base._extract_pair_tensors(
                    trained,
                    pair,
                    process_audio=process_audio,
                    config=config,
                    torch=torch,
                    device=device,
                )["target_wav"]

    def batch_for(
        item: Mapping[str, Any], negative_item: Mapping[str, Any] | None = None
    ) -> Any:
        if arguments.trainable_target == FULL_CONVERTER_TARGET:
            _set_converter_training_only(trained)
        elif arguments.trainable_target == ACOUSTIC_ENCODER_TARGET:
            _set_acoustic_encoder_training_only(trained)
        elif arguments.trainable_target == SOURCE36_TARGET:
            _set_existing_adapter_scope_training_only(trained, scope)
        else:
            role_mix._set_scope_training_only(trained, scope)
        tensors = _batch_from_item(
            trained,
            item,
            source_work=arguments.source_work,
            control_work=arguments.control_work,
            diverse_work=arguments.diverse_work,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
            factorized_unpaired=(manifest.get("kind") in UNPAIRED_HUMAN_KINDS),
        )
        if arguments.training_objective == CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE:
            if negative_item is None or negative_item.get("id") == item.get("id"):
                raise PostRehearsalError(
                    "contrastive output cycle requires a distinct negative row"
                )
            negative = _batch_from_item(
                trained,
                negative_item,
                source_work=arguments.source_work,
                control_work=arguments.control_work,
                diverse_work=arguments.diverse_work,
                process_audio=process_audio,
                config=config,
                torch=torch,
                device=device,
                factorized_unpaired=True,
            )
            if negative["ssl_feat"].shape != tensors["ssl_feat"].shape:
                raise PostRehearsalError("contrastive negative content shape drifted")
            tensors["negative_ssl_feat"] = negative["ssl_feat"]
        gpu_batch = base._gpu_batch(tensors, torch=torch, device=device)
        if "negative_ssl_feat" in tensors:
            gpu_batch["negative_ssl_feat"] = tensors["negative_ssl_feat"].to(
                device=device, dtype=torch.float32
            )
        return gpu_batch

    if arguments.optimizer_mode == PCGRAD_PAIRED_OPTIMIZER:
        for hard_item, easy_item in paired_hard_easy_rows(rows):
            task_gradients: list[list[Any]] = []
            for item in (hard_item, easy_item):
                optimizer.zero_grad(set_to_none=True)
                batch = batch_for(item)
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                    loss, numeric = role_mix.training_loss(
                        trained,
                        batch,
                        "real-donor-teacher-output",
                        torch=torch,
                        teacher_loss="standard",
                    )
                gradients = torch.autograd.grad(
                    loss,
                    trainable,
                    allow_unused=True,
                )
                task_gradients.append(
                    [
                        gradient.detach()
                        if gradient is not None
                        else torch.zeros_like(parameter)
                        for parameter, gradient in zip(
                            trainable, gradients, strict=True
                        )
                    ]
                )
                losses.append(numeric)
            merged_gradients, metrics = project_conflicting_pair(
                task_gradients[0], task_gradients[1], torch=torch
            )
            pcgrad_metrics.append(metrics)
            optimizer.zero_grad(set_to_none=True)
            for parameter, gradient in zip(trainable, merged_gradients, strict=True):
                parameter.grad = gradient
            gradient_norm = torch.nn.utils.clip_grad_norm_(
                trainable, base.GRADIENT_CLIP_NORM
            )
            if not math.isfinite(float(gradient_norm.detach().cpu())):
                raise PostRehearsalError("paired PCGrad merged norm is non-finite")
            if not arguments.smoke:
                optimizer.step()
                optimizer_steps += 1
    else:
        for row_index, item in enumerate(rows):
            negative_item = (
                rows[(row_index + 1) % len(rows)]
                if arguments.training_objective
                == CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE
                else None
            )
            batch = batch_for(item, negative_item)
            if (
                arguments.training_objective
                in {
                    OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
                    CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
                    DISCRETE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
                }
                and output_cycle_frontend_metrics is None
            ):
                output_cycle_frontend_metrics = validate_output_cycle_frontend(
                    trained.semantic_encoder,
                    batch["source_wav"],
                    batch["ssl_feat"],
                    torch=torch,
                )
            if (
                arguments.optimizer_mode == PCGRAD_CONTENT_VOICE_OPTIMIZER
                and discriminator is not None
                and discriminator_optimizer is not None
            ):
                metrics, geometry = content_voice_pcgrad_adversarial_update(
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
                pcgrad_metrics.append(geometry)
            elif discriminator is not None and discriminator_optimizer is not None:
                metrics = breadth._adversarial_update(
                    trained,
                    discriminator,
                    optimizer,
                    discriminator_optimizer,
                    trainable,
                    batch,
                    torch=torch,
                    real_audios=(
                        realism_targets[str(item["target_id"])].to(
                            device=device, dtype=torch.float32
                        )
                        if arguments.training_objective
                        in {
                            REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
                            PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
                            PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
                        }
                        else None
                    ),
                    generator_regularizer=(
                        (
                            lambda: parameter_anchor_regularizer(
                                trainable,
                                parameter_anchors,
                                torch=torch,
                            )
                        )
                        if parameter_anchors is not None
                        else None
                    ),
                    generator_training_setter=(
                        (
                            lambda current: _set_existing_adapter_scope_training_only(
                                current, scope
                            )
                        )
                        if arguments.trainable_target == SOURCE36_TARGET
                        else (
                            lambda current: (
                                _set_acoustic_encoder_training_only(current)
                                if arguments.trainable_target == ACOUSTIC_ENCODER_TARGET
                                else None
                            )
                        )
                    ),
                    output_regularizer=(
                        (
                            lambda reconstruction, _current_batch: (
                                output_speaker_identity_regularizer(
                                    reconstruction,
                                    realism_targets[str(item["target_id"])],
                                    speaker_encoder=trained.speaker_encoder,
                                    torch=torch,
                                )
                            )
                        )
                        if arguments.training_objective
                        == PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE
                        else
                        (
                            lambda reconstruction, current_batch: (
                                source_activity_envelope_regularizer(
                                    reconstruction,
                                    current_batch,
                                    torch=torch,
                                )
                            )
                        )
                        if arguments.source_activity_envelope
                        else None
                    ),
                    generator_loss_fn=(
                        (
                            lambda outputs, current_batch: (
                                speaker_path_unpaired_generator_loss(
                                    outputs,
                                    current_batch,
                                    torch=torch,
                                )
                            )
                        )
                        if arguments.training_objective
                        == SPEAKER_PATH_UNPAIRED_OBJECTIVE
                        else (
                            lambda outputs, current_batch: (
                                factorized_unpaired_generator_loss(
                                    outputs,
                                    current_batch,
                                    torch=torch,
                                )
                            )
                        )
                        if arguments.training_objective == FACTORIZED_UNPAIRED_OBJECTIVE
                        else (
                            lambda outputs, current_batch: (
                                output_cycle_unpaired_generator_loss(
                                    outputs,
                                    current_batch,
                                    semantic_encoder=trained.semantic_encoder,
                                    torch=torch,
                                )
                            )
                        )
                        if arguments.training_objective
                        == OUTPUT_CYCLE_UNPAIRED_OBJECTIVE
                        else (
                            lambda outputs, current_batch: (
                                contrastive_output_cycle_unpaired_generator_loss(
                                    outputs,
                                    current_batch,
                                    semantic_encoder=trained.semantic_encoder,
                                    torch=torch,
                                )
                            )
                        )
                        if arguments.training_objective
                        == CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE
                        else (
                            lambda outputs, current_batch: (
                                discrete_output_cycle_unpaired_generator_loss(
                                    outputs,
                                    current_batch,
                                    semantic_encoder=trained.semantic_encoder,
                                    torch=torch,
                                )
                            )
                        )
                        if arguments.training_objective
                        == DISCRETE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE
                        else None
                    ),
                )
                losses.append(metrics["total"])
                adversarial_metrics.append(metrics)
            else:
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                    loss, numeric = role_mix.training_loss(
                        trained,
                        batch,
                        "real-donor-teacher-output",
                        torch=torch,
                        teacher_loss="standard",
                    )
                loss.backward()
                gradient_norm = torch.nn.utils.clip_grad_norm_(
                    trainable, base.GRADIENT_CLIP_NORM
                )
                if not math.isfinite(float(gradient_norm.detach().cpu())):
                    raise PostRehearsalError(
                        "post-rehearsal gradient norm is non-finite"
                    )
                if not arguments.smoke:
                    optimizer.step()
                losses.append(numeric)
            if not arguments.smoke:
                optimizer_steps += 1
            if adapter_ema is not None:
                adapter_ema.update()
    if arguments.smoke:
        smoke = {
            "status": "smoked-control69-clean-post-rehearsal",
            "loss": losses[0],
            "trainable_parameters": expected_trainable,
            "training_objective": arguments.training_objective,
            "optimizer_mode": arguments.optimizer_mode,
            "parameter_anchor": arguments.parameter_anchor,
            "output_cycle_frontend": output_cycle_frontend_metrics,
            "prospective_optimizer_steps": (
                1 if arguments.optimizer_mode == PCGRAD_PAIRED_OPTIMIZER else len(rows)
            ),
            "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        }
        if adversarial_metrics:
            smoke["adversarial_metrics"] = {
                "first": adversarial_metrics[0],
                "last": adversarial_metrics[-1],
            }
        else:
            smoke["gradient_norm"] = float(gradient_norm.detach().cpu())
        if adapter_ema is not None:
            smoke["adapter_ema"] = adapter_ema.receipt()
        if pcgrad_metrics:
            smoke["pcgrad"] = pcgrad_metrics[0]
        method._write_json(arguments.work_dir / "smoke.json", smoke)
        print(json.dumps(smoke, sort_keys=True))
        return 0
    if len(losses) != EXPECTED_ROWS:
        raise PostRehearsalError("post-rehearsal update count drifted")
    if arguments.trainable_target == FULL_CONVERTER_TARGET:
        checkpoint_metadata = save_converter_checkpoint(
            trained, arguments.work_dir / f"converter-{EXPECTED_ROWS}", torch
        )
    elif arguments.trainable_target == ACOUSTIC_ENCODER_TARGET:
        checkpoint_metadata = save_acoustic_encoder_checkpoint(
            trained,
            arguments.work_dir / f"acoustic-encoder-{EXPECTED_ROWS}",
            torch,
        )
    else:
        checkpoint_steps = (
            optimizer_steps
            if arguments.optimizer_mode == PCGRAD_PAIRED_OPTIMIZER
            else EXPECTED_ROWS
        )
        adapter_dir = arguments.work_dir / f"adapter-{checkpoint_steps}"
        if adapter_ema is not None:
            online_dir = arguments.work_dir / f"online-adapter-{EXPECTED_ROWS}"
            trained.save_pretrained(online_dir, safe_serialization=True)
            adapter_ema.copy_to()
        trained.save_pretrained(adapter_dir, safe_serialization=True)
        checkpoint_metadata = {
            "kind": "peft-adapter-ema" if adapter_ema is not None else "peft-adapter",
            "directory": adapter_dir.name,
            "online_directory": (
                f"online-adapter-{EXPECTED_ROWS}" if adapter_ema is not None else None
            ),
        }

    target_id, target_path, target_digest = target_rows[0]
    target = base._extract_pair_tensors(
        trained,
        _pair(target_id, target_path, target_digest),
        process_audio=process_audio,
        config=config,
        torch=torch,
        device=device,
    )
    evaluation_root = arguments.work_dir / "evaluation-sources"
    evaluation_root.mkdir()
    evaluation_pairs: list[base.MaterializedPair] = []
    evaluation_tensors: list[dict[str, Any]] = []
    for item in evaluation["items"]:
        pair, tensors = breadth._reference_tensor(
            trained,
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
                target,
                seed=base.SEED + index,
                torch=torch,
                device=device,
            )
            .detach()
            .cpu()
            for index, source in enumerate(evaluation_tensors)
        ]

    candidate_outputs = render(trained)
    control_base = method._load_xvc(arguments, XVC, device)
    control = PeftModel.from_pretrained(
        control_base, str(arguments.control_adapter), is_trainable=False
    )
    control_outputs = render(control)
    del control, control_base
    torch.cuda.empty_cache()
    plain_base = method._load_xvc(arguments, XVC, device)
    base_outputs = render(plain_base)
    del plain_base
    torch.cuda.empty_cache()

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    listener_rows: list[dict[str, Any]] = []
    for index, (item, pair) in enumerate(
        zip(evaluation["items"], evaluation_pairs, strict=True)
    ):
        row_root = staging / f"{index:02d}-{item['id']}"
        row_root.mkdir()
        shutil.copyfile(pair.source_path, row_root / "00-source-reference.wav")
        shutil.copyfile(target_path, row_root / "01-target-reference.wav")
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
            role_mix.listening_index(item, hashes=hashes, policy=policy),
        )
        listener_rows.append({"source_id": item["id"], "hashes": hashes})
    staging.rename(arguments.listener_dir)
    result = {
        "schema_version": 1,
        "kind": policy["result_kind"],
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": policy["question"],
        "independent_variable": policy["independent_variable"],
        "training_manifest_sha256": sha256_file(arguments.training_manifest),
        **source_receipt_identities(
            str(manifest.get("kind")),
            arguments.source_work,
            arguments.training_manifest,
        ),
        "control_probe_result_sha256": (
            sha256_file(arguments.control_work / "result.json")
            if arguments.control_work is not None
            else None
        ),
        "control_adapter": str(arguments.control_adapter),
        "trainable_target": arguments.trainable_target,
        "training_objective": arguments.training_objective,
        "optimizer_mode": arguments.optimizer_mode,
        "parameter_anchor": (
            {
                "implementation": PARAMETER_ANCHOR_IMPLEMENTATION,
                "coefficient": PARAMETER_ANCHOR_COEFFICIENT,
                "reference": "immutable EXP-035 control69 trainable parameters",
                "first_loss": adversarial_metrics[0]["parameter_anchor_loss"],
                "last_loss": adversarial_metrics[-1]["parameter_anchor_loss"],
                "last_squared_distance": adversarial_metrics[-1][
                    "parameter_anchor_squared_distance"
                ],
            }
            if arguments.parameter_anchor
            else None
        ),
        "source_activity_envelope": (
            {
                "implementation": SOURCE_ACTIVITY_ENVELOPE_IMPLEMENTATION,
                "weight": SOURCE_ACTIVITY_ENVELOPE_WEIGHT,
                "first_distance": adversarial_metrics[0][
                    "source_activity_envelope_distance"
                ],
                "last_distance": adversarial_metrics[-1][
                    "source_activity_envelope_distance"
                ],
            }
            if arguments.source_activity_envelope
            else None
        ),
        "output_speaker_identity": (
            {
                "implementation": OUTPUT_SPEAKER_IDENTITY_IMPLEMENTATION,
                "weight": OUTPUT_SPEAKER_IDENTITY_WEIGHT,
                "target": "assigned-authorized-real-Amitaro-window",
                "first_similarity": adversarial_metrics[0][
                    "output_speaker_identity_similarity"
                ],
                "last_similarity": adversarial_metrics[-1][
                    "output_speaker_identity_similarity"
                ],
            }
            if arguments.training_objective
            == PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE
            else None
        ),
        "adapter_ema": adapter_ema.receipt() if adapter_ema is not None else None,
        "candidate_checkpoint": checkpoint_metadata,
        "optimizer_steps": optimizer_steps,
        "training_examples": len(losses),
        "updates": optimizer_steps,
        "role_counts": {"real-donor-teacher-output": len(losses)},
        "learning_target_counts": manifest.get(
            "learning_target_counts", {"base-teacher": len(losses)}
        ),
        "composition": manifest["composition"],
        "learning_rate": LEARNING_RATE,
        "gradient_clip_norm": base.GRADIENT_CLIP_NORM,
        "trainable_parameters": expected_trainable,
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "adversarial_metrics": (
            {
                "updates": len(adversarial_metrics),
                "first": adversarial_metrics[0],
                "last": adversarial_metrics[-1],
                "real_audio": "authorized-original-Amitaro-target",
                "generative_audio": (
                    "speaker-path-target-voice-plus-real-wave-adversarial"
                    if arguments.training_objective == SPEAKER_PATH_UNPAIRED_OBJECTIVE
                    else "final-waveform-source-content-cycle-plus-target-speaker"
                    if arguments.training_objective == OUTPUT_CYCLE_UNPAIRED_OBJECTIVE
                    else (
                        "final-waveform-contrastive-source-content-cycle-plus-"
                        "target-speaker"
                    )
                    if arguments.training_objective
                    == CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE
                    else (
                        "final-waveform-discrete-source-token-cycle-plus-target-speaker"
                    )
                    if arguments.training_objective
                    == DISCRETE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE
                    else "source-semantic-plus-target-speaker-factorization"
                    if arguments.training_objective == FACTORIZED_UNPAIRED_OBJECTIVE
                    else "source-aligned-control69-complete-generative-target"
                    if arguments.training_objective
                    == PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE
                    or arguments.training_objective
                    == PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE
                    else "selective-repair-or-retention-target"
                ),
            }
            if adversarial_metrics
            else None
        ),
        "output_cycle_frontend": output_cycle_frontend_metrics,
        "pcgrad_metrics": (
            {
                "pairs": len(pcgrad_metrics),
                "conflicts": sum(bool(item["conflict"]) for item in pcgrad_metrics),
                "cosine_min": min(float(item["cosine"]) for item in pcgrad_metrics),
                "cosine_mean": sum(float(item["cosine"]) for item in pcgrad_metrics)
                / len(pcgrad_metrics),
                "cosine_max": max(float(item["cosine"]) for item in pcgrad_metrics),
            }
            if pcgrad_metrics
            else None
        ),
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "evaluation_set_sha256": sha256_file(arguments.evaluation_set),
        "listener_rows": listener_rows,
        "boundary": (
            "Auxiliary content/corruption screening only; not naturalness, target "
            "identity, a keeper, or promotion"
        ),
        "claims": {
            "perceptual_winner": False,
            "promoted": False,
            "route_qualified": False,
        },
    }
    method._write_json(arguments.work_dir / "result.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "optimizer_steps": optimizer_steps,
                "training_examples": len(losses),
                "listener_dir": str(arguments.listener_dir),
            },
            sort_keys=True,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--smoke", action="store_true")
    value.add_argument("--training-manifest", type=Path, required=True)
    value.add_argument("--source-work", type=Path, required=True)
    value.add_argument("--control-work", type=Path)
    value.add_argument("--diverse-work", type=Path)
    value.add_argument("--evaluation-set", type=Path, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--pair-root", type=Path, required=True)
    value.add_argument("--control-adapter", type=Path, required=True)
    value.add_argument(
        "--trainable-target",
        choices=(
            LORA69_TARGET,
            SOURCE36_TARGET,
            SPEAKER7_OVERLAY_TARGET,
            FULL_CONVERTER_TARGET,
            ACOUSTIC_ENCODER_TARGET,
        ),
        default=LORA69_TARGET,
    )
    value.add_argument(
        "--training-objective",
        choices=(
            GENERATIVE_OBJECTIVE,
            REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
            FACTORIZED_UNPAIRED_OBJECTIVE,
            OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
            CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
            DISCRETE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
            SPEAKER_PATH_UNPAIRED_OBJECTIVE,
            PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
            PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
        ),
        default=GENERATIVE_OBJECTIVE,
    )
    value.add_argument(
        "--optimizer-mode",
        choices=(
            SEQUENTIAL_OPTIMIZER,
            PCGRAD_PAIRED_OPTIMIZER,
            PCGRAD_CONTENT_VOICE_OPTIMIZER,
        ),
        default=SEQUENTIAL_OPTIMIZER,
    )
    value.add_argument("--adapter-ema", action="store_true")
    value.add_argument("--parameter-anchor", action="store_true")
    value.add_argument("--source-activity-envelope", action="store_true")
    value.add_argument("--xvc-source-root", type=Path, required=True)
    value.add_argument("--xvc-config", type=Path, required=True)
    value.add_argument("--checkpoint", type=Path, required=True)
    value.add_argument(
        "--inventory",
        type=Path,
        default=REPO_ROOT / "artifacts/exp007/phase0-inputs-v1/inventory.json",
    )
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    value.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    value.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        manifest, evaluation, targets = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "training_rows": len(manifest["items"]),
                        "composition": manifest["composition"],
                        "evaluation_rows": len(evaluation["items"]),
                        "initialization": "EXP-035-control69",
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, manifest, evaluation, targets)
    except (
        PostRehearsalError,
        base.ListenNowError,
        breadth.BreadthError,
        external.ExternalEvaluationError,
        method.SourceDiversityError,
        role_mix.RoleMixError,
        OSError,
        ValueError,
    ) as error:
        print(f"exp141-post-rehearsal-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
