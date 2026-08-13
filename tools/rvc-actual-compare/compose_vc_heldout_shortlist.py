#!/usr/bin/env python3
"""Compose the two surviving live-Gateway VC arms into one hearing shortlist."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ROWS = (
    {
        "source_id": "EMOTION100_002",
        "text": "シュヴァイツァーは見習うべき人間です。",
        "directory": "01-EMOTION100_002",
        "source_sha256": (
            "8f27065d5b2f66baeafea5e96653f87c57ce866ea42f4e19df82886078c5e536"
        ),
    },
    {
        "source_id": "EMOTION100_004",
        "text": "スティーヴはジェーンから手紙をもらった。",
        "directory": "02-EMOTION100_004",
        "source_sha256": (
            "0a3828c54f83fb28f885d0d452beab029a38030f6429a32e6720e5bb4f4c9ab5"
        ),
    },
    {
        "source_id": "EMOTION100_017",
        "text": "あっベルが鳴ってる。",
        "directory": "03-EMOTION100_017",
        "source_sha256": (
            "9fad53ec17379745bc7e56d9306a1ffa1fda1ee0dfdf077826792e6e8199d455"
        ),
    },
)
ARMS = (
    {
        "arm_id": "rvc-sasayaki-clean-bright",
        "family_id": "rvc-v2",
        "profile_id": "vc.rvc-v2.amitaro-sasayaki-clean-bright.v1",
        "display_name": "RVC Sasayaki clean-bright / live Gateway",
        "collection": "exp020-sasayaki-heldout-generalization-v1",
        "input_file": "20-vc.rvc-v2.amitaro-sasayaki-clean-bright.v1.wav",
        "output_file": "10-rvc-sasayaki-clean-bright.wav",
        "hashes": {
            "EMOTION100_002": (
                "1009a84fefaf359cc2bb4c295d7f0b63794f2e53c1bba210b962cd14eaf05a92"
            ),
            "EMOTION100_004": (
                "7e1558ba108a3a366a6d258fd4e6212ab08ed6535ad3c79c901244797e64cb19"
            ),
            "EMOTION100_017": (
                "62c4c53134ee3d5a65ad4a10847485d61798b83216ec065a6f9afaf1389bbf8d"
            ),
        },
        "macro_content_cer": 0.18421052631578946,
    },
    {
        "arm_id": "xvc-yofukashi-q34",
        "family_id": "x-vc",
        "profile_id": "vc.x-vc.amitaro-yofukashi-q34.v1",
        "display_name": "X-VC Yofukashi Q034 / live Gateway",
        "collection": "exp026-xvc-yofukashi-q34-heldout-route-v1",
        "input_file": "10-vc.x-vc.amitaro-yofukashi-q34.v1.wav",
        "output_file": "20-xvc-yofukashi-q34.wav",
        "hashes": {
            "EMOTION100_002": (
                "71ea2e43f7219ba40dbe3dae660534d9a93b12b368a085c910f33879a7304b04"
            ),
            "EMOTION100_004": (
                "cfd74bd0e47a8b25136c1ff8f20f223e4d992d912fcc316fd105c8b755d446bc"
            ),
            "EMOTION100_017": (
                "8f050600f59bd02165b62b538866f3eedb7382486df49c6ea994461a0875eec3"
            ),
        },
        "macro_content_cer": 0.16569200779727095,
    },
)


class ShortlistError(RuntimeError):
    """The exact two-arm shortlist cannot be composed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_file(path: Path, expected_sha256: str, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ShortlistError(f"{label} is unavailable")
    if sha256_file(path) != expected_sha256:
        raise ShortlistError(f"{label} identity drifted")
    return path


def inputs() -> list[tuple[Path, str, str]]:
    result: list[tuple[Path, str, str]] = []
    listening = ROOT / "artifacts/ms3/listening"
    for row in ROWS:
        directory = str(row["directory"])
        source = listening / str(ARMS[0]["collection"]) / directory / "00-source.wav"
        result.append((source, str(row["source_sha256"]), f"{row['source_id']} source"))
        for arm in ARMS:
            path = (
                listening / str(arm["collection"]) / directory / str(arm["input_file"])
            )
            expected = arm["hashes"][row["source_id"]]
            result.append((path, expected, f"{row['source_id']} {arm['arm_id']}"))
    return result


def validate(listener_dir: Path) -> None:
    if (
        listener_dir.exists()
        or listener_dir.with_name(listener_dir.name + ".staging").exists()
    ):
        raise ShortlistError("listener output must be new")
    for path, expected, label in inputs():
        checked_file(path, expected, label)


def compose(listener_dir: Path) -> dict[str, Any]:
    validate(listener_dir)
    staging = listener_dir.with_name(listener_dir.name + ".staging")
    staging.mkdir(parents=True)
    listening = ROOT / "artifacts/ms3/listening"
    try:
        for row in ROWS:
            directory = str(row["directory"])
            destination = staging / directory
            destination.mkdir()
            source = (
                listening / str(ARMS[0]["collection"]) / directory / "00-source.wav"
            )
            shutil.copyfile(source, destination / "00-source.wav")
            variants = []
            for order, arm in enumerate(ARMS, start=1):
                arm_source = (
                    listening
                    / str(arm["collection"])
                    / directory
                    / str(arm["input_file"])
                )
                arm_output = destination / str(arm["output_file"])
                shutil.copyfile(arm_source, arm_output)
                expected = arm["hashes"][row["source_id"]]
                if sha256_file(arm_output) != expected:
                    raise ShortlistError("copied shortlist output identity drifted")
                variants.append(
                    {
                        "variant_id": arm["arm_id"],
                        "profile_id": arm["profile_id"],
                        "family_id": arm["family_id"],
                        "display_name": arm["display_name"],
                        "display_order": order,
                        "output_file": arm["output_file"],
                        "output_sha256": "sha256:" + expected,
                        "status": "passed",
                        "operator_judgment": "unreviewed",
                        "quality_status": "not_assessed",
                        "route_status": "listen_now_gateway",
                    }
                )
            index = {
                "schema_version": 1,
                "title": f"VC heldout shortlist / {row['source_id']}",
                "run_kind": "MS-3 machine-screened two-family hearing shortlist",
                "status": "completed-listen-now-unselected",
                "source_file": f"Hadou public heldout / {row['source_id']}",
                "source_text": row["text"],
                "source_id": row["source_id"],
                "source_output_file": "00-source.wav",
                "source_sha256": "sha256:" + str(row["source_sha256"]),
                "comparison_scope": {
                    "human_hearing_pending": True,
                    "machine_selection_allowed": False,
                    "question": (
                        "Which surviving live route sounds clearer and more natural?"
                    ),
                    "note": (
                        "Auxiliary CER only rejected gross corruption; it did not "
                        "rank voice quality."
                    ),
                },
                "variants": variants,
            }
            (destination / "index.json").write_text(
                json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        result = {
            "schema_version": 1,
            "kind": "liveconv-ms3-vc-heldout-shortlist-result",
            "status": "completed-listen-now-unselected",
            "git_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "source_ids": [row["source_id"] for row in ROWS],
            "arms": [
                {
                    "arm_id": arm["arm_id"],
                    "profile_id": arm["profile_id"],
                    "macro_content_cer": arm["macro_content_cer"],
                }
                for arm in ARMS
            ],
            "claims": {"perceptual_winner": False, "product_selected": False},
        }
        (staging / "shortlist-result.json").write_text(
            json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging.rename(listener_dir)
        return result
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    mode = value.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    value.add_argument("--listener-dir", type=Path, required=True)
    return value


def main() -> int:
    arguments = parser().parse_args()
    try:
        validate(arguments.listener_dir)
        if arguments.check:
            print("ok   exact two-family VC shortlist inputs")
            return 0
        print(
            json.dumps(
                compose(arguments.listener_dir), ensure_ascii=True, sort_keys=True
            )
        )
        return 0
    except (OSError, ShortlistError, ValueError) as error:
        print(f"compose_vc_heldout_shortlist: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
