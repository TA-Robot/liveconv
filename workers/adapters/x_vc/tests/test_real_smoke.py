from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from workers.adapters.x_vc.backend import RUNTIME_LOCK_PATH, WORKER_PACKAGE_NAME
from workers.adapters.x_vc.real_smoke import locked_packages

RUN_REAL = os.environ.get("LIVECONV_RUN_XVC_REAL") == "1"
_REQUIREMENT = re.compile(r"^[A-Za-z0-9_.-]+==[^ ;\\]+(?: \\)?$")


def test_runtime_lock_is_complete_and_hash_locked() -> None:
    lines = RUNTIME_LOCK_PATH.read_text(encoding="utf-8").splitlines()
    packages = locked_packages(RUNTIME_LOCK_PATH)

    assert len(packages) == 123
    assert WORKER_PACKAGE_NAME not in packages
    assert packages["torch"] == "2.8.0+cu128"
    assert packages["torchaudio"] == "2.8.0+cu128"
    for index, line in enumerate(lines):
        if not _REQUIREMENT.match(line):
            continue
        stanza = [line]
        cursor = index + 1
        while stanza[-1].endswith("\\"):
            stanza.append(lines[cursor])
            cursor += 1
        assert any("--hash=sha256:" in item for item in stanza), line


@pytest.mark.skipif(not RUN_REAL, reason="real X-VC runtime is opt-in")
def test_installed_wheel_runs_real_supervisor_smoke_from_tmp() -> None:
    runtime_python = Path(os.environ["LIVECONV_XVC_INTERPRETER_PATH"]).absolute()
    report_path = Path(os.environ["LIVECONV_XVC_SMOKE_REPORT_PATH"]).absolute()
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in {"PYTHONPATH", "PYTHONHOME"}
    }

    completed = subprocess.run(
        [
            str(runtime_python),
            "-I",
            "-m",
            "workers.adapters.x_vc.real_smoke",
        ],
        check=False,
        capture_output=True,
        cwd="/tmp",
        env=environment,
        text=True,
        timeout=480,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "technical-smoke-pass"
    assert report["quality_status"] == "fail-nonselectable"
    assert report["runtime"]["inventory_matches_lock_plus_worker_wheel"] is True
    assert report["runtime"]["worker_cwd"] == "/tmp"
    assert report["runtime"]["worker_bytecode_disabled"] is True
    assert report["runtime"]["worker_pythonpath_unset"] is True
    assert report["network_isolation"] == {
        "af_inet6_denied": True,
        "af_inet_denied": True,
        "af_unix_allowed": True,
        "installed_before_model_imports": True,
        "mechanism": "seccomp-deny-socket-domain-ne-AF_UNIX",
    }
    assert (
        report["authorization"]["record_sha256"]
        == report["identity"]["target_authorization_sha256"]
    )
