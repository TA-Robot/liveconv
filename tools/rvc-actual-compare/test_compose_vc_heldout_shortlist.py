"""CPU-only tests for the two-family heldout shortlist composer."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

RUNNER = Path(__file__).parent / "compose_vc_heldout_shortlist.py"
SPEC = importlib.util.spec_from_file_location("vc_heldout_shortlist", RUNNER)
assert SPEC and SPEC.loader
run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run
SPEC.loader.exec_module(run)


def test_shortlist_is_exactly_three_rows_by_two_live_route_arms() -> None:
    assert [row["source_id"] for row in run.ROWS] == [
        "EMOTION100_002",
        "EMOTION100_004",
        "EMOTION100_017",
    ]
    assert [arm["family_id"] for arm in run.ARMS] == ["rvc-v2", "x-vc"]
    assert all(len(arm["hashes"]) == 3 for arm in run.ARMS)


def test_checked_file_rejects_identity_drift(tmp_path: Path) -> None:
    artifact = tmp_path / "candidate.wav"
    artifact.write_bytes(b"audio")
    expected = hashlib.sha256(b"audio").hexdigest()
    assert run.checked_file(artifact, expected, "candidate") == artifact

    try:
        run.checked_file(artifact, "0" * 64, "candidate")
    except run.ShortlistError as error:
        assert "identity drifted" in str(error)
    else:
        raise AssertionError("candidate identity drift was accepted")
