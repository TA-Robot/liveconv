from __future__ import annotations

import hashlib
import json
import re
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from ._adapter_registry import validate_profile_adapter

_PRIVATE_CONFIGURATION_KEY = re.compile(
    r"(^|_)(api_?key|credential|directory|dir|endpoint|file|password|path|"
    r"private_?key|secret|socket|token|url)($|_)",
    re.IGNORECASE,
)


class TimeoutSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    first_output_ms: StrictInt = Field(gt=0)
    stall_ms: StrictInt = Field(gt=0)


class RuntimeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    adapter: Literal["passthrough", "gain", "worker"]
    configuration: dict[str, Any]
    worker_module: StrictStr | None = None
    worker_endpoint: StrictStr | None
    max_vram_mb: StrictInt = Field(ge=0, le=32_607)


class PromotionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["technical_validation", "approved"]
    pack_id: StrictStr = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    pack_sha256: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evidence_sha256: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    endpoint_sha256: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ModelProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    profile_id: StrictStr = Field(
        pattern=r"^(test|vc|tts)\.[a-z0-9][a-z0-9.-]*\.v[0-9]+$"
    )
    kind: Literal["deterministic_test", "voice_conversion", "text_to_speech"]
    readiness: Literal["ready", "loading", "unavailable"]
    adapter_api_version: Literal[1]
    implementation_revision: StrictStr = Field(min_length=1)
    weight_revision: StrictStr | None
    streaming: StrictBool
    cancellation: Literal["immediate", "cooperative", "generation_only"]
    input_sample_rates: list[StrictInt] = Field(min_length=1)
    output_sample_rates: list[StrictInt] = Field(min_length=1)
    frame_ms: StrictInt = Field(ge=5, le=200)
    minimum_context_ms: StrictInt = Field(ge=0, le=10_000)
    voice_requirement: Literal["none", "authorized_target_required", "pretrained_voice"]
    warmup_policy: Literal["none", "eager", "lazy"]
    resource_class: Literal["cpu", "gpu", "external"]
    license_record: StrictStr = Field(min_length=1)
    promotion: PromotionSpec | None = None
    timeouts: TimeoutSpec
    runtime: RuntimeSpec

    @property
    def selectable(self) -> bool:
        return self.readiness == "ready" and (
            self.runtime.adapter in {"passthrough", "gain"}
            or (
                self.runtime.adapter == "worker"
                and self.runtime.worker_endpoint is not None
                and self.promotion is not None
                and self.promotion.status == "approved"
            )
        )

    def validate_builtin(self, *, model_pack_directory: Path | None = None) -> None:
        self._reject_private_configuration_keys(self.runtime.configuration)
        validate_profile_adapter(self)
        if self.runtime.adapter == "worker":
            self._validate_promotion(model_pack_directory=model_pack_directory)
        elif self.promotion is not None:
            raise ValueError(
                f"{self.profile_id}: builtin profiles cannot declare promotion"
            )

    def _validate_promotion(self, *, model_pack_directory: Path | None) -> None:
        promotion = self.promotion
        if promotion is None:
            raise ValueError(f"{self.profile_id}: worker promotion is required")
        try:
            if model_pack_directory is None:
                raw = (
                    files("workers")
                    .joinpath("packs")
                    .joinpath(f"{promotion.pack_id}.json")
                    .read_bytes()
                )
            else:
                raw = (model_pack_directory / f"{promotion.pack_id}.json").read_bytes()
        except (FileNotFoundError, OSError) as exc:
            raise ValueError(
                f"{self.profile_id}: promotion model pack is unavailable"
            ) from exc
        actual_digest = f"sha256:{hashlib.sha256(raw).hexdigest()}"
        if actual_digest != promotion.pack_sha256:
            raise ValueError(f"{self.profile_id}: promotion model pack digest differs")
        try:
            pack = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{self.profile_id}: promotion model pack is invalid"
            ) from exc
        if pack.get("pack_id") != promotion.pack_id:
            raise ValueError(f"{self.profile_id}: promotion model pack ID differs")
        evidence = pack.get("promotion_evidence")
        if not isinstance(evidence, dict):
            raise ValueError(
                f"{self.profile_id}: promotion model pack has no reviewed evidence"
            )
        evidence_status = evidence.get("status")
        allowed_evidence_statuses = (
            {"approved"}
            if promotion.status == "approved"
            else {"technical_validation", "approved"}
        )
        if evidence_status not in allowed_evidence_statuses:
            raise ValueError(
                f"{self.profile_id}: promotion evidence does not authorize profile"
            )
        if evidence.get("evidence_sha256") != promotion.evidence_sha256:
            raise ValueError(f"{self.profile_id}: promotion evidence digest differs")
        if promotion.status == "approved" and pack.get("ready_for_runtime") is not True:
            raise ValueError(
                f"{self.profile_id}: model pack is not approved for runtime"
            )
        endpoint_value = self.runtime.worker_endpoint
        if endpoint_value is None:
            raise ValueError(f"{self.profile_id}: worker endpoint is missing")
        endpoint_path = Path(endpoint_value)
        if promotion.status == "approved":
            if endpoint_path.is_symlink():
                raise ValueError(
                    f"{self.profile_id}: approved worker endpoint cannot be a symlink"
                )
            for candidate in (endpoint_path, *endpoint_path.parents):
                if candidate.stat().st_mode & 0o022:
                    raise ValueError(
                        f"{self.profile_id}: approved worker endpoint ancestry "
                        "is writable"
                    )
        try:
            endpoint_digest = hashlib.sha256(endpoint_path.read_bytes()).hexdigest()
        except OSError as exc:
            raise ValueError(
                f"{self.profile_id}: worker endpoint is unavailable"
            ) from exc
        if f"sha256:{endpoint_digest}" != promotion.endpoint_sha256:
            raise ValueError(f"{self.profile_id}: worker endpoint digest differs")

    def public_dict(self) -> dict[str, Any]:
        value = self.model_dump(exclude={"runtime", "license_record", "timeouts"})
        if value["promotion"] is None:
            value.pop("promotion")
        return {
            **value,
            "profile_hash": self.profile_hash,
            "configuration_hash": self.configuration_hash,
        }

    @staticmethod
    def _canonical_hash(value: Any) -> str:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    @property
    def profile_hash(self) -> str:
        value = self.model_dump(mode="json")
        value["runtime"].pop("worker_endpoint", None)
        if value["runtime"].get("worker_module") is None:
            value["runtime"].pop("worker_module", None)
        if value["promotion"] is None:
            value.pop("promotion")
        return self._canonical_hash(value)

    @property
    def configuration_hash(self) -> str:
        return self._canonical_hash(self.runtime.configuration)

    @classmethod
    def _reject_private_configuration_keys(
        cls,
        value: Any,
        *,
        parent: str = "runtime.configuration",
    ) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if _PRIVATE_CONFIGURATION_KEY.search(key):
                    raise ValueError(f"{parent}.{key}: private key names are forbidden")
                cls._reject_private_configuration_keys(item, parent=f"{parent}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                cls._reject_private_configuration_keys(
                    item, parent=f"{parent}[{index}]"
                )


class ProfileDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    profiles: list[ModelProfile] = Field(min_length=1)


class ProfileRegistry:
    def __init__(
        self,
        profiles: dict[str, ModelProfile],
        *,
        allow_technical_profiles: bool = False,
    ) -> None:
        self._profiles = profiles
        self._allow_technical_profiles = allow_technical_profiles

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        allow_technical_profiles: bool = False,
        model_pack_directory: Path | None = None,
    ) -> ProfileRegistry:
        with path.open(encoding="utf-8") as stream:
            document = ProfileDocument.model_validate(json.load(stream))
        profiles: dict[str, ModelProfile] = {}
        for profile in document.profiles:
            if profile.profile_id in profiles:
                raise ValueError(f"duplicate profile_id: {profile.profile_id}")
            profile.validate_builtin(model_pack_directory=model_pack_directory)
            profiles[profile.profile_id] = profile
        return cls(
            profiles,
            allow_technical_profiles=allow_technical_profiles,
        )

    def _is_selectable(self, profile: ModelProfile) -> bool:
        if profile.selectable:
            return True
        promotion = profile.promotion
        return (
            self._allow_technical_profiles
            and profile.readiness == "ready"
            and profile.runtime.adapter == "worker"
            and promotion is not None
            and promotion.status == "technical_validation"
        )

    def get_selectable(self, profile_id: str) -> ModelProfile | None:
        profile = self._profiles.get(profile_id)
        return profile if profile is not None and self._is_selectable(profile) else None

    def get(self, profile_id: str) -> ModelProfile | None:
        return self._profiles.get(profile_id)

    def public_profiles(self) -> list[dict[str, Any]]:
        return [
            profile.public_dict()
            for profile in self._profiles.values()
            if self._is_selectable(profile)
        ]

    @property
    def ready(self) -> bool:
        return any(self._is_selectable(profile) for profile in self._profiles.values())
