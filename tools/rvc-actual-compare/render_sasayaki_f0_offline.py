#!/usr/bin/env python3
"""Compare RMVPE and PM F0 extraction for the bounded Sasayaki candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_ROOT = ROOT / "artifacts/rvc-v2/upstream"
RUNTIME_PYTHON = ROOT / "artifacts/rvc-v2/runtime/bin/python"
CHECKPOINT = Path(
    "/tmp/liveconv-ms3-intake/amitaro-rvc/extracted/sasayaki/"
    "Amitaro_sasayaki_V.1.0_250e_6250s.pth"
)
INDEX = Path(
    "/tmp/liveconv-ms3-intake/amitaro-rvc/extracted/sasayaki/"
    "Amitaro_sasayaki_V.1.0.index"
)
EXPECTED_UPSTREAM_REVISION = "81eed5e8f68b6bed1789f682fe78cdd324495afc"
EXPECTED_CHECKPOINT_SHA256 = (
    "fd3f156a578fbf5547edb3a05cc144136c749420f1c1ff49a953e2b4d33fe8e7"
)
EXPECTED_INDEX_SHA256 = (
    "d8a45ecb40e3d2c2e548e3748d21d41ead4e60ddc8ef55fe0a112a0dd2a4ea1a"
)
SOURCES = (
    (
        "EMOTION100_002",
        "シュヴァイツァーは見習うべき人間です。",
        ROOT
        / "artifacts/ms3/listening/exp026-human87-horizon-v1/01-EMOTION100_002"
        / "00-source-reference.wav",
        "8f27065d5b2f66baeafea5e96653f87c57ce866ea42f4e19df82886078c5e536",
    ),
    (
        "EMOTION100_004",
        "スティーヴはジェーンから手紙をもらった。",
        ROOT
        / "artifacts/ms3/listening/exp026-human87-horizon-v1/02-EMOTION100_004"
        / "00-source-reference.wav",
        "0a3828c54f83fb28f885d0d452beab029a38030f6429a32e6720e5bb4f4c9ab5",
    ),
    (
        "EMOTION100_017",
        "あっベルが鳴ってる。",
        ROOT
        / "artifacts/ms3/listening/exp026-human87-horizon-v1/03-EMOTION100_017"
        / "00-source-reference.wav",
        "9fad53ec17379745bc7e56d9306a1ffa1fda1ee0dfdf077826792e6e8199d455",
    ),
)


class F0ProbeError(RuntimeError):
    """The bounded F0 comparison cannot continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checked_file(path: Path, expected: str, label: str) -> Path:
    if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
        raise F0ProbeError(f"{label} identity drifted")
    return path


def cli_argv(method: str, source_dir: Path, output_dir: Path) -> list[str]:
    if method not in {"rmvpe", "pm"}:
        raise F0ProbeError("F0 method must be rmvpe or pm")
    return [
        "rvc-cli",
        "--model",
        str(CHECKPOINT),
        "--input",
        str(source_dir.resolve()),
        "--output",
        str(output_dir.resolve()),
        "--speaker-id",
        "0",
        "--pitch",
        "4",
        "--f0-method",
        method,
        "--index",
        str(INDEX),
        "--index-rate",
        "0.3",
        "--resample-sr",
        "48000",
        "--rms-mix-rate",
        "0.5",
        "--protect",
        "0",
        "--format",
        "wav",
        "--overwrite",
    ]


def run_upstream(method: str, source_dir: Path, output_dir: Path) -> None:
    argv = cli_argv(method, source_dir, output_dir)
    cli = UPSTREAM_ROOT / "infer/cli.py"
    code = (
        "import runpy, sys; "
        f"sys.path.insert(0, {str(UPSTREAM_ROOT)!r}); "
        f"sys.argv = {argv!r}; "
        f"runpy.run_path({str(cli)!r}, run_name='__main__')"
    )
    subprocess.run([str(RUNTIME_PYTHON), "-I", "-c", code], check=True)


