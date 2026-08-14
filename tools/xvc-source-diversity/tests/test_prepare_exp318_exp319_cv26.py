from __future__ import annotations

import sys
import hashlib
from pathlib import Path

import numpy as np
import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_exp318_exp319_cv26 as cv26  # noqa: E402


CV_POSITIONS = [
    4,
    5,
    6,
    11,
    13,
    14,
    16,
    19,
    25,
    27,
    30,
    31,
    35,
    36,
    39,
    43,
    48,
    52,
    54,
    55,
    57,
    58,
    59,
    63,
    71,
    75,
    78,
    80,
    86,
    91,
    101,
    103,
    106,
    110,
    113,
    114,
    127,
    133,
    138,
    139,
    140,
    143,
    144,
    146,
    149,
    153,
    159,
    169,
]


def digest(number: int) -> str:
    return f"{number:064x}"


def base_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    cv_set = set(CV_POSITIONS)
    for index in range(170):
        domain = "commonvoice-unpaired" if index in cv_set else "hadou-unpaired"
        if index not in cv_set and sum(row["domain"] == "hadou-unpaired" for row in rows) >= 34:
            domain = "jsut-unpaired"
        if index not in cv_set and sum(row["domain"] == "hadou-unpaired" for row in rows) < 34:
            domain = "hadou-unpaired"
        if index not in cv_set and domain == "jsut-unpaired" and sum(row["domain"] == "jsut-unpaired" for row in rows) >= 85:
            domain = "jvs-unpaired"
        rows.append(
            {
                "id": f"base-{index:03d}",
                "teacher_id": f"teacher-{index:03d}",
                "domain": domain,
                "source_manifest_id": f"EXP238:{index}",
                "source_root": "source-work",
                "source_file": f"sources/{index:03d}.wav",
                "source_sha256": digest(index + 1),
                "source_text": f"元文{index}",
                "target_root": "diverse-work",
                "target_file": f"control-outputs/{index:03d}.wav",
                "target_sha256": digest(index + 101),
                "target_id": f"target-{index:03d}",
                "target_text": f"元文{index}",
                "real_target_root": "source-work",
                "real_target_file": f"targets/{index:03d}.wav",
                "real_target_sha256": digest(index + 201),
                "real_target_text": f"Amitaro文{index}",
                "learning_target": "source-aligned-control69-plus-real-target-adversarial",
            }
        )
    # Replace the simple filler domains with the exact required composition.
    remaining = [index for index, row in enumerate(rows) if index not in cv_set]
    for index, position in enumerate(remaining):
        rows[position]["domain"] = (
            "jsut-unpaired"
            if index < 85
            else "jvs-unpaired"
            if index < 88
            else "hadou-unpaired"
        )
    return rows


def fixture_manifests() -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    base = base_rows()
    exp238 = {
        "kind": cv26.EXP238_KIND,
        "composition": cv26.EXPECTED_BASE_COMPOSITION,
        "items": base,
    }
    pool_items: list[dict[str, object]] = []
    exp317_rows = [dict(row) for row in base]
    for cv_index, position in enumerate(CV_POSITIONS[:32]):
        row = dict(base[position])
        row.update(
            {
                "id": f"cv32-{cv_index:02d}",
                "teacher_id": f"cv32-teacher-{cv_index:02d}",
                "source_manifest_id": f"EXP055:cv{cv_index:02d}",
                "source_file": f"new-sources/{cv_index:02d}.wav",
                "source_sha256": digest(5000 + cv_index),
                "source_client_id_sha256": digest(6000 + cv_index),
                "source_original_sha256": digest(7000 + cv_index),
                "target_file": f"control-outputs/cv32-{cv_index:02d}.wav",
                "target_sha256": digest(8000 + cv_index),
                "target_id": base[position]["target_id"],
                "real_target_file": base[position]["real_target_file"],
                "real_target_sha256": base[position]["real_target_sha256"],
            }
        )
        exp317_rows[position] = dict(row)
        pool_items.append(
            {
                **row,
                "position": cv_index,
            }
        )
    exp317 = {
        "kind": cv26.EXP317_KIND,
        "composition": cv26.EXPECTED_BASE_COMPOSITION,
        "items": exp317_rows,
    }
    exp306 = {
        "kind": cv26.EXP306_KIND,
        "composition": cv26.EXPECTED_BASE_COMPOSITION,
        "items": base + [dict(row) for row in pool_items],
    }
    exp306_pool = {
        "kind": cv26.EXP306_POOL_KIND,
        "composition": {"commonvoice-unpaired": 32},
        "items": pool_items,
    }
    return exp238, exp317, exp306, exp306_pool


def active_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    excluded_cv_indices = {5, 11, 17, 26, 27, 29}
    for index in [index for index in range(32) if index not in excluded_cv_indices]:
        rows.append(
            {
                "id": f"cv{index:02d}",
                "client_id_sha256": digest(6000 + index),
                "source_text": f"元文{CV_POSITIONS[index]}",
                "source_original_sha256": digest(7000 + index),
                "source_sha256": digest(9000 + index),
                "source_wav": b"window",
                "window": {"active_sample_fraction": 0.25, "window_start_sample": 0},
            }
        )
    return rows


