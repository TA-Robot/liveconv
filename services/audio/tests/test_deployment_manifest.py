from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from liveconv_audio import deployment


class StubRegistry:
    def __init__(self, profiles: dict[str, object]) -> None:
        self._profiles = profiles

    def get_selectable(self, profile_id: str) -> object | None:
        return self._profiles.get(profile_id)


def deployment_fixture() -> tuple[dict[str, object], StubRegistry]:
    families = ("rvc-v2", "meanvc2", "x-vc", "openvoice-v2")
    profiles: dict[str, object] = {}
    profile_documents = []
    variants = []
    for index in range(1, 10):
        family = families[(index - 1) % len(families)]
        profile_id = f"vc.{family}.voice-{index}.v1"
        profile_hash = f"sha256:{index:064x}"
        configuration_hash = f"sha256:{index + 100:064x}"
        evidence_hash = f"sha256:{index + 200:064x}"
        profile_documents.append({"profile_id": profile_id, "revision": index})
        profiles[profile_id] = SimpleNamespace(
            kind="voice_conversion",
            profile_hash=profile_hash,
            configuration_hash=configuration_hash,
            promotion=SimpleNamespace(
                pack_id=family,
                evidence_sha256=evidence_hash,
            ),
        )
        variant = {
            "variant_id": f"{family}-voice-{index}",
            "family_id": family,
            "display_order": index,
            "display_name": f"Voice {index}",
            "target_presentation": "youthful-feminine",
            "lane": "voice-conversion",
            "invocation_mode": "live",
            "profile_id": profile_id,
            "profile_hash": profile_hash,
            "configuration_hash": configuration_hash,
            "pack_id": family,
            "promotion_evidence_sha256": evidence_hash,
            "authorization_record_sha256": f"sha256:{index + 300:064x}",
            "variant_manifest_sha256": f"sha256:{0:064x}",
        }
        variant["variant_manifest_sha256"] = deployment._canonical_hash(
            {
                key: value
                for key, value in variant.items()
                if key != "variant_manifest_sha256"
            }
        )
        variants.append(variant)

    bundle = {
        "schema_version": 1,
        "bundle_id": "ms3-runtime-test-v1",
        "created_at": "2026-08-10T00:00:00Z",
        "bundle_revision": f"sha256:{0:064x}",
        "protocol_version": 1,
        "gateway_profile_registry": {
            "schema_version": 1,
            "profiles": profile_documents,
        },
        "authorization_registry_revision": f"sha256:{500:064x}",
        "authorization_records": [{"record": index} for index in range(1, 10)],
        "public_manifest": {
            "schema_version": 1,
            "bundle_id": "ms3-runtime-test-v1",
            "bundle_revision": f"sha256:{0:064x}",
            "protocol_version": 1,
            "transport_scope": "loopback-ssh",
            "max_sessions": 1,
            "variants": variants,
        },
        "consumer_contract": {"activation": "prevalidated"},
    }
    rebind_bundle(bundle)
    return bundle, StubRegistry(profiles)


def rebind_bundle(bundle: dict[str, object]) -> None:
    revision = deployment._bundle_revision(bundle)
    bundle["bundle_revision"] = revision
    bundle["public_manifest"]["bundle_revision"] = revision


def write_bundle(
    tmp_path: Path,
    bundle: dict[str, object],
) -> tuple[Path, Path]:
    bundle_path = tmp_path / "bundle.json"
    profile_path = tmp_path / "profiles.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    profile_path.write_text(
        json.dumps(bundle["gateway_profile_registry"]),
        encoding="utf-8",
    )
    return bundle_path, profile_path


def test_runtime_manifest_binds_bundle_registry_and_profiles(tmp_path: Path) -> None:
    bundle, registry = deployment_fixture()
    bundle_path, profile_path = write_bundle(tmp_path, bundle)

    manifest = deployment.DeploymentManifest.load(
        bundle_path,
        profile_config=profile_path,
        registry=registry,
        max_sessions=1,
    )

    assert manifest.bundle_revision == bundle["bundle_revision"]
    assert manifest.public_document() == bundle["public_manifest"]
    assert "gateway_profile_registry" not in manifest.public_document()


def test_runtime_manifest_allows_an_incremental_single_family_bundle(
    tmp_path: Path,
) -> None:
    bundle, registry = deployment_fixture()
    bundle["gateway_profile_registry"]["profiles"] = bundle["gateway_profile_registry"][
        "profiles"
    ][:1]
    bundle["authorization_records"] = bundle["authorization_records"][:1]
    bundle["public_manifest"]["variants"] = bundle["public_manifest"]["variants"][:1]
    rebind_bundle(bundle)
    bundle_path, profile_path = write_bundle(tmp_path, bundle)

    manifest = deployment.DeploymentManifest.load(
        bundle_path,
        profile_config=profile_path,
        registry=registry,
        max_sessions=1,
    )

    assert len(manifest.public_document()["variants"]) == 1


@pytest.mark.parametrize(
    "mutation",
    ["bundle-revision", "profile-registry", "profile-hash", "max-sessions"],
)
def test_runtime_manifest_rejects_deployment_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    bundle, registry = deployment_fixture()
    max_sessions = 1
    if mutation == "bundle-revision":
        bundle["bundle_revision"] = f"sha256:{999:064x}"
    elif mutation == "profile-hash":
        variant = bundle["public_manifest"]["variants"][0]
        variant["profile_hash"] = f"sha256:{999:064x}"
        variant["variant_manifest_sha256"] = deployment._canonical_hash(
            {
                key: value
                for key, value in variant.items()
                if key != "variant_manifest_sha256"
            }
        )
        rebind_bundle(bundle)
    elif mutation == "max-sessions":
        max_sessions = 2
    bundle_path, profile_path = write_bundle(tmp_path, bundle)
    if mutation == "profile-registry":
        configured = json.loads(profile_path.read_text(encoding="utf-8"))
        configured["profiles"][0]["revision"] = 99
        profile_path.write_text(json.dumps(configured), encoding="utf-8")

    with pytest.raises(ValueError):
        deployment.DeploymentManifest.load(
            bundle_path,
            profile_config=profile_path,
            registry=registry,
            max_sessions=max_sessions,
        )
