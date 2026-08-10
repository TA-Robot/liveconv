from __future__ import annotations

import hashlib
import importlib.util
import shutil
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "fetch-ms3-openvoice-amitaro.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("fetch_ms3_openvoice", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FETCH = _load()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fixture(
    tmp_path: Path,
    *,
    unsafe_member: bool = False,
) -> tuple[Path, dict[str, object]]:
    archive = tmp_path / "reference.zip"
    reference = b"RIFF approved reference"
    readme = b"approved terms"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr(
            "../escape.wav" if unsafe_member else "corpus/48k/REFERENCE.wav",
            b"not selected",
        )
        output.writestr("corpus/48k/QUESTION_007.wav", reference)
        output.writestr("Readme.txt", readme)
        output.writestr("corpus/44.1k/QUESTION_007.wav", b"wrong sample rate")
    intake = {
        "schema_version": 1,
        "provider_id": "amitaro",
        "variants": [
            {
                "style_id": "runrun",
                "download_url": "https://amitaro.net/download/reference.zip",
                "archive_name": "reference.zip",
                "archive_sha256": FETCH.COMMON._sha256_file(archive),
                "reference_member": "corpus/48k/QUESTION_007.wav",
                "reference_name": "QUESTION_007.wav",
                "reference_sha256": _sha256(reference),
                "readme_member": "Readme.txt",
                "readme_name": "Readme.txt",
                "readme_sha256": _sha256(readme),
            }
        ],
    }
    return archive, intake


def _copy_downloader(source: Path):
    def copy(_url: str, destination: Path, _expected: str) -> None:
        shutil.copyfile(source, destination)

    return copy


def test_reference_fetch_selects_exact_48k_clip_and_terms(tmp_path: Path) -> None:
    archive, intake = _fixture(tmp_path)
    destination = tmp_path / "references"

    assert (
        FETCH.fetch_references(
            intake,
            destination,
            downloader=_copy_downloader(archive),
        )
        == 1
    )

    extracted = destination / "extracted" / "runrun"
    assert {path.name for path in extracted.iterdir()} == {
        "QUESTION_007.wav",
        "Readme.txt",
    }
    assert (extracted / "QUESTION_007.wav").read_bytes() == b"RIFF approved reference"


def test_reference_fetch_rejects_any_unsafe_archive_member(tmp_path: Path) -> None:
    archive, intake = _fixture(tmp_path, unsafe_member=True)
    destination = tmp_path / "references"

    with pytest.raises(ValueError, match="unsafe ZIP member"):
        FETCH.fetch_references(
            intake,
            destination,
            downloader=_copy_downloader(archive),
        )

    assert not destination.exists()