def test_build_pair_replaces_retained_and_restores_six_positions() -> None:
    exp238, exp317, _, exp306_pool = fixture_manifests()
    curriculum, pool, positions = cv26.build_pair(
        exp238["items"], exp317["items"], exp306_pool["items"], active_rows()
    )
    assert curriculum["kind"] == cv26.EXP318_KIND
    assert pool["kind"] == cv26.EXP319_KIND
    assert positions == cv26.RETAINED_POSITIONS
    assert len(pool["items"]) == 26
    assert curriculum["composition"] == cv26.EXPECTED_BASE_COMPOSITION
    for position in cv26.EXCLUDED_POSITIONS:
        assert curriculum["items"][position] == exp238["items"][position]
    for position in cv26.RETAINED_POSITIONS:
        assert curriculum["items"][position]["source_file"] == exp317["items"][position]["source_file"]
        assert curriculum["items"][position]["source_sha256"] == exp317["items"][position]["source_sha256"]
        assert curriculum["items"][position]["target_id"] == exp238["items"][position]["target_id"]
    assert all(
        item["source_file"].startswith("active-sources/")
        and item["source_file"] != exp317["items"][position]["source_file"]
        and item["source_sha256"] != exp317["items"][position]["source_sha256"]
        for item, position in zip(pool["items"], cv26.RETAINED_POSITIONS, strict=True)
    )


def test_build_pair_rejects_target_assignment_drift() -> None:
    exp238, exp317, _, exp306_pool = fixture_manifests()
    exp317["items"][cv26.RETAINED_POSITIONS[0]]["real_target_sha256"] = digest(9999)
    with pytest.raises(cv26.Cv26Error, match="position identity"):
        cv26.build_pair(
            exp238["items"], exp317["items"], exp306_pool["items"], active_rows()
        )


def test_build_pair_rejects_wrong_active_client() -> None:
    exp238, exp317, _, exp306_pool = fixture_manifests()
    active = active_rows()
    active[0]["client_id_sha256"] = digest(12345)
    with pytest.raises(cv26.Cv26Error, match="active source metadata"):
        cv26.build_pair(
            exp238["items"], exp317["items"], exp306_pool["items"], active
        )


def test_active_commonvoice_records_exact_six_zero_active(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    zero = set(cv26.ZERO_ACTIVE_IDS)
    items = []
    for index in range(32):
        identifier = f"cv{index:02d}u"
        payload = f"mp3-{identifier}".encode()
        path = tmp_path / f"{identifier}.mp3"
        path.write_bytes(payload)
        items.append(
            {
                "id": identifier,
                "filename": path.name,
                "sha256": __import__("hashlib").sha256(payload).hexdigest(),
                "client_id_sha256": digest(10000 + index),
                "text": f"文{index}",
            }
        )
    # Make the test metadata use the frozen six IDs while retaining 32 rows.
    for index, identifier in enumerate(cv26.ZERO_ACTIVE_IDS):
        items[index]["id"] = identifier
        items[index]["filename"] = f"{identifier}.mp3"
        payload = f"mp3-{identifier}".encode()
        (tmp_path / items[index]["filename"]).write_bytes(payload)
        items[index]["sha256"] = hashlib.sha256(payload).hexdigest()
    excluded_payload = b"mp3-cv27706775u"
    (tmp_path / "cv27706775u.mp3").write_bytes(excluded_payload)
    items.append(
        {
            "id": cv26.EXP055_EXCLUDED_ID,
            "filename": "cv27706775u.mp3",
            "sha256": hashlib.sha256(excluded_payload).hexdigest(),
            "client_id_sha256": digest(11000),
            "text": "除外文",
        }
    )
    def fake_decode(path: Path) -> np.ndarray:
        return np.zeros(cv26.WINDOW_SAMPLES, dtype=np.int16) if path.stem in zero else np.full(cv26.WINDOW_SAMPLES, 1000, dtype=np.int16)
    monkeypatch.setattr(cv26, "decode_mp3", fake_decode)
    active, identities = cv26.active_commonvoice(
        {"kind": "liveconv-exp055-commonvoice-local-unused/v1", "items": items},
        tmp_path,
    )
    assert len(identities) == 32
    assert len(active) == 26
    assert {item["id"] for item in identities if item["id"] not in {row["id"] for row in active}} == zero


def test_materialize_writes_only_treatment_source_work(tmp_path: Path) -> None:
    exp238, exp317, _, exp306_pool = fixture_manifests()
    base = exp238["items"]
    source_root = tmp_path / "exp238-source-work"
    source_root.mkdir()
    for index, row in enumerate(base):
        source_path = source_root / str(row["source_file"])
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_bytes = f"source-{index}".encode()
        source_path.write_bytes(source_bytes)
        row["source_sha256"] = cv26.sha256_bytes(source_bytes)
        target_path = source_root / str(row["real_target_file"])
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_bytes = f"real-target-{index}".encode()
        target_path.write_bytes(target_bytes)
        row["real_target_sha256"] = cv26.sha256_bytes(target_bytes)
        exp317["items"][index]["source_sha256"] = row["source_sha256"]
        exp317["items"][index]["real_target_sha256"] = row["real_target_sha256"]
        if index in CV_POSITIONS[:32]:
            cv_index = CV_POSITIONS[:32].index(index)
            exp306_pool["items"][cv_index]["real_target_sha256"] = row["real_target_sha256"]
            exp306_pool["items"][cv_index]["source_sha256"] = exp317["items"][index]["source_sha256"]
    active = active_rows()
    for row in active:
        payload = f"active-{row['id']}".encode()
        row["source_wav"] = payload
        row["source_sha256"] = cv26.sha256_bytes(payload)
    curriculum, pool, _ = cv26.build_pair(
        base, exp317["items"], exp306_pool["items"], active
    )
    output_root = tmp_path / "exp318-exp319"
    cv26.materialize(
        exp238_rows=base,
        curriculum=curriculum,
        pool=pool,
        active=active,
        exp238_source_work=source_root,
        current_source_work=source_root,
        output_root=output_root,
    )
    assert (output_root / "source-work/sources/000.wav").is_file()
    assert len(list((output_root / "source-work/active-sources").glob("*.wav"))) == 26
