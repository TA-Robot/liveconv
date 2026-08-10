from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from .profiles import ProfileRegistry


class PublicVariant(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    variant_id: StrictStr = Field(pattern=r"^[a-z0-9][a-z0-9.-]{2,95}$")
    family_id: StrictStr = Field(pattern=r"^[a-z0-9][a-z0-9.-]{1,63}$")
    display_order: StrictInt = Field(ge=1, le=12)
    display_name: StrictStr = Field(min_length=1, max_length=100)
    target_presentation: Literal[
        "youthful-feminine",
        "bright-youthful-feminine",
        "soft-youthful-feminine",
        "relaxed-youthful-feminine",
    ]
    lane: Literal["voice-conversion"]
    invocation_mode: Literal["live", "buffered_end"]
    profile_id: StrictStr = Field(pattern=r"^vc\.[a-z0-9][a-z0-9.-]*\.v[0-9]+$")
    profile_hash: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    configuration_hash: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    pack_id: StrictStr = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    promotion_evidence_sha256: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authorization_record_sha256: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    variant_manifest_sha256: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class PublicManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    bundle_id: StrictStr = Field(pattern=r"^[a-z0-9][a-z0-9.-]{2,95}$")
    bundle_revision: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    protocol_version: Literal[1]
    transport_scope: Literal["loopback-ssh"]
    max_sessions: Literal[1]
    variants: list[PublicVariant] = Field(min_length=1, max_length=12)


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _bundle_revision(value: dict[str, Any]) -> str:
    material = copy.deepcopy(value)
    material.pop("bundle_revision", None)
    public_manifest = material.get("public_manifest")
    if isinstance(public_manifest, dict):
        public_manifest.pop("bundle_revision", None)
    return _canonical_hash(material)


def _variant_revision(value: PublicVariant) -> str:
    material = value.model_dump(mode="json")
    material.pop("variant_manifest_sha256", None)
    return _canonical_hash(material)


class DeploymentManifest:
    def __init__(self, public_manifest: PublicManifest) -> None:
        self._public_manifest = public_manifest

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        profile_config: Path,
        registry: ProfileRegistry,
        max_sessions: int,
    ) -> DeploymentManifest:
        with path.open(encoding="utf-8") as stream:
            raw = json.load(stream)
        if not isinstance(raw, dict):
            raise ValueError("deployment bundle must be an object")
        required_fields = {
            "schema_version",
            "bundle_id",
            "created_at",
            "bundle_revision",
            "protocol_version",
            "gateway_profile_registry",
            "authorization_registry_revision",
            "authorization_records",
            "public_manifest",
            "consumer_contract",
        }
        if set(raw) != required_fields:
            raise ValueError("deployment bundle has unexpected fields")
        if raw.get("schema_version") != 1 or raw.get("protocol_version") != 1:
            raise ValueError("deployment bundle protocol is incompatible")
        expected_revision = _bundle_revision(raw)
        if raw.get("bundle_revision") != expected_revision:
            raise ValueError("deployment bundle revision differs")

        public_manifest = PublicManifest.model_validate(raw.get("public_manifest"))
        if raw.get("bundle_id") != public_manifest.bundle_id:
            raise ValueError("deployment bundle ID differs from public manifest")
        if raw.get("bundle_revision") != public_manifest.bundle_revision:
            raise ValueError("deployment bundle revision differs from public manifest")
        if public_manifest.max_sessions != max_sessions:
            raise ValueError("deployment bundle max_sessions differs from Gateway")

        with profile_config.open(encoding="utf-8") as stream:
            configured_profiles = json.load(stream)
        if raw.get("gateway_profile_registry") != configured_profiles:
            raise ValueError("deployment bundle profile registry differs from Gateway")

        variant_ids = [variant.variant_id for variant in public_manifest.variants]
        profile_ids = [variant.profile_id for variant in public_manifest.variants]
        display_orders = [variant.display_order for variant in public_manifest.variants]
        if len(set(variant_ids)) != len(variant_ids):
            raise ValueError("deployment manifest contains duplicate variant IDs")
        if len(set(profile_ids)) != len(profile_ids):
            raise ValueError("deployment manifest contains duplicate profile IDs")
        if display_orders != list(range(1, len(public_manifest.variants) + 1)):
            raise ValueError("deployment manifest display order is not contiguous")

        for variant in public_manifest.variants:
            if _variant_revision(variant) != variant.variant_manifest_sha256:
                raise ValueError(f"{variant.variant_id}: variant revision differs")
            if variant.family_id != variant.pack_id:
                raise ValueError(f"{variant.variant_id}: family and pack differ")
            profile = registry.get_selectable(variant.profile_id)
            if profile is None or profile.kind != "voice_conversion":
                raise ValueError(f"{variant.variant_id}: profile is not selectable VC")
            promotion = profile.promotion
            if promotion is None:
                raise ValueError(f"{variant.variant_id}: profile promotion is missing")
            if profile.profile_hash != variant.profile_hash:
                raise ValueError(f"{variant.variant_id}: profile hash differs")
            if profile.configuration_hash != variant.configuration_hash:
                raise ValueError(f"{variant.variant_id}: configuration hash differs")
            if promotion.pack_id != variant.pack_id:
                raise ValueError(f"{variant.variant_id}: promotion pack differs")
            if promotion.evidence_sha256 != variant.promotion_evidence_sha256:
                raise ValueError(f"{variant.variant_id}: promotion evidence differs")

        return cls(public_manifest)

    @property
    def bundle_revision(self) -> str:
        return self._public_manifest.bundle_revision

    def public_document(self) -> dict[str, Any]:
        return self._public_manifest.model_dump(mode="json")
