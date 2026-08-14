#!/usr/bin/env python3
"""Render EXP-039 on same external speakers saying new utterances."""

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
import run_breadth as breadth  # noqa: E402
import run_post_rehearsal as post  # noqa: E402
import run_role_mix as role_mix  # noqa: E402
import screen  # noqa: E402
from prepare_jsut_evaluation import (  # noqa: E402
    CATEGORY_COUNTS as JSUT_CATEGORY_COUNTS,
)
from prepare_jsut_evaluation import OUTPUT_KIND as JSUT_KIND  # noqa: E402
from prepare_jsut_evaluation import (  # noqa: E402
    WINDOW_POLICY as JSUT_WINDOW_POLICY,
)
from prepare_src4vc_heldout_evaluation import (  # noqa: E402
    OUTPUT_KIND as SRC4VC_HELDOUT_KIND,
)
from prepare_src4vc_heldout_evaluation import (  # noqa: E402
    SOURCE_LICENSE as SRC4VC_SOURCE_LICENSE,
)

KIND = "liveconv-exp039-commonvoice-same-speaker-new-utterances/v1"
EXPANDED_KIND = "liveconv-exp055-commonvoice-local-unused/v1"
HADOU_KIND = "liveconv-exp060-hadou-clean-heldout/v1"
STRESS_KIND = "liveconv-exp086-commonvoice-condition-matrix/v1"
EXPANDED_STRESS_KIND = "liveconv-exp243-length-balanced-symmetric-stress144/v1"
FRESH48_KIND = "liveconv-exp112-commonvoice-fresh48/v1"
JSUT_ROWS = sum(JSUT_CATEGORY_COUNTS.values())
EXPECTED_ROWS = 12
EXPECTED_SPEAKERS = 6
EXPANDED_ROWS = 33
EXPANDED_SPEAKERS = 33
HADOU_ROWS = 31
HADOU_SPEAKERS = 1
STRESS_ROWS = 60
STRESS_SPEAKERS = 6
EXPANDED_STRESS_ROWS = 144
EXPANDED_STRESS_SPEAKERS = 16
FRESH48_ROWS = 48
FRESH48_SPEAKERS = 48
JSUT_SPEAKERS = 1
SRC4VC_HELDOUT_ROWS = 30
SRC4VC_HELDOUT_SPEAKERS = 15
STRESS_GROUPS = {
    "stress-clean",
    "stress-noise20",
    "stress-silence300",
    "stress-tempo120",
    "stress-pitchp3",
}
EXPANDED_STRESS_LENGTHS = {
    "short10to14",
    "medium15to21",
    "long22to30",
    "verylong40plus",
}
EXPANDED_STRESS_TRANSFORMS = {
    "clean": {"kind": "clean"},
    "noise30": {"kind": "noise", "snr_db": 30.0},
    "noise10": {"kind": "noise", "snr_db": 10.0},
    "silence100": {"kind": "leading-silence", "milliseconds": 100},
    "silence600": {"kind": "leading-silence", "milliseconds": 600},
    "tempo080": {"kind": "tempo", "factor": 0.8},
    "tempo120": {"kind": "tempo", "factor": 1.2},
    "pitchn3": {"kind": "pitch", "factor": 0.840896415},
    "pitchp3": {"kind": "pitch", "factor": 1.189207115},
}
EXPANDED_STRESS_CONDITIONS = set(EXPANDED_STRESS_TRANSFORMS)
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
    if kind == "wave-adversarial":
        return {
            "experiment_id": "EXP-065",
            "variant_id": "cv12-wave-adversarial",
            "display_name": (
                "EXP-064 / CV12 / pretrained waveform adversarial"
            ),
            "result_kind": "liveconv-exp065-xvc-wave-adversarial-new-utterance/v1",
            "question": (
                "Does waveform-adversarial adaptation preserve changed utterances?"
            ),
        }
    if kind == "wave-adversarial-hadou":
        return {
            "experiment_id": "EXP-067",
            "variant_id": "cv12-wave-adversarial",
            "display_name": (
                "EXP-064 / CV12 / pretrained waveform adversarial"
            ),
            "result_kind": "liveconv-exp067-xvc-wave-adversarial-hadou/v1",
            "question": (
                "Does waveform-adversarial adaptation preserve clean Hadou "
                "heldout sentences?"
            ),
        }
    if kind == "wave-adversarial-expanded":
        return {
            "experiment_id": "EXP-076",
            "variant_id": "cv12-wave-adversarial",
            "display_name": "EXP-064 / CV12 / pretrained waveform adversarial",
            "result_kind": "liveconv-exp076-xvc-wave-adversarial-expanded/v1",
            "question": (
                "Does waveform-adversarial adaptation remain content-viable on "
                "33 locally unused Common Voice speakers and utterances?"
            ),
        }
    if kind == "wave-adversarial-fresh48":
        return {
            "experiment_id": "EXP-113",
            "variant_id": "cv12-wave-adversarial",
            "display_name": "EXP-064 / CV12 / pretrained waveform adversarial",
            "result_kind": "liveconv-exp113-xvc-wave-adversarial-fresh48/v1",
            "question": (
                "Does the frozen waveform-adversarial adapter avoid corruption "
                "and preserve content on 48 fresh Common Voice speakers?"
            ),
        }
    if kind == "output2":
        return {
            "experiment_id": "EXP-069",
            "variant_id": "cv12-output2",
            "display_name": "EXP-068 / CV12 / decoder-interface output2 LoRA",
            "result_kind": "liveconv-exp069-xvc-output2-new-utterance/v1",
            "question": (
                "Does decoder-interface output2 remain content-viable on changed "
                "utterances from heldout speakers?"
            ),
        }
    if kind == "output2-hadou":
        return {
            "experiment_id": "EXP-071",
            "variant_id": "cv12-output2",
            "display_name": "EXP-068 / CV12 / decoder-interface output2 LoRA",
            "result_kind": "liveconv-exp071-xvc-output2-hadou/v1",
            "question": (
                "Does decoder-interface output2 remain content-viable on 31 clean "
                "Hadou heldout sentences?"
            ),
        }
    if kind == "real-reconstruction20":
        return {
            "experiment_id": "EXP-073",
            "variant_id": "cv12-real-reconstruction20",
            "display_name": "EXP-072 / 20% real Common Voice rehearsal",
            "result_kind": "liveconv-exp073-xvc-real-rehearsal-new-utterance/v1",
            "question": (
                "Does real-speech rehearsal preserve changed utterances from "
                "heldout speakers?"
            ),
        }
    if kind == "real-reconstruction20-hadou":
        return {
            "experiment_id": "EXP-075",
            "variant_id": "cv12-real-reconstruction20",
            "display_name": "EXP-072 / 20% real Common Voice rehearsal",
            "result_kind": "liveconv-exp075-xvc-real-rehearsal-hadou/v1",
            "question": (
                "Does real-speech rehearsal preserve 31 clean Hadou heldout "
                "sentences?"
            ),
        }
    if kind == "decoder-final":
        return {
            "experiment_id": "EXP-078",
            "variant_id": "cv12-decoder-final",
            "display_name": "EXP-077 / final waveform decoder stage",
            "result_kind": "liveconv-exp078-xvc-decoder-final-new/v1",
            "question": "Does decoder-final preserve changed heldout utterances?",
        }
    if kind == "decoder-final-hadou":
        return {
            "experiment_id": "EXP-080",
            "variant_id": "cv12-decoder-final",
            "display_name": "EXP-077 / final waveform decoder stage",
            "result_kind": "liveconv-exp080-xvc-decoder-final-hadou/v1",
            "question": "Does decoder-final preserve 31 clean Hadou sentences?",
        }
    if kind == "source-semantic":
        return {
            "experiment_id": "EXP-082",
            "variant_id": "cv12-source-semantic",
            "display_name": "EXP-081 / source-hidden semantic supervision",
            "result_kind": "liveconv-exp082-xvc-source-semantic-new/v1",
            "question": (
                "Does source-hidden supervision preserve changed heldout "
                "utterances?"
            ),
        }
    if kind == "source-semantic-hadou":
        return {
            "experiment_id": "EXP-084",
            "variant_id": "cv12-source-semantic",
            "display_name": "EXP-081 / source-hidden semantic supervision",
            "result_kind": "liveconv-exp084-xvc-source-semantic-hadou/v1",
            "question": (
                "Does source-hidden supervision preserve 31 clean Hadou "
                "sentences?"
            ),
        }
    if kind == "source-semantic-expanded":
        return {
            "experiment_id": "EXP-085",
            "variant_id": "cv12-source-semantic",
            "display_name": "EXP-081 / source-hidden semantic supervision",
            "result_kind": "liveconv-exp085-xvc-source-semantic-expanded/v1",
            "question": (
                "Does source-hidden supervision remain content-viable on 33 "
                "locally unused Common Voice speakers and utterances?"
            ),
        }
    if kind == "source-semantic-stress":
        return {
            "experiment_id": "EXP-086",
            "variant_id": "cv12-source-semantic",
            "display_name": "EXP-081 / source-hidden semantic supervision",
            "result_kind": "liveconv-exp086-xvc-source-semantic-stress/v1",
            "question": (
                "Does source-hidden supervision improve named audio limitations "
                "across twelve real Common Voice utterances?"
            ),
        }
    denoise_policies = {
        "denoise-semantic": (
            "EXP-088",
            "liveconv-exp088-xvc-denoise-semantic-new/v1",
            "changed heldout utterances",
        ),
        "denoise-semantic-hadou": (
            "EXP-090",
            "liveconv-exp090-xvc-denoise-semantic-hadou/v1",
            "31 clean Hadou sentences",
        ),
        "denoise-semantic-expanded": (
            "EXP-091",
            "liveconv-exp091-xvc-denoise-semantic-expanded/v1",
            "33 locally unused Common Voice speakers",
        ),
        "denoise-semantic-stress": (
            "EXP-092",
            "liveconv-exp092-xvc-denoise-semantic-stress/v1",
            "the 60-row multi-speaker stress matrix",
        ),
    }
    if kind in denoise_policies:
        experiment_id, result_kind, evaluation_name = denoise_policies[kind]
        return {
            "experiment_id": experiment_id,
            "variant_id": "cv12-denoise-semantic",
            "display_name": "EXP-087 / clean-noise denoising semantic consistency",
            "result_kind": result_kind,
            "question": (
                "Does denoising semantic consistency preserve content on "
                f"{evaluation_name}?"
            ),
        }
    condition_policies = {
        "cross-target-condition": (
            "EXP-095",
            "liveconv-exp095-xvc-cross-target-condition-new/v1",
        ),
        "cross-target-condition-hadou": (
            "EXP-097",
            "liveconv-exp097-xvc-cross-target-condition-hadou/v1",
        ),
        "cross-target-condition-expanded": (
            "EXP-098",
            "liveconv-exp098-xvc-cross-target-condition-expanded/v1",
        ),
        "cross-target-condition-stress": (
            "EXP-099",
            "liveconv-exp099-xvc-cross-target-condition-stress/v1",
        ),
    }
    if kind in condition_policies:
        experiment_id, result_kind = condition_policies[kind]
        return {
            "experiment_id": experiment_id,
            "variant_id": "cv12-cross-target-condition",
            "display_name": (
                "EXP-094 / same-speaker cross-utterance frame condition"
            ),
            "result_kind": result_kind,
            "question": (
                "Does cross-utterance target-frame conditioning preserve content "
                "and avoid corruption on this frozen evaluation set?"
            ),
            "conditioned_inference": True,
        }
    token_hold_policies = {
        "semantic-token-hold": (
            "EXP-101",
            "liveconv-exp101-xvc-semantic-token-hold-new/v1",
        ),
        "semantic-token-hold-hadou": (
            "EXP-103",
            "liveconv-exp103-xvc-semantic-token-hold-hadou/v1",
        ),
        "semantic-token-hold-expanded": (
            "EXP-104",
            "liveconv-exp104-xvc-semantic-token-hold-expanded/v1",
        ),
        "semantic-token-hold-stress": (
            "EXP-105",
            "liveconv-exp105-xvc-semantic-token-hold-stress/v1",
        ),
    }
    if kind in token_hold_policies:
        experiment_id, result_kind = token_hold_policies[kind]
        return {
            "experiment_id": experiment_id,
            "variant_id": "cv12-semantic-token-hold",
            "display_name": (
                "EXP-100 / alternating clean and 5-frame-held semantic tokens"
            ),
            "result_kind": result_kind,
            "question": (
                "Does semantic-token hold training preserve content and avoid "
                "corruption on this frozen evaluation set?"
            ),
        }
    real_teacher_policies = {
        "real-teacher-semantic20": (
            "EXP-107",
            "liveconv-exp107-xvc-real-teacher-semantic-new/v1",
        ),
        "real-teacher-semantic20-hadou": (
            "EXP-109",
            "liveconv-exp109-xvc-real-teacher-semantic-hadou/v1",
        ),
        "real-teacher-semantic20-expanded": (
            "EXP-110",
            "liveconv-exp110-xvc-real-teacher-semantic-expanded/v1",
        ),
        "real-teacher-semantic20-stress": (
            "EXP-111",
            "liveconv-exp111-xvc-real-teacher-semantic-stress/v1",
        ),
        "real-teacher-semantic20-fresh48": (
            "EXP-112",
            "liveconv-exp112-xvc-real-teacher-semantic-fresh48/v1",
        ),
    }
    if kind in real_teacher_policies:
        experiment_id, result_kind = real_teacher_policies[kind]
        return {
            "experiment_id": experiment_id,
            "variant_id": "cv12-real-teacher-semantic20",
            "display_name": (
                "EXP-106 / real-source frozen-teacher semantic rehearsal"
            ),
            "result_kind": result_kind,
            "question": (
                "Does real-source frozen-teacher semantic rehearsal preserve "
                "content and avoid corruption on this frozen evaluation set?"
            ),
        }
    if kind == "real-teacher-breadth48-fresh48":
        return {
            "experiment_id": "EXP-115",
            "variant_id": "cv12-real-teacher-breadth48",
            "display_name": (
                "EXP-114 / semantic teacher / 48 training-only speakers"
            ),
            "result_kind": "liveconv-exp115-xvc-real-teacher-breadth48-fresh48/v1",
            "question": (
                "Does expanding only real semantic-teacher source diversity "
                "avoid corruption and improve content on frozen fresh48?"
            ),
        }
    if kind == "real-teacher-output48-fresh48":
        return {
            "experiment_id": "EXP-117",
            "variant_id": "cv12-real-teacher-output48",
            "display_name": (
                "EXP-116 / frozen-base full-output teacher / 48 speakers"
            ),
            "result_kind": "liveconv-exp117-xvc-real-teacher-output48-fresh48/v1",
            "question": (
                "Does full converted-output distillation prevent corruption "
                "and preserve content on frozen fresh48?"
            ),
        }
    if kind == "real-teacher-output48-ffn22-fresh48":
        return {
            "experiment_id": "EXP-119",
            "variant_id": "cv12-real-teacher-output48-ffn22",
            "display_name": (
                "EXP-118 / full-output teacher / FFN-only LoRA"
            ),
            "result_kind": (
                "liveconv-exp119-xvc-real-teacher-output48-ffn22-fresh48/v1"
            ),
            "question": (
                "Does freezing attention adaptation retain the broad "
                "full-output teacher signal without adding corruption on "
                "frozen fresh48?"
            ),
        }
    if kind == "real-teacher-output48-dora-fresh48":
        return {
            "experiment_id": "EXP-121",
            "variant_id": "cv12-real-teacher-output48-dora",
            "display_name": "EXP-120 / full-output teacher / control69 DoRA",
            "result_kind": (
                "liveconv-exp121-xvc-real-teacher-output48-dora-fresh48/v1"
            ),
            "question": (
                "Does DoRA retain the broad full-output teacher signal without "
                "adding corruption on frozen fresh48?"
            ),
        }
    if kind == "real-teacher-output48-temporal-fresh48":
        return {
            "experiment_id": "EXP-123",
            "variant_id": "cv12-real-teacher-output48-temporal",
            "display_name": (
                "EXP-122 / full-output teacher / temporal difference"
            ),
            "result_kind": (
                "liveconv-exp123-xvc-real-teacher-output48-temporal-fresh48/v1"
            ),
            "question": (
                "Does aligned waveform first-difference matching avoid "
                "corruption on frozen fresh48?"
            ),
        }
    if kind == "real-teacher-output-multidomain48-fresh48":
        return {
            "experiment_id": "EXP-125",
            "variant_id": "cv12-real-teacher-output-multidomain48",
            "display_name": (
                "EXP-124 / full-output teacher / CV24 + Hadou21 + JVS3"
            ),
            "result_kind": (
                "liveconv-exp125-xvc-real-teacher-output-multidomain48-fresh48/v1"
            ),
            "question": (
                "Does cross-corpus teacher-source composition avoid corruption "
                "and generalize on frozen fresh48?"
            ),
        }
    if kind == "real-teacher-output-multidomain48-hadou":
        return {
            "experiment_id": "EXP-127",
            "variant_id": "cv12-real-teacher-output-multidomain48",
            "display_name": (
                "EXP-124 / full-output teacher / CV24 + Hadou21 + JVS3"
            ),
            "result_kind": (
                "liveconv-exp127-xvc-real-teacher-output-multidomain48-hadou31/v1"
            ),
            "question": (
                "Does cross-corpus teacher-source composition preserve content "
                "on 31 disjoint clean Hadou utterances?"
            ),
        }
    if kind == "real-teacher-output-multidomain48-stress":
        return {
            "experiment_id": "EXP-128",
            "variant_id": "cv12-real-teacher-output-multidomain48",
            "display_name": (
                "EXP-124 / full-output teacher / CV24 + Hadou21 + JVS3"
            ),
            "result_kind": (
                "liveconv-exp128-xvc-real-teacher-output-multidomain48-stress60/v1"
            ),
            "question": (
                "Does cross-corpus teacher-source composition remain stable "
                "across frozen clean, noise, silence, tempo, and pitch inputs?"
            ),
        }
    if kind in {
        "real-teacher-output-phonetic48-fresh48",
        "real-teacher-output-phonetic48-hadou",
    }:
        hadou = kind.endswith("-hadou")
        return {
            "experiment_id": "EXP-132" if hadou else "EXP-131",
            "variant_id": "cv12-real-teacher-output-phonetic48",
            "display_name": (
                "EXP-130 / full-output teacher / quality + kana coverage"
            ),
            "result_kind": (
                "liveconv-exp132-xvc-real-teacher-output-phonetic48-hadou31/v1"
                if hadou
                else "liveconv-exp131-xvc-real-teacher-output-phonetic48-fresh48/v1"
            ),
            "question": (
                "Does quality-filtered kana and length coverage preserve content "
                "on 31 disjoint clean Hadou utterances?"
                if hadou
                else "Does quality-filtered kana and length coverage avoid "
                "corruption and generalize on frozen fresh48?"
            ),
        }
    if kind in {
        "real-teacher-output-window48-fresh48",
        "real-teacher-output-window48-hadou",
    }:
        hadou = kind.endswith("-hadou")
        return {
            "experiment_id": "EXP-136" if hadou else "EXP-135",
            "variant_id": "cv12-real-teacher-output-window48",
            "display_name": (
                "EXP-134 / full-output teacher / audited start-middle-end windows"
            ),
            "result_kind": (
                "liveconv-exp136-xvc-real-teacher-output-window48-hadou31/v1"
                if hadou
                else "liveconv-exp135-xvc-real-teacher-output-window48-fresh48/v1"
            ),
            "question": (
                "Does model-window-aware teacher selection preserve content on "
                "31 disjoint clean Hadou utterances?"
                if hadou
                else "Does model-window-aware teacher selection avoid corruption "
                "and generalize on frozen fresh48?"
            ),
        }
    if kind in {
        "real-teacher-output-window201-fresh48",
        "real-teacher-output-window201-hadou",
    }:
        hadou = kind.endswith("-hadou")
        return {
            "experiment_id": "EXP-140" if hadou else "EXP-139",
            "variant_id": "cv12-real-teacher-output-window201",
            "display_name": (
                "EXP-138 / full-output teacher / 201 near-one-pass real windows"
            ),
            "result_kind": (
                "liveconv-exp140-xvc-real-teacher-window201-hadou31/v1"
                if hadou
                else "liveconv-exp139-xvc-real-teacher-window201-fresh48/v1"
            ),
            "question": (
                "Does near-one-pass real-window breadth preserve content on 31 "
                "disjoint clean Hadou utterances?"
                if hadou
                else "Does near-one-pass real-window breadth avoid corruption "
                "and generalize on frozen fresh48?"
            ),
        }
    if kind in {
        "clean-post-rehearsal-fresh48",
        "clean-post-rehearsal-hadou",
    }:
        hadou = kind.endswith("-hadou")
        return {
            "experiment_id": "EXP-143" if hadou else "EXP-142",
            "variant_id": "cv12-clean-post-rehearsal170",
            "display_name": (
                "EXP-141 / control69 + clean unique teacher rehearsal pass"
            ),
            "result_kind": (
                "liveconv-exp143-xvc-clean-post-rehearsal-hadou31/v1"
                if hadou
                else "liveconv-exp142-xvc-clean-post-rehearsal-fresh48/v1"
            ),
            "question": (
                "Does clean post-adaptation rehearsal avoid heldout corruption "
                "on 31 disjoint Hadou utterances?"
                if hadou
                else "Does clean post-adaptation rehearsal avoid corruption and "
                "generalize on frozen fresh48?"
            ),
        }
    if kind == "clean-post-rehearsal-jsut":
        return {
            "experiment_id": "EXP-144",
            "variant_id": "cv12-clean-post-rehearsal170",
            "display_name": (
                "EXP-141 / control69 + clean unique teacher rehearsal pass"
            ),
            "result_kind": (
                "liveconv-exp144-xvc-clean-post-rehearsal-jsut24/v1"
            ),
            "question": (
                "Does clean post-adaptation rehearsal avoid corruption across "
                "untouched JSUT normal, onomatopoeia, counter-suffix, loanword, "
                "and travel categories?"
            ),
        }
    if kind in {
        "hard-negative-curriculum-fresh48",
        "hard-negative-curriculum-hadou",
        "hard-negative-curriculum-jsut",
    }:
        hadou = kind.endswith("-hadou")
        jsut = kind.endswith("-jsut")
        return {
            "experiment_id": "EXP-149" if jsut else "EXP-148" if hadou else "EXP-147",
            "variant_id": "cv12-hard-negative-curriculum170",
            "display_name": (
                "EXP-146 / control69 + failure-triggered 50/50 curriculum"
            ),
            "result_kind": (
                "liveconv-exp149-xvc-hard-negative-curriculum-jsut24/v1"
                if jsut
                else (
                    "liveconv-exp148-xvc-hard-negative-curriculum-hadou31/v1"
                    if hadou
                    else "liveconv-exp147-xvc-hard-negative-curriculum-fresh48/v1"
                )
            ),
            "question": (
                "Does training-only failure-triggered sampling avoid corruption "
                "across untouched JSUT categories?"
                if jsut
                else (
                    "Does training-only failure-triggered sampling repair the "
                    "heldout Hadou collapse without broad regression?"
                    if hadou
                    else "Does training-only failure-triggered sampling repair "
                    "control69 collapse on frozen fresh48?"
                )
            ),
        }
    if kind in {
        "selective-retention-fresh48",
        "selective-retention-hadou",
        "selective-retention-jsut",
    }:
        hadou = kind.endswith("-hadou")
        jsut = kind.endswith("-jsut")
        return {
            "experiment_id": "EXP-153" if jsut else "EXP-152" if hadou else "EXP-151",
            "variant_id": "cv12-selective-retention170",
            "display_name": (
                "EXP-150 / hard repair + control69 retention distillation"
            ),
            "result_kind": (
                "liveconv-exp153-xvc-selective-retention-jsut24/v1"
                if jsut
                else (
                    "liveconv-exp152-xvc-selective-retention-hadou31/v1"
                    if hadou
                    else "liveconv-exp151-xvc-selective-retention-fresh48/v1"
                )
            ),
            "question": (
                "Does selective failure repair survive untouched JSUT categories?"
                if jsut
                else (
                    "Does selective failure repair remove the heldout Hadou loop "
                    "without regression?"
                    if hadou
                    else "Does selective failure repair preserve broad fresh48 "
                    "control69 behavior?"
                )
            ),
        }
    if kind in {
        "full-converter-retention-fresh48",
        "full-converter-retention-hadou",
        "full-converter-retention-jsut",
    }:
        hadou = kind.endswith("-hadou")
        jsut = kind.endswith("-jsut")
        return {
            "experiment_id": "EXP-157" if jsut else "EXP-156" if hadou else "EXP-155",
            "variant_id": "cv12-selective-retention-full-converter170",
            "display_name": (
                "EXP-154 / selective retention / full acoustic converter"
            ),
            "candidate_format": "merged-control69-converter",
            "result_kind": (
                "liveconv-exp157-xvc-full-converter-retention-jsut24/v1"
                if jsut
                else (
                    "liveconv-exp156-xvc-full-converter-retention-hadou31/v1"
                    if hadou
                    else "liveconv-exp155-xvc-full-converter-retention-fresh48/v1"
                )
            ),
            "question": (
                "Does full-converter selective repair survive untouched JSUT "
                "categories?"
                if jsut
                else (
                    "Does full-converter selective repair remove the heldout Hadou "
                    "loop without broad regression?"
                    if hadou
                    else "Does full-converter selective repair preserve broad "
                    "fresh48 control69 behavior?"
                )
            ),
        }
    if kind in {
        "real-reference-adversarial-fresh48",
        "real-reference-adversarial-hadou",
        "real-reference-adversarial-stress",
        "real-reference-adversarial-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-162"
            if jsut
            else "EXP-161"
            if stress
            else "EXP-160"
            if hadou
            else "EXP-159"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        question = (
            "Does real-reference adversarial retention survive untouched JSUT "
            "categories?"
            if jsut
            else (
                "Does real-reference adversarial retention survive frozen rate, "
                "pitch, silence, and noise conditions?"
                if stress
                else (
                    "Does real-reference adversarial retention avoid heldout "
                    "Hadou collapse?"
                    if hadou
                    else "Does real-reference adversarial retention preserve "
                    "broad fresh48 behavior?"
                )
            )
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "cv12-selective-retention-real-adversarial170",
            "display_name": (
                "EXP-158 / selective retention + real-reference adversarial"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-real-reference-adversarial-"
                f"{suffix}/v1"
            ),
            "question": question,
        }
    if kind in {
        "real-adversarial-ema-fresh48",
        "real-adversarial-ema-hadou",
        "real-adversarial-ema-stress",
        "real-adversarial-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-167"
            if jsut
            else "EXP-166"
            if stress
            else "EXP-165"
            if hadou
            else "EXP-164"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "cv12-selective-real-adversarial-ema170",
            "display_name": (
                "EXP-163 / selective real-adversarial / upstream EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-real-adversarial-ema-"
                f"{suffix}/v1"
            ),
            "question": (
                "Does upstream EMA survive untouched JSUT categories?"
                if jsut
                else (
                    "Does upstream EMA survive frozen rate, pitch, silence, and "
                    "noise conditions?"
                    if stress
                    else (
                        "Does upstream EMA avoid heldout Hadou collapse?"
                        if hadou
                        else "Does upstream EMA preserve broad fresh48 behavior "
                        "without online-checkpoint collapse?"
                    )
                )
            ),
        }
    if kind == "real-adversarial-ema-expanded":
        return {
            "experiment_id": "EXP-168",
            "variant_id": "cv12-selective-real-adversarial-ema170",
            "display_name": (
                "EXP-163 / selective real-adversarial / upstream EMA"
            ),
            "result_kind": "liveconv-exp168-xvc-real-adversarial-ema-expanded33/v1",
            "question": (
                "Does the frozen upstream-EMA candidate avoid corruption across "
                "33 additional Common Voice speakers and utterances?"
            ),
        }
    if kind in {
        "paired-pcgrad-fresh48",
        "paired-pcgrad-hadou",
        "paired-pcgrad-stress",
        "paired-pcgrad-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-180"
            if jsut
            else "EXP-179"
            if stress
            else "EXP-178"
            if hadou
            else "EXP-177"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "cv12-selective-pcgrad85",
            "display_name": "EXP-176 / paired hard-retention PCGrad",
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-paired-pcgrad-"
                f"{suffix}/v1"
            ),
            "question": (
                "Does paired gradient-conflict surgery survive the same frozen "
                "content and corruption gate?"
            ),
        }
    if kind in {
        "jsut-retention-ema-fresh48",
        "jsut-retention-ema-hadou",
        "jsut-retention-ema-stress",
        "jsut-retention-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-175"
            if jsut
            else "EXP-174"
            if stress
            else "EXP-173"
            if hadou
            else "EXP-172"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "cv12-jsut-retention-real-adversarial-ema170",
            "display_name": (
                "EXP-171 / JSUT retention + real-adversarial + EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-jsut-retention-ema-"
                f"{suffix}/v1"
            ),
            "question": (
                "Does JSUT retention survive the same frozen independent gate?"
            ),
        }
    if kind in {
        "parameter-anchor-ema-fresh48",
        "parameter-anchor-ema-hadou",
        "parameter-anchor-ema-stress",
        "parameter-anchor-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-185"
            if jsut
            else "EXP-184"
            if stress
            else "EXP-183"
            if hadou
            else "EXP-182"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "cv12-selective-real-adversarial-anchor-ema170",
            "display_name": (
                "EXP-181 / control69 parameter anchor + adversarial + EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-parameter-anchor-ema-"
                f"{suffix}/v1"
            ),
            "question": (
                "Does the control69 parameter anchor survive the same frozen "
                "content and corruption gate?"
            ),
        }
    if kind in {
        "commonvoice48-retention-ema-fresh48",
        "commonvoice48-retention-ema-hadou",
        "commonvoice48-retention-ema-stress",
        "commonvoice48-retention-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-190"
            if jsut
            else "EXP-189"
            if stress
            else "EXP-188"
            if hadou
            else "EXP-187"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": (
                "cv12-commonvoice48-retention-real-adversarial-ema170"
            ),
            "display_name": (
                "EXP-186 / Common Voice 48-speaker retention + "
                "real-adversarial + EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-commonvoice48-"
                f"retention-ema-{suffix}/v1"
            ),
            "question": (
                "Does the speech-active 48-speaker retention method survive "
                "the same frozen independent gate?"
            ),
        }
    if kind in {
        "conditioned-retention-ema-fresh48",
        "conditioned-retention-ema-stress",
    }:
        stress = kind.endswith("-stress")
        experiment_id = "EXP-193" if stress else "EXP-192"
        suffix = "stress60" if stress else "fresh48"
        return {
            "experiment_id": experiment_id,
            "variant_id": (
                "cv12-conditioned-retention-real-adversarial-ema170"
            ),
            "display_name": (
                "EXP-191 / condition-balanced control69 retention + "
                "real-adversarial + EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-conditioned-"
                f"retention-ema-{suffix}/v1"
            ),
            "question": (
                "Does condition-balanced control69 retention survive the "
                "same frozen independent content and condition gate?"
            ),
        }
    if kind == "source36-retention-ema-stress":
        return {
            "experiment_id": "EXP-195",
            "variant_id": (
                "cv12-commonvoice48-source36-real-adversarial-ema170"
            ),
            "display_name": (
                "EXP-194 / source36 retention + real-adversarial + EMA"
            ),
            "result_kind": (
                "liveconv-exp-195-xvc-source36-retention-ema-stress60/v1"
            ),
            "question": (
                "Does source-path-only retention preserve frozen clean, noise, "
                "pitch, silence, and tempo behavior?"
            ),
        }
    if kind == "source-envelope-retention-ema-stress":
        return {
            "experiment_id": "EXP-197",
            "variant_id": (
                "cv12-commonvoice48-source-envelope-real-adversarial-ema170"
            ),
            "display_name": (
                "EXP-196 / source activity envelope retention + "
                "real-adversarial + EMA"
            ),
            "result_kind": (
                "liveconv-exp-197-xvc-source-envelope-retention-ema-stress60/v1"
            ),
            "question": (
                "Does explicit source activity-envelope retention preserve "
                "frozen clean, noise, pitch, silence, and tempo behavior?"
            ),
        }
    if kind in {
        "acoustic-encoder-ema-fresh48",
        "acoustic-encoder-ema-hadou",
        "acoustic-encoder-ema-stress",
        "acoustic-encoder-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-202"
            if jsut
            else "EXP-201"
            if stress
            else "EXP-200"
            if hadou
            else "EXP-199"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": (
                "cv12-selective-acoustic-encoder-real-adversarial-ema170"
            ),
            "display_name": (
                "EXP-198 / selective real-adversarial / acoustic encoder / EMA"
            ),
            "candidate_format": "merged-control69-acoustic-encoder",
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-acoustic-encoder-"
                f"real-adversarial-ema-{suffix}/v1"
            ),
            "question": (
                "Does source acoustic-representation adaptation survive the "
                "complete frozen cross-corpus and condition contract?"
            ),
        }
    if kind in {
        "unpaired-human-ema-fresh48",
        "unpaired-human-ema-hadou",
        "unpaired-human-ema-stress",
        "unpaired-human-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-207"
            if jsut
            else "EXP-206"
            if stress
            else "EXP-205"
            if hadou
            else "EXP-204"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "human170-factorized-unpaired-ema170",
            "display_name": (
                "EXP-203 / unpaired human content-identity factorization / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-unpaired-human-"
                f"factorized-ema-{suffix}/v1"
            ),
            "question": (
                "Does alignment-free human content/identity factorization survive "
                "the complete frozen cross-corpus and condition contract?"
            ),
        }
    if kind in {
        "unpaired-output-cycle-ema-fresh48",
        "unpaired-output-cycle-ema-hadou",
        "unpaired-output-cycle-ema-stress",
        "unpaired-output-cycle-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-212"
            if jsut
            else "EXP-211"
            if stress
            else "EXP-210"
            if hadou
            else "EXP-209"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "human170-unpaired-output-cycle-ema170",
            "display_name": "EXP-208 / unpaired human output-cycle content / EMA",
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-unpaired-human-"
                f"output-cycle-ema-{suffix}/v1"
            ),
            "question": (
                "Does final-WAV frozen-Whisper content cycling prevent corruption "
                "and preserve tempo across the complete fixed evaluation contract?"
            ),
        }
    if kind in {
        "cross-corpus-output-cycle-ema-fresh48",
        "cross-corpus-output-cycle-ema-hadou",
        "cross-corpus-output-cycle-ema-stress",
        "cross-corpus-output-cycle-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-217"
            if jsut
            else "EXP-216"
            if stress
            else "EXP-215"
            if hadou
            else "EXP-214"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "cross-corpus170-unpaired-output-cycle-ema170",
            "display_name": (
                "EXP-213 / cross-corpus unpaired output-cycle / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-cross-corpus-"
                f"output-cycle-ema-{suffix}/v1"
            ),
            "question": (
                "Does training-only CV/JSUT/JVS/Hadou source diversity reduce "
                "unknown-speaker collapse while preserving fixed cross-condition "
                "content behavior?"
            ),
        }
    if kind in {
        "contrastive-output-cycle-ema-fresh48",
        "contrastive-output-cycle-ema-hadou",
        "contrastive-output-cycle-ema-stress",
        "contrastive-output-cycle-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-222"
            if jsut
            else "EXP-221"
            if stress
            else "EXP-220"
            if hadou
            else "EXP-219"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "cross-corpus170-contrastive-output-cycle-ema170",
            "display_name": (
                "EXP-218 / cross-corpus contrastive output-cycle / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-contrastive-"
                f"output-cycle-ema-{suffix}/v1"
            ),
            "question": (
                "Does source-versus-negative final-WAV content discrimination "
                "reduce collapse without losing the cross-corpus stability signal?"
            ),
        }
    if kind in {
        "content-voice-pcgrad-ema-fresh48",
        "content-voice-pcgrad-ema-hadou",
        "content-voice-pcgrad-ema-stress",
        "content-voice-pcgrad-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-232"
            if jsut
            else "EXP-231"
            if stress
            else "EXP-230"
            if hadou
            else "EXP-229"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "cross-corpus170-content-voice-pcgrad-ema170",
            "display_name": (
                "EXP-228 / cross-corpus content-voice PCGrad / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-content-voice-pcgrad-"
                f"ema-{suffix}/v1"
            ),
            "question": (
                "Does per-row content-versus-voice gradient surgery retain "
                "cross-corpus gains without the ordinary-JSUT tradeoff?"
            ),
        }
    if kind in {
        "pseudoparallel-real-adv-ema-expanded-stress",
    }:
        return {
            "experiment_id": "EXP-243",
            "variant_id": "cross-corpus170-pseudoparallel-real-adv-ema170",
            "display_name": (
                "EXP-238 / source-aligned control69 targets / real-adversarial / EMA"
            ),
            "result_kind": (
                "liveconv-exp243-xvc-pseudoparallel-expanded-stress144/v1"
            ),
            "question": (
                "Does the EXP-238 technical survivor remain content-stable across "
                "symmetric speed, pitch, silence, noise, and text-length strata?"
            ),
        }
    if kind == "output-speaker-ema-expanded-stress":
        return {
            "experiment_id": "EXP-257",
            "variant_id": "cross-corpus170-pseudoparallel-output-speaker-ema170",
            "display_name": (
                "EXP-252 / final-WAV speaker identity / pseudoparallel / "
                "real-adversarial / EMA"
            ),
            "result_kind": (
                "liveconv-exp257-xvc-output-speaker-expanded-stress144/v1"
            ),
            "question": (
                "Does final-WAV speaker supervision retain content across the "
                "frozen symmetric length and condition matrix?"
            ),
        }
    if kind in {
        "real-speaker-condition-ema-fresh48",
        "real-speaker-condition-ema-hadou",
        "real-speaker-condition-ema-stress",
        "real-speaker-condition-ema-jsut",
        "real-speaker-condition-ema-expanded-stress",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress") and not kind.endswith(
            "-expanded-stress"
        )
        jsut = kind.endswith("-jsut")
        expanded = kind.endswith("-expanded-stress")
        experiment_id = (
            "EXP-272"
            if expanded
            else "EXP-271"
            if jsut
            else "EXP-270"
            if stress
            else "EXP-269"
            if hadou
            else "EXP-268"
        )
        suffix = (
            "expanded-stress144"
            if expanded
            else "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": (
                "cross-corpus170-pseudoparallel-real-speaker-condition-ema170"
            ),
            "display_name": (
                "EXP-267 / real target speaker condition / pseudoparallel / "
                "real-adversarial / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-real-speaker-condition-"
                f"ema-{suffix}/v1"
            ),
            "question": (
                "Does separating the real target speaker condition from the "
                "same-content reconstruction target preserve content across "
                "the established broad surfaces?"
            ),
        }
    if kind in {
        "fresh-lora-pseudoparallel-ema-fresh48",
        "fresh-lora-pseudoparallel-ema-hadou",
        "fresh-lora-pseudoparallel-ema-stress",
        "fresh-lora-pseudoparallel-ema-jsut",
        "fresh-lora-pseudoparallel-ema-expanded-stress",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress") and not kind.endswith(
            "-expanded-stress"
        )
        jsut = kind.endswith("-jsut")
        expanded = kind.endswith("-expanded-stress")
        experiment_id = (
            "EXP-278"
            if expanded
            else "EXP-277"
            if jsut
            else "EXP-276"
            if stress
            else "EXP-275"
            if hadou
            else "EXP-274"
        )
        suffix = (
            "expanded-stress144"
            if expanded
            else "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": (
                "cross-corpus170-pseudoparallel-fresh-lora-real-adv-ema170"
            ),
            "display_name": (
                "EXP-273 / source-aligned targets / fresh LoRA69 / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-fresh-lora-"
                f"pseudoparallel-{suffix}/v1"
            ),
            "question": (
                "Does fresh LoRA distillation of the source-aligned teacher "
                "avoid inherited failures across the established broad surfaces?"
            ),
        }
    if kind in {
        "acoustic-dropout-pseudoparallel-ema-fresh48",
        "acoustic-dropout-pseudoparallel-ema-hadou",
        "acoustic-dropout-pseudoparallel-ema-stress",
        "acoustic-dropout-pseudoparallel-ema-jsut",
        "acoustic-dropout-pseudoparallel-ema-expanded-stress",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress") and not kind.endswith(
            "-expanded-stress"
        )
        jsut = kind.endswith("-jsut")
        expanded = kind.endswith("-expanded-stress")
        experiment_id = (
            "EXP-284"
            if expanded
            else "EXP-283"
            if jsut
            else "EXP-282"
            if stress
            else "EXP-281"
            if hadou
            else "EXP-280"
        )
        suffix = (
            "expanded-stress144"
            if expanded
            else "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": (
                "cross-corpus170-pseudoparallel-acoustic-dropout-"
                "real-adv-ema170"
            ),
            "display_name": (
                "EXP-279 / source-aligned targets / acoustic-code dropout / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-acoustic-dropout-"
                f"pseudoparallel-{suffix}/v1"
            ),
            "question": (
                "Does training-time acoustic-code dropout improve robust content "
                "across the established broad surfaces?"
            ),
        }
    if kind in {
        "continuous-acoustic-pseudoparallel-ema-fresh48",
        "continuous-acoustic-pseudoparallel-ema-hadou",
        "continuous-acoustic-pseudoparallel-ema-stress",
        "continuous-acoustic-pseudoparallel-ema-jsut",
        "continuous-acoustic-pseudoparallel-ema-expanded-stress",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress") and not kind.endswith(
            "-expanded-stress"
        )
        jsut = kind.endswith("-jsut")
        expanded = kind.endswith("-expanded-stress")
        experiment_id = (
            "EXP-290"
            if expanded
            else "EXP-289"
            if jsut
            else "EXP-288"
            if stress
            else "EXP-287"
            if hadou
            else "EXP-286"
        )
        suffix = (
            "expanded-stress144"
            if expanded
            else "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": (
                "cross-corpus170-pseudoparallel-continuous-acoustic-"
                "real-adv-ema170"
            ),
            "display_name": (
                "EXP-285 / source-aligned targets / continuous pre-VQ acoustic / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-continuous-acoustic-"
                f"pseudoparallel-ema-{suffix}/v1"
            ),
            "question": (
                "Does a continuous pre-VQ acoustic representation improve robust "
                "content across the established broad surfaces?"
            ),
            "candidate_attachment": "continuous-acoustic-latent",
        }
    if kind in {
        "acoustic-temporal-jitter-pseudoparallel-ema-fresh48",
        "acoustic-temporal-jitter-pseudoparallel-ema-hadou",
        "acoustic-temporal-jitter-pseudoparallel-ema-stress",
        "acoustic-temporal-jitter-pseudoparallel-ema-jsut",
        "acoustic-temporal-jitter-pseudoparallel-ema-expanded-stress",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress") and not kind.endswith(
            "-expanded-stress"
        )
        jsut = kind.endswith("-jsut")
        expanded = kind.endswith("-expanded-stress")
        experiment_id = (
            "EXP-296"
            if expanded
            else "EXP-295"
            if jsut
            else "EXP-294"
            if stress
            else "EXP-293"
            if hadou
            else "EXP-292"
        )
        suffix = (
            "expanded-stress144"
            if expanded
            else "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": (
                "cross-corpus170-pseudoparallel-acoustic-temporal-jitter-"
                "real-adv-ema170"
            ),
            "display_name": (
                "EXP-291 / source-aligned targets / acoustic temporal jitter / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-acoustic-temporal-jitter-"
                f"pseudoparallel-ema-{suffix}/v1"
            ),
            "question": (
                "Does training-only one-frame right-shifted quantized source "
                "acoustics improve robust content across the established broad "
                "evaluation surfaces while inference remains normal?"
            ),
        }
    if kind in {
        "robust-semantic-pseudoparallel-ema-fresh48",
        "robust-semantic-pseudoparallel-ema-hadou",
        "robust-semantic-pseudoparallel-ema-stress",
        "robust-semantic-pseudoparallel-ema-jsut",
        "robust-semantic-pseudoparallel-ema-expanded144",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        expanded = kind.endswith("-expanded144")
        experiment_id = (
            "EXP-302"
            if expanded
            else "EXP-301"
            if jsut
            else "EXP-300"
            if stress
            else "EXP-299"
            if hadou
            else "EXP-298"
        )
        suffix = (
            "expanded144"
            if expanded
            else "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": (
                "cross-corpus170-pseudoparallel-robust-semantic-real-adv-ema170"
            ),
            "display_name": (
                "EXP-297 / source-aligned targets / scale-matched robust semantic "
                "decoder / real-adversarial / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-robust-semantic-"
                f"pseudoparallel-ema-{suffix}/v1"
            ),
            "question": (
                "Does scale-matched SmoothL1 semantic-decoder supervision improve "
                "robust content across the established broad evaluation surfaces?"
            ),
        }
    if kind in {
        "cv32-breadth-pseudoparallel-ema-external7",
        "cv32-breadth-pseudoparallel-ema-fresh48",
        "cv32-breadth-pseudoparallel-ema-hadou",
        "cv32-breadth-pseudoparallel-ema-stress",
        "cv32-breadth-pseudoparallel-ema-jsut",
        "cv32-breadth-pseudoparallel-ema-expanded144",
    }:
        external = kind.endswith("-external7")
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        expanded = kind.endswith("-expanded144")
        experiment_id = (
            "EXP-306"
            if external
            else "EXP-311"
            if expanded
            else "EXP-310"
            if jsut
            else "EXP-309"
            if stress
            else "EXP-308"
            if hadou
            else "EXP-307"
        )
        suffix = (
            "external7"
            if external
            else "expanded144"
            if expanded
            else "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": (
                "cross-corpus202-pseudoparallel-cv32-breadth-real-adv-ema202"
            ),
            "display_name": (
                "EXP-306 / exact EXP-238 + genuine Common Voice32 breadth / "
                "real-adversarial / EMA"
            ),
            "result_kind": (
                "liveconv-exp306-xvc-pseudoparallel-cv32-breadth-real-adv-ema/v1"
                if external
                else (
                    f"liveconv-{experiment_id.lower()}-xvc-cv32-breadth-"
                    f"pseudoparallel-ema-{suffix}/v1"
                )
            ),
            "question": (
                "Does genuinely new CV32 utterance breadth preserve content "
                "across the fixed external and broad evaluation surfaces?"
            ),
        }
    if kind in {
        "repeat-control-pseudoparallel-ema-external7",
        "repeat-control-pseudoparallel-ema-fresh48",
        "repeat-control-pseudoparallel-ema-hadou",
        "repeat-control-pseudoparallel-ema-stress",
        "repeat-control-pseudoparallel-ema-jsut",
        "repeat-control-pseudoparallel-ema-expanded144",
    }:
        external = kind.endswith("-external7")
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        expanded = kind.endswith("-expanded144")
        experiment_id = (
            "EXP-305"
            if external
            else "EXP-316"
            if expanded
            else "EXP-315"
            if jsut
            else "EXP-314"
            if stress
            else "EXP-313"
            if hadou
            else "EXP-312"
        )
        suffix = (
            "external7"
            if external
            else "expanded144"
            if expanded
            else "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": (
                "cross-corpus202-pseudoparallel-repeat32-control-real-adv-ema202"
            ),
            "display_name": (
                "EXP-305 / exact EXP-238 + matched Common Voice repeat32 / "
                "real-adversarial / EMA"
            ),
            "result_kind": (
                "liveconv-exp305-xvc-pseudoparallel-repeat32-control-real-adv-ema/v1"
                if external
                else (
                    f"liveconv-{experiment_id.lower()}-xvc-repeat32-"
                    f"pseudoparallel-ema-{suffix}/v1"
                )
            ),
            "question": (
                "Does the exposure-matched repeat32 control preserve content "
                "across the fixed external and broad evaluation surfaces?"
            ),
        }
    if kind in {
        "speaker-condition-calibrator-fresh48",
        "speaker-condition-calibrator-hadou",
        "speaker-condition-calibrator-stress",
        "speaker-condition-calibrator-jsut",
        "speaker-condition-calibrator-expanded-stress",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress") and not kind.endswith(
            "-expanded-stress"
        )
        jsut = kind.endswith("-jsut")
        expanded = kind.endswith("-expanded-stress")
        experiment_id = (
            "EXP-264"
            if expanded
            else "EXP-263"
            if jsut
            else "EXP-262"
            if stress
            else "EXP-261"
            if hadou
            else "EXP-260"
        )
        suffix = (
            "expanded-stress144"
            if expanded
            else "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "exp238-speaker-condition-delta-output-speaker-ema170",
            "display_name": (
                "EXP-259 / frozen EXP-238 + speaker-condition delta / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-speaker-condition-"
                f"calibrator-{suffix}/v1"
            ),
            "question": (
                "Does the frozen EXP-238 adapter plus a 192-value target-speaker "
                "condition delta improve target identity without losing content "
                "on the established broad surfaces?"
            ),
            "candidate_format": "frozen-exp238-plus-speaker-condition-calibrator",
        }
    if kind in {
        "output-speaker-ema-fresh48",
        "output-speaker-ema-hadou",
        "output-speaker-ema-stress",
        "output-speaker-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-256"
            if jsut
            else "EXP-255"
            if stress
            else "EXP-254"
            if hadou
            else "EXP-253"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "cross-corpus170-pseudoparallel-output-speaker-ema170",
            "display_name": (
                "EXP-252 / final-WAV speaker identity / pseudoparallel / "
                "real-adversarial / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-output-speaker-"
                f"ema-{suffix}/v1"
            ),
            "question": (
                "Does final-WAV speaker supervision improve target identity "
                "without losing content on the established broad surfaces?"
            ),
        }
    if kind in {
        "src4vc-pseudoparallel-ema-expanded-stress",
    }:
        return {
            "experiment_id": "EXP-249",
            "variant_id": "src4vc85-pseudoparallel-real-adv-ema170",
            "display_name": (
                "EXP-244 / SRC4VC85 source substitution / pseudoparallel / "
                "real-adversarial / EMA"
            ),
            "result_kind": (
                "liveconv-exp249-xvc-src4vc-pseudoparallel-expanded-stress144/v1"
            ),
            "question": (
                "Does the SRC4VC85 source substitution remain content-stable "
                "across the frozen symmetric length and condition matrix?"
            ),
        }
    if kind == "src4vc-pseudoparallel-ema-heldout30":
        return {
            "experiment_id": "EXP-250",
            "variant_id": "src4vc85-pseudoparallel-real-adv-ema170",
            "display_name": (
                "EXP-244 / SRC4VC85 source substitution / pseudoparallel / "
                "real-adversarial / EMA"
            ),
            "result_kind": (
                "liveconv-exp250-xvc-src4vc-pseudoparallel-heldout30/v1"
            ),
            "question": (
                "Does the SRC4VC85 source substitution retain content on thirty "
                "rows from fifteen disjoint SRC4VC speakers?"
            ),
        }
    if kind in {
        "src4vc-pseudoparallel-ema-fresh48",
        "src4vc-pseudoparallel-ema-hadou",
        "src4vc-pseudoparallel-ema-stress",
        "src4vc-pseudoparallel-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-248"
            if jsut
            else "EXP-247"
            if stress
            else "EXP-246"
            if hadou
            else "EXP-245"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "src4vc85-pseudoparallel-real-adv-ema170",
            "display_name": (
                "EXP-244 / SRC4VC85 source substitution / pseudoparallel / "
                "real-adversarial / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-src4vc-pseudoparallel-"
                f"ema-{suffix}/v1"
            ),
            "question": (
                "Does replacing only JSUT85 with 85 distinct SRC4VC smartphone "
                "speakers improve the fixed pseudoparallel method across the "
                "established evaluation surfaces?"
            ),
        }
    if kind in {
        "pseudoparallel-real-adv-ema-fresh48",
        "pseudoparallel-real-adv-ema-hadou",
        "pseudoparallel-real-adv-ema-stress",
        "pseudoparallel-real-adv-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-242"
            if jsut
            else "EXP-241"
            if stress
            else "EXP-240"
            if hadou
            else "EXP-239"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "cross-corpus170-pseudoparallel-real-adv-ema170",
            "display_name": (
                "EXP-238 / source-aligned control69 targets / real-adversarial / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-pseudoparallel-real-"
                f"adv-ema-{suffix}/v1"
            ),
            "question": (
                "Does source-aligned pseudo-parallel supervision remove the "
                "broad-content tradeoff of unrelated-target retraining?"
            ),
        }
    if kind in {
        "speaker7-voice-overlay-ema-fresh48",
        "speaker7-voice-overlay-ema-hadou",
        "speaker7-voice-overlay-ema-stress",
        "speaker7-voice-overlay-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-237"
            if jsut
            else "EXP-236"
            if stress
            else "EXP-235"
            if hadou
            else "EXP-234"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "control69-speaker7-real-voice-ema170",
            "display_name": "EXP-233 / control69 + speaker7 voice overlay / EMA",
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-speaker7-voice-overlay-"
                f"ema-{suffix}/v1"
            ),
            "question": (
                "Does voice-only speaker-path refinement preserve broad content "
                "while creating a useful audible alternative?"
            ),
            "candidate_format": "merged-control69-plus-adapter",
        }
    if kind in {
        "discrete-output-cycle-ema-fresh48",
        "discrete-output-cycle-ema-hadou",
        "discrete-output-cycle-ema-stress",
        "discrete-output-cycle-ema-jsut",
    }:
        hadou = kind.endswith("-hadou")
        stress = kind.endswith("-stress")
        jsut = kind.endswith("-jsut")
        experiment_id = (
            "EXP-227"
            if jsut
            else "EXP-226"
            if stress
            else "EXP-225"
            if hadou
            else "EXP-224"
        )
        suffix = (
            "jsut24"
            if jsut
            else "stress60"
            if stress
            else "hadou31"
            if hadou
            else "fresh48"
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": "cross-corpus170-discrete-output-cycle-ema170",
            "display_name": (
                "EXP-223 / cross-corpus discrete output-cycle / EMA"
            ),
            "result_kind": (
                f"liveconv-{experiment_id.lower()}-xvc-discrete-"
                f"output-cycle-ema-{suffix}/v1"
            ),
            "question": (
                "Does direct final-WAV classification into frozen source semantic "
                "tokens preserve categorical Japanese content across the fixed "
                "speaker and condition contract?"
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
        STRESS_KIND: STRESS_ROWS,
        EXPANDED_STRESS_KIND: EXPANDED_STRESS_ROWS,
        FRESH48_KIND: FRESH48_ROWS,
        JSUT_KIND: JSUT_ROWS,
        SRC4VC_HELDOUT_KIND: SRC4VC_HELDOUT_ROWS,
    }.get(kind, EXPECTED_ROWS)
    expected_speakers = {
        EXPANDED_KIND: EXPANDED_SPEAKERS,
        HADOU_KIND: HADOU_SPEAKERS,
        STRESS_KIND: STRESS_SPEAKERS,
        EXPANDED_STRESS_KIND: EXPANDED_STRESS_SPEAKERS,
        FRESH48_KIND: FRESH48_SPEAKERS,
        JSUT_KIND: JSUT_SPEAKERS,
        SRC4VC_HELDOUT_KIND: SRC4VC_HELDOUT_SPEAKERS,
    }.get(kind, EXPECTED_SPEAKERS)
    if (
        not isinstance(value, dict)
        or kind
        not in {
            KIND,
            EXPANDED_KIND,
            HADOU_KIND,
            STRESS_KIND,
            EXPANDED_STRESS_KIND,
            FRESH48_KIND,
            JSUT_KIND,
            SRC4VC_HELDOUT_KIND,
        }
        or not isinstance(source, dict)
        or source.get("license")
        != (
            "CC-BY-4.0"
            if kind == HADOU_KIND
            else (
                "JSUT-LICENCE.txt (category-specific CC BY/CC BY-SA)"
                if kind == JSUT_KIND
                else (
                    SRC4VC_SOURCE_LICENSE
                    if kind == SRC4VC_HELDOUT_KIND
                    else "CC0-1.0"
                )
            )
        )
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
        if kind == STRESS_KIND and (
            item.get("group") not in STRESS_GROUPS
            or not isinstance(item.get("base_id"), str)
            or not isinstance(item.get("stress_condition"), dict)
            or item.get("duration_seconds") != base.MODEL_SAMPLES / 16_000
        ):
            raise NewUtteranceError("stress evaluation row identity drifted")
        if kind == EXPANDED_STRESS_KIND and (
            item.get("length_bin") not in EXPANDED_STRESS_LENGTHS
            or item.get("group")
            not in {
                f"expanded-stress-{length}-{condition}"
                for length in EXPANDED_STRESS_LENGTHS
                for condition in EXPANDED_STRESS_CONDITIONS
            }
            or not isinstance(item.get("base_id"), str)
            or not isinstance(item.get("stress_condition"), dict)
            or item.get("duration_seconds") != base.MODEL_SAMPLES / 16_000
            or not isinstance(
                item.get("source_original_duration_seconds"), (int, float)
            )
        ):
            raise NewUtteranceError(
                "expanded stress evaluation row identity drifted"
            )
        if kind == EXPANDED_STRESS_KIND:
            condition = item["group"].removeprefix(
                f"expanded-stress-{item['length_bin']}-"
            )
            if (
                condition not in EXPANDED_STRESS_CONDITIONS
                or item["stress_condition"]
                != EXPANDED_STRESS_TRANSFORMS[condition]
            ):
                raise NewUtteranceError(
                    "expanded stress transform identity drifted"
                )
        if kind == FRESH48_KIND and (
            len(normalized) < 10
            or item.get("source_normalized_characters") != len(normalized)
            or item.get("window_policy") != "first-2.4s-right-pad-if-short"
            or item.get("group") != "commonvoice-fresh-disjoint"
            or item.get("down_votes") != 0
            or not isinstance(item.get("up_votes"), int)
            or int(item["up_votes"]) < 2
        ):
            raise NewUtteranceError("fresh48 evaluation row identity drifted")
        if kind == JSUT_KIND and (
            item.get("jsut_category") not in JSUT_CATEGORY_COUNTS
            or item.get("group")
            != f"jsut-heldout-{item.get('jsut_category')}"
            or item.get("selection_policy")
            != "transcript-order-equal-bin-center"
            or item.get("window_policy") != JSUT_WINDOW_POLICY
            or item.get("sample_rate") != 48_000
            or not isinstance(item.get("transcript_position"), int)
            or not isinstance(transcript, str)
            or len(normalized) < 2
        ):
            raise NewUtteranceError("JSUT evaluation row identity drifted")
        if kind == SRC4VC_HELDOUT_KIND and (
            item.get("group") != "src4vc-disjoint-heldout"
            or item.get("selection_policy")
            != (
                "first two RECITATION rows from each of fifteen frozen speakers "
                "disjoint from SRC4VC85 training"
            )
            or item.get("window_policy") != "first-2.4s-right-pad-if-short"
            or item.get("sample_rate") not in {24_000, 44_100, 48_000}
            or not isinstance(item.get("src4vc_speaker_id"), str)
            or not isinstance(transcript, str)
            or not normalized
        ):
            raise NewUtteranceError("SRC4VC heldout row identity drifted")
        identifiers.add(identifier)
        filenames.add(filename)
        clients.add(client)
    if len(clients) != expected_speakers:
        raise NewUtteranceError("evaluation speaker count drifted")
    if kind == EXPANDED_STRESS_KIND:
        expected_groups = {
            f"expanded-stress-{length}-{condition}": 4
            for length in EXPANDED_STRESS_LENGTHS
            for condition in EXPANDED_STRESS_CONDITIONS
        }
        bases = Counter(str(item["base_id"]) for item in items)
        if (
            Counter(str(item["group"]) for item in items) != expected_groups
            or len(bases) != EXPANDED_STRESS_SPEAKERS
            or set(bases.values()) != {len(EXPANDED_STRESS_CONDITIONS)}
            or any(
                len(
                    {
                        item["group"].removeprefix(
                            f"expanded-stress-{item['length_bin']}-"
                        )
                        for item in items
                        if item["base_id"] == base_id
                    }
                )
                != len(EXPANDED_STRESS_CONDITIONS)
                for base_id in bases
            )
        ):
            raise NewUtteranceError(
                "expanded stress matrix balance drifted"
            )
    if kind == SRC4VC_HELDOUT_KIND and Counter(
        str(item["src4vc_speaker_id"]) for item in items
    ) != {str(item["src4vc_speaker_id"]): 2 for item in items}:
        raise NewUtteranceError("SRC4VC heldout speaker balance drifted")
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
    if evaluation["kind"] == FRESH48_KIND:
        expanded = load_evaluation(arguments.expanded_evaluation)
        prior_clients = original_clients | donor_clients | {
            item["client_id_sha256"] for item in expanded["items"]
        }
        prior_files = original_files | donor_files | {
            item["filename"] for item in expanded["items"]
        }
        if clients & prior_clients or any(
            item["filename"] in prior_files for item in evaluation["items"]
        ):
            raise NewUtteranceError("fresh48 evaluation binding drifted")
    elif evaluation["kind"] in {KIND, STRESS_KIND}:
        if not clients < original_clients or clients & donor_clients:
            raise NewUtteranceError("evaluation speaker binding drifted")
    elif evaluation["kind"] == EXPANDED_STRESS_KIND:
        fresh48 = load_evaluation(arguments.fresh48_evaluation)
        fresh48_clients = {
            item["client_id_sha256"] for item in fresh48["items"]
        }
        if not clients < fresh48_clients or clients & (
            original_clients | donor_clients
        ):
            raise NewUtteranceError("expanded stress speaker binding drifted")
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
    for label, adapter in (("EXP-035 control", arguments.control_adapter),):
        if adapter.is_symlink() or not (
            adapter / "adapter_model.safetensors"
        ).is_file():
            raise NewUtteranceError(f"{label} adapter is unavailable")
    policy = candidate_policy(arguments.candidate_kind)
    if policy.get("candidate_format") == "merged-control69-converter":
        if (
            arguments.candidate_adapter is not None
            or arguments.candidate_converter is None
            or arguments.candidate_acoustic_encoder is not None
            or arguments.candidate_calibrator is not None
        ):
            raise NewUtteranceError("full converter candidate arguments drifted")
        metadata_path = arguments.candidate_converter / "converter.json"
        weights = arguments.candidate_converter / "converter-parameters.safetensors"
        if (
            arguments.candidate_converter.is_symlink()
            or metadata_path.is_symlink()
            or weights.is_symlink()
            or not metadata_path.is_file()
            or not weights.is_file()
        ):
            raise NewUtteranceError("full converter candidate is unavailable")
        metadata = post.load_json(metadata_path)
        if (
            metadata.get("kind") != post.CONVERTER_CHECKPOINT_KIND
            or metadata.get("parameter_count") != post.EXPECTED_CONVERTER_PARAMETERS
            or metadata.get("weights_sha256") != base.sha256_file(weights)
        ):
            raise NewUtteranceError("full converter candidate identity drifted")
    elif policy.get("candidate_format") == "merged-control69-acoustic-encoder":
        if (
            arguments.candidate_adapter is not None
            or arguments.candidate_converter is not None
            or arguments.candidate_acoustic_encoder is None
            or arguments.candidate_calibrator is not None
        ):
            raise NewUtteranceError("acoustic encoder candidate arguments drifted")
        metadata_path = (
            arguments.candidate_acoustic_encoder / "acoustic-encoder.json"
        )
        weights = (
            arguments.candidate_acoustic_encoder
            / "acoustic-encoder-parameters.safetensors"
        )
        if (
            arguments.candidate_acoustic_encoder.is_symlink()
            or metadata_path.is_symlink()
            or weights.is_symlink()
            or not metadata_path.is_file()
            or not weights.is_file()
        ):
            raise NewUtteranceError("acoustic encoder candidate is unavailable")
        metadata = post.load_json(metadata_path)
        if (
            metadata.get("kind") != post.ACOUSTIC_ENCODER_CHECKPOINT_KIND
            or metadata.get("parameter_count")
            != post.EXPECTED_ACOUSTIC_ENCODER_PARAMETERS
            or metadata.get("weights_sha256") != base.sha256_file(weights)
        ):
            raise NewUtteranceError("acoustic encoder candidate identity drifted")
    elif (
        policy.get("candidate_format")
        == "frozen-exp238-plus-speaker-condition-calibrator"
    ):
        if (
            arguments.candidate_adapter is None
            or arguments.candidate_converter is not None
            or arguments.candidate_acoustic_encoder is not None
            or arguments.candidate_calibrator is None
        ):
            raise NewUtteranceError(
                "speaker-condition calibrator candidate arguments drifted"
            )
        adapter_weights = arguments.candidate_adapter / "adapter_model.safetensors"
        metadata_path = arguments.candidate_calibrator / "calibrator.json"
        weights = arguments.candidate_calibrator / "calibrator.safetensors"
        if (
            arguments.candidate_adapter.is_symlink()
            or adapter_weights.is_symlink()
            or not adapter_weights.is_file()
            or base.sha256_file(adapter_weights) != post.EXP238_ADAPTER_SHA256
            or arguments.candidate_calibrator.is_symlink()
            or metadata_path.is_symlink()
            or weights.is_symlink()
            or not metadata_path.is_file()
            or not weights.is_file()
        ):
            raise NewUtteranceError(
                "speaker-condition calibrator candidate is unavailable"
            )
        metadata = post.load_json(metadata_path)
        if (
            metadata.get("kind") != post.SPEAKER_CONDITION_CALIBRATOR_KIND
            or metadata.get("parameter_count")
            != post.SPEAKER_CONDITION_DIMENSION
            or metadata.get("weights_sha256") != base.sha256_file(weights)
        ):
            raise NewUtteranceError(
                "speaker-condition calibrator candidate identity drifted"
            )
    elif (
        arguments.candidate_converter is not None
        or arguments.candidate_acoustic_encoder is not None
        or arguments.candidate_calibrator is not None
        or arguments.candidate_adapter is None
    ):
        raise NewUtteranceError("adapter candidate arguments drifted")
    elif arguments.candidate_adapter.is_symlink() or not (
        arguments.candidate_adapter / "adapter_model.safetensors"
    ).is_file():
        raise NewUtteranceError("method candidate adapter is unavailable")
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
        else (
            "JSUT 1.1"
            if str(item["group"]).startswith("jsut-heldout-")
            else "Common Voice 25.0"
        )
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


def _attach_candidate_representation(
    candidate: Any, policy: Mapping[str, str], *, torch: Any
) -> Any:
    """Attach candidate-only inference wrappers selected by the policy.

    The attachment API mutates the X-VC module in place (like the existing
    acoustic-code-dropout attachment) and may return its wrapper for receipt
    bookkeeping.  Rendering must continue to use the candidate model itself;
    base and control models are intentionally loaded and rendered unchanged.
    """

    if policy.get("candidate_attachment") == "continuous-acoustic-latent":
        post.attach_continuous_acoustic_latent(candidate, torch=torch)
    return candidate


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
    condition_path, condition_digest = by_id[role_mix.FRAME_CONDITION_REFERENCE_ID]
    condition_pair = base.MaterializedPair(
        role_mix.FRAME_CONDITION_REFERENCE_ID,
        condition_path,
        condition_path,
        condition_digest,
        condition_digest,
    )
    frame_condition_tensor = base._extract_pair_tensors(
        model,
        condition_pair,
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
    for label, adapter in (("cv12-control69", arguments.control_adapter),):
        adapted_base = method._load_xvc(arguments, XVC, device)
        adapted = PeftModel.from_pretrained(
            adapted_base, str(adapter), is_trainable=False
        )
        outputs[label] = (
            [
                role_mix.conditioned_inference(
                    adapted,
                    source,
                    target_tensor,
                    frame_condition_tensor,
                    seed=base.SEED + index,
                    torch=torch,
                    device=device,
                )
                .detach()
                .cpu()
                for index, source in enumerate(evaluation_tensors)
            ]
            if label == policy["variant_id"]
            and policy.get("conditioned_inference")
            else render(adapted)
        )
        del adapted, adapted_base
        torch.cuda.empty_cache()
    candidate_base = method._load_xvc(arguments, XVC, device)
    if policy.get("candidate_format") == "merged-control69-converter":
        candidate_control = PeftModel.from_pretrained(
            candidate_base, str(arguments.control_adapter), is_trainable=False
        )
        candidate = candidate_control.merge_and_unload(safe_merge=True)
        post.load_converter_checkpoint(
            candidate,
            arguments.candidate_converter,
            torch=torch,
            device=device,
        )
    elif policy.get("candidate_format") == "merged-control69-acoustic-encoder":
        candidate_control = PeftModel.from_pretrained(
            candidate_base, str(arguments.control_adapter), is_trainable=False
        )
        candidate = candidate_control.merge_and_unload(safe_merge=True)
        post.load_acoustic_encoder_checkpoint(
            candidate,
            arguments.candidate_acoustic_encoder,
            torch=torch,
            device=device,
        )
    elif policy.get("candidate_format") == "merged-control69-plus-adapter":
        candidate_control = PeftModel.from_pretrained(
            candidate_base, str(arguments.control_adapter), is_trainable=False
        )
        candidate_merged = candidate_control.merge_and_unload(safe_merge=True)
        candidate = PeftModel.from_pretrained(
            candidate_merged,
            str(arguments.candidate_adapter),
            is_trainable=False,
        )
    elif (
        policy.get("candidate_format")
        == "frozen-exp238-plus-speaker-condition-calibrator"
    ):
        candidate = PeftModel.from_pretrained(
            candidate_base,
            str(arguments.candidate_adapter),
            is_trainable=False,
        )
        post.load_speaker_condition_calibrator(
            candidate,
            arguments.candidate_calibrator,
            torch=torch,
            device=device,
        )
    else:
        candidate = PeftModel.from_pretrained(
            candidate_base, str(arguments.candidate_adapter), is_trainable=False
        )
    candidate = _attach_candidate_representation(candidate, policy, torch=torch)
    outputs[policy["variant_id"]] = (
        [
            role_mix.conditioned_inference(
                candidate,
                source,
                target_tensor,
                frame_condition_tensor,
                seed=base.SEED + index,
                torch=torch,
                device=device,
            )
            .detach()
            .cpu()
            for index, source in enumerate(evaluation_tensors)
        ]
        if policy.get("conditioned_inference")
        else render(candidate)
    )
    del candidate, candidate_base
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
            "wave-adversarial",
            "wave-adversarial-hadou",
            "wave-adversarial-expanded",
            "wave-adversarial-fresh48",
            "output2",
            "output2-hadou",
            "real-reconstruction20",
            "real-reconstruction20-hadou",
            "decoder-final",
            "decoder-final-hadou",
            "source-semantic",
            "source-semantic-hadou",
            "source-semantic-expanded",
            "source-semantic-stress",
            "denoise-semantic",
            "denoise-semantic-hadou",
            "denoise-semantic-expanded",
            "denoise-semantic-stress",
            "cross-target-condition",
            "cross-target-condition-hadou",
            "cross-target-condition-expanded",
            "cross-target-condition-stress",
            "semantic-token-hold",
            "semantic-token-hold-hadou",
            "semantic-token-hold-expanded",
            "semantic-token-hold-stress",
            "real-teacher-semantic20",
            "real-teacher-semantic20-hadou",
            "real-teacher-semantic20-expanded",
            "real-teacher-semantic20-stress",
            "real-teacher-semantic20-fresh48",
            "real-teacher-breadth48-fresh48",
            "real-teacher-output48-fresh48",
            "real-teacher-output48-ffn22-fresh48",
            "real-teacher-output48-dora-fresh48",
            "real-teacher-output48-temporal-fresh48",
            "real-teacher-output-multidomain48-fresh48",
            "real-teacher-output-multidomain48-hadou",
            "real-teacher-output-multidomain48-stress",
            "real-teacher-output-phonetic48-fresh48",
            "real-teacher-output-phonetic48-hadou",
            "real-teacher-output-window48-fresh48",
            "real-teacher-output-window48-hadou",
            "real-teacher-output-window201-fresh48",
            "real-teacher-output-window201-hadou",
            "clean-post-rehearsal-fresh48",
            "clean-post-rehearsal-hadou",
            "clean-post-rehearsal-jsut",
            "hard-negative-curriculum-fresh48",
            "hard-negative-curriculum-hadou",
            "hard-negative-curriculum-jsut",
            "selective-retention-fresh48",
            "selective-retention-hadou",
            "selective-retention-jsut",
            "full-converter-retention-fresh48",
            "full-converter-retention-hadou",
            "full-converter-retention-jsut",
            "real-reference-adversarial-fresh48",
            "real-reference-adversarial-hadou",
            "real-reference-adversarial-stress",
            "real-reference-adversarial-jsut",
            "real-adversarial-ema-fresh48",
            "real-adversarial-ema-hadou",
            "real-adversarial-ema-stress",
            "real-adversarial-ema-jsut",
            "real-adversarial-ema-expanded",
            "paired-pcgrad-fresh48",
            "paired-pcgrad-hadou",
            "paired-pcgrad-stress",
            "paired-pcgrad-jsut",
            "jsut-retention-ema-fresh48",
            "jsut-retention-ema-hadou",
            "jsut-retention-ema-stress",
            "jsut-retention-ema-jsut",
            "parameter-anchor-ema-fresh48",
            "parameter-anchor-ema-hadou",
            "parameter-anchor-ema-stress",
            "parameter-anchor-ema-jsut",
            "commonvoice48-retention-ema-fresh48",
            "commonvoice48-retention-ema-hadou",
            "commonvoice48-retention-ema-stress",
            "commonvoice48-retention-ema-jsut",
            "conditioned-retention-ema-fresh48",
            "conditioned-retention-ema-stress",
            "source36-retention-ema-stress",
            "source-envelope-retention-ema-stress",
            "acoustic-encoder-ema-fresh48",
            "acoustic-encoder-ema-hadou",
            "acoustic-encoder-ema-stress",
            "acoustic-encoder-ema-jsut",
            "unpaired-human-ema-fresh48",
            "unpaired-human-ema-hadou",
            "unpaired-human-ema-stress",
            "unpaired-human-ema-jsut",
            "unpaired-output-cycle-ema-fresh48",
            "unpaired-output-cycle-ema-hadou",
            "unpaired-output-cycle-ema-stress",
            "unpaired-output-cycle-ema-jsut",
            "cross-corpus-output-cycle-ema-fresh48",
            "cross-corpus-output-cycle-ema-hadou",
            "cross-corpus-output-cycle-ema-stress",
            "cross-corpus-output-cycle-ema-jsut",
            "contrastive-output-cycle-ema-fresh48",
            "contrastive-output-cycle-ema-hadou",
            "contrastive-output-cycle-ema-stress",
            "contrastive-output-cycle-ema-jsut",
            "discrete-output-cycle-ema-fresh48",
            "discrete-output-cycle-ema-hadou",
            "discrete-output-cycle-ema-stress",
            "discrete-output-cycle-ema-jsut",
            "content-voice-pcgrad-ema-fresh48",
            "content-voice-pcgrad-ema-hadou",
            "content-voice-pcgrad-ema-stress",
            "content-voice-pcgrad-ema-jsut",
            "speaker7-voice-overlay-ema-fresh48",
            "speaker7-voice-overlay-ema-hadou",
            "speaker7-voice-overlay-ema-stress",
            "speaker7-voice-overlay-ema-jsut",
            "pseudoparallel-real-adv-ema-fresh48",
            "pseudoparallel-real-adv-ema-hadou",
            "pseudoparallel-real-adv-ema-stress",
            "pseudoparallel-real-adv-ema-jsut",
            "pseudoparallel-real-adv-ema-expanded-stress",
            "output-speaker-ema-fresh48",
            "output-speaker-ema-hadou",
            "output-speaker-ema-stress",
            "output-speaker-ema-jsut",
            "output-speaker-ema-expanded-stress",
            "real-speaker-condition-ema-fresh48",
            "real-speaker-condition-ema-hadou",
            "real-speaker-condition-ema-stress",
            "real-speaker-condition-ema-jsut",
            "real-speaker-condition-ema-expanded-stress",
            "fresh-lora-pseudoparallel-ema-fresh48",
            "fresh-lora-pseudoparallel-ema-hadou",
            "fresh-lora-pseudoparallel-ema-stress",
            "fresh-lora-pseudoparallel-ema-jsut",
            "fresh-lora-pseudoparallel-ema-expanded-stress",
            "acoustic-dropout-pseudoparallel-ema-fresh48",
            "acoustic-dropout-pseudoparallel-ema-hadou",
            "acoustic-dropout-pseudoparallel-ema-stress",
            "acoustic-dropout-pseudoparallel-ema-jsut",
            "acoustic-dropout-pseudoparallel-ema-expanded-stress",
            "continuous-acoustic-pseudoparallel-ema-fresh48",
            "continuous-acoustic-pseudoparallel-ema-hadou",
            "continuous-acoustic-pseudoparallel-ema-stress",
            "continuous-acoustic-pseudoparallel-ema-jsut",
            "continuous-acoustic-pseudoparallel-ema-expanded-stress",
            "acoustic-temporal-jitter-pseudoparallel-ema-fresh48",
            "acoustic-temporal-jitter-pseudoparallel-ema-hadou",
            "acoustic-temporal-jitter-pseudoparallel-ema-stress",
            "acoustic-temporal-jitter-pseudoparallel-ema-jsut",
            "acoustic-temporal-jitter-pseudoparallel-ema-expanded-stress",
            "robust-semantic-pseudoparallel-ema-fresh48",
            "robust-semantic-pseudoparallel-ema-hadou",
            "robust-semantic-pseudoparallel-ema-stress",
            "robust-semantic-pseudoparallel-ema-jsut",
            "robust-semantic-pseudoparallel-ema-expanded144",
            "cv32-breadth-pseudoparallel-ema-external7",
            "cv32-breadth-pseudoparallel-ema-fresh48",
            "cv32-breadth-pseudoparallel-ema-hadou",
            "cv32-breadth-pseudoparallel-ema-stress",
            "cv32-breadth-pseudoparallel-ema-jsut",
            "cv32-breadth-pseudoparallel-ema-expanded144",
            "repeat-control-pseudoparallel-ema-external7",
            "repeat-control-pseudoparallel-ema-fresh48",
            "repeat-control-pseudoparallel-ema-hadou",
            "repeat-control-pseudoparallel-ema-stress",
            "repeat-control-pseudoparallel-ema-jsut",
            "repeat-control-pseudoparallel-ema-expanded144",
            "speaker-condition-calibrator-fresh48",
            "speaker-condition-calibrator-hadou",
            "speaker-condition-calibrator-stress",
            "speaker-condition-calibrator-jsut",
            "speaker-condition-calibrator-expanded-stress",
            "src4vc-pseudoparallel-ema-fresh48",
            "src4vc-pseudoparallel-ema-hadou",
            "src4vc-pseudoparallel-ema-stress",
            "src4vc-pseudoparallel-ema-jsut",
            "src4vc-pseudoparallel-ema-expanded-stress",
            "src4vc-pseudoparallel-ema-heldout30",
        ),
        default="speaker7",
    )
    parser.add_argument("--evaluation-set", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--control-adapter", type=Path, required=True)
    parser.add_argument("--candidate-adapter", type=Path)
    parser.add_argument("--candidate-converter", type=Path)
    parser.add_argument("--candidate-acoustic-encoder", type=Path)
    parser.add_argument("--candidate-calibrator", type=Path)
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
        "--expanded-evaluation",
        type=Path,
        default=(
            REPO_ROOT
            / "experiments"
            / "EXP-055-xvc-target-text-breadth"
            / "expanded-evaluation.json"
        ),
    )
    parser.add_argument(
        "--fresh48-evaluation",
        type=Path,
        default=(
            REPO_ROOT
            / "artifacts/xvc-source-diversity/exp112-fresh48-inputs-v1/evaluation.json"
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
