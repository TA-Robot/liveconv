from __future__ import annotations

import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import run_post_rehearsal as post  # noqa: E402
import run_role_mix as role_mix  # noqa: E402


def test_listening_policy_satisfies_shared_index_contract() -> None:
    policy = post.listening_policy()
    item = {
        "age": "",
        "gender": "",
        "text": "評価文",
    }
    hashes = {
        "base": "a" * 64,
        "cv12-standard": "b" * 64,
        post.CANDIDATE_ID: "c" * 64,
    }

    index = role_mix.listening_index(item, hashes=hashes, policy=policy)

    assert index["run_kind"] == policy["run_kind"]
    assert index["variants"][2]["profile_id"] == (
        f"xvc.exp141.{post.CANDIDATE_ID}.listen-now"
    )
