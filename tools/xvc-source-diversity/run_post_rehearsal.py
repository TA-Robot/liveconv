#!/usr/bin/env python3
"""Run one clean teacher pass after the frozen control69 X-VC adaptation."""

from __future__ import annotations

import argparse
import hashlib
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
from prepare_exp305_exp306_cv32 import (  # noqa: E402
    BREADTH_OUTPUT_KIND as CV32_BREADTH_OUTPUT_KIND,
)
from prepare_exp305_exp306_cv32 import (  # noqa: E402
    REPEAT_OUTPUT_KIND as CV32_REPEAT_OUTPUT_KIND,
)
from prepare_exp317_cv32_replacement import (  # noqa: E402
    OUTPUT_KIND as CV32_REPLACEMENT_OUTPUT_KIND,
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
CV32_EXPECTED_ROWS = EXPECTED_ROWS + 32
CV32_EXPECTED_COMPOSITION = {
    "commonvoice-unpaired": 80,
    "hadou-unpaired": 34,
    "jsut-unpaired": 85,
    "jvs-unpaired": 3,
}
FULL_CONVERTER_TARGET = "full-converter"
ACOUSTIC_ENCODER_TARGET = "acoustic-encoder"
LORA69_TARGET = "lora69"
SOURCE36_TARGET = "source36"
SPEAKER7_OVERLAY_TARGET = "speaker7-overlay"
SPEAKER_CONDITION_CALIBRATOR_TARGET = "speaker-condition-calibrator"
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
PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE = (
    "pseudoparallel-generative-real-adversarial-robust-semantic"
)
PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE = (
    "pseudoparallel-generative-real-adversarial-fresh-lora"
)
PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE = (
    "pseudoparallel-generative-real-adversarial-acoustic-code-dropout"
)
PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE = (
    "pseudoparallel-generative-real-adversarial-continuous-acoustic"
)
PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE = (
    "pseudoparallel-generative-real-adversarial-acoustic-temporal-jitter"
)
PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE = (
    "pseudoparallel-generative-real-adversarial-output-speaker"
)
PSEUDOPARALLEL_CONDITION_CALIBRATOR_OBJECTIVE = (
    "pseudoparallel-generative-real-adversarial-condition-calibrator"
)
PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE = (
    "pseudoparallel-generative-real-adversarial-latent-speaker-margin"
)
PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE = (
    "pseudoparallel-generative-real-adversarial-real-speaker-condition"
)
# EXP-325/326 deliberately share one ordered 170-row manifest.  Keep the
# objective names separate so the control and treatment can be admitted from
# the same bytes while the treatment changes only the generator gradient.
PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE = (
    "pseudoparallel-generative-real-adversarial-source-speaker-grl"
)
SOURCE_SPEAKER_GRL_OBJECTIVE = PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE
SRC4VC_TWO_UTTERANCE_OUTPUT_KIND = (
    "liveconv-exp325-exp326-xvc-src4vc-two-utterance-inputs/v1"
)
# The short spellings were used by early CPU materializers.  Accepting them is
# harmless, but all result identities below remain explicitly EXP-325/326.
SRC4VC_TWO_UTTERANCE_KINDS = {
    SRC4VC_TWO_UTTERANCE_OUTPUT_KIND,
    "liveconv-exp325-xvc-src4vc-two-utterance-inputs/v1",
    "liveconv-exp325-src4vc-two-utterance-inputs/v1",
    "liveconv-exp325-exp326-src4vc-two-utterance-inputs/v1",
}
SRC4VC_TWO_UTTERANCE_COMPOSITION = {
    "src4vc-smartphone-unpaired": 170,
}
SOURCE_SPEAKER_CLASS_COUNT = 85
SOURCE_SPEAKER_FEATURE_DIMENSION = 2048
SOURCE_SPEAKER_GRL_WEIGHT = 1.0
SOURCE_SPEAKER_POOL_IMPLEMENTATION = (
    "mean-std-pool-acoustic-converter-x-1024xT/v1"
)
SOURCE_SPEAKER_GRL_IMPLEMENTATION = (
    "normalized-cross-entropy-gradient-reversal/v1"
)
SOURCE_SPEAKER_PROBE_IMPLEMENTATION = (
    "frozen-control69-cross-utterance-acoustic-converter-centroid/v1"
)
SOURCE_SPEAKER_PROBE_MIN_TOP1_MULTIPLE = 2.0
SOURCE_SPEAKER_PROBE_MIN_TOP5_MULTIPLE = 2.0
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
LATENT_SOURCE_SPEAKER_MARGIN = 0.1
LATENT_SOURCE_SPEAKER_MARGIN_WEIGHT = 10.0
LATENT_SOURCE_SPEAKER_MARGIN_IMPLEMENTATION = (
    "xvc-speaker-predictor-target-over-frozen-source-eres2net-hinge/v1"
)
ACOUSTIC_CODE_DROPOUT_IMPLEMENTATION = (
    "alternating-odd-row-zero-quantized-source-acoustic-code/v1"
)
CONTINUOUS_ACOUSTIC_IMPLEMENTATION = (
    "projected-pre-vq-continuous-source-acoustic/v1"
)
ACOUSTIC_TEMPORAL_JITTER_IMPLEMENTATION = (
    "one-frame-right-shifted-quantized-source-acoustic/v1"
)
ROBUST_SEMANTIC_IMPLEMENTATION = (
    "scale-matched-smooth-l1-semantic-decoder-beta1/v1"
)
ROBUST_SEMANTIC_BETA = 1.0
ROBUST_SEMANTIC_SCALE = 2.0
ROBUST_SEMANTIC_WEIGHT = 1000.0
SPEAKER_CONDITION_DIMENSION = 192
SPEAKER_CONDITION_CALIBRATOR_KIND = (
    "liveconv-xvc-speaker-condition-calibrator/v1"
)
EXP238_ADAPTER_SHA256 = (
    "778b430133b5397d86bd70bd7c9fa7bd4f7f9cc4d737ca94e4b91e5c7bc8a9da"
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
    *SRC4VC_TWO_UTTERANCE_KINDS,
    CV32_REPEAT_OUTPUT_KIND,
    CV32_BREADTH_OUTPUT_KIND,
    CV32_REPLACEMENT_OUTPUT_KIND,
    "liveconv-exp318-xvc-pseudoparallel-cv26-current-window-control-inputs/v1",
    "liveconv-exp319-xvc-pseudoparallel-cv26-active-window-inputs/v1",
}
CV32_PSEUDOPARALLEL_KINDS = {
    CV32_REPEAT_OUTPUT_KIND,
    CV32_BREADTH_OUTPUT_KIND,
}
CV32_REPLACEMENT_POSITIONS = (
    4,
    5,
    6,
    11,
    13,
    14,
    16,
    19,
    25,
    27,
    30,
    31,
    35,
    36,
    39,
    43,
    48,
    52,
    54,
    55,
    57,
    58,
    59,
    63,
    71,
    75,
    78,
    80,
    86,
    91,
    101,
    103,
)
CV32_REPLACEMENT_KINDS = {CV32_REPLACEMENT_OUTPUT_KIND}
CV32_REPLACEMENT_COMPOSITION = dict(PSEUDOPARALLEL_EXPECTED_DOMAINS)
CV26_CURRENT_WINDOW_OUTPUT_KIND = (
    "liveconv-exp318-xvc-pseudoparallel-cv26-current-window-control-inputs/v1"
)
CV26_ACTIVE_WINDOW_OUTPUT_KIND = (
    "liveconv-exp319-xvc-pseudoparallel-cv26-active-window-inputs/v1"
)
CV26_KINDS = {
    CV26_CURRENT_WINDOW_OUTPUT_KIND,
    CV26_ACTIVE_WINDOW_OUTPUT_KIND,
}
CV26_REPLACEMENT_POSITIONS = (
    4,
    5,
    6,
    11,
    13,
    16,
    19,
    25,
    27,
    30,
    35,
    36,
    39,
    43,
    48,
    54,
    55,
    57,
    58,
    59,
    63,
    71,
    75,
    86,
    101,
    103,
)
CV26_COMPOSITION = dict(PSEUDOPARALLEL_EXPECTED_DOMAINS)


class PostRehearsalError(RuntimeError):
    """The bounded clean post-adaptation rehearsal cannot safely continue."""


def expected_training_rows(manifest_kind: str) -> int:
    """Return the admitted horizon while preserving every legacy 170-row lane."""

    return (
        CV32_EXPECTED_ROWS
        if manifest_kind in CV32_PSEUDOPARALLEL_KINDS
        else EXPECTED_ROWS
    )


_PSEUDOPARALLEL_ROW_FIELDS = (
    "domain",
    "source_manifest_id",
    "source_text",
    "source_root",
    "source_file",
    "source_sha256",
    "source_relative_distance",
    "target_id",
    "target_text",
    "target_root",
    "target_file",
    "target_sha256",
    "learning_target",
    "real_target_text",
    "real_target_root",
    "real_target_file",
    "real_target_sha256",
)
_REPEAT_ROW_FIELDS = tuple(
    key for key in _PSEUDOPARALLEL_ROW_FIELDS if key != "source_manifest_id"
)


def _source_identity(row: Mapping[str, Any]) -> str | None:
    """Extract the stable source ID without depending on a generated row ID."""

    value = row.get("source_manifest_id")
    if isinstance(value, str) and value:
        return value.rsplit(":", 1)[-1]
    value = row.get("source_id")
    if isinstance(value, str) and value:
        return value.removesuffix("-e1").removesuffix("-e2")
    value = row.get("source_file")
    if isinstance(value, str) and value:
        return Path(value).stem
    return None


def _client_identity(row: Mapping[str, Any]) -> str | None:
    for key in (
        "client_id_sha256",
        "client_sha256",
        "source_client_id_sha256",
    ):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _same_repeat_tuple(
    candidate: Mapping[str, Any], expected: Mapping[str, Any]
) -> bool:
    repeat_of_id = candidate.get("repeat_of_id")
    if repeat_of_id is not None and repeat_of_id != expected.get("id"):
        return False
    if repeat_of_id is None and _source_identity(candidate) != _source_identity(
        expected
    ):
        return False
    return all(
        candidate.get(key) == expected.get(key) for key in _REPEAT_ROW_FIELDS
    )


def validate_cv32_manifest(
    manifest: Mapping[str, Any],
    *,
    reference_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Admit EXP-305/306 rows against the frozen ordered EXP-238 curriculum."""

    kind = manifest.get("kind")
    if kind not in CV32_PSEUDOPARALLEL_KINDS:
        return None
    items = manifest.get("items")
    if (
        not isinstance(items, list)
        or len(items) != CV32_EXPECTED_ROWS
        or manifest.get("composition") != CV32_EXPECTED_COMPOSITION
    ):
        raise PostRehearsalError("CV32 pseudoparallel manifest drifted")
    reference = reference_manifest or _load_exp238_manifest()
    reference_items = reference.get("items") if reference else None
    if (
        not isinstance(reference_items, list)
        or len(reference_items) != EXPECTED_ROWS
        or items[:EXPECTED_ROWS] != reference_items
    ):
        raise PostRehearsalError("CV32 manifest does not preserve EXP-238 order")
    additions = items[EXPECTED_ROWS:]
    if any(not isinstance(item, Mapping) for item in additions):
        raise PostRehearsalError("CV32 appended row is malformed")
    forbidden = {
        "source_representation",
        "representation_attachment",
        "inference_attachment",
        "inference_representation",
    }
    if any(
        key in manifest and manifest.get(key) is not None for key in forbidden
    ) or any(
        key in item and item.get(key) is not None
        for item in items
        if isinstance(item, Mapping)
        for key in forbidden
    ):
        raise PostRehearsalError("CV32 policy must not attach representation/inference")

    old_cv = [
        item
        for item in reference_items
        if isinstance(item, Mapping) and item.get("domain") == "commonvoice-unpaired"
    ]
    if len(old_cv) != 48:
        raise PostRehearsalError("EXP-238 Common Voice rows drifted")
    if kind == CV32_REPEAT_OUTPUT_KIND:
        expected = old_cv[:32]
        if any(
            item.get("domain") != "commonvoice-unpaired"
            or not _same_repeat_tuple(item, expected_row)
            for item, expected_row in zip(additions, expected, strict=True)
        ):
            raise PostRehearsalError("EXP-305 repeat32 rows drifted")
        policy = "repeat-first-32-commonvoice-tuples"
    else:
        source_ids = {_source_identity(item) for item in old_cv}
        source_shas = {item.get("source_sha256") for item in old_cv}
        source_texts = {item.get("source_text") for item in old_cv}
        added_ids = {_source_identity(item) for item in additions}
        added_shas = {item.get("source_sha256") for item in additions}
        added_texts = {item.get("source_text") for item in additions}
        added_clients = {_client_identity(item) for item in additions}
        if (
            any(item.get("domain") != "commonvoice-unpaired" for item in additions)
            or any(
                not str(item.get("source_manifest_id", "")).startswith("EXP055:")
                for item in additions
            )
            or None in added_ids
            or len(added_ids) != 32
            or len(added_shas) != 32
            or len(added_texts) != 32
            or None in added_clients
            or len(added_clients) != 32
            or added_ids & source_ids
            or added_shas & source_shas
            or added_texts & source_texts
        ):
            raise PostRehearsalError("EXP-306 CV32 breadth identity drifted")
        policy = "genuine-new-commonvoice-32-speaker-tuples"
    return {
        "manifest_kind": kind,
        "manifest_row_count": CV32_EXPECTED_ROWS,
        "base_row_count": EXPECTED_ROWS,
        "additional_row_count": len(additions),
        "first170_exact_exp238": True,
        "addition_policy": policy,
        "representation": None,
        "inference_attachment": None,
    }


def validate_cv32_replacement_manifest(
    manifest: Mapping[str, Any],
    *,
    reference_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Admit EXP-317's fixed-position 32-row source replacement."""

    if manifest.get("kind") not in CV32_REPLACEMENT_KINDS:
        return None
    items = manifest.get("items")
    if (
        not isinstance(items, list)
        or len(items) != EXPECTED_ROWS
        or manifest.get("composition") != CV32_REPLACEMENT_COMPOSITION
    ):
        raise PostRehearsalError("EXP-317 replacement manifest drifted")
    reference = reference_manifest or _load_exp238_manifest()
    reference_items = reference.get("items") if reference else None
    if not isinstance(reference_items, list) or len(reference_items) != EXPECTED_ROWS:
        raise PostRehearsalError("EXP-317 EXP-238 reference is unavailable")
    expected_positions = tuple(
        index
        for index, row in enumerate(reference_items)
        if isinstance(row, Mapping) and row.get("domain") == "commonvoice-unpaired"
    )
    if (
        expected_positions[: len(CV32_REPLACEMENT_POSITIONS)]
        != CV32_REPLACEMENT_POSITIONS
    ):
        raise PostRehearsalError("EXP-317 replacement positions drifted")
    if len(expected_positions) != 48:
        raise PostRehearsalError("EXP-238 Common Voice positions drifted")
    forbidden = {
        "source_representation",
        "representation_attachment",
        "inference_attachment",
        "inference_representation",
    }
    if any(
        key in manifest and manifest.get(key) is not None for key in forbidden
    ) or any(
        key in row and row.get(key) is not None
        for row in items
        if isinstance(row, Mapping)
        for key in forbidden
    ):
        raise PostRehearsalError(
            "EXP-317 policy must not attach representation/inference"
        )

    replaced: list[Mapping[str, Any]] = []
    for position, (candidate, expected) in enumerate(
        zip(items, reference_items, strict=True)
    ):
        if not isinstance(candidate, Mapping) or not isinstance(expected, Mapping):
            raise PostRehearsalError("EXP-317 row is malformed")
        if position not in CV32_REPLACEMENT_POSITIONS:
            if candidate != expected:
                raise PostRehearsalError(
                    f"EXP-317 unchanged row drifted at position {position}"
                )
            continue
        replaced.append(candidate)
        if (
            candidate.get("domain") != "commonvoice-unpaired"
            or expected.get("domain") != "commonvoice-unpaired"
            or not str(candidate.get("source_manifest_id", "")).startswith("EXP055:")
            or candidate.get("source_root") != "source-work"
            or candidate.get("target_root") != "diverse-work"
            or candidate.get("learning_target") != PSEUDOPARALLEL_LEARNING_TARGET
            or candidate.get("target_text") != candidate.get("source_text")
            or candidate.get("source_relative_distance") != 0.0
        ):
            raise PostRehearsalError("EXP-317 replacement source boundary drifted")
        for key in (
            "target_id",
            "real_target_text",
            "real_target_root",
            "real_target_file",
            "real_target_sha256",
        ):
            if candidate.get(key) != expected.get(key):
                raise PostRehearsalError(
                    f"EXP-317 position-specific target drifted at {position}"
                )

    base_sources = [row for row in reference_items if isinstance(row, Mapping)]
    base_ids = {_source_identity(row) for row in base_sources}
    base_shas = {row.get("source_sha256") for row in base_sources}
    base_texts = {row.get("source_text") for row in base_sources}
    base_teachers = {row.get("teacher_id") for row in base_sources}
    replacement_ids = {_source_identity(row) for row in replaced}
    replacement_shas = {row.get("source_sha256") for row in replaced}
    replacement_texts = {row.get("source_text") for row in replaced}
    replacement_teachers = {row.get("teacher_id") for row in replaced}
    replacement_clients = {_client_identity(row) for row in replaced}
    if (
        len(replaced) != len(CV32_REPLACEMENT_POSITIONS)
        or None in replacement_ids
        or len(replacement_ids) != len(replaced)
        or len(replacement_shas) != len(replaced)
        or len(replacement_texts) != len(replaced)
        or None in replacement_clients
        or len(replacement_clients) != len(replaced)
        or len(replacement_teachers) != len(replaced)
        or replacement_ids & base_ids
        or replacement_shas & base_shas
        or replacement_texts & base_texts
        or replacement_teachers & base_teachers
    ):
        raise PostRehearsalError("EXP-317 replacement identity is not new and unique")
    return {
        "manifest_kind": manifest["kind"],
        "manifest_row_count": EXPECTED_ROWS,
        "replacement_row_count": len(replaced),
        "replacement_positions": list(CV32_REPLACEMENT_POSITIONS),
        "unchanged_row_count": EXPECTED_ROWS - len(replaced),
        "remaining_commonvoice_rows": 16,
        "position_specific_real_targets": True,
        "representation": None,
        "inference_attachment": None,
    }


_CV26_FORBIDDEN_ATTACHMENTS = {
    "source_representation",
    "representation_attachment",
    "inference_attachment",
    "inference_representation",
}


def _cv26_active_fraction(row: Mapping[str, Any]) -> float | None:
    """Read the materializer's active-window fraction without accepting a guess."""

    metadata = row.get("source_window")
    candidates: list[Any] = []
    if isinstance(metadata, Mapping):
        candidates.extend(
            metadata.get(key)
            for key in ("active_sample_fraction", "active_fraction")
        )
    candidates.extend(
        row.get(key)
        for key in ("active_sample_fraction", "active_fraction")
    )
    for value in candidates:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            fraction = float(value)
            if math.isfinite(fraction):
                return fraction
    return None


def _cv26_source_variant(row: Mapping[str, Any]) -> tuple[Any, ...]:
    """Return fields that identify the actual source bytes, not the CV speaker."""

    return (
        row.get("source_file"),
        row.get("source_sha256"),
        row.get("source_original_sha256"),
    )


def validate_cv26_manifest(
    manifest: Mapping[str, Any],
    *,
    reference_manifest: Mapping[str, Any] | None = None,
    current_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Admit EXP-318/319's fixed-position, 170-row CV26 pair."""

    kind = manifest.get("kind")
    if kind not in CV26_KINDS:
        return None
    items = manifest.get("items")
    if (
        not isinstance(items, list)
        or len(items) != EXPECTED_ROWS
        or manifest.get("composition") != CV26_COMPOSITION
    ):
        raise PostRehearsalError(
            "CV26 manifest drifted from the 170-row EXP-238 composition"
        )
    reference = reference_manifest or _load_exp238_manifest()
    reference_items = reference.get("items") if reference else None
    if not isinstance(reference_items, list) or len(reference_items) != EXPECTED_ROWS:
        raise PostRehearsalError("CV26 EXP-238 reference is unavailable")
    commonvoice_positions = tuple(
        index
        for index, row in enumerate(reference_items)
        if isinstance(row, Mapping) and row.get("domain") == "commonvoice-unpaired"
    )
    if (
        len(commonvoice_positions) != 48
        or any(
            position not in commonvoice_positions
            for position in CV26_REPLACEMENT_POSITIONS
        )
    ):
        raise PostRehearsalError("CV26 EXP-238 Common Voice positions drifted")
    if any(
        key in manifest and manifest.get(key) is not None
        for key in _CV26_FORBIDDEN_ATTACHMENTS
    ) or any(
        key in row and row.get(key) is not None
        for row in items
        if isinstance(row, Mapping)
        for key in _CV26_FORBIDDEN_ATTACHMENTS
    ):
        raise PostRehearsalError("CV26 policy must not attach representation/inference")

    replaced: list[Mapping[str, Any]] = []
    for position, (candidate, expected) in enumerate(
        zip(items, reference_items, strict=True)
    ):
        if not isinstance(candidate, Mapping) or not isinstance(expected, Mapping):
            raise PostRehearsalError(f"CV26 row is malformed at position {position}")
        if position not in CV26_REPLACEMENT_POSITIONS:
            if candidate != expected:
                raise PostRehearsalError(
                    f"CV26 unchanged EXP-238 row drifted at position {position}"
                )
            continue
        replaced.append(candidate)
        if (
            candidate.get("domain") != "commonvoice-unpaired"
            or expected.get("domain") != "commonvoice-unpaired"
            or not str(candidate.get("source_manifest_id", "")).startswith("EXP055:")
            or candidate.get("source_root") != "source-work"
            or candidate.get("target_root") != "diverse-work"
            or candidate.get("learning_target") != PSEUDOPARALLEL_LEARNING_TARGET
            or candidate.get("target_text") != candidate.get("source_text")
            or candidate.get("source_relative_distance") != 0.0
        ):
            raise PostRehearsalError(
                f"CV26 replacement source boundary drifted at position {position}"
            )
        for key in (
            "target_id",
            "real_target_text",
            "real_target_root",
            "real_target_file",
            "real_target_sha256",
        ):
            if candidate.get(key) != expected.get(key):
                raise PostRehearsalError(
                    f"CV26 position-specific real target drifted at {position}"
                )
        if kind == CV26_ACTIVE_WINDOW_OUTPUT_KIND:
            active_fraction = _cv26_active_fraction(candidate)
            if active_fraction is None or active_fraction <= 0.0:
                raise PostRehearsalError(
                    f"CV26 active-window fraction is not positive at {position}"
                )

    base_sources = [row for row in reference_items if isinstance(row, Mapping)]
    base_ids = {_source_identity(row) for row in base_sources}
    base_shas = {row.get("source_sha256") for row in base_sources}
    base_texts = {row.get("source_text") for row in base_sources}
    base_teachers = {row.get("teacher_id") for row in base_sources}
    replacement_ids = {_source_identity(row) for row in replaced}
    replacement_shas = {row.get("source_sha256") for row in replaced}
    replacement_texts = {row.get("source_text") for row in replaced}
    replacement_teachers = {row.get("teacher_id") for row in replaced}
    replacement_clients = {_client_identity(row) for row in replaced}
    if (
        len(replaced) != len(CV26_REPLACEMENT_POSITIONS)
        or None in replacement_ids
        or len(replacement_ids) != len(replaced)
        or len(replacement_shas) != len(replaced)
        or len(replacement_texts) != len(replaced)
        or None in replacement_clients
        or len(replacement_clients) != len(replaced)
        or len(replacement_teachers) != len(replaced)
        or replacement_ids & base_ids
        or replacement_shas & base_shas
        or replacement_texts & base_texts
        or replacement_teachers & base_teachers
    ):
        raise PostRehearsalError(
            "CV26 replacement source/teacher/client identity is not new and unique"
        )

    current_source_exact: bool | None = None
    if kind == CV26_CURRENT_WINDOW_OUTPUT_KIND and reference_manifest is None:
        current_reference = _load_exp317_manifest()
        current_items = current_reference.get("items") if current_reference else None
        if isinstance(current_items, list) and len(current_items) == EXPECTED_ROWS:
            current_source_exact = True
            for position in CV26_REPLACEMENT_POSITIONS:
                current = current_items[position]
                candidate = items[position]
                if not isinstance(current, Mapping) or not isinstance(
                    candidate, Mapping
                ):
                    raise PostRehearsalError(
                        "CV26 current-source comparison row is malformed"
                    )
                for key in (
                    "source_manifest_id",
                    "source_file",
                    "source_sha256",
                    "source_text",
                    "teacher_id",
                    "source_client_id_sha256",
                ):
                    if candidate.get(key) != current.get(key):
                        raise PostRehearsalError(
                            "EXP-318 current source drifted at "
                            f"position {position}: {key}"
                        )

    source_identity_distinct: bool | None = None
    if kind == CV26_ACTIVE_WINDOW_OUTPUT_KIND:
        comparison = current_manifest
        if comparison is None and reference_manifest is None:
            comparison = _load_exp317_manifest()
        current_items = comparison.get("items") if comparison else None
        if isinstance(current_items, list) and len(current_items) == EXPECTED_ROWS:
            source_identity_distinct = True
            for position in CV26_REPLACEMENT_POSITIONS:
                current = current_items[position]
                candidate = items[position]
                if not isinstance(current, Mapping) or not isinstance(
                    candidate, Mapping
                ):
                    raise PostRehearsalError(
                        "CV26 current-window comparison row is malformed"
                    )
                if _cv26_source_variant(candidate) == _cv26_source_variant(
                    current
                ):
                    raise PostRehearsalError(
                        "EXP-319 active source is identical to EXP-318 at "
                        f"position {position}"
                    )

    return {
        "manifest_kind": kind,
        "manifest_row_count": EXPECTED_ROWS,
        "replacement_row_count": len(replaced),
        "replacement_positions": list(CV26_REPLACEMENT_POSITIONS),
        "unchanged_row_count": EXPECTED_ROWS - len(replaced),
        "remaining_commonvoice_rows": 16,
        "position_specific_real_targets": True,
        "source_teacher_client_unique": True,
        "current_source_identity_exact": current_source_exact,
        "active_window_metadata": kind == CV26_ACTIVE_WINDOW_OUTPUT_KIND,
        "source_identity_distinct_from_current_window": source_identity_distinct,
        "source_identity_differs_from_exp318": source_identity_distinct,
        "representation": None,
        "inference_attachment": None,
    }


def validate_source_speaker_manifest(
    manifest: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Admit the shared EXP-325/326 85-speaker, two-utterance substrate.

    The source-speaker label is an explicit corpus identity, never inferred
    from a filename or from the Common Voice client hash.  Keeping this gate
    here means both the ordinary control and the GRL treatment consume the
    exact same ordered bytes and label map.
    """

    kind = manifest.get("kind")
    if kind not in SRC4VC_TWO_UTTERANCE_KINDS:
        return None
    items = manifest.get("items")
    if (
        not isinstance(items, list)
        or len(items) != EXPECTED_ROWS
        or manifest.get("composition") != SRC4VC_TWO_UTTERANCE_COMPOSITION
    ):
        raise PostRehearsalError(
            "EXP-325/326 manifest must contain exactly 170 SRC4VC rows"
        )
    labels: dict[str, list[int]] = {}
    source_hashes: set[str] = set()
    for position, row in enumerate(items):
        if not isinstance(row, Mapping):
            raise PostRehearsalError("EXP-325/326 source row is malformed")
        speaker = row.get("source_speaker_id")
        source_hash = row.get("source_sha256")
        if (
            not isinstance(speaker, str)
            or not speaker
            or not base._is_sha256(source_hash)
            or source_hash in source_hashes
        ):
            raise PostRehearsalError(
                "EXP-325/326 requires distinct hashed source rows and explicit "
                "source_speaker_id values"
            )
        source_hashes.add(source_hash)
        labels.setdefault(speaker, []).append(position)
    if len(labels) != SOURCE_SPEAKER_CLASS_COUNT or any(
        len(positions) != 2 for positions in labels.values()
    ):
        raise PostRehearsalError(
            "EXP-325/326 requires exactly 85 source-speaker classes x2 rows"
        )
    # If a materializer records the selected RECITATION index, enforce the
    # intended zero/one pair.  Older receipts omitted this redundant field, so
    # absence remains accepted while present metadata is strict.
    for speaker, positions in labels.items():
        values: list[Any] = []
        for position in positions:
            row = items[position]
            value = row.get("source_utterance_index", row.get("utterance_index"))
            if value is not None:
                values.append(value)
        if values and sorted(values) != [0, 1]:
            raise PostRehearsalError(
                f"EXP-325/326 utterance zero/one metadata drifted for {speaker}"
            )
    ordered_speakers = sorted(labels)
    label_map = {speaker: index for index, speaker in enumerate(ordered_speakers)}
    return {
        "manifest_kind": kind,
        "manifest_row_count": EXPECTED_ROWS,
        "source_speaker_class_count": len(label_map),
        "rows_per_source_speaker": 2,
        "source_speaker_label_map": label_map,
        "source_speaker_label_map_sha256": hashlib.sha256(
            json.dumps(label_map, ensure_ascii=True, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "source_hash_count": len(source_hashes),
        "ordered_pair_positions": {
            speaker: positions for speaker, positions in sorted(labels.items())
        },
        "same_manifest_for_control_and_treatment": True,
        "inference_attachment": None,
    }


def source_speaker_label_map(manifest: Mapping[str, Any]) -> dict[str, int]:
    """Return the deterministic sorted source-speaker class map."""

    receipt = validate_source_speaker_manifest(manifest)
    if receipt is None:
        raise PostRehearsalError("source-speaker labels require EXP-325/326 rows")
    return dict(receipt["source_speaker_label_map"])


def _load_exp238_manifest() -> Mapping[str, Any] | None:
    path = (
        REPO_ROOT
        / "artifacts/xvc-source-diversity/exp238-cross-corpus-control69-targets-v1"
        / "curriculum.json"
    )
    if not path.is_file() or path.is_symlink():
        return None
    value = load_json(path)
    return value if isinstance(value, Mapping) else None


def _load_exp317_manifest() -> Mapping[str, Any] | None:
    path = (
        REPO_ROOT
        / "artifacts/xvc-source-diversity/exp317-cv32-replacement170-v1"
        / "curriculum.json"
    )
    if not path.is_file() or path.is_symlink():
        return None
    value = load_json(path)
    return value if isinstance(value, Mapping) else None


def listening_policy(
    manifest_kind: str = OUTPUT_KIND,
    trainable_target: str = LORA69_TARGET,
    training_objective: str = GENERATIVE_OBJECTIVE,
    use_adapter_ema: bool = False,
    optimizer_mode: str = SEQUENTIAL_OPTIMIZER,
    parameter_anchor: bool = False,
    source_activity_envelope: bool = False,
) -> dict[str, Any]:
    """Return the complete shared-listener identity for the admitted method."""

    if manifest_kind in SRC4VC_TWO_UTTERANCE_KINDS:
        if (
            trainable_target != LORA69_TARGET
            or training_objective
            not in {
                PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
                PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE,
            }
            or not use_adapter_ema
            or optimizer_mode != SEQUENTIAL_OPTIMIZER
            or parameter_anchor
            or source_activity_envelope
        ):
            raise PostRehearsalError(
                "EXP-325/326 requires control69 LoRA69, ordinary real-adversarial "
                "loss, EMA, and the fixed sequential 170-update contract"
            )
        if training_objective == PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE:
            return {
                "slug": "exp326",
                "candidate_id": (
                    "src4vc170-two-utterance-pseudoparallel-source-speaker-"
                    "grl-real-adv-ema170"
                ),
                "candidate_name": (
                    "EXP-326 / SRC4VC two-utterance source-speaker GRL / "
                    "real-adversarial / EMA"
                ),
                "run_kind": (
                    "EXP-326 X-VC SRC4VC two-utterance source-speaker GRL "
                    "external7 evaluation"
                ),
                "result_kind": (
                    "liveconv-exp326-xvc-src4vc-two-utterance-source-speaker-"
                    "grl-real-adv-ema/v1"
                ),
                "question": (
                    "Does reversing normalized source-speaker CE from the "
                    "post-converter latent improve robust target-voice conversion "
                    "without adding content corruption?"
                ),
                "independent_variable": (
                    "relative to matched EXP-325 on the exact same ordered 170 "
                    "SRC4VC rows (85 explicit source speakers x2), only a "
                    "training-only 2048-value mean/std pooled acoustic-converter "
                    "latent head changes the generator gradient: its detached-x "
                    "classifier step is separate, then its normalized 85-class CE "
                    "gradient is reversed into the existing control69 LoRA69; "
                    "ordinary composite plus real-adversarial losses, target order, "
                    "LR, 170 updates, EMA, zero frame condition, normal quantized "
                    "inference, and export remain fixed; the head is not exported"
                ),
                "source_speaker_grl": True,
            }
        return {
            "slug": "exp325",
            "candidate_id": (
                "src4vc170-two-utterance-pseudoparallel-real-adv-ema170"
            ),
            "candidate_name": (
                "EXP-325 / matched SRC4VC two-utterance control / "
                "real-adversarial / EMA"
            ),
            "run_kind": (
                "EXP-325 X-VC SRC4VC two-utterance matched control external7 "
                "evaluation"
            ),
            "result_kind": (
                "liveconv-exp325-xvc-src4vc-two-utterance-real-adv-ema/v1"
            ),
            "question": (
                "What does ordinary source-aligned pseudoparallel training do on "
                "the fixed two-utterance-per-speaker SRC4VC substrate?"
            ),
            "independent_variable": (
                "the exact 170-row, 85-speaker x2 SRC4VC source manifest is used "
                "as the matched EXP-326 control; control69 LoRA69 initialization, "
                "ordinary complete generative plus real-adversarial loss, LR, "
                "sequential 170 updates, EMA, zero frame condition, normal "
                "quantized source acoustics, and ordinary inference remain fixed"
            ),
            "source_speaker_grl": False,
        }

    if manifest_kind in CV26_KINDS:
        if (
            trainable_target != LORA69_TARGET
            or training_objective != PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE
            or not use_adapter_ema
            or optimizer_mode != SEQUENTIAL_OPTIMIZER
            or parameter_anchor
            or source_activity_envelope
        ):
            raise PostRehearsalError(
                "EXP-318/319 requires the exact EXP-238 model and loss contract"
            )
        if manifest_kind == CV26_CURRENT_WINDOW_OUTPUT_KIND:
            return {
                "slug": "exp318",
                "candidate_id": (
                    "cross-corpus170-pseudoparallel-cv26-current-window-"
                    "real-adv-ema170"
                ),
                "candidate_name": (
                    "EXP-318 / CV26 current-window control / source-aligned "
                    "targets / real-adversarial / EMA"
                ),
                "run_kind": (
                    "EXP-318 X-VC pseudoparallel CV26 current-window control "
                    "external7 evaluation"
                ),
                "result_kind": (
                    "liveconv-exp318-xvc-pseudoparallel-cv26-current-window-"
                    "real-adv-ema/v1"
                ),
                "question": (
                    "Does the evaluation-style CV26 current-window construction "
                    "preserve content and avoid corruption on external7?"
                ),
                "independent_variable": (
                    "relative to exact EXP-238, only 26 fixed Common Voice "
                    "positions use the retained current-window sources and new "
                    "source-aligned control69 teacher tuples; the other 144 "
                    "rows, position-specific real Amitaro targets and text, "
                    "generator plus real-adversarial loss, control69 LoRA69 "
                    "initialization/scope, LR, sequential 170 updates, norm-5 "
                    "clip, zero frame condition, discriminator, EMA, normal "
                    "quantized source acoustics, and ordinary inference remain "
                    "fixed"
                ),
            }
        return {
            "slug": "exp319",
            "candidate_id": (
                "cross-corpus170-pseudoparallel-cv26-active-window-"
                "real-adv-ema170"
            ),
            "candidate_name": (
                "EXP-319 / CV26 active-window treatment / source-aligned "
                "targets / real-adversarial / EMA"
            ),
            "run_kind": (
                "EXP-319 X-VC pseudoparallel CV26 active-window external7 "
                "evaluation"
            ),
            "result_kind": (
                "liveconv-exp319-xvc-pseudoparallel-cv26-active-window-"
                "real-adv-ema/v1"
            ),
            "question": (
                "Does speech-active CV26 window construction preserve content "
                "and avoid corruption on external7?"
            ),
            "independent_variable": (
                "relative to exact EXP-318 and EXP-238, only the same 26 fixed "
                "Common Voice positions use distinct speech-active source "
                "windows with positive active fraction; the other 144 rows, "
                "position-specific real Amitaro targets and text, generator "
                "plus real-adversarial loss, control69 LoRA69 initialization/"
                "scope, LR, sequential 170 updates, norm-5 clip, zero frame "
                "condition, discriminator, EMA, normal quantized source "
                "acoustics, and ordinary inference remain fixed"
            ),
        }

    if manifest_kind in CV32_REPLACEMENT_KINDS:
        if (
            trainable_target != LORA69_TARGET
            or training_objective != PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE
            or not use_adapter_ema
            or optimizer_mode != SEQUENTIAL_OPTIMIZER
            or parameter_anchor
            or source_activity_envelope
        ):
            raise PostRehearsalError(
                "EXP-317 requires the exact EXP-238 model and loss contract"
            )
        return {
            "slug": "exp317",
            "candidate_id": (
                "cross-corpus170-pseudoparallel-cv32-replacement-"
                "real-adv-ema170"
            ),
            "candidate_name": (
                "EXP-317 / CV32 replacement / source-aligned targets / "
                "real-adversarial / EMA"
            ),
            "run_kind": (
                "EXP-317 X-VC pseudoparallel CV32 replacement external7 evaluation"
            ),
            "result_kind": (
                "liveconv-exp317-xvc-pseudoparallel-cv32-replacement-"
                "real-adv-ema/v1"
            ),
            "question": (
                "Does replacing 32 Common Voice training tuples preserve content "
                "and avoid corruption on fixed external7?"
            ),
            "independent_variable": (
                "relative to exact EXP-238, only the first 32 ordered Common Voice "
                "positions are replaced by the disjoint CV32 source and frozen "
                "control69 teacher tuples; the remaining 138 rows, including 16 "
                "Common Voice rows, position-specific real Amitaro assignments, "
                "complete generator plus real-adversarial loss, control69 LoRA69 "
                "initialization/scope, LR, sequential optimizer, norm-5 clip, zero "
                "frame condition, discriminator, EMA, normal quantized source "
                "acoustics, ordinary inference, and external7 remain fixed"
            ),
        }

    if manifest_kind in CV32_PSEUDOPARALLEL_KINDS:
        if (
            trainable_target != LORA69_TARGET
            or training_objective != PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE
            or not use_adapter_ema
            or optimizer_mode != SEQUENTIAL_OPTIMIZER
            or parameter_anchor
            or source_activity_envelope
        ):
            raise PostRehearsalError(
                "EXP-305/306 requires the exact EXP-238 model and loss contract"
            )
        if manifest_kind == CV32_REPEAT_OUTPUT_KIND:
            return {
                "slug": "exp305",
                "candidate_id": (
                    "cross-corpus202-pseudoparallel-repeat32-control-real-adv-ema202"
                ),
                "candidate_name": (
                    "EXP-305 / exact EXP-238 + matched Common Voice repeat32 / "
                    "real-adversarial / EMA"
                ),
                "run_kind": "EXP-305 X-VC pseudoparallel repeat32 external7 evaluation",
                "result_kind": (
                    "liveconv-exp305-xvc-pseudoparallel-repeat32-control-real-adv-ema/v1"
                ),
                "question": (
                    "Does a 202-update repeat32 control distinguish horizon from "
                    "genuine Common Voice breadth on external7?"
                ),
                "independent_variable": (
                    "relative to exact EXP-238, only 32 repeats of its first "
                    "Common Voice rows are appended in original order; model, "
                    "complete generator plus real-Amitaro adversarial loss, "
                    "control69 LoRA69 initialization/scope, LR, sequential "
                    "optimizer, norm-5 clip, zero frame condition, discriminator, "
                    "EMA, normal quantized source acoustics, ordinary inference, "
                    "and external7 evaluation remain fixed"
                ),
            }
        return {
            "slug": "exp306",
            "candidate_id": (
                "cross-corpus202-pseudoparallel-cv32-breadth-real-adv-ema202"
            ),
            "candidate_name": (
                "EXP-306 / exact EXP-238 + genuine Common Voice32 breadth / "
                "real-adversarial / EMA"
            ),
            "run_kind": "EXP-306 X-VC pseudoparallel CV32 external7 evaluation",
            "result_kind": (
                "liveconv-exp306-xvc-pseudoparallel-cv32-breadth-real-adv-ema/v1"
            ),
            "question": (
                "Does adding 32 genuinely new Common Voice speakers and texts "
                "improve broad X-VC conversion at the matched 202-update horizon?"
            ),
            "independent_variable": (
                "relative to exact EXP-238, only 32 genuinely new Common Voice "
                "source IDs, audio hashes, texts, and clients are appended after "
                "the unchanged ordered 170 rows; model, complete generator plus "
                "real-Amitaro adversarial loss, control69 LoRA69 initialization/"
                "scope, LR, sequential optimizer, norm-5 clip, zero frame "
                "condition, discriminator, EMA, normal quantized source acoustics, "
                "ordinary inference, and external7 evaluation remain fixed"
            ),
        }

    if training_objective == PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE:
        if (
            manifest_kind != PSEUDOPARALLEL_OUTPUT_KIND
            or trainable_target != LORA69_TARGET
            or not use_adapter_ema
            or optimizer_mode != SEQUENTIAL_OPTIMIZER
            or parameter_anchor
            or source_activity_envelope
        ):
            raise PostRehearsalError(
                "robust semantic decoder requires the exact EXP-238 contract"
            )
        return {
            "slug": "exp297",
            "candidate_id": (
                "cross-corpus170-pseudoparallel-robust-semantic-real-adv-ema170"
            ),
            "candidate_name": (
                "EXP-297 / source-aligned targets / scale-matched robust semantic "
                "decoder / real-adversarial / EMA"
            ),
            "run_kind": (
                "EXP-297 X-VC pseudoparallel robust-semantic evaluation"
            ),
            "result_kind": (
                "liveconv-exp297-xvc-pseudoparallel-robust-semantic-real-adv-ema/v1"
            ),
            "question": (
                "Does scale-matched SmoothL1 semantic-decoder supervision improve "
                "robust X-VC conversion while preserving the exact EXP-238 lane?"
            ),
            "independent_variable": (
                "relative to the exact EXP-238 contract, only the standard "
                "weight-1000 semantic decoder MSE between outputs['pred'] and "
                "outputs['ssl_feat'] changes to 2.0 * SmoothL1(beta=1.0); the "
                f"implementation is {ROBUST_SEMANTIC_IMPLEMENTATION}; the "
                "outer semantic weight remains 1000, so the differentiable total "
                "substitution is 1000*(2.0*smooth_l1 - mse); normal quantized "
                "source representation, speaker MSE, mel, VQ, real-wave "
                "adversarial/feature losses, CV48/JSUT85/JVS3/Hadou34 data, "
                "source-aligned control69 teacher targets, exact ordered real "
                "Amitaro targets, control69 LoRA69 initialization and scope, LR, "
                "sequential 170 updates, clip, zero frame condition, discriminator, "
                "and EMA remain fixed; inference has no attachment"
            ),
        }

    if training_objective == PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE:
        if (
            manifest_kind != PSEUDOPARALLEL_OUTPUT_KIND
            or trainable_target != LORA69_TARGET
            or not use_adapter_ema
            or optimizer_mode != SEQUENTIAL_OPTIMIZER
            or parameter_anchor
            or source_activity_envelope
        ):
            raise PostRehearsalError(
                "acoustic temporal jitter requires the exact EXP-238 contract"
            )
        return {
            "slug": "exp291",
            "candidate_id": (
                "cross-corpus170-pseudoparallel-acoustic-temporal-jitter-"
                "real-adv-ema170"
            ),
            "candidate_name": (
                "EXP-291 / source-aligned targets / acoustic temporal jitter / EMA"
            ),
            "run_kind": (
                "EXP-291 X-VC pseudoparallel acoustic temporal jitter evaluation"
            ),
            "result_kind": (
                "liveconv-exp291-xvc-pseudoparallel-acoustic-temporal-jitter-"
                "real-adv-ema/v1"
            ),
            "question": (
                "Does a one-frame right shift of quantized source acoustics on "
                "odd training rows improve robust X-VC conversion while normal "
                "inference remains unchanged?"
            ),
            "independent_variable": (
                "relative to the exact EXP-238 contract, only the quantizer's "
                "first output zq_a changes on deterministic odd-indexed 85 of "
                "170 training rows to torch.cat([zq_a[..., :1], zq_a[..., :-1]], "
                "dim=-1); the other 85 rows use normal quantized zq_a, all "
                "quantizer bookkeeping, data, targets, complete losses, LR, "
                "control69 LoRA69 initialization and scope, discriminator, "
                "optimizer, clip, zero frame condition, and EMA remain fixed; "
                "inference uses normal quantized zq_a"
            ),
        }

    if (
        trainable_target == SPEAKER_CONDITION_CALIBRATOR_TARGET
        or training_objective == PSEUDOPARALLEL_CONDITION_CALIBRATOR_OBJECTIVE
    ):
        if (
            manifest_kind != PSEUDOPARALLEL_OUTPUT_KIND
            or trainable_target != SPEAKER_CONDITION_CALIBRATOR_TARGET
            or training_objective
            != PSEUDOPARALLEL_CONDITION_CALIBRATOR_OBJECTIVE
            or not use_adapter_ema
            or optimizer_mode != SEQUENTIAL_OPTIMIZER
            or parameter_anchor
            or source_activity_envelope
        ):
            raise PostRehearsalError(
                "speaker-condition calibration requires the exact EXP-259 pilot"
            )
        return {
            "slug": "exp259",
            "candidate_id": (
                "exp238-speaker-condition-delta-output-speaker-ema170"
            ),
            "candidate_name": (
                "EXP-259 / frozen EXP-238 + speaker-condition delta / EMA"
            ),
            "run_kind": "EXP-259 X-VC speaker-condition calibration evaluation",
            "result_kind": (
                "liveconv-exp259-xvc-speaker-condition-calibrator-ema/v1"
            ),
            "question": (
                "Can a 192-parameter target-speaker condition calibration retain "
                "EXP-252's identity direction without changing content weights?"
            ),
            "independent_variable": (
                "freeze the exact EXP-238 EMA adapter and add only one zero-"
                "initialized 192-value delta to the frozen target-speaker "
                "embedding immediately before the acoustic converter; train that "
                "delta with EXP-252's unchanged weight-10 final-WAV ERes2Net loss "
                "plus the exact EXP-238 complete generative and real-adversarial "
                "objectives; curriculum, source-aligned targets, real Amitaro "
                "references, LR, sequential 170 updates, clip, zero frame "
                "condition, discriminator, and EMA remain fixed"
            ),
        }

    if (
        manifest_kind in PSEUDOPARALLEL_KINDS
        or training_objective
        in {
            PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
            PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE,
            PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE,
            PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE,
            PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE,
            PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE,
            PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
            PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE,
            PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE,
        }
    ):
        if (
            manifest_kind not in PSEUDOPARALLEL_KINDS
            or trainable_target != LORA69_TARGET
            or training_objective
            not in {
                PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
                PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE,
                PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE,
                PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE,
                PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE,
                PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE,
                PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
                PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE,
                PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE,
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
            and training_objective == PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE
        ):
            raise PostRehearsalError(
                "continuous acoustic latent requires the retained EXP-238 curriculum"
            )
        if (
            manifest_kind == SRC4VC_PSEUDOPARALLEL_OUTPUT_KIND
            and training_objective
            in {
                PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
                PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE,
                PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE,
                PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE,
                PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE,
            }
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
        if training_objective == PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE:
            return {
                "slug": "exp285",
                "candidate_id": (
                    "cross-corpus170-pseudoparallel-continuous-acoustic-"
                    "real-adv-ema170"
                ),
                "candidate_name": (
                    "EXP-285 / source-aligned targets / continuous pre-VQ "
                    "acoustic latent / EMA"
                ),
                "run_kind": (
                    "EXP-285 X-VC pseudoparallel continuous-acoustic evaluation"
                ),
                "result_kind": (
                    "liveconv-exp285-xvc-pseudoparallel-continuous-acoustic-ema/v1"
                ),
                "question": (
                    "Does replacing quantized source acoustics with the frozen "
                    "quantizer's projected continuous pre-VQ latent improve "
                    "robust X-VC conversion?"
                ),
                "independent_variable": (
                    "relative to EXP-238, only the source representation changes: "
                    "at both training and inference the quantized source acoustic "
                    "output is replaced by the frozen quantizer's projected "
                    "continuous pre-VQ representation out_project(in_project("
                    "acoustic_encoder_out)); quantizer outputs and bookkeeping "
                    "remain intact; the exact CV48/JSUT85/JVS3/Hadou34 curriculum, "
                    "source-aligned control69 teacher targets, assigned real "
                    "Amitaro adversarial targets, control69 LoRA69 initialization "
                    "and scope, complete losses, LR, sequential 170 updates, "
                    "clip, zero frame condition, discriminator, and EMA remain "
                    "fixed"
                ),
            }
        if training_objective == PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE:
            return {
                "slug": "exp273",
                "candidate_id": (
                    "cross-corpus170-pseudoparallel-fresh-lora-real-adv-ema170"
                ),
                "candidate_name": (
                    "EXP-273 / source-aligned targets / fresh LoRA69 / EMA"
                ),
                "run_kind": "EXP-273 X-VC fresh-LoRA pseudoparallel evaluation",
                "result_kind": (
                    "liveconv-exp273-xvc-pseudoparallel-fresh-lora-ema/v1"
                ),
                "question": (
                    "Does learning the source-aligned teacher from a fresh LoRA "
                    "avoid inherited control69 failures and improve robust X-VC?"
                ),
                "independent_variable": (
                    "relative to EXP-238, only LoRA69 initialization changes from "
                    "the trained EXP-035 control69 adapter to a new zero-initialized "
                    "rank-8 adapter on the same frozen base X-VC; the exact "
                    "CV48/JSUT85/JVS3/Hadou34 curriculum, source-aligned control69 "
                    "teacher targets, assigned real Amitaro adversarial targets, "
                    "complete generative and real-adversarial losses, trainable "
                    "scope, LR, sequential 170 updates, clip, zero frame condition, "
                    "discriminator, and EMA remain fixed"
                ),
            }
        if training_objective == PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE:
            return {
                "slug": "exp279",
                "candidate_id": (
                    "cross-corpus170-pseudoparallel-acoustic-dropout-"
                    "real-adv-ema170"
                ),
                "candidate_name": (
                    "EXP-279 / source-aligned targets / acoustic-code dropout / EMA"
                ),
                "run_kind": (
                    "EXP-279 X-VC pseudoparallel acoustic-code dropout evaluation"
                ),
                "result_kind": (
                    "liveconv-exp279-xvc-pseudoparallel-acoustic-code-dropout-ema/v1"
                ),
                "question": (
                    "Does reducing training reliance on quantized source acoustics "
                    "improve robust X-VC conversion across speakers and conditions?"
                ),
                "independent_variable": (
                    "relative to EXP-238, only the source representation on 85 "
                    "alternating training rows changes by zeroing the quantized "
                    "acoustic code before concatenation with unchanged semantic "
                    "tokens; the other 85 rows and listen-now inference remain "
                    "unmasked; the exact CV48/JSUT85/JVS3/Hadou34 curriculum, "
                    "source-aligned control69 teacher targets, assigned real "
                    "Amitaro adversarial targets, control69 LoRA69 initialization "
                    "and scope, complete losses, LR, sequential 170 updates, clip, "
                    "zero frame condition, discriminator, and EMA remain fixed"
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
        if training_objective == PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE:
            return {
                "slug": "exp266",
                "candidate_id": (
                    "cross-corpus170-pseudoparallel-latent-speaker-margin-ema170"
                ),
                "candidate_name": (
                    "EXP-266 / source-speaker leakage margin / EMA"
                ),
                "run_kind": "EXP-266 X-VC latent speaker leakage evaluation",
                "result_kind": (
                    "liveconv-exp266-xvc-latent-speaker-margin-ema/v1"
                ),
                "question": (
                    "Does explicitly rejecting source-speaker leakage in X-VC's "
                    "converter latent improve robust target-voice conversion?"
                ),
                "independent_variable": (
                    "relative to EXP-238, add one weight-10 hinge loss requiring "
                    "the converter-latent speaker prediction's target cosine to "
                    "exceed its frozen source-speaker ERes2Net cosine by margin "
                    "0.1; the exact CV48/JSUT85/JVS3/Hadou34 curriculum, source-"
                    "aligned control69 targets, real Amitaro discriminator targets, "
                    "complete generative loss including the existing target-speaker "
                    "MSE, control69 LoRA69 initialization and scope, LR, sequential "
                    "170 updates, clip, zero frame condition, discriminator, and EMA "
                    "remain fixed"
                ),
            }
        if training_objective == PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE:
            return {
                "slug": "exp267",
                "candidate_id": (
                    "cross-corpus170-pseudoparallel-real-speaker-condition-ema170"
                ),
                "candidate_name": (
                    "EXP-267 / real target-speaker condition / EMA"
                ),
                "run_kind": "EXP-267 X-VC real speaker-condition evaluation",
                "result_kind": (
                    "liveconv-exp267-xvc-real-speaker-condition-ema/v1"
                ),
                "question": (
                    "Does conditioning X-VC on the real target speaker while "
                    "retaining source-aligned teacher audio improve robust voice "
                    "conversion?"
                ),
                "independent_variable": (
                    "relative to EXP-238, only the waveform used for X-VC's global "
                    "speaker condition and existing speaker-predictor MSE changes "
                    "from the source-aligned control69 teacher output to that row's "
                    "assigned authorized real Amitaro window; the teacher output "
                    "remains the exact semantic and mel reconstruction target, and "
                    "the exact CV48/JSUT85/JVS3/Hadou34 curriculum, real adversarial "
                    "target, complete loss and weights, control69 LoRA69 "
                    "initialization and scope, LR, sequential 170 updates, clip, "
                    "zero frame condition, discriminator, and EMA remain fixed"
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
    elif kind in CV32_PSEUDOPARALLEL_KINDS:
        expected_domains = CV32_EXPECTED_COMPOSITION
    elif kind in CV32_REPLACEMENT_KINDS:
        expected_domains = CV32_REPLACEMENT_COMPOSITION
    elif kind in CV26_KINDS:
        expected_domains = CV26_COMPOSITION
    elif kind in SRC4VC_TWO_UTTERANCE_KINDS:
        expected_domains = SRC4VC_TWO_UTTERANCE_COMPOSITION
    elif kind == COMMONVOICE_RETENTION_OUTPUT_KIND:
        expected_domains = COMMONVOICE_RETENTION_EXPECTED_DOMAINS
    elif kind == CONDITIONED_RETENTION_OUTPUT_KIND:
        expected_domains = CONDITIONED_RETENTION_EXPECTED_DOMAINS
    elif kind in {HARD_OUTPUT_KIND, SELECTIVE_OUTPUT_KIND}:
        expected_domains = HARD_EXPECTED_DOMAINS
    else:
        expected_domains = EXPECTED_DOMAINS
    expected_rows = expected_training_rows(str(kind))
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
            CV32_REPEAT_OUTPUT_KIND,
            CV32_BREADTH_OUTPUT_KIND,
            CV32_REPLACEMENT_OUTPUT_KIND,
            *CV26_KINDS,
            *SRC4VC_TWO_UTTERANCE_KINDS,
        }
        or value.get("composition") != expected_domains
        or not isinstance(items, list)
        or len(items) != expected_rows
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
    validate_cv32_manifest(value)
    validate_cv32_replacement_manifest(value)
    validate_cv26_manifest(value)
    validate_source_speaker_manifest(value)
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
    if arguments.trainable_target == SPEAKER_CONDITION_CALIBRATOR_TARGET:
        initial = arguments.initial_adapter
        weights = (
            initial / "adapter_model.safetensors"
            if initial is not None
            else None
        )
        if (
            initial is None
            or initial.is_symlink()
            or weights is None
            or weights.is_symlink()
            or not weights.is_file()
            or sha256_file(weights) != EXP238_ADAPTER_SHA256
        ):
            raise PostRehearsalError("exact EXP-238 EMA adapter is required")
    elif arguments.initial_adapter is not None:
        raise PostRehearsalError(
            "initial adapter is admitted only for speaker-condition calibration"
        )
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


def robust_semantic_receipt(
    manifest_kind: str = PSEUDOPARALLEL_OUTPUT_KIND,
) -> dict[str, Any]:
    """Bind the loss-only EXP-297 change to the exact EXP-238 lane."""

    if manifest_kind != PSEUDOPARALLEL_OUTPUT_KIND:
        raise PostRehearsalError(
            "robust semantic decoder requires exact EXP-238 manifest"
        )
    if ROBUST_SEMANTIC_WEIGHT != role_mix.STANDARD_LOSS_WEIGHTS["mse_loss"]:
        raise PostRehearsalError("robust semantic weight drifted from standard MSE")
    return {
        "implementation": ROBUST_SEMANTIC_IMPLEMENTATION,
        "beta": ROBUST_SEMANTIC_BETA,
        "scale_factor": ROBUST_SEMANTIC_SCALE,
        "weight": ROBUST_SEMANTIC_WEIGHT,
        "replacement": "1000*(2.0*smooth_l1_loss(beta=1.0)-mse_loss)",
        "reference": "exact-EXP-238-pseudoparallel-contract",
        "manifest_kind": manifest_kind,
        "exp238_adapter_sha256": EXP238_ADAPTER_SHA256,
        "normal_quantized_representation": True,
        "inference_attachment": None,
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


def _base_xvc(model: Any) -> Any:
    return model.get_base_model() if hasattr(model, "get_base_model") else model


def acoustic_code_dropout_schedule(row_count: int) -> list[bool]:
    """Alternate exact clean/masked rows without adding training randomness."""

    if row_count not in {2, EXPECTED_ROWS} or row_count % 2:
        raise PostRehearsalError("acoustic-code dropout row count drifted")
    schedule = [bool(index % 2) for index in range(row_count)]
    if schedule.count(False) != schedule.count(True):
        raise PostRehearsalError("acoustic-code dropout balance drifted")
    return schedule


def acoustic_temporal_jitter_schedule(row_count: int) -> list[bool]:
    """Alternate exact normal/shifted rows without training randomness."""

    if row_count not in {2, EXPECTED_ROWS} or row_count % 2:
        raise PostRehearsalError("acoustic temporal jitter row count drifted")
    schedule = [bool(index % 2) for index in range(row_count)]
    if schedule.count(False) != schedule.count(True):
        raise PostRehearsalError("acoustic temporal jitter balance drifted")
    return schedule


def training_row_identity_receipt(
    manifest: Mapping[str, Any], rows: Sequence[Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """Record the ordered EXP-238 row identity used by the jitter schedule."""

    if manifest.get("kind") != PSEUDOPARALLEL_OUTPUT_KIND:
        raise PostRehearsalError("acoustic temporal jitter requires EXP-238 rows")
    items = manifest.get("items")
    if not isinstance(items, list) or len(items) != EXPECTED_ROWS:
        raise PostRehearsalError("EXP-238 training row identity drifted")
    selected = list(items if rows is None else rows)
    if not selected or len(selected) > len(items):
        raise PostRehearsalError("acoustic temporal jitter row selection drifted")
    expected_by_id = {
        str(item["id"]): (position, item)
        for position, item in enumerate(items)
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    identities: list[dict[str, Any]] = []
    for item in selected:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
            raise PostRehearsalError("EXP-238 row identity changed")
        expected = expected_by_id.get(item["id"])
        if expected is None:
            raise PostRehearsalError("EXP-238 row identity changed")
        position, expected_item = expected
        for key in (
            "teacher_id",
            "target_id",
            "source_sha256",
            "target_sha256",
            "real_target_sha256",
        ):
            if item.get(key) != expected_item.get(key):
                raise PostRehearsalError("EXP-238 row identity changed")
        identities.append(
            {
                "position": position,
                "id": item["id"],
                "teacher_id": item.get("teacher_id"),
                "target_id": item.get("target_id"),
                "source_sha256": item.get("source_sha256"),
                "target_sha256": item.get("target_sha256"),
                "real_target_sha256": item.get("real_target_sha256"),
            }
        )
    positions = [item["position"] for item in identities]
    if positions != list(range(len(identities))):
        raise PostRehearsalError("EXP-238 training row order changed")
    encoded = json.dumps(
        identities, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "source": "exact-exp238-ordered-training-manifest",
        "manifest_kind": manifest["kind"],
        "manifest_row_count": len(items),
        "selected_row_count": len(identities),
        "selected_positions": positions,
        "row_ids": [item["id"] for item in identities],
        "row_identity_sha256": hashlib.sha256(encoded).hexdigest(),
        "unchanged": True,
    }


def finite_nonzero_gradient_diagnostics(
    parameters: Sequence[Any], *, torch: Any
) -> dict[str, float | int | bool]:
    """Require and summarize finite, nonzero trainable gradients for smoke."""

    gradients = [
        parameter.grad for parameter in parameters if parameter.grad is not None
    ]
    if not gradients:
        raise PostRehearsalError("acoustic temporal jitter produced no gradients")
    if not all(bool(torch.isfinite(gradient).all()) for gradient in gradients):
        raise PostRehearsalError(
            "acoustic temporal jitter produced non-finite gradients"
        )
    nonzero_elements = sum(
        int(torch.count_nonzero(gradient).detach().cpu()) for gradient in gradients
    )
    if nonzero_elements <= 0:
        raise PostRehearsalError(
            "acoustic temporal jitter produced zero trainable gradients"
        )
    squared_norm = sum(
        float(torch.sum(torch.square(gradient.detach().float())).cpu())
        for gradient in gradients
    )
    norm = math.sqrt(squared_norm)
    if not math.isfinite(norm) or norm <= 0.0:
        raise PostRehearsalError("acoustic temporal jitter gradient norm is invalid")
    return {
        "finite": True,
        "nonzero_elements": nonzero_elements,
        "l2_norm": norm,
    }


def source_speaker_pooled_features(x: Any, *, torch: Any) -> Any:
    """Mean/std-pool an acoustic-converter latent ``[B,1024,T]`` to 2048."""

    if (
        not hasattr(x, "ndim")
        or x.ndim != 3
        or x.shape[1] != 1024
        or x.shape[-1] < 1
        or not bool(torch.isfinite(x).all())
    ):
        raise PostRehearsalError(
            "source-speaker acoustic-converter latent must be finite [B,1024,T]"
        )
    value = x.float()
    pooled = torch.cat(
        (value.mean(dim=-1), value.std(dim=-1, unbiased=False)), dim=-1
    )
    if pooled.shape[-1] != SOURCE_SPEAKER_FEATURE_DIMENSION or not bool(
        torch.isfinite(pooled).all()
    ):
        raise PostRehearsalError("source-speaker pooled feature shape drifted")
    return pooled


def source_speaker_signal_probe(
    features: Any,
    source_speaker_ids: Sequence[str],
    *,
    torch: Any,
) -> dict[str, Any]:
    """Identify each speaker's second utterance from its first latent centroid."""

    if (
        not hasattr(features, "ndim")
        or features.ndim != 2
        or features.shape[-1] != SOURCE_SPEAKER_FEATURE_DIMENSION
        or len(source_speaker_ids) != int(features.shape[0])
    ):
        raise PostRehearsalError("source-speaker probe feature shape drifted")
    positions: dict[str, list[int]] = {}
    for position, speaker in enumerate(source_speaker_ids):
        if not isinstance(speaker, str) or not speaker:
            raise PostRehearsalError("source-speaker probe label is malformed")
        positions.setdefault(speaker, []).append(position)
    if len(positions) != SOURCE_SPEAKER_CLASS_COUNT or any(
        len(value) != 2 for value in positions.values()
    ):
        raise PostRehearsalError("source-speaker probe requires 85 classes x2")
    ordered = sorted(positions)
    centroids = torch.stack([features[positions[key][0]] for key in ordered]).float()
    queries = torch.stack([features[positions[key][1]] for key in ordered]).float()
    centroids = torch.nn.functional.normalize(centroids, dim=-1)
    queries = torch.nn.functional.normalize(queries, dim=-1)
    similarities = queries @ centroids.transpose(0, 1)
    if not bool(torch.isfinite(similarities).all()):
        raise PostRehearsalError("source-speaker probe similarities are non-finite")
    ranks = similarities.argsort(dim=-1, descending=True)
    truth = torch.arange(len(ordered), device=ranks.device).unsqueeze(1)
    top1 = (ranks[:, :1] == truth).any(dim=1).float().mean()
    top5 = (ranks[:, :5] == truth).any(dim=1).float().mean()
    top1_value = float(top1.detach().cpu())
    top5_value = float(top5.detach().cpu())
    chance_top1 = 1.0 / SOURCE_SPEAKER_CLASS_COUNT
    chance_top5 = 5.0 / SOURCE_SPEAKER_CLASS_COUNT
    materially_above_chance = (
        top1_value >= SOURCE_SPEAKER_PROBE_MIN_TOP1_MULTIPLE * chance_top1
        and top5_value >= SOURCE_SPEAKER_PROBE_MIN_TOP5_MULTIPLE * chance_top5
    )
    return {
        "implementation": SOURCE_SPEAKER_PROBE_IMPLEMENTATION,
        "class_count": SOURCE_SPEAKER_CLASS_COUNT,
        "reference_utterance": 0,
        "query_utterance": 1,
        "top1_accuracy": top1_value,
        "top5_accuracy": top5_value,
        "chance_top1": chance_top1,
        "chance_top5": chance_top5,
        "top1_over_chance": top1_value / chance_top1,
        "top5_over_chance": top5_value / chance_top5,
        "materially_above_chance": materially_above_chance,
    }


def attach_source_speaker_adversary(
    model: Any,
    *,
    torch: Any,
) -> Any:
    """Capture converter latents only while the EXP-326 training hook is live."""

    xvc = _base_xvc(model)
    converter = getattr(xvc, CONVERTER_PREFIX, None)
    if converter is None:
        raise PostRehearsalError("source-speaker converter hook is unavailable")

    class SourceSpeakerAdversary:
        def __init__(self, target: Any) -> None:
            self.target = target
            self.enabled = False
            self.latest = None
            self.training_calls = 0
            self.inference_calls = 0
            self.removed = False
            self._handle = target.register_forward_hook(self._capture)

        def _capture(self, _module: Any, _inputs: Any, output: Any) -> None:
            if not self.enabled:
                self.inference_calls += 1
                return
            if not hasattr(output, "shape"):
                raise PostRehearsalError(
                    "source-speaker converter hook output is malformed"
                )
            self.latest = output
            self.training_calls += 1

        def set_enabled(self, enabled: bool) -> None:
            self.enabled = bool(enabled)
            if not self.enabled:
                self.latest = None

        def clear(self) -> None:
            self.latest = None

        def pooled(self) -> Any:
            if self.latest is None:
                raise PostRehearsalError(
                    "source-speaker converter hook captured no training latent"
                )
            return source_speaker_pooled_features(self.latest, torch=torch)

        def diagnostics(self) -> dict[str, Any]:
            return {
                "implementation": SOURCE_SPEAKER_POOL_IMPLEMENTATION,
                "training_only": True,
                "training_calls": self.training_calls,
                "inference_calls": self.inference_calls,
                "hook_removed_before_inference": self.removed,
            }

        def close(self) -> None:
            self.enabled = False
            self.latest = None
            self._handle.remove()
            self.removed = True

    return SourceSpeakerAdversary(converter)


def source_speaker_classifier(
    *,
    torch: Any,
    device: Any = None,
) -> Any:
    """Create the training-only 2048 -> 85 source-speaker head."""

    head = torch.nn.Linear(
        SOURCE_SPEAKER_FEATURE_DIMENSION,
        SOURCE_SPEAKER_CLASS_COUNT,
        bias=True,
    )
    if device is not None:
        head = head.to(device=device)
    return head


def _optimizer_parameter_ids(optimizer: Any) -> set[int]:
    return {
        id(parameter)
        for group in optimizer.param_groups
        for parameter in group.get("params", ())
    }


def source_speaker_grl_adversarial_update(
    trained: Any,
    discriminator: Any,
    generator_optimizer: Any,
    discriminator_optimizer: Any,
    classifier: Any,
    classifier_optimizer: Any,
    trainable: Sequence[Any],
    batch: Mapping[str, Any],
    hook: Any,
    *,
    torch: Any,
) -> dict[str, float]:
    """Run one EXP-326 discriminator, classifier, and reversed-generator step."""

    labels = batch.get("source_speaker_label")
    if labels is None or labels.ndim != 1 or labels.dtype != torch.long:
        raise PostRehearsalError("source-speaker class labels are malformed")
    if labels.numel() != batch["source_wav"].shape[0]:
        raise PostRehearsalError("source-speaker class batch size drifted")
    if _optimizer_parameter_ids(generator_optimizer) & _optimizer_parameter_ids(
        classifier_optimizer
    ):
        raise PostRehearsalError("source-speaker classifier leaked into LoRA optimizer")
    base._set_adapter_training_only(trained)
    discriminator.train()
    hook.set_enabled(True)
    generator_optimizer.zero_grad(set_to_none=True)
    discriminator_optimizer.zero_grad(set_to_none=True)
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        hook.clear()
        outputs = trained(breadth._generator_model_inputs(batch))
        reconstruction = outputs.get("recons") if isinstance(outputs, dict) else None
        if reconstruction is None or not bool(torch.isfinite(reconstruction).all()):
            raise PostRehearsalError("source-speaker discriminator reconstruction malformed")
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
        raise PostRehearsalError("source-speaker discriminator norm is non-finite")
    discriminator_optimizer.step()

    # Classifier update receives no graph into the converter.  It is deliberately
    # a separate optimization step, so its parameters cannot enter the LoRA
    # update by accidental optimizer grouping.
    classifier.train(True)
    for parameter in classifier.parameters():
        parameter.requires_grad_(True)
    classifier_optimizer.zero_grad(set_to_none=True)
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        hook.clear()
        classifier_outputs = trained(breadth._generator_model_inputs(batch))
        del classifier_outputs
        classifier_features = hook.pooled().detach()
        classifier_logits = classifier(classifier_features)
        classifier_ce = torch.nn.functional.cross_entropy(classifier_logits, labels)
        classifier_loss = classifier_ce / math.log(float(SOURCE_SPEAKER_CLASS_COUNT))
    if not bool(torch.isfinite(classifier_loss)):
        raise PostRehearsalError("source-speaker classifier loss is non-finite")
    classifier_loss.backward()
    classifier_norm = torch.nn.utils.clip_grad_norm_(
        classifier.parameters(), base.GRADIENT_CLIP_NORM
    )
    if not math.isfinite(float(classifier_norm.detach().cpu())):
        raise PostRehearsalError("source-speaker classifier gradient is non-finite")
    classifier_nonzero = sum(
        int(torch.count_nonzero(parameter.grad).detach().cpu())
        for parameter in classifier.parameters()
        if parameter.grad is not None
    )
    if classifier_nonzero <= 0:
        raise PostRehearsalError("source-speaker classifier gradient is zero")
    classifier_optimizer.step()

    # Freeze the head for the generator step.  A fresh forward is intentional:
    # the classifier has just been updated, while the CE gradient still travels
    # through the frozen linear operation into the converter latent.
    for parameter in classifier.parameters():
        parameter.requires_grad_(False)
    classifier.zero_grad(set_to_none=True)
    try:
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            hook.clear()
            outputs = trained(breadth._generator_model_inputs(batch))
            reconstruction = outputs.get("recons")
            if reconstruction is None or not bool(torch.isfinite(reconstruction).all()):
                raise PostRehearsalError("source-speaker generator reconstruction malformed")
            outputs["audios"] = batch["target_wav"][..., : reconstruction.shape[-1]]
            generator_losses = trained.generative_loss(outputs)
            outputs["audios"] = discriminator_real
            adversarial_losses = discriminator.adversarial_loss(outputs)
            generator_loss = breadth._finite_loss(
                generator_losses.get("loss"),
                torch=torch,
                label="X-VC generative loss",
            )
            adversarial_loss = breadth._finite_loss(
                adversarial_losses.get("loss"),
                torch=torch,
                label="X-VC adversarial loss",
            )
            features = hook.pooled()
            logits = classifier(features)
            normalized_ce = torch.nn.functional.cross_entropy(logits, labels) / math.log(
                float(SOURCE_SPEAKER_CLASS_COUNT)
            )
            reversed_loss = -SOURCE_SPEAKER_GRL_WEIGHT * normalized_ce
            total_loss = generator_loss + adversarial_loss + reversed_loss
        if not bool(torch.isfinite(total_loss)):
            raise PostRehearsalError("source-speaker GRL total is non-finite")
        total_loss.backward()
        generator_norm = torch.nn.utils.clip_grad_norm_(
            trainable, base.GRADIENT_CLIP_NORM
        )
        if not math.isfinite(float(generator_norm.detach().cpu())):
            raise PostRehearsalError("source-speaker GRL-to-LoRA gradient is non-finite")
        generator_nonzero = sum(
            int(torch.count_nonzero(parameter.grad).detach().cpu())
            for parameter in trainable
            if parameter.grad is not None
        )
        if generator_nonzero <= 0:
            raise PostRehearsalError("source-speaker GRL-to-LoRA gradient is zero")
        generator_optimizer.step()
    finally:
        for parameter in classifier.parameters():
            parameter.requires_grad_(True)
        hook.clear()
    return {
        "total": float(total_loss.detach().cpu()),
        "generative": float(generator_loss.detach().cpu()),
        "discriminator": float(discriminator_loss.detach().cpu()),
        "adversarial_generator": float(adversarial_losses["adv_gen_loss"]),
        "adversarial_feature": float(adversarial_losses["adv_feat_loss"]),
        "source_speaker_classifier_loss": float(classifier_loss.detach().cpu()),
        "source_speaker_normalized_ce": float(normalized_ce.detach().cpu()),
        "source_speaker_reversed_loss": float(reversed_loss.detach().cpu()),
        "source_speaker_classifier_gradient_norm": float(
            classifier_norm.detach().cpu()
        ),
        "source_speaker_grl_to_lora_gradient_norm": float(
            generator_norm.detach().cpu()
        ),
        "source_speaker_classifier_gradient_nonzero": float(classifier_nonzero),
        "source_speaker_grl_to_lora_gradient_nonzero": float(generator_nonzero),
    }


def attach_acoustic_code_dropout(model: Any, *, torch: Any) -> Any:
    """Mask only the quantized source-acoustic tensor for selected forwards."""

    xvc = _base_xvc(model)
    quantizer = getattr(xvc, "acoustic_quantizer", None)
    if quantizer is None or hasattr(quantizer, "acoustic_code_dropout"):
        raise PostRehearsalError("acoustic quantizer topology drifted")

    class AcousticCodeDropout(torch.nn.Module):
        def __init__(self, base_quantizer: Any) -> None:
            super().__init__()
            self.base_quantizer = base_quantizer
            self.acoustic_code_dropout = ACOUSTIC_CODE_DROPOUT_IMPLEMENTATION
            self.enabled = False
            self.clean_calls = 0
            self.masked_calls = 0
            self.last_input_nonzero = 0
            self.last_output_nonzero = 0

        def set_enabled(self, enabled: bool) -> None:
            self.enabled = bool(enabled)

        def forward(self, *args: Any, **kwargs: Any) -> Any:
            output = self.base_quantizer(*args, **kwargs)
            if not isinstance(output, (tuple, list)) or not output:
                raise PostRehearsalError("acoustic quantizer output drifted")
            quantized = output[0]
            if not hasattr(quantized, "shape") or not bool(
                torch.isfinite(quantized).all()
            ):
                raise PostRehearsalError("quantized acoustic code is malformed")
            self.last_input_nonzero = int(torch.count_nonzero(quantized).detach().cpu())
            values = list(output)
            if self.enabled:
                values[0] = torch.zeros_like(quantized)
                self.masked_calls += 1
            else:
                self.clean_calls += 1
            self.last_output_nonzero = int(
                torch.count_nonzero(values[0]).detach().cpu()
            )
            return tuple(values) if isinstance(output, tuple) else values

    wrapped = AcousticCodeDropout(quantizer)
    xvc.acoustic_quantizer = wrapped
    return wrapped


def attach_acoustic_temporal_jitter(model: Any, *, torch: Any) -> Any:
    """Shift only ``zq_a`` on selected training forwards.

    The wrapped quantizer still computes its normal output and all bookkeeping.
    Only the first output tensor is replaced during explicitly enabled training
    rows.  The wrapper is disabled before candidate inference, which therefore
    uses normal quantized acoustics.
    """

    xvc = _base_xvc(model)
    quantizer = getattr(xvc, "acoustic_quantizer", None)
    if quantizer is None or hasattr(quantizer, "acoustic_temporal_jitter"):
        raise PostRehearsalError("acoustic quantizer topology drifted")

    class AcousticTemporalJitter(torch.nn.Module):
        def __init__(self, base_quantizer: Any) -> None:
            super().__init__()
            self.base_quantizer = base_quantizer
            self.acoustic_temporal_jitter = ACOUSTIC_TEMPORAL_JITTER_IMPLEMENTATION
            self.enabled = False
            self.training_active = False
            self.inference_started = False
            self.call_count = 0
            self.normal_calls = 0
            self.shifted_calls = 0
            self.setup_normal_calls = 0
            self.training_normal_calls = 0
            self.training_shifted_calls = 0
            self.inference_normal_calls = 0
            self.last_mode = "normal"
            self.last_input_nonzero = 0
            self.last_output_nonzero = 0
            self.last_input_rms = 0.0
            self.last_output_rms = 0.0
            self.last_input_abs_max = 0.0
            self.last_output_abs_max = 0.0

        def set_enabled(self, enabled: bool) -> None:
            self.enabled = bool(enabled)
            if self.enabled and not self.training_active and not self.inference_started:
                self.training_active = True

        def set_training_active(self, active: bool) -> None:
            if not active and self.enabled:
                raise PostRehearsalError(
                    "acoustic temporal jitter must be disabled before inference"
                )
            self.training_active = bool(active)
            if not active:
                self.inference_started = True

        def diagnostics(self) -> dict[str, float | int | str | bool]:
            return {
                "implementation": ACOUSTIC_TEMPORAL_JITTER_IMPLEMENTATION,
                "call_count": self.call_count,
                "normal_calls": self.normal_calls,
                "shifted_calls": self.shifted_calls,
                "setup_normal_calls": self.setup_normal_calls,
                "training_normal_calls": self.training_normal_calls,
                "training_shifted_calls": self.training_shifted_calls,
                "inference_normal_calls": self.inference_normal_calls,
                "enabled": self.enabled,
                "training_active": self.training_active,
                "last_mode": self.last_mode,
                "input_nonzero": self.last_input_nonzero,
                "output_nonzero": self.last_output_nonzero,
                "input_rms": self.last_input_rms,
                "output_rms": self.last_output_rms,
                "input_abs_max": self.last_input_abs_max,
                "output_abs_max": self.last_output_abs_max,
            }

        def forward(self, *args: Any, **kwargs: Any) -> Any:
            output = self.base_quantizer(*args, **kwargs)
            if not isinstance(output, (tuple, list)) or not output:
                raise PostRehearsalError("acoustic quantizer output drifted")
            quantized = output[0]
            if (
                not hasattr(quantized, "shape")
                or quantized.ndim < 1
                or quantized.shape[-1] < 1
                or not bool(torch.isfinite(quantized).all())
            ):
                raise PostRehearsalError("quantized acoustic code is malformed")
            input_nonzero = int(torch.count_nonzero(quantized).detach().cpu())
            input_rms = torch.sqrt(torch.mean(torch.square(quantized.float())))
            input_abs_max = torch.amax(torch.abs(quantized.float()))
            if (
                not bool(torch.isfinite(input_rms))
                or not bool(torch.isfinite(input_abs_max))
            ):
                raise PostRehearsalError("quantized acoustic amplitude is invalid")
            values = list(output)
            if self.enabled:
                shifted = torch.cat(
                    [quantized[..., :1], quantized[..., :-1]], dim=-1
                )
                if shifted.shape != quantized.shape:
                    raise PostRehearsalError(
                        "acoustic temporal jitter shape drifted"
                    )
                values[0] = shifted
                mode = "shifted"
                self.shifted_calls += 1
                if self.training_active:
                    self.training_shifted_calls += 1
                else:
                    raise PostRehearsalError(
                        "acoustic temporal jitter enabled outside training"
                    )
            else:
                mode = "normal"
                self.normal_calls += 1
                if self.training_active:
                    self.training_normal_calls += 1
                elif not self.inference_started:
                    self.setup_normal_calls += 1
                else:
                    self.inference_normal_calls += 1
            transformed = values[0]
            if not bool(torch.isfinite(transformed).all()):
                raise PostRehearsalError("acoustic temporal jitter is non-finite")
            output_nonzero = int(torch.count_nonzero(transformed).detach().cpu())
            if input_nonzero > 0 and output_nonzero <= 0:
                raise PostRehearsalError(
                    "acoustic temporal jitter removed all acoustic signal"
                )
            output_rms = torch.sqrt(torch.mean(torch.square(transformed.float())))
            output_abs_max = torch.amax(torch.abs(transformed.float()))
            if (
                not bool(torch.isfinite(output_rms))
                or not bool(torch.isfinite(output_abs_max))
                or (input_nonzero > 0 and not bool(output_rms > 0))
            ):
                raise PostRehearsalError(
                    "acoustic temporal jitter amplitude is invalid"
                )
            self.call_count += 1
            self.last_mode = mode
            self.last_input_nonzero = input_nonzero
            self.last_output_nonzero = output_nonzero
            self.last_input_rms = float(input_rms.detach().cpu())
            self.last_output_rms = float(output_rms.detach().cpu())
            self.last_input_abs_max = float(input_abs_max.detach().cpu())
            self.last_output_abs_max = float(output_abs_max.detach().cpu())
            return tuple(values) if isinstance(output, tuple) else values

    wrapped = AcousticTemporalJitter(quantizer)
    xvc.acoustic_quantizer = wrapped
    return wrapped


def attach_continuous_acoustic_latent(model: Any, *, torch: Any) -> Any:
    """Use the frozen quantizer's projected pre-VQ latent at every forward.

    The wrapped quantizer still runs normally, so indices, commitment/codebook
    losses, perplexity, and cluster bookkeeping remain the X-VC checkpoint's
    own values.  Only the first returned tensor (``zq_a``) is replaced by
    ``out_project(in_project(acoustic_encoder_out))``.  The wrapper is left
    installed after training so the candidate's evaluation inference uses the
    exact same source representation.
    """

    xvc = _base_xvc(model)
    quantizer = getattr(xvc, "acoustic_quantizer", None)
    if quantizer is None or hasattr(quantizer, "continuous_acoustic_latent"):
        raise PostRehearsalError("acoustic quantizer topology drifted")
    in_project = getattr(quantizer, "in_project", None)
    out_project = getattr(quantizer, "out_project", None)
    if not callable(in_project) or not callable(out_project):
        raise PostRehearsalError("continuous acoustic projections are unavailable")

    class ContinuousAcousticLatent(torch.nn.Module):
        def __init__(self, base_quantizer: Any) -> None:
            super().__init__()
            self.base_quantizer = base_quantizer
            self.continuous_acoustic_latent = CONTINUOUS_ACOUSTIC_IMPLEMENTATION
            self.call_count = 0
            self.last_quantized_nonzero = 0
            self.last_continuous_nonzero = 0
            self.last_quantized_rms = 0.0
            self.last_continuous_rms = 0.0
            self.last_rms_ratio = 0.0

        def diagnostics(self) -> dict[str, float | int | str]:
            return {
                "implementation": CONTINUOUS_ACOUSTIC_IMPLEMENTATION,
                "call_count": self.call_count,
                "quantized_nonzero": self.last_quantized_nonzero,
                "continuous_nonzero": self.last_continuous_nonzero,
                "quantized_rms": self.last_quantized_rms,
                "continuous_rms": self.last_continuous_rms,
                "rms_ratio": self.last_rms_ratio,
            }

        def forward(self, *args: Any, **kwargs: Any) -> Any:
            if args:
                acoustic_encoder_out = args[0]
            else:
                acoustic_encoder_out = kwargs.get("z")
            if acoustic_encoder_out is None or not hasattr(
                acoustic_encoder_out, "shape"
            ):
                raise PostRehearsalError("continuous acoustic input is malformed")
            output = self.base_quantizer(*args, **kwargs)
            if not isinstance(output, (tuple, list)) or not output:
                raise PostRehearsalError("acoustic quantizer output drifted")
            quantized = output[0]
            if not hasattr(quantized, "shape"):
                raise PostRehearsalError("quantized acoustic code is malformed")
            try:
                continuous = self.base_quantizer.out_project(
                    self.base_quantizer.in_project(acoustic_encoder_out)
                )
            except Exception as error:
                raise PostRehearsalError(
                    "continuous acoustic projection failed"
                ) from error
            if continuous.shape != quantized.shape:
                raise PostRehearsalError("continuous acoustic shape drifted")
            if (
                not bool(torch.isfinite(quantized).all())
                or not bool(torch.isfinite(continuous).all())
            ):
                raise PostRehearsalError(
                    "continuous acoustic representation is non-finite"
                )
            quantized_nonzero = int(torch.count_nonzero(quantized).detach().cpu())
            continuous_nonzero = int(torch.count_nonzero(continuous).detach().cpu())
            if quantized_nonzero <= 0:
                raise PostRehearsalError("quantized acoustic representation is zero")
            if continuous_nonzero <= 0:
                raise PostRehearsalError("continuous acoustic representation is zero")
            quantized_rms = torch.sqrt(torch.mean(torch.square(quantized)))
            continuous_rms = torch.sqrt(torch.mean(torch.square(continuous)))
            if (
                not bool(torch.isfinite(quantized_rms))
                or not bool(torch.isfinite(continuous_rms))
                or not bool(quantized_rms > 0)
                or not bool(continuous_rms > 0)
            ):
                raise PostRehearsalError("continuous acoustic RMS is invalid")
            rms_ratio = continuous_rms / quantized_rms
            if not bool(torch.isfinite(rms_ratio)) or not bool(rms_ratio > 0):
                raise PostRehearsalError("continuous acoustic RMS ratio is invalid")
            self.call_count += 1
            self.last_quantized_nonzero = quantized_nonzero
            self.last_continuous_nonzero = continuous_nonzero
            self.last_quantized_rms = float(quantized_rms.detach().cpu())
            self.last_continuous_rms = float(continuous_rms.detach().cpu())
            self.last_rms_ratio = float(rms_ratio.detach().cpu())
            values = list(output)
            values[0] = continuous
            return tuple(values) if isinstance(output, tuple) else values

    wrapped = ContinuousAcousticLatent(quantizer)
    xvc.acoustic_quantizer = wrapped
    return wrapped


def attach_speaker_condition_calibrator(model: Any, *, torch: Any) -> Any:
    """Insert one zero-delta speaker calibration before the frozen converter."""

    xvc = _base_xvc(model)
    converter = getattr(xvc, "acoustic_converter", None)
    if converter is None or getattr(converter, "condition_dim", None) != (
        SPEAKER_CONDITION_DIMENSION
    ):
        raise PostRehearsalError("speaker-condition converter topology drifted")

    class SpeakerConditionCalibratedConverter(torch.nn.Module):
        def __init__(self, base_converter: Any) -> None:
            super().__init__()
            self.base_converter = base_converter
            self.condition_dim = SPEAKER_CONDITION_DIMENSION
            self.speaker_condition_delta = torch.nn.Parameter(
                torch.zeros(SPEAKER_CONDITION_DIMENSION, dtype=torch.float32)
            )

        def forward(
            self,
            acoustic_latent: Any,
            frame_condition: Any = None,
            speaker_condition: Any = None,
            mask: Any = None,
        ) -> Any:
            if (
                speaker_condition is None
                or speaker_condition.ndim != 2
                or speaker_condition.shape[-1] != self.condition_dim
            ):
                raise PostRehearsalError(
                    "speaker-condition calibrator input drifted"
                )
            calibrated = speaker_condition + self.speaker_condition_delta.to(
                device=speaker_condition.device,
                dtype=speaker_condition.dtype,
            ).unsqueeze(0)
            return self.base_converter(
                acoustic_latent,
                frame_condition,
                calibrated,
                mask=mask,
            )

    wrapped = SpeakerConditionCalibratedConverter(converter)
    xvc.acoustic_converter = wrapped
    return wrapped


def _speaker_condition_calibrator(model: Any) -> Any:
    converter = getattr(_base_xvc(model), "acoustic_converter", None)
    delta = getattr(converter, "speaker_condition_delta", None)
    if (
        converter is None
        or delta is None
        or tuple(delta.shape) != (SPEAKER_CONDITION_DIMENSION,)
    ):
        raise PostRehearsalError("speaker-condition calibrator is unavailable")
    return converter


def _set_speaker_condition_calibrator_training_only(model: Any) -> list[Any]:
    model.eval()
    converter = _speaker_condition_calibrator(model)
    selected: list[Any] = []
    for parameter in model.parameters():
        trainable = parameter is converter.speaker_condition_delta
        parameter.requires_grad_(trainable)
        if trainable:
            selected.append(parameter)
    if (
        len(selected) != 1
        or sum(parameter.numel() for parameter in selected)
        != SPEAKER_CONDITION_DIMENSION
    ):
        raise PostRehearsalError("speaker-condition trainable topology drifted")
    return selected


def save_speaker_condition_calibrator(
    model: Any, directory: Path, *, torch: Any
) -> dict[str, Any]:
    from safetensors.torch import load_file, save_file

    directory.mkdir()
    converter = _speaker_condition_calibrator(model)
    delta = converter.speaker_condition_delta.detach().cpu().float().contiguous()
    if not bool(torch.isfinite(delta).all()):
        raise PostRehearsalError("speaker-condition delta is non-finite")
    weights = directory / "calibrator.safetensors"
    save_file(
        {"speaker_condition_delta": delta},
        str(weights),
        metadata={"format": "xvc_speaker_condition_calibrator_v1"},
    )
    reloaded = load_file(str(weights), device="cpu")
    if (
        set(reloaded) != {"speaker_condition_delta"}
        or not torch.equal(reloaded["speaker_condition_delta"], delta)
    ):
        raise PostRehearsalError(
            "speaker-condition calibrator serialization drifted"
        )
    metadata = {
        "schema_version": 1,
        "kind": SPEAKER_CONDITION_CALIBRATOR_KIND,
        "initialization": "zero-delta-over-frozen-exp238-ema",
        "parameter_count": SPEAKER_CONDITION_DIMENSION,
        "weights_sha256": sha256_file(weights),
        "delta_l2_norm": float(torch.linalg.vector_norm(delta)),
    }
    method._write_json(directory / "calibrator.json", metadata)
    return metadata


def load_speaker_condition_calibrator(
    model: Any, directory: Path, *, torch: Any, device: Any
) -> dict[str, Any]:
    from safetensors.torch import load_file

    metadata_path = directory / "calibrator.json"
    weights = directory / "calibrator.safetensors"
    if (
        directory.is_symlink()
        or metadata_path.is_symlink()
        or weights.is_symlink()
        or not metadata_path.is_file()
        or not weights.is_file()
    ):
        raise PostRehearsalError("speaker-condition calibrator is unavailable")
    metadata = load_json(metadata_path)
    if (
        metadata.get("kind") != SPEAKER_CONDITION_CALIBRATOR_KIND
        or metadata.get("parameter_count") != SPEAKER_CONDITION_DIMENSION
        or metadata.get("weights_sha256") != sha256_file(weights)
    ):
        raise PostRehearsalError("speaker-condition calibrator identity drifted")
    stored = load_file(str(weights), device="cpu")
    value = stored.get("speaker_condition_delta")
    if value is None or tuple(value.shape) != (SPEAKER_CONDITION_DIMENSION,):
        raise PostRehearsalError("speaker-condition calibrator tensor drifted")
    converter = attach_speaker_condition_calibrator(model, torch=torch)
    with torch.no_grad():
        converter.speaker_condition_delta.copy_(
            value.to(device=device, dtype=torch.float32)
        )
    return metadata


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
    if manifest.get("kind") in CV26_KINDS:
        return items[:1]
    if manifest.get("kind") in SRC4VC_TWO_UTTERANCE_KINDS:
        selected: list[Mapping[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            speaker = item.get("source_speaker_id")
            if speaker in seen:
                continue
            selected.append(item)
            seen.add(str(speaker))
            if len(selected) == 2:
                break
        if len(selected) != 2:
            raise PostRehearsalError("EXP-326 smoke requires two speakers")
        return selected
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


def latent_source_speaker_margin_generator_loss(
    model: Any,
    outputs: Mapping[str, Any],
    batch: Mapping[str, Any],
    *,
    torch: Any,
    margin: float = LATENT_SOURCE_SPEAKER_MARGIN,
    weight: float = LATENT_SOURCE_SPEAKER_MARGIN_WEIGHT,
) -> dict[str, Any]:
    """Keep the converter latent closer to the target than the source speaker."""
    if (
        not math.isfinite(margin)
        or margin <= 0.0
        or not math.isfinite(weight)
        or weight <= 0.0
    ):
        raise PostRehearsalError("latent source-speaker margin is invalid")
    predicted = outputs.get("pred_sim_feat")
    target = outputs.get("sim_feat")
    source_waveform = batch.get("source_wav")
    speaker_encoder = getattr(model, "speaker_encoder", None)
    if (
        predicted is None
        or target is None
        or source_waveform is None
        or speaker_encoder is None
    ):
        raise PostRehearsalError("latent source-speaker margin input is unavailable")
    predicted = torch.nn.functional.normalize(predicted.float(), dim=-1)
    target = torch.nn.functional.normalize(target.detach().float(), dim=-1)
    with torch.no_grad():
        source = differentiable_xvc_speaker_embedding(
            speaker_encoder,
            source_waveform,
            torch=torch,
        )
    if predicted.shape != target.shape or predicted.shape != source.shape:
        raise PostRehearsalError("latent source-speaker margin shape drifted")
    target_similarity = torch.nn.functional.cosine_similarity(
        predicted, target, dim=-1
    )
    source_similarity = torch.nn.functional.cosine_similarity(
        predicted, source, dim=-1
    )
    advantage = target_similarity - source_similarity
    deficit = torch.nn.functional.relu(margin - advantage)
    margin_loss = weight * deficit.mean()
    if not bool(torch.isfinite(margin_loss)):
        raise PostRehearsalError("latent source-speaker margin loss is non-finite")
    losses = dict(model.generative_loss(outputs))
    base_loss = losses.get("loss")
    if base_loss is None or not bool(torch.isfinite(base_loss)):
        raise PostRehearsalError("base X-VC generative loss is non-finite")
    losses["loss"] = base_loss + margin_loss
    losses["latent_source_speaker_margin_loss"] = margin_loss
    losses["latent_source_speaker_target_similarity"] = target_similarity.mean()
    losses["latent_source_speaker_source_similarity"] = source_similarity.mean()
    losses["latent_source_speaker_advantage"] = advantage.mean()
    losses["latent_source_speaker_active_fraction"] = (
        deficit.gt(0.0).float().mean()
    )
    return losses


def robust_semantic_generator_loss(
    model: Any,
    outputs: Mapping[str, Any],
    _batch: Mapping[str, Any] | None = None,
    *,
    torch: Any,
    beta: float = ROBUST_SEMANTIC_BETA,
    scale_factor: float = ROBUST_SEMANTIC_SCALE,
    weight: float = ROBUST_SEMANTIC_WEIGHT,
) -> dict[str, Any]:
    """Substitute only the standard semantic-decoder term.

    model.generative_loss remains the source of every standard component and
    diagnostic. The returned total differentiably removes its standard
    weight-1000 MSE contribution and inserts the scale-matched SmoothL1 term.
    """

    del _batch
    if (
        not math.isfinite(beta)
        or beta <= 0.0
        or not math.isfinite(scale_factor)
        or scale_factor <= 0.0
        or not math.isfinite(weight)
        or weight <= 0.0
    ):
        raise PostRehearsalError("robust semantic loss parameters are invalid")
    if weight != role_mix.STANDARD_LOSS_WEIGHTS["mse_loss"]:
        raise PostRehearsalError("robust semantic weight is not standard MSE weight")
    standard = dict(model.generative_loss(outputs))
    base_loss = standard.get("loss")
    prediction = outputs.get("pred")
    target = outputs.get("ssl_feat")
    if (
        base_loss is None
        or prediction is None
        or target is None
        or prediction.shape != target.shape
    ):
        raise PostRehearsalError("robust semantic decoder output shape drifted")
    semantic_mse = torch.nn.functional.mse_loss(prediction, target)
    semantic_smooth_l1 = torch.nn.functional.smooth_l1_loss(
        prediction, target, beta=beta
    )
    replacement = scale_factor * semantic_smooth_l1
    total = base_loss + weight * (replacement - semantic_mse)
    if not all(
        bool(torch.isfinite(value))
        for value in (base_loss, semantic_mse, semantic_smooth_l1, total)
    ):
        raise PostRehearsalError("robust semantic loss is non-finite")
    standard["loss"] = total
    standard["semantic_mse"] = semantic_mse
    standard["semantic_smooth_l1"] = semantic_smooth_l1
    standard["semantic_smooth_l1_scaled"] = replacement
    return standard


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
    expected_rows = expected_training_rows(str(manifest["kind"]))

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
    calibrator = None
    if arguments.trainable_target == SPEAKER_CONDITION_CALIBRATOR_TARGET:
        trained = PeftModel.from_pretrained(
            model, str(arguments.initial_adapter), is_trainable=False
        )
        calibrator = attach_speaker_condition_calibrator(trained, torch=torch)
        trainable = _set_speaker_condition_calibrator_training_only(trained)
        expected_trainable = SPEAKER_CONDITION_DIMENSION
    elif arguments.trainable_target in {
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
    elif arguments.training_objective == PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE:
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
    source_speaker_receipt = validate_source_speaker_manifest(manifest)
    source_speaker_labels = (
        source_speaker_label_map(manifest)
        if arguments.training_objective == PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE
        else {}
    )
    source_speaker_classifier_head = None
    source_speaker_classifier_optimizer = None
    source_speaker_hook = None
    source_speaker_probe: dict[str, Any] | None = None
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
    if (
        arguments.smoke
        and arguments.training_objective
        == PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE
    ):
        # The smoke contract is exactly one train forward plus one inference
        # forward, making wrapper coverage auditable without changing the 170-row
        # admitted run.
        rows = list(manifest["items"][:1])
    acoustic_code_dropout = (
        attach_acoustic_code_dropout(trained, torch=torch)
        if arguments.training_objective
        == PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE
        else None
    )
    continuous_acoustic = (
        attach_continuous_acoustic_latent(trained, torch=torch)
        if arguments.training_objective
        == PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE
        else None
    )
    acoustic_temporal_jitter = (
        attach_acoustic_temporal_jitter(trained, torch=torch)
        if arguments.training_objective
        == PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE
        else None
    )
    acoustic_code_dropout_modes = (
        acoustic_code_dropout_schedule(len(rows))
        if acoustic_code_dropout is not None
        else [False] * len(rows)
    )
    acoustic_temporal_jitter_modes = (
        acoustic_temporal_jitter_schedule(len(rows))
        if acoustic_temporal_jitter is not None
        else [False] * len(rows)
    )
    jitter_gradient_diagnostics: dict[str, float | int | bool] | None = None
    robust_semantic_gradient_diagnostics: (
        dict[str, float | int | bool] | None
    ) = None
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
        PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE,
        PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE,
        PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE,
        PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE,
        PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE,
        PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
        PSEUDOPARALLEL_CONDITION_CALIBRATOR_OBJECTIVE,
        PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE,
        PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE,
        PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE,
    }:
        discriminator, discriminator_optimizer = breadth._load_pretrained_discriminator(
            arguments, config, torch=torch, device=device
        )
        if arguments.training_objective in {
            REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
            PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
            PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE,
            PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE,
            PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE,
            PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE,
            PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE,
            PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
            PSEUDOPARALLEL_CONDITION_CALIBRATOR_OBJECTIVE,
            PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE,
            PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE,
            PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE,
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
                        PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE,
                        PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE,
                        PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE,
                        PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE,
                        PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE,
                        PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
                        PSEUDOPARALLEL_CONDITION_CALIBRATOR_OBJECTIVE,
                        PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE,
                        PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE,
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

    if acoustic_temporal_jitter is not None:
        acoustic_temporal_jitter.set_training_active(True)

    def batch_for(
        item: Mapping[str, Any], negative_item: Mapping[str, Any] | None = None
    ) -> Any:
        if arguments.trainable_target == SPEAKER_CONDITION_CALIBRATOR_TARGET:
            _set_speaker_condition_calibrator_training_only(trained)
        elif arguments.trainable_target == FULL_CONVERTER_TARGET:
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
        if arguments.training_objective == PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE:
            speaker_id = item.get("source_speaker_id")
            if speaker_id not in source_speaker_labels:
                raise PostRehearsalError("source-speaker label map drifted")
            gpu_batch["source_speaker_label"] = torch.tensor(
                [source_speaker_labels[str(speaker_id)]],
                device=device,
                dtype=torch.long,
            )
        return gpu_batch

    if arguments.training_objective == PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE:
        source_speaker_classifier_head = source_speaker_classifier(
            torch=torch, device=device
        )
        source_speaker_classifier_optimizer = torch.optim.AdamW(
            source_speaker_classifier_head.parameters(), lr=LEARNING_RATE
        )
        source_speaker_hook = attach_source_speaker_adversary(trained, torch=torch)
        source_speaker_hook.set_enabled(True)
        if arguments.smoke:
            source_speaker_probe = {
                "implementation": SOURCE_SPEAKER_PROBE_IMPLEMENTATION,
                "status": "skipped-in-two-speaker-cuda-smoke",
                "class_count": SOURCE_SPEAKER_CLASS_COUNT,
                "reference_utterance": 0,
                "query_utterance": 1,
            }
        else:
            probe_features: list[Any] = []
            probe_labels: list[str] = []
            trained.eval()
            with torch.no_grad():
                for item in manifest["items"]:
                    probe_batch = batch_for(item)
                    source_speaker_hook.clear()
                    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                        trained(breadth._generator_model_inputs(probe_batch))
                    probe_features.append(source_speaker_hook.pooled().detach())
                    probe_labels.append(str(item["source_speaker_id"]))
            source_speaker_hook.clear()
            source_speaker_probe = source_speaker_signal_probe(
                torch.cat(probe_features, dim=0), probe_labels, torch=torch
            )
            if not source_speaker_probe["materially_above_chance"]:
                raise PostRehearsalError(
                    "frozen control69 source-speaker signal is not materially above chance"
                )

    if arguments.training_objective == PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE:
        if (
            source_speaker_classifier_head is None
            or source_speaker_classifier_optimizer is None
            or source_speaker_hook is None
        ):
            raise PostRehearsalError("source-speaker GRL components are unavailable")
        for row_index, item in enumerate(rows):
            batch = batch_for(item)
            metrics = source_speaker_grl_adversarial_update(
                trained,
                discriminator,
                optimizer,
                discriminator_optimizer,
                source_speaker_classifier_head,
                source_speaker_classifier_optimizer,
                trainable,
                batch,
                source_speaker_hook,
                torch=torch,
            )
            losses.append(metrics["total"])
            adversarial_metrics.append(metrics)
            if not arguments.smoke:
                optimizer_steps += 1
            if adapter_ema is not None:
                adapter_ema.update()
    elif arguments.optimizer_mode == PCGRAD_PAIRED_OPTIMIZER:
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
            acoustic_code_dropout_mode = acoustic_code_dropout_modes[row_index]
            if acoustic_code_dropout is not None:
                acoustic_code_dropout.set_enabled(acoustic_code_dropout_mode)
            acoustic_temporal_jitter_mode = acoustic_temporal_jitter_modes[row_index]
            if acoustic_temporal_jitter is not None:
                acoustic_temporal_jitter.set_enabled(acoustic_temporal_jitter_mode)
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
                            PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE,
                            PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE,
                            PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
                            PSEUDOPARALLEL_CONDITION_CALIBRATOR_OBJECTIVE,
                            PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE,
                            PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE,
                        }
                        else None
                    ),
                    speaker_target_wav=(
                        realism_targets[str(item["target_id"])].to(
                            device=device, dtype=torch.float32
                        )
                        if arguments.training_objective
                        == PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE
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
                                _set_speaker_condition_calibrator_training_only(
                                    current
                                )
                            )
                        )
                        if arguments.trainable_target
                        == SPEAKER_CONDITION_CALIBRATOR_TARGET
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
                        in {
                            PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
                            PSEUDOPARALLEL_CONDITION_CALIBRATOR_OBJECTIVE,
                        }
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
                        else (
                            lambda outputs, current_batch: (
                                robust_semantic_generator_loss(
                                    trained,
                                    outputs,
                                    current_batch,
                                    torch=torch,
                                )
                            )
                        )
                        if arguments.training_objective
                        == PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE
                        else (
                            lambda outputs, current_batch: (
                                latent_source_speaker_margin_generator_loss(
                                    trained,
                                    outputs,
                                    current_batch,
                                    torch=torch,
                                )
                            )
                        )
                        if arguments.training_objective
                        == PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE
                        else None
                    ),
                )
                if acoustic_code_dropout is not None:
                    if acoustic_code_dropout.last_input_nonzero <= 0:
                        raise PostRehearsalError(
                            "quantized acoustic code unexpectedly contains no signal"
                        )
                    expected_nonzero = (
                        0
                        if acoustic_code_dropout_mode
                        else acoustic_code_dropout.last_input_nonzero
                    )
                    if acoustic_code_dropout.last_output_nonzero != expected_nonzero:
                        raise PostRehearsalError(
                            "acoustic-code dropout did not match its schedule"
                        )
                    metrics["acoustic_code_dropout_masked"] = float(
                        acoustic_code_dropout_mode
                    )
                    metrics["acoustic_code_input_nonzero"] = float(
                        acoustic_code_dropout.last_input_nonzero
                    )
                    metrics["acoustic_code_output_nonzero"] = float(
                        acoustic_code_dropout.last_output_nonzero
                    )
                if continuous_acoustic is not None:
                    continuous_metrics = continuous_acoustic.diagnostics()
                    metrics["continuous_acoustic_call_count"] = float(
                        continuous_metrics["call_count"]
                    )
                    metrics["continuous_acoustic_quantized_nonzero"] = float(
                        continuous_metrics["quantized_nonzero"]
                    )
                    metrics["continuous_acoustic_nonzero"] = float(
                        continuous_metrics["continuous_nonzero"]
                    )
                    metrics["continuous_acoustic_quantized_rms"] = float(
                        continuous_metrics["quantized_rms"]
                    )
                    metrics["continuous_acoustic_rms"] = float(
                        continuous_metrics["continuous_rms"]
                    )
                    metrics["continuous_acoustic_rms_ratio"] = float(
                        continuous_metrics["rms_ratio"]
                    )
                if acoustic_temporal_jitter is not None:
                    jitter_metrics = acoustic_temporal_jitter.diagnostics()
                    expected_nonzero = jitter_metrics["input_nonzero"]
                    if (
                        int(expected_nonzero) <= 0
                        or int(jitter_metrics["output_nonzero"]) <= 0
                    ):
                        raise PostRehearsalError(
                            "acoustic temporal jitter representation is zero"
                        )
                    metrics["acoustic_temporal_jitter_shifted"] = float(
                        acoustic_temporal_jitter_mode
                    )
                    metrics["acoustic_temporal_jitter_input_nonzero"] = float(
                        jitter_metrics["input_nonzero"]
                    )
                    metrics["acoustic_temporal_jitter_output_nonzero"] = float(
                        jitter_metrics["output_nonzero"]
                    )
                    metrics["acoustic_temporal_jitter_input_rms"] = float(
                        jitter_metrics["input_rms"]
                    )
                    metrics["acoustic_temporal_jitter_output_rms"] = float(
                        jitter_metrics["output_rms"]
                    )
                    jitter_gradient_diagnostics = (
                        finite_nonzero_gradient_diagnostics(trainable, torch=torch)
                    )
                if (
                    arguments.training_objective
                    == PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE
                ):
                    for metric_name in (
                        "generator_semantic_mse",
                        "generator_semantic_smooth_l1",
                        "total",
                    ):
                        metric_value = metrics.get(metric_name)
                        if metric_value is None or not math.isfinite(metric_value):
                            raise PostRehearsalError(
                                f"robust semantic {metric_name} is non-finite"
                            )
                    robust_semantic_gradient_diagnostics = (
                        finite_nonzero_gradient_diagnostics(trainable, torch=torch)
                    )
                if calibrator is not None:
                    delta_norm = float(
                        torch.linalg.vector_norm(
                            calibrator.speaker_condition_delta.detach().float()
                        ).cpu()
                    )
                    if not math.isfinite(delta_norm) or delta_norm <= 0.0:
                        raise PostRehearsalError(
                            "speaker-condition delta did not receive a finite update"
                        )
                    metrics["speaker_condition_delta_l2_norm"] = delta_norm
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
    if source_speaker_hook is not None:
        source_speaker_hook.close()
        if source_speaker_hook.inference_calls != 0:
            raise PostRehearsalError(
                "source-speaker inference hook captured an unexpected call"
            )
    if acoustic_temporal_jitter is not None:
        expected_each = len(rows) // 2
        if (
            acoustic_temporal_jitter.training_normal_calls != expected_each
            or acoustic_temporal_jitter.training_shifted_calls != expected_each
        ):
            raise PostRehearsalError(
                "acoustic temporal jitter training call count drifted"
            )
        acoustic_temporal_jitter.set_enabled(False)
        acoustic_temporal_jitter.set_training_active(False)
    if acoustic_code_dropout is not None:
        expected_each = len(rows) // 2
        if (
            acoustic_code_dropout.clean_calls != expected_each
            or acoustic_code_dropout.masked_calls != expected_each
        ):
            raise PostRehearsalError("acoustic-code dropout call count drifted")
        acoustic_code_dropout.set_enabled(False)
    if acoustic_temporal_jitter is not None and arguments.smoke:
        # The final smoke call must use ordinary quantized zq_a while the
        # training-only wrapper remains installed for call-count evidence.
        base._inference(
            trained,
            {
                "source_wav": batch["source_wav"],
                "semantic_tokens": batch["semantic_tokens"],
            },
            {
                "target_wav": batch["target_wav"],
                "ssl_feat": batch["ssl_feat"],
            },
            seed=base.SEED,
            torch=torch,
            device=device,
        )
        if acoustic_temporal_jitter.inference_normal_calls != 1:
            raise PostRehearsalError(
                "acoustic temporal jitter smoke requires normal inference"
            )
    if continuous_acoustic is not None and arguments.smoke:
        # The second and final smoke call must enter XVC.inference while the
        # wrapper remains installed, matching the external7 candidate path.
        base._inference(
            trained,
            {
                "source_wav": batch["source_wav"],
                "semantic_tokens": batch["semantic_tokens"],
            },
            {
                "target_wav": batch["target_wav"],
                "ssl_feat": batch["ssl_feat"],
            },
            seed=base.SEED,
            torch=torch,
            device=device,
        )
        if continuous_acoustic.call_count != 2:
            raise PostRehearsalError(
                "continuous acoustic smoke requires one train and one inference call"
            )
    source_speaker_inference_shape: list[int] | None = None
    if (
        arguments.training_objective == PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE
        and arguments.smoke
    ):
        rendered = base._inference(
            trained,
            {
                "source_wav": batch["source_wav"],
                "semantic_tokens": batch["semantic_tokens"],
            },
            {
                "target_wav": batch["target_wav"],
                "ssl_feat": batch["ssl_feat"],
            },
            seed=base.SEED,
            torch=torch,
            device=device,
        )
        if rendered.ndim != 3 or tuple(rendered.shape[:2]) != (1, 1):
            raise PostRehearsalError(
                "source-speaker GRL inference output shape changed"
            )
        source_speaker_inference_shape = list(rendered.shape)
    if arguments.smoke:
        smoke = {
            "status": (
                "smoked-fresh-lora-pseudoparallel"
                if arguments.training_objective
                == PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE
                else "smoked-robust-semantic-pseudoparallel"
                if arguments.training_objective
                == PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE
                else "smoked-acoustic-code-dropout-pseudoparallel"
                if arguments.training_objective
                == PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE
                else "smoked-continuous-acoustic-pseudoparallel"
                if arguments.training_objective
                == PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE
                else "smoked-acoustic-temporal-jitter-pseudoparallel"
                if arguments.training_objective
                == PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE
                else "smoked-source-speaker-grl-pseudoparallel"
                if arguments.training_objective
                == PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE
                else "smoked-control69-clean-post-rehearsal"
            ),
            "loss": losses[0],
            "trainable_parameters": expected_trainable,
            "training_initialization": (
                "fresh-zero-initialized-rank8-lora69-on-base-xvc"
                if arguments.training_objective
                == PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE
                else "exp035-control69-adapter"
            ),
            "training_objective": arguments.training_objective,
            "optimizer_mode": arguments.optimizer_mode,
            "parameter_anchor": arguments.parameter_anchor,
            "source_speaker": (
                {
                    **(source_speaker_receipt or {}),
                    "objective": (
                        PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE
                        if arguments.training_objective
                        == PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE
                        else "ordinary-matched-control"
                    ),
                    "pool_implementation": SOURCE_SPEAKER_POOL_IMPLEMENTATION,
                    "grl_implementation": SOURCE_SPEAKER_GRL_IMPLEMENTATION,
                    "grl_weight": SOURCE_SPEAKER_GRL_WEIGHT,
                    "classifier_feature_dimension": SOURCE_SPEAKER_FEATURE_DIMENSION,
                    "classifier_class_count": SOURCE_SPEAKER_CLASS_COUNT,
                    "probe": source_speaker_probe,
                    "head_exported": False,
                    "head_inference_attachment": None,
                    "inference_output_shape": source_speaker_inference_shape,
                    "hook": (
                        source_speaker_hook.diagnostics()
                        if source_speaker_hook is not None
                        else None
                    ),
                }
                if source_speaker_receipt is not None
                else None
            ),
            "output_cycle_frontend": output_cycle_frontend_metrics,
            "acoustic_code_dropout": (
                {
                    "implementation": ACOUSTIC_CODE_DROPOUT_IMPLEMENTATION,
                    "clean_rows": acoustic_code_dropout_modes.count(False),
                    "masked_rows": acoustic_code_dropout_modes.count(True),
                    "inference": "unmasked",
                }
                if acoustic_code_dropout is not None
                else None
            ),
            "continuous_acoustic": (
                continuous_acoustic.diagnostics()
                if continuous_acoustic is not None
                else None
            ),
            "acoustic_temporal_jitter": (
                {
                    **acoustic_temporal_jitter.diagnostics(),
                    "normal_rows": acoustic_temporal_jitter_modes.count(False),
                    "shifted_rows": acoustic_temporal_jitter_modes.count(True),
                    "inference": "normal-quantized-zq_a",
                    "training_row_identity": training_row_identity_receipt(
                        manifest, rows
                    ),
                }
                if acoustic_temporal_jitter is not None
                else None
            ),
            "robust_semantic": (
                {
                    **robust_semantic_receipt(str(manifest["kind"])),
                    "semantic_mse": adversarial_metrics[0][
                        "generator_semantic_mse"
                    ],
                    "semantic_smooth_l1": adversarial_metrics[0][
                        "generator_semantic_smooth_l1"
                    ],
                    "total": adversarial_metrics[0]["total"],
                    "gradient_diagnostics": robust_semantic_gradient_diagnostics,
                }
                if arguments.training_objective
                == PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE
                else None
            ),
            "gradient_diagnostics": jitter_gradient_diagnostics,
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
    if len(losses) != expected_rows:
        raise PostRehearsalError("post-rehearsal update count drifted")
    if arguments.trainable_target == FULL_CONVERTER_TARGET:
        checkpoint_metadata = save_converter_checkpoint(
            trained, arguments.work_dir / f"converter-{expected_rows}", torch
        )
    elif arguments.trainable_target == ACOUSTIC_ENCODER_TARGET:
        checkpoint_metadata = save_acoustic_encoder_checkpoint(
            trained,
            arguments.work_dir / f"acoustic-encoder-{expected_rows}",
            torch,
        )
    elif arguments.trainable_target == SPEAKER_CONDITION_CALIBRATOR_TARGET:
        online_dir = arguments.work_dir / f"online-calibrator-{expected_rows}"
        online_metadata = save_speaker_condition_calibrator(
            trained, online_dir, torch=torch
        )
        if adapter_ema is None:
            raise PostRehearsalError("speaker-condition calibrator requires EMA")
        adapter_ema.copy_to()
        calibrator_dir = arguments.work_dir / f"calibrator-{expected_rows}"
        checkpoint_metadata = save_speaker_condition_calibrator(
            trained, calibrator_dir, torch=torch
        )
        checkpoint_metadata.update(
            {
                "directory": calibrator_dir.name,
                "online_directory": online_dir.name,
                "online_weights_sha256": online_metadata["weights_sha256"],
            }
        )
    else:
        checkpoint_steps = (
            optimizer_steps
            if arguments.optimizer_mode == PCGRAD_PAIRED_OPTIMIZER
            else expected_rows
        )
        adapter_dir = arguments.work_dir / f"adapter-{checkpoint_steps}"
        if adapter_ema is not None:
            online_dir = arguments.work_dir / f"online-adapter-{expected_rows}"
            trained.save_pretrained(online_dir, safe_serialization=True)
            adapter_ema.copy_to()
        trained.save_pretrained(adapter_dir, safe_serialization=True)
        checkpoint_metadata = {
            "kind": "peft-adapter-ema" if adapter_ema is not None else "peft-adapter",
            "directory": adapter_dir.name,
            "online_directory": (
                f"online-adapter-{expected_rows}" if adapter_ema is not None else None
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
        "cv32": validate_cv32_manifest(manifest),
        "cv32_replacement": validate_cv32_replacement_manifest(manifest),
        "cv26": validate_cv26_manifest(manifest),
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
        "training_initialization": (
            "fresh-zero-initialized-rank8-lora69-on-base-xvc"
            if arguments.training_objective
            == PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE
            else "exp035-control69-adapter"
        ),
        "initial_adapter": (
            str(arguments.initial_adapter)
            if arguments.initial_adapter is not None
            else None
        ),
        "trainable_target": arguments.trainable_target,
        "training_objective": arguments.training_objective,
        "source_speaker": (
            {
                **(source_speaker_receipt or {}),
                "objective": (
                    PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE
                    if arguments.training_objective
                    == PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE
                    else "ordinary-matched-control"
                ),
                "pool_implementation": SOURCE_SPEAKER_POOL_IMPLEMENTATION,
                "grl_implementation": SOURCE_SPEAKER_GRL_IMPLEMENTATION,
                "grl_weight": SOURCE_SPEAKER_GRL_WEIGHT,
                "classifier_feature_dimension": SOURCE_SPEAKER_FEATURE_DIMENSION,
                "classifier_class_count": SOURCE_SPEAKER_CLASS_COUNT,
                "probe": source_speaker_probe,
                "head_exported": False,
                "head_inference_attachment": None,
                "inference_output_shape": None,
                "hook": (
                    source_speaker_hook.diagnostics()
                    if source_speaker_hook is not None
                    else None
                ),
            }
            if source_speaker_receipt is not None
            else None
        ),
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
        "acoustic_code_dropout": (
            {
                "implementation": ACOUSTIC_CODE_DROPOUT_IMPLEMENTATION,
                "clean_rows": acoustic_code_dropout_modes.count(False),
                "masked_rows": acoustic_code_dropout_modes.count(True),
                "training_only": True,
                "inference": "unmasked",
                "first_row_masked": bool(
                    adversarial_metrics[0]["acoustic_code_dropout_masked"]
                ),
                "last_row_masked": bool(
                    adversarial_metrics[-1]["acoustic_code_dropout_masked"]
                ),
            }
            if acoustic_code_dropout is not None
            else None
        ),
        "continuous_acoustic": (
            continuous_acoustic.diagnostics()
            if continuous_acoustic is not None
            else None
        ),
        "acoustic_temporal_jitter": (
            {
                **acoustic_temporal_jitter.diagnostics(),
                "normal_rows": acoustic_temporal_jitter_modes.count(False),
                "shifted_rows": acoustic_temporal_jitter_modes.count(True),
                "training_only": True,
                "inference": "normal-quantized-zq_a",
                "training_row_identity": training_row_identity_receipt(manifest),
            }
            if acoustic_temporal_jitter is not None
            else None
        ),
        "robust_semantic": (
            {
                **robust_semantic_receipt(str(manifest["kind"])),
                "first_semantic_mse": adversarial_metrics[0][
                    "generator_semantic_mse"
                ],
                "last_semantic_mse": adversarial_metrics[-1][
                    "generator_semantic_mse"
                ],
                "first_semantic_smooth_l1": adversarial_metrics[0][
                    "generator_semantic_smooth_l1"
                ],
                "last_semantic_smooth_l1": adversarial_metrics[-1][
                    "generator_semantic_smooth_l1"
                ],
                "first_total": adversarial_metrics[0]["total"],
                "last_total": adversarial_metrics[-1]["total"],
                "gradient_diagnostics": robust_semantic_gradient_diagnostics,
            }
            if arguments.training_objective
            == PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE
            else None
        ),
        "gradient_diagnostics": jitter_gradient_diagnostics,
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
            in {
                PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
                PSEUDOPARALLEL_CONDITION_CALIBRATOR_OBJECTIVE,
            }
            else None
        ),
        "latent_source_speaker_margin": (
            {
                "implementation": LATENT_SOURCE_SPEAKER_MARGIN_IMPLEMENTATION,
                "margin": LATENT_SOURCE_SPEAKER_MARGIN,
                "weight": LATENT_SOURCE_SPEAKER_MARGIN_WEIGHT,
                "source": "current-source-window-frozen-XVC-ERes2Net",
                "target": "assigned-pseudoparallel-target-XVC-ERes2Net",
                "first_advantage": adversarial_metrics[0][
                    "generator_latent_source_speaker_advantage"
                ],
                "last_advantage": adversarial_metrics[-1][
                    "generator_latent_source_speaker_advantage"
                ],
                "first_active_fraction": adversarial_metrics[0][
                    "generator_latent_source_speaker_active_fraction"
                ],
                "last_active_fraction": adversarial_metrics[-1][
                    "generator_latent_source_speaker_active_fraction"
                ],
            }
            if arguments.training_objective
            == PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE
            else None
        ),
        "speaker_condition_target": (
            "assigned-authorized-real-Amitaro-window"
            if arguments.training_objective
            == PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE
            else "generator-reconstruction-target"
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
                    == PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE
                    or arguments.training_objective
                    == PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE
                    or arguments.training_objective
                    == PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE
                    or arguments.training_objective
                    == PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE
                    or arguments.training_objective
                    == PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE
                    or arguments.training_objective
                    == PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE
                    or arguments.training_objective
                    == PSEUDOPARALLEL_CONDITION_CALIBRATOR_OBJECTIVE
                    or arguments.training_objective
                    == PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE
                    or arguments.training_objective
                    == PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE
                    or arguments.training_objective
                    == PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE
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
            SPEAKER_CONDITION_CALIBRATOR_TARGET,
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
            PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE,
            PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE,
            PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE,
            PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE,
            PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE,
            PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
            PSEUDOPARALLEL_CONDITION_CALIBRATOR_OBJECTIVE,
            PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE,
            PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE,
            PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE,
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
    value.add_argument("--initial-adapter", type=Path)
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
                        "initialization": (
                            "EXP-238-EMA-plus-zero-speaker-condition-delta"
                            if arguments.trainable_target
                            == SPEAKER_CONDITION_CALIBRATOR_TARGET
                            else "fresh-zero-initialized-rank8-LoRA69-on-base-XVC"
                            if arguments.training_objective
                            == PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE
                            else "EXP-035-control69"
                        ),
                        "acoustic_code_dropout": (
                            {
                                "implementation": ACOUSTIC_CODE_DROPOUT_IMPLEMENTATION,
                                "clean_rows": EXPECTED_ROWS // 2,
                                "masked_rows": EXPECTED_ROWS // 2,
                                "inference": "unmasked",
                            }
                            if arguments.training_objective
                            == PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE
                            else None
                        ),
                        "continuous_acoustic": (
                            {
                                "implementation": CONTINUOUS_ACOUSTIC_IMPLEMENTATION,
                                "calls": "one-training-plus-one-inference-smoke",
                                "inference": "active",
                            }
                            if arguments.training_objective
                            == PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE
                            else None
                        ),
                        "acoustic_temporal_jitter": (
                            {
                                "implementation": (
                                    ACOUSTIC_TEMPORAL_JITTER_IMPLEMENTATION
                                ),
                                "normal_rows": EXPECTED_ROWS // 2,
                                "shifted_rows": EXPECTED_ROWS // 2,
                                "training_only": True,
                                "inference": "normal-quantized-zq_a",
                                "training_row_identity": (
                                    training_row_identity_receipt(manifest)
                                ),
                            }
                            if arguments.training_objective
                            == PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE
                            else None
                        ),
                        "robust_semantic": (
                            robust_semantic_receipt(str(manifest["kind"]))
                            if arguments.training_objective
                            == PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE
                            else None
                        ),
                        "cv32": validate_cv32_manifest(manifest),
                        "cv32_replacement": validate_cv32_replacement_manifest(
                            manifest
                        ),
                        "cv26": validate_cv26_manifest(manifest),
                        "source_speaker": (
                            {
                                **validate_source_speaker_manifest(manifest),
                                "objective": (
                                    PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE
                                    if arguments.training_objective
                                    == PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE
                                    else "ordinary-matched-control"
                                ),
                                "pool_implementation": SOURCE_SPEAKER_POOL_IMPLEMENTATION,
                                "grl_implementation": SOURCE_SPEAKER_GRL_IMPLEMENTATION,
                                "grl_weight": SOURCE_SPEAKER_GRL_WEIGHT,
                                "classifier_feature_dimension": SOURCE_SPEAKER_FEATURE_DIMENSION,
                                "classifier_class_count": SOURCE_SPEAKER_CLASS_COUNT,
                                "head_exported": False,
                                "head_inference_attachment": None,
                            }
                            if manifest.get("kind") in SRC4VC_TWO_UTTERANCE_KINDS
                            else None
                        ),
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
