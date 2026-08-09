from __future__ import annotations

import math

import pytest

from liveconv_speaker import ComparisonPolicy, compare_embeddings, sha256_model_tree
from liveconv_speaker.evidence import SpeakerEvidenceError


def test_compares_source_target_and_output_independently():
    policy = ComparisonPolicy("pilot", "proposed", 0.8, 0.1, 0.2)

    evidence = compare_embeddings((1, 0), (0, 1), (0.1, 0.9), policy)

    assert evidence.status == "pass"
    assert evidence.target_to_output > 0.99
    assert evidence.target_similarity_gain > 0.99
    assert evidence.source_to_output < 0.12
    assert evidence.target_advantage > 0.8
    assert len(evidence.evidence) == 3


def test_failed_advantage_is_not_hidden_by_high_target_similarity():
    policy = ComparisonPolicy("pilot", "approved", 0.7, 0.1, 0.1)

    evidence = compare_embeddings((1, 0), (1, 0), (1, 0), policy)

    assert evidence.target_to_output == pytest.approx(1.0)
    assert evidence.target_similarity_gain == pytest.approx(0.0)
    assert evidence.target_advantage == pytest.approx(0.0)
    assert evidence.status == "fail"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 1.1, -1.1])
def test_rejects_invalid_policy_thresholds(value):
    with pytest.raises(SpeakerEvidenceError):
        ComparisonPolicy("pilot", "proposed", value, 0.0, 0.0)


def test_model_tree_digest_is_content_addressed_and_rejects_symlinks(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    (model / "weights.bin").write_bytes(b"first")
    first = sha256_model_tree(model)
    (model / "weights.bin").write_bytes(b"second")
    assert sha256_model_tree(model) != first

    (model / "link.bin").symlink_to(model / "weights.bin")
    with pytest.raises(SpeakerEvidenceError, match="symlinks"):
        sha256_model_tree(model)
