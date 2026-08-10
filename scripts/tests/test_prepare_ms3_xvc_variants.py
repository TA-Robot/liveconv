from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "prepare-ms3-xvc-variants.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("prepare_ms3_xvc", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREPARE = _load()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _base_registry(tmp_path: Path) -> dict[str, object]:
    material = json.loads(
        (
            PREPARE.REPOSITORY_ROOT
            / "workers"
            / "adapters"
            / "x_vc"
            / "technical-profile.json"
        ).read_text(encoding="utf-8")
    )
    profile = copy.deepcopy(material["profile"])
    profile["runtime"] = {
        "adapter": "worker",
        "configuration": copy.deepcopy(material["runtime"]["configuration"]),
        "worker_module": material["runtime"]["worker_module"],
        "worker_endpoint": str(tmp_path / "python"),
        "max_vram_mb": profile.pop("max_vram_mb"),
    }
    profile.pop("quality_status")
    profile.pop("selectable_default")
    return {"schema_version": 1, "profiles": [profile]}


def _empty_prepared() -> tuple[dict[str, object], dict[str, object]]:
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
    return draft, registry


def test_xvc_extension_binds_reference_authorization_and_private_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = b"RIFF test reference"
    archive = b"test archive"
    readme = b"test terms"
    root = tmp_path / "references"
    (root / "downloads").mkdir(parents=True)
    (root / "extracted" / "runrun").mkdir(parents=True)
    (root / "downloads" / "reference.zip").write_bytes(archive)
    (root / "extracted" / "runrun" / "reference.wav").write_bytes(reference)
    (root / "extracted" / "runrun" / "Readme.txt").write_bytes(readme)
    reference_sha256 = _sha256(reference)
    candidate = {
        "variant_id": "xvc-amitaro-runrun",
        "profile_id": "vc.x-vc.amitaro-runrun.v1",
        "style_id": "runrun",
        "display_name": "X-VC Runrun",
        "target_presentation": "bright-youthful-feminine",
        "download_url": "https://amitaro.net/reference.zip",
        "archive_name": "reference.zip",
        "archive_sha256": _sha256(archive),
        "reference_name": "reference.wav",
        "reference_sha256": reference_sha256,
        "readme_name": "Readme.txt",
        "readme_sha256": _sha256(readme),
        "target_authorization_sha256": "pending",
    }
    authorization = PREPARE._authorization_document(candidate)
    authorization_sha256 = _sha256(PREPARE._json_bytes(authorization))
    candidate["target_authorization_sha256"] = authorization_sha256
    monkeypatch.setitem(
        PREPARE.APPROVED_TARGETS,
        candidate["profile_id"],
        (reference_sha256, authorization_sha256),
    )
    draft, registry = _empty_prepared()
    intake = {
        "schema_version": 1,
        "source_page_url": "https://amitaro.net/source",
        "download_page_url": "https://amitaro.net/downloads",
        "terms_url": "https://amitaro.net/terms",
        "required_attribution": "Amitaro",
        "variants": [candidate],
    }
    output = tmp_path / "prepared"
    result = PREPARE.extend_documents(
        _base_registry(tmp_path),
        draft,
        registry,
        intake,
        root,
        output / "target-authorizations",
        reviewed_at=datetime(2026, 8, 10, tzinfo=UTC),
    )

    PREPARE.write_preparation(output, *result)

    profile = result[0]["gateway_profile_registry"]["profiles"][0]
    configuration = profile["runtime"]["configuration"]
    assert configuration["target_reference_sha256"] == reference_sha256
    assert configuration["target_authorization_sha256"] == authorization_sha256
    assert (output / "target-authorizations" / "runrun.json").is_file()
    names = PREPARE.target_environment_names(candidate["profile_id"])
    assert result[3][names[2]] == str(
        output.resolve() / "target-authorizations" / "runrun.json"
    )
    assert result[0]["public_manifest"]["variants"][0]["invocation_mode"] == "live"


def test_xvc_extension_rejects_unapproved_target_identity(tmp_path: Path) -> None:
    draft, registry = _empty_prepared()
    intake = {
        "schema_version": 1,
        "source_page_url": "https://amitaro.net/source",
        "download_page_url": "https://amitaro.net/downloads",
        "terms_url": "https://amitaro.net/terms",
        "required_attribution": "Amitaro",
        "variants": [
            {
                "variant_id": "xvc-amitaro-runrun",
                "profile_id": "vc.x-vc.amitaro-runrun.v1",
                "reference_sha256": "0" * 64,
                "target_authorization_sha256": "0" * 64,
            }
        ],
    }
    with pytest.raises(ValueError, match="not statically approved"):
        PREPARE.extend_documents(
            _base_registry(tmp_path),
            draft,
            registry,
            intake,
            tmp_path,
            tmp_path / "output" / "target-authorizations",
            reviewed_at=datetime(2026, 8, 10, tzinfo=UTC),
        )
