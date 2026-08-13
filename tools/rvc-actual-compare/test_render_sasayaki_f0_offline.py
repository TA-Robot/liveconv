"""CPU-only tests for the Sasayaki clean-bright F0 probe."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RUNNER = Path(__file__).parent / "render_sasayaki_f0_offline.py"
SPEC = importlib.util.spec_from_file_location("rvc_sasayaki_f0", RUNNER)
assert SPEC and SPEC.loader
run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run
SPEC.loader.exec_module(run)


def test_cli_changes_only_f0_method() -> None:
    rmvpe = run.cli_argv("rmvpe", Path("/source"), Path("/output"))
    pm = run.cli_argv("pm", Path("/source"), Path("/output"))
    assert len(rmvpe) == len(pm)
    assert [(left, right) for left, right in zip(rmvpe, pm) if left != right] == [
        ("rmvpe", "pm")
    ]
    assert rmvpe[rmvpe.index("--input") + 1] == "/source"
    assert rmvpe[rmvpe.index("--output") + 1] == "/output"


def test_cli_rejects_another_f0_method() -> None:
    with pytest.raises(run.F0ProbeError, match="F0 method"):
        run.cli_argv("harvest", Path("/source"), Path("/output"))


def test_index_is_unselected_offline_diagnostic() -> None:
    index = run.build_index(
        "EMOTION100_002",
        "本文",
        "a" * 64,
        {"rmvpe": ("rmvpe.wav", "b" * 64), "pm": ("pm.wav", "c" * 64)},
    )
    assert index["comparison_scope"]["single_changed_variable"] == "f0_method"
    methods = [
        item["effective_parameters"]["f0_method"] for item in index["variants"]
    ]
    assert methods == [
        "rmvpe",
        "pm",
    ]
    assert all(item["operator_judgment"] == "unreviewed" for item in index["variants"])
    assert all(
        item["route_status"] == "offline_diagnostic" for item in index["variants"]
    )
