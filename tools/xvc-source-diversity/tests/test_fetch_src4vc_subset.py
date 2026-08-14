from __future__ import annotations

import importlib.util
import io
import sys
import zipfile
from collections import Counter
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "fetch_src4vc_subset.py"
SPEC = importlib.util.spec_from_file_location("xvc_fetch_src4vc_subset", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
FETCH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = FETCH
SPEC.loader.exec_module(FETCH)


def _archive(names: list[str]) -> bytes:
    value = io.BytesIO()
    with zipfile.ZipFile(value, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for name in names:
            handle.writestr(name, f"payload:{name}".encode())
    return value.getvalue()


def _central(value: bytes) -> bytes:
    marker = value.rfind(b"PK\x05\x06")
    assert marker >= 0
    size = int.from_bytes(value[marker + 12 : marker + 16], "little")
    offset = int.from_bytes(value[marker + 16 : marker + 20], "little")
    return value[offset : offset + size]


def test_heldout_speakers_are_evenly_spread_and_disjoint() -> None:
    heldout = FETCH.heldout_speakers()

    assert len(heldout) == 15
    assert "SRC4VC004" in heldout
    assert "SRC4VC097" in heldout
    assert not heldout & {
        f"SRC4VC{index:03d}"
        for index in range(1, 101)
        if f"SRC4VC{index:03d}" not in heldout
    }


def test_central_parser_and_payload_inflater_round_trip() -> None:
    value = _archive(["safe/file.txt"])
    entries = FETCH.parse_central_directory(_central(value))
    entry = entries["safe/file.txt"]
    offset = int(entry["local_offset"])

    payload = FETCH.extract_local_payload(value[offset:], entry)

    assert payload == b"payload:safe/file.txt"


def test_payload_inflater_rejects_corruption() -> None:
    value = bytearray(_archive(["safe/file.txt"]))
    entries = FETCH.parse_central_directory(_central(value))
    entry = entries["safe/file.txt"]
    offset = int(entry["local_offset"])
    value[offset + 30 + len("safe/file.txt")] ^= 0x01

    with pytest.raises(FETCH.Src4vcFetchError, match="corrupt|CRC"):
        FETCH.extract_local_payload(bytes(value[offset:]), entry)


def test_selection_freezes_85_train_and_30_disjoint_evaluation_rows() -> None:
    names: list[str] = []
    for speaker_index in range(1, 101):
        speaker = f"SRC4VC{speaker_index:03d}"
        names.append(f"SRC4VC_ver1/{speaker}/speaker_metadata.yml")
        for row_index in range(10):
            stem = f"RECITATION_{row_index:03d}"
            names.extend(
                (
                    f"SRC4VC_ver1/{speaker}/wav/{stem}.wav",
                    f"SRC4VC_ver1/{speaker}/txt/{stem}.txt",
                )
            )
    entries = {name: {"filename": name} for name in names}

    rows = FETCH.selected_rows(entries)

    assert Counter(row["split"] for row in rows) == {
        "train": 85,
        "evaluation": 30,
    }
    train_speakers = {row["speaker_id"] for row in rows if row["split"] == "train"}
    evaluation_speakers = {
        row["speaker_id"] for row in rows if row["split"] == "evaluation"
    }
    assert len(train_speakers) == 85
    assert len(evaluation_speakers) == 15
    assert not train_speakers & evaluation_speakers


def test_metadata_parser_accepts_only_published_flat_multiline_shape() -> None:
    value = b"""device_raw_name: 'iPhone XS

  iOS 16.6.1'
device_normalized_name: iPhone XS
gender: female
age: 45.0
locale: Aichi
dialect: standard
acting_experience: none
"""

    parsed = FETCH.parse_metadata(value)

    assert parsed["device_raw_name"] == "iPhone XS iOS 16.6.1"
    assert parsed["age"] == 45.0


def test_metadata_parser_rejects_unknown_yaml_shape() -> None:
    value = b"""device_raw_name: !unsafe value
device_normalized_name: value
gender: value
age: 45.0
locale: value
dialect: value
acting_experience: value
unknown: value
"""

    with pytest.raises(FETCH.Src4vcFetchError, match="shape"):
        FETCH.parse_metadata(value)
