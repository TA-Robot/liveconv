from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
MODULE_PATH = TOOL_ROOT / "compare_actual_scopes.py"
SPEC = importlib.util.spec_from_file_location("xvc_compare_actual_scopes", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
COMPARE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = COMPARE
SPEC.loader.exec_module(COMPARE)


def test_index_exposes_exact_scope_comparison() -> None:
    hashes = {
        "base": "a" * 64,
        "expanded79-e12": "b" * 64,
        "control69-e12": "c" * 64,
    }
    document = COMPARE.listening_index(hashes)
    assert [item["variant_id"] for item in document["variants"]] == [
        "xvc-base-offline",
        "xvc-expanded79-e12-offline",
        "xvc-control69-e12-offline",
    ]
    assert [item["output_sha256"] for item in document["variants"]] == list(
        hashes.values()
    )


def test_runner_is_offline_atomic_and_unselected() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "offline._offline" in source
    assert "run_streaming" not in source
    assert "staging.rename(arguments.listener_dir)" in source
    assert '"product_selected": False' in source
