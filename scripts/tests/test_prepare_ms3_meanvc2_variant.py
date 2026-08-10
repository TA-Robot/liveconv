from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _load_script() -> ModuleType:
    path = REPOSITORY_ROOT / "scripts" / "prepare-ms3-meanvc2-variant.py"
    spec = importlib.util.spec_from_file_location("prepare_ms3_meanvc2", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = _load_script()
INTAKE = json.loads(
    (REPOSITORY_ROOT / "config" / "ms3-meanvc2-amitaro-intake.json").read_text(
        encoding="utf-8"
    )
)


def _base_documents() -> tuple[dict[str, object], dict[str, object]]:
    return (
        {
            "schema_version": 1,
            "bundle_id": "base",
            "bundle_revision": SCRIPT.ZERO_SHA256,
            "created_at": "2026-08-10T00:00:00Z",
            "authorization_registry_revision": SCRIPT.ZERO_SHA256,
            "authorization_records": [],
            "gateway_profile_registry": {"schema_version": 1, "profiles": []},
            "public_manifest": {
                "schema_version": 1,
                "protocol_version": 1,
                "bundle_id": "base",
                "bundle_revision": SCRIPT.ZERO_SHA256,
                "secrets_included": False,
                "variants": [],
            },
        },
        {
            "schema_version": 1,
            "registry_revision": SCRIPT.ZERO_SHA256,
            "records": [],
        },
    )


def _identity(tmp_path: Path) -> dict[str, str]:
    return {
        "LIVECONV_MEANVC2_INTERPRETER_PATH": str(tmp_path / "python"),
        "LIVECONV_MEANVC2_TARGET_REFERENCE_PATH": str(
            tmp_path / "runrun" / "QUESTION_007.wav"
        ),
    }


def test_extends_bundle_with_one_exact_fourth_family(tmp_path: Path) -> None:
    bundle, registry = _base_documents()
    draft, trusted, materials = SCRIPT.extend_documents(
        bundle,
        registry,
        INTAKE,
        _identity(tmp_path),
        reviewed_at=datetime(2026, 8, 10, 12, tzinfo=UTC),
    )

    profile = draft["gateway_profile_registry"]["profiles"][0]
    variant = draft["public_manifest"]["variants"][0]
    record = trusted["records"][0]
    assert profile["profile_id"] == "vc.meanvc2.amitaro-runrun.v1"
    assert profile["runtime"]["configuration"] == SCRIPT.meanvc2.CANONICAL_CONFIGURATION
    assert profile["promotion"]["pack_id"] == "meanvc2"
    assert variant["family_id"] == "meanvc2"
    assert variant["target_presentation"] == "bright-youthful-feminine"
    assert record["profile_id"] == profile["profile_id"]
    assert materials["manifests"][0]["license_state"] == (
        "personal-technical-evaluation-only"
    )


def test_rejects_target_or_duplicate_identity(tmp_path: Path) -> None:
    bundle, registry = _base_documents()
    changed = dict(INTAKE)
    changed["reference_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="target identity differs"):
        SCRIPT.extend_documents(
            bundle,
            registry,
            changed,
            _identity(tmp_path),
            reviewed_at=datetime(2026, 8, 10, 12, tzinfo=UTC),
        )

    bundle["public_manifest"]["variants"].append(
        {"variant_id": "meanvc2-amitaro-runrun"}
    )
    with pytest.raises(ValueError, match="already exists"):
        SCRIPT.extend_documents(
            bundle,
            registry,
            INTAKE,
            _identity(tmp_path),
            reviewed_at=datetime(2026, 8, 10, 12, tzinfo=UTC),
        )
