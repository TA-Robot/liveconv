from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

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
    worker_endpoint: StrictStr | None
    max_vram_mb: StrictInt = Field(ge=0, le=32_607)


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
    timeouts: TimeoutSpec
    runtime: RuntimeSpec

    @property
    def selectable(self) -> bool:
        return self.readiness == "ready" and self.runtime.adapter in {
            "passthrough",
            "gain",
        }

    def validate_builtin(self) -> None:
        self._reject_private_configuration_keys(self.runtime.configuration)
        if self.runtime.adapter == "gain":
            if set(self.runtime.configuration) != {"gain"}:
                raise ValueError(
                    f"{self.profile_id}: gain requires only configuration.gain"
                )
            gain = self.runtime.configuration["gain"]
            if isinstance(gain, bool) or not isinstance(gain, (int, float)):
                raise ValueError(f"{self.profile_id}: gain must be numeric")
            if not math.isfinite(gain) or not 0 <= gain <= 1:
                raise ValueError(
                    f"{self.profile_id}: gain must be finite and between 0 and 1"
                )
        elif self.runtime.adapter == "passthrough" and self.runtime.configuration:
            raise ValueError(
                f"{self.profile_id}: passthrough configuration must be empty"
            )

    def public_dict(self) -> dict[str, Any]:
        return {
            **self.model_dump(exclude={"runtime", "license_record", "timeouts"}),
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
    def __init__(self, profiles: dict[str, ModelProfile]) -> None:
        self._profiles = profiles

    @classmethod
    def load(cls, path: Path) -> ProfileRegistry:
        with path.open(encoding="utf-8") as stream:
            document = ProfileDocument.model_validate(json.load(stream))
        profiles: dict[str, ModelProfile] = {}
        for profile in document.profiles:
            if profile.profile_id in profiles:
                raise ValueError(f"duplicate profile_id: {profile.profile_id}")
            profile.validate_builtin()
            profiles[profile.profile_id] = profile
        return cls(profiles)

    def get_selectable(self, profile_id: str) -> ModelProfile | None:
        profile = self._profiles.get(profile_id)
        return profile if profile is not None and profile.selectable else None

    def public_profiles(self) -> list[dict[str, Any]]:
        return [
            profile.public_dict()
            for profile in self._profiles.values()
            if profile.selectable
        ]

    @property
    def ready(self) -> bool:
        return any(profile.selectable for profile in self._profiles.values())
