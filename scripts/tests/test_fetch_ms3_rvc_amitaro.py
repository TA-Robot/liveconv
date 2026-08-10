from __future__ import annotations

import hashlib
import importlib.util
import shutil
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "fetch-ms3-rvc-amitaro.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("fetch_ms3_rvc_amitaro", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FETCH = _load()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fixture(
    tmp_path: Path, *, unsafe_member: bool = False
) -> tuple[Path, dict[str, object]]:
    archive = tmp_path / "fixture.zip"
    contents = {
        "voice.pth": b"checkpoint",
        "voice.index": b"index",
        "Readme.txt": b"terms",
    }
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name, value in contents.items():
            member = (
                f"../{name}"
                if unsafe_member and name == "voice.pth"
                else f"folder\\{name}"
            )
            output.writestr(member, value)
    intake = {
        "schema_version": 1,
        "provider_id": "amitaro",
        "variants": [
            {
                "style_id": "bright",
                "download_url": "https://amitaro.net/download/voice.zip",
                "archive_name": "voice.zip",
                "archive_sha256": FETCH._sha256_file(archive),
                "checkpoint_name": "voice.pth",
                "checkpoint_sha256": _sha256(contents["voice.pth"]),
                "index_name": "voice.index",
                "index_sha256": _sha256(contents["voice.index"]),
                "readme_name": "Readme.txt",
                "readme_sha256": _sha256(contents["Readme.txt"]),
            }
        ],
    }
    return archive, intake


def _copy_downloader(source: Path):
    def copy(_url: str, destination: Path, _expected: str) -> None:
        shutil.copyfile(source, destination)

    return copy


def test_fetch_verifies_and_extracts_only_required_files(tmp_path: Path) -> None:
    archive, intake = _fixture(tmp_path)
    destination = tmp_path / "candidates"

    assert (
        FETCH.fetch_candidates(
            intake,
            destination,
            downloader=_copy_downloader(archive),
        )
        == 1
    )

    assert (destination / "downloads" / "voice.zip").is_file()
    extracted = destination / "extracted" / "bright"
    assert {path.name for path in extracted.iterdir()} == {
        "voice.pth",
        "voice.index",
        "Readme.txt",
    }
    assert (extracted / "voice.pth").read_bytes() == b"checkpoint"
    with pytest.raises(FileExistsError):
        FETCH.fetch_candidates(
            intake,
            destination,
            downloader=_copy_downloader(archive),
        )


def test_fetch_rejects_archive_path_traversal_without_partial_output(
    tmp_path: Path,
) -> None:
    archive, intake = _fixture(tmp_path, unsafe_member=True)
    destination = tmp_path / "candidates"

    with pytest.raises(ValueError, match="unsafe ZIP member"):
        FETCH.fetch_candidates(
            intake,
            destination,
            downloader=_copy_downloader(archive),
        )

    assert not destination.exists()
    assert not list(tmp_path.glob(".candidates.tmp-*"))


def test_fetch_rejects_download_digest_drift(tmp_path: Path) -> None:
    archive, intake = _fixture(tmp_path)
    intake["variants"][0]["archive_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="download digest differs"):
        FETCH.fetch_candidates(
            intake,
            tmp_path / "candidates",
            downloader=_copy_downloader(archive),
        )
