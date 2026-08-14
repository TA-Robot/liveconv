from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import render_cross_corpus_pseudoparallel_targets as render  # noqa: E402


def source_manifest() -> dict[str, object]:
    items = []
    position = 0
    for domain, count in render.EXPECTED_COMPOSITION.items():
        for domain_index in range(count):
            items.append(
                {
                    "id": f"{position:03d}-{domain}-{domain_index}",
                    "teacher_id": f"{domain}-{domain_index}",
                    "domain": domain,
                    "source_manifest_id": f"fixture:{position}",
                    "source_text": f"評価文{position}",
                    "source_root": "diverse-work",
                    "source_file": f"sources/{position:03d}.wav",
                    "source_sha256": f"{position + 1:064x}",
                    "source_relative_distance": 0.0,
                    "target_id": f"target-{position % 74}",
                    "target_text": f"無関係文{position}",
                    "target_root": "diverse-work",
                    "target_file": f"targets/{position:03d}.wav",
                    "target_sha256": f"{position + 1000:064x}",
                    "learning_target": ("source-content-plus-unpaired-target-identity"),
                }
            )
            position += 1
    return {
        "kind": render.SOURCE_KIND,
        "composition": render.EXPECTED_COMPOSITION,
        "items": items,
    }


def src4vc_source_manifest() -> dict[str, object]:
    manifest = source_manifest()
    items = manifest["items"]
    assert isinstance(items, list)
    replacements = iter(
        (
            "src4vc-smartphone-unpaired",
            f"src4vc-smartphone-unpaired-{index:03d}",
        )
        for index in range(85)
    )
    for item in items:
        if item["domain"] == "jsut-unpaired":
            item["domain"], item["teacher_id"] = next(replacements)
    manifest["kind"] = render.SRC4VC_SOURCE_KIND
    manifest["composition"] = render.SRC4VC_EXPECTED_COMPOSITION
    return manifest


def output_rows(pool: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "position": row["position"],
            "teacher_id": row["teacher_id"],
            "target_id": row["target_id"],
            "target_file": f"control-outputs/{row['position']:03d}.wav",
            "output_sha256": f"{row['position'] + 2000:064x}",
        }
        for row in pool["items"]
    ]


def test_curriculum_replaces_only_target_audio_with_same_content() -> None:
    pool = render.source_pool(source_manifest())

    manifest = render.curriculum(pool, output_rows(pool))

    assert manifest["kind"] == render.OUTPUT_KIND
    assert len(manifest["items"]) == render.EXPECTED_ROWS
    assert manifest["learning_target_counts"] == {
        render.LEARNING_TARGET: render.EXPECTED_ROWS
    }
    first = manifest["items"][0]
    assert first["source_root"] == "source-work"
    assert first["target_root"] == "diverse-work"
    assert first["target_text"] == first["source_text"]
    assert first["real_target_text"] != first["source_text"]


def test_curriculum_rejects_output_target_assignment_drift() -> None:
    pool = render.source_pool(source_manifest())
    outputs = output_rows(pool)
    outputs[0]["target_id"] = "wrong-target"

    with pytest.raises(render.PseudoparallelTargetError, match="identity"):
        render.curriculum(pool, outputs)


def test_src4vc_policy_changes_only_admitted_source_composition() -> None:
    pool = render.source_pool(src4vc_source_manifest())

    manifest = render.curriculum(pool, output_rows(pool))

    assert manifest["kind"] == render.SRC4VC_OUTPUT_KIND
    assert manifest["composition"] == render.SRC4VC_EXPECTED_COMPOSITION
    assert len(manifest["items"]) == render.EXPECTED_ROWS


def test_source_pool_rejects_unrelated_contract_drift() -> None:
    manifest = source_manifest()
    manifest["items"][0]["source_root"] = "source-work"

    with pytest.raises(render.PseudoparallelTargetError, match="source row"):
        render.source_pool(manifest)