def validate(arguments: argparse.Namespace) -> None:
    _checked_file(CHECKPOINT, EXPECTED_CHECKPOINT_SHA256, "Sasayaki checkpoint")
    _checked_file(INDEX, EXPECTED_INDEX_SHA256, "Sasayaki index")
    if not RUNTIME_PYTHON.exists() or not (UPSTREAM_ROOT / "infer/cli.py").is_file():
        raise F0ProbeError("retained RVC runtime or upstream CLI is unavailable")
    head = subprocess.run(
        ["git", "-C", str(UPSTREAM_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(UPSTREAM_ROOT), "diff", "--quiet", "--no-ext-diff"],
        check=False,
    ).returncode
    if head != EXPECTED_UPSTREAM_REVISION or dirty:
        raise F0ProbeError("retained RVC source revision drifted")
    for source_id, _text, path, expected in SOURCES:
        _checked_file(path, expected, source_id)
    if arguments.work_dir.exists() or arguments.listener_dir.exists():
        raise F0ProbeError("work and listener outputs must be new")


def build_index(
    source_id: str,
    display_text: str,
    source_sha256: str,
    outputs: dict[str, tuple[str, str]],
) -> dict[str, Any]:
    variants = []
    for order, method in enumerate(("rmvpe", "pm"), start=1):
        output_file, output_sha256 = outputs[method]
        variants.append(
            {
                "variant_id": f"rvc-sasayaki-clean-bright-{method}",
                "profile_id": (
                    f"offline.rvc-v2.amitaro-sasayaki-clean-bright-{method}.v1"
                ),
                "family_id": "rvc-v2",
                "display_name": f"Sasayaki clean-bright / F0 {method.upper()}",
                "display_order": order,
                "status": "passed",
                "operator_judgment": "unreviewed",
                "quality_status": "not_assessed",
                "route_status": "offline_diagnostic",
                "output_file": output_file,
                "output_sha256": "sha256:" + output_sha256,
                "effective_parameters": {
                    "route": "upstream-infer-cli-full-utterance",
                    "pitch_shift": 4,
                    "f0_method": method,
                    "index_rate": 0.3,
                    "rms_mix_rate": 0.5,
                    "protect": 0.0,
                },
            }
        )
    return {
        "schema_version": 1,
        "title": f"RVC Sasayaki F0 / {source_id}",
        "run_kind": "EXP-020 Sasayaki clean-bright RMVPE versus PM",
        "status": "completed-listen-now-unselected",
        "source_file": f"Hadou public heldout / {source_id}",
        "source_text": display_text,
        "source_id": source_id,
        "source_output_file": "00-source.wav",
        "source_sha256": "sha256:" + source_sha256,
        "comparison_scope": {
            "single_changed_variable": "f0_method",
            "offline_diagnostic_only": True,
            "human_hearing_pending": True,
            "machine_selection_allowed": False,
        },
        "variants": variants,
    }


def execute(arguments: argparse.Namespace) -> dict[str, Any]:
    arguments.work_dir.mkdir(parents=True)
    source_dir = arguments.work_dir / "sources"
    source_dir.mkdir()
    outputs_by_method: dict[str, Path] = {}
    for source_id, _text, path, _expected in SOURCES:
        shutil.copyfile(path, source_dir / f"{source_id}.wav")
    for method in ("rmvpe", "pm"):
        output_dir = arguments.work_dir / method
        run_upstream(method, source_dir, output_dir)
        outputs_by_method[method] = output_dir

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    hashes: dict[str, dict[str, str]] = {}
    for order, (source_id, text, path, source_sha256) in enumerate(SOURCES, start=1):
        row_dir = staging / f"{order:02d}-{source_id}"
        row_dir.mkdir()
        shutil.copyfile(path, row_dir / "00-source.wav")
        row_outputs: dict[str, tuple[str, str]] = {}
        hashes[source_id] = {}
        for arm_order, method in enumerate(("rmvpe", "pm"), start=1):
            produced = outputs_by_method[method] / f"{source_id}.wav"
            if not produced.is_file() or produced.stat().st_size <= 44:
                raise F0ProbeError(f"{method} produced no output for {source_id}")
            output_file = f"{arm_order}0-clean-bright-{method}.wav"
            copied = row_dir / output_file
            shutil.copyfile(produced, copied)
            digest = sha256_file(copied)
            hashes[source_id][method] = digest
            row_outputs[method] = (output_file, digest)
        (row_dir / "index.json").write_text(
            json.dumps(
                build_index(source_id, text, source_sha256, row_outputs),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    result = {
        "schema_version": 1,
        "kind": "liveconv-exp020-rvc-sasayaki-f0-offline-result",
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "single_changed_variable": "f0_method",
        "source_ids": [source[0] for source in SOURCES],
        "output_sha256": hashes,
        "claims": {
            "gateway_routed": False,
            "perceptual_winner": False,
            "product_selected": False,
        },
    }
    (arguments.work_dir / "listen-now-result.json").write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    staging.rename(arguments.listener_dir)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--execute", action="store_true")
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    return value


def main() -> int:
    arguments = parser().parse_args()
    try:
        if arguments.check == arguments.execute:
            raise F0ProbeError("choose exactly one of --check or --execute")
        validate(arguments)
        if arguments.check:
            print("ok   RVC Sasayaki F0 CPU admission complete")
            return 0
        print(json.dumps(execute(arguments), ensure_ascii=True, sort_keys=True))
        return 0
    except (F0ProbeError, OSError, subprocess.SubprocessError) as error:
        print(f"render_sasayaki_f0_offline: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
