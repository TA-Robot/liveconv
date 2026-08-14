from __future__ import annotations

import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
TEST_ROOT = Path(__file__).resolve().parent
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

import prepare_commonvoice_retention_curriculum as common  # noqa: E402
import prepare_conditioned_retention_curriculum as conditioned  # noqa: E402
from test_prepare_commonvoice_retention_curriculum import inputs  # noqa: E402


def test_conditioned_curriculum_preserves_all_five_easy_conditions() -> None:
    selective, sources, targets, screen = inputs()
    kinds = ["clean", "noise", "tempo", "pitch", "leading-silence"]
    sources["kind"] = conditioned.SOURCE_KIND
    targets["kind"] = conditioned.TARGET_KIND
    for index, (source, target) in enumerate(zip(sources["items"], targets["rows"], strict=True)):
        condition = {"kind": kinds[index % 5]}
        source["condition"] = condition
        source["condition_index"] = index
        target["condition"] = condition

    manifest = conditioned.build_curriculum(selective, sources, targets, screen)

    assert manifest["kind"] == conditioned.OUTPUT_KIND
    assert manifest["composition"] == common.EXPECTED_COMPOSITION
    assert manifest["curriculum"]["easy_condition_counts"] == {
        "clean": 17,
        "noise": 17,
        "tempo": 17,
        "pitch": 17,
        "leading-silence": 17,
    }
