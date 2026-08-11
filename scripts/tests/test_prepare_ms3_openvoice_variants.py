from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "prepare-ms3-openvoice-variants.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("prepare_ms3_openvoice", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREPARE = _load()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _base_registry(tmp_path: Path) -> dict[str, object]:
    endpoint = tmp_path / "python"
    endpoint.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    endpoint.chmod(0o700)
    material = PREPARE.MS2_BUILDER._load_object(
        PREPARE.REPOSITORY_ROOT
        / "workers"
        / "adapters"
        / "openvoice_v2"
        / "canonical-profile.json"
    )
    profile = PREPARE.MS2_BUILDER._openvoice_profile(
        material,
        endpoint=endpoint,
        repository_root=PREPARE.REPOSITORY_ROOT,
    )
    return {"schema_version": 1, "profiles": [profile]}


def test_openvoice_extension_binds_reference_profile_and_private_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    reference = b"RIFF test reference"
    archive = b"test archive"
    readme = b"test terms"
    reference_sha256 = _sha256(reference)
    profile_id = "vc.openvoice-v2.amitaro-runrun.v1"
    monkeypatch.setitem(PREPARE.APPROVED_TARGETS, profile_id, (reference_sha256, 0.3))
    root = tmp_path / "references"
    (root / "downloads").mkdir(parents=True)
    (root / "extracted" / "runrun").mkdir(parents=True)
    (root / "downloads" / "reference.zip").write_bytes(archive)
    (root / "extracted" / "runrun" / "reference.wav").write_bytes(reference)
    (root / "extracted" / "runrun" / "Readme.txt").write_bytes(readme)
    registry = {
        "schema_version": 1,
        "registry_revision": PREPARE.ZERO_SHA256,
        "records": [],
    }
    registry["registry_revision"] = PREPARE.VALIDATOR.authorization_registry_revision(
        registry
    )
    draft = {
        "schema_version": 1,
        "bundle_id": "initial",
        "created_at": "2026-08-10T00:00:00Z",
        "bundle_revision": PREPARE.ZERO_SHA256,
        "protocol_version": 1,
        "gateway_profile_registry": {"schema_version": 1, "profiles": []},
        "authorization_registry_revision": registry["registry_revision"],
        "authorization_records": [],
        "public_manifest": {
            "schema_version": 1,
            "bundle_id": "initial",
            "bundle_revision": PREPARE.ZERO_SHA256,
            "protocol_version": 1,
            "transport_scope": "loopback-ssh",
            "max_sessions": 1,
            "variants": [],
        },
        "consumer_contract": {},
    }
    intake = {
        "schema_version": 1,
        "source_page_url": "https://amitaro.net/source",
        "download_page_url": "https://amitaro.net/downloads",
        "terms_url": "https://amitaro.net/terms",
        "required_attribution": "Amitaro",
        "variants": [
            {
                "variant_id": "openvoice-amitaro-runrun",
                "profile_id": profile_id,
                "style_id": "runrun",
                "display_name": "OpenVoice Runrun",
                "target_presentation": "bright-youthful-feminine",
                "download_url": "https://amitaro.net/reference.zip",
                "archive_name": "reference.zip",
                "archive_sha256": _sha256(archive),
                "reference_name": "reference.wav",
                "reference_sha256": reference_sha256,
                "readme_name": "Readme.txt",
                "readme_sha256": _sha256(readme),
            }
        ],
    }

    result = PREPARE.extend_documents(
        _base_registry(tmp_path),
        draft,
        registry,
        intake,
        root,
        reviewed_at=datetime(2026, 8, 10, tzinfo=UTC),
    )

    profile = result[0]["gateway_profile_registry"]["profiles"][0]
    variant = result[0]["public_manifest"]["variants"][0]
    assert profile["profile_id"] == profile_id
    assert profile["runtime"]["configuration"]["target_reference_sha256"] == (
        reference_sha256
    )
    assert profile["runtime"]["configuration"]["tau"] == 0.3
    assert variant["invocation_mode"] == "buffered_end"
    path_name, digest_name = PREPARE.target_environment_names(profile_id)
    assert result[3][path_name].endswith("reference.wav")
    assert result[3][digest_name] == reference_sha256
    output = tmp_path / "prepared-six"
    PREPARE.write_preparation(output, *result)
    assert json.loads((output / "draft.json").read_text())["bundle_id"] == (
        "ms3-amitaro-rvc-openvoice-first-wave-v1"
    )
