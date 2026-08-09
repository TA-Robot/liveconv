from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigurationError

_PROFILE_ID = re.compile(r"^(test|vc|tts)\.[a-z0-9][a-z0-9.-]*\.v[0-9]+$")
_PRIVATE_CONFIGURATION_KEY = re.compile(
    r"(^|_)(api_?key|credential|directory|dir|endpoint|file|password|path|"
    r"private_?key|secret|socket|token|url)($|_)",
    re.IGNORECASE,
)
_SENSITIVE_FILENAME = re.compile(
    r"(^key$|^\.env($|\.)|credential|private.?key|secret|token)", re.IGNORECASE
)
_PROFILE_FIELDS = {
    "profile_id",
    "kind",
    "readiness",
    "adapter_api_version",
    "implementation_revision",
    "weight_revision",
    "streaming",
    "cancellation",
    "input_sample_rates",
    "output_sample_rates",
    "frame_ms",
    "minimum_context_ms",
    "voice_requirement",
    "warmup_policy",
    "resource_class",
    "license_record",
    "timeouts",
    "runtime",
    "promotion",
}
_PROFILE_REQUIRED_FIELDS = _PROFILE_FIELDS - {"promotion"}
_RUNTIME_REQUIRED_FIELDS = {
    "adapter",
    "configuration",
    "worker_endpoint",
    "max_vram_mb",
}
_RUNTIME_FIELDS = _RUNTIME_REQUIRED_FIELDS | {"worker_module"}
_WORKER_MODULE = re.compile(r"^workers\.adapters\.[a-z0-9_]+(?:\.[a-z0-9_]+)*$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_PACK_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_PROMOTION_FIELDS = {
    "status",
    "pack_id",
    "pack_sha256",
    "evidence_sha256",
    "endpoint_sha256",
}


def _reject_constant(value: str) -> None:
    raise ConfigurationError(f"non-finite registry number {value!r} is forbidden")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ConfigurationError(f"non-finite registry number {value!r} is forbidden")
    return parsed


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError(f"duplicate registry field {key!r}")
        result[key] = value
    return result


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True, allow_nan=False
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _require_int(value: object, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ConfigurationError(f"{name} must be an integer >= {minimum}")
    return value


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{name} must be non-empty text")
    return value


def _integer_list(value: object, name: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise ConfigurationError(f"{name} must be a non-empty array")
    return tuple(_require_int(item, name, minimum=1) for item in value)


def _reject_private_configuration_keys(value: object, *, location: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ConfigurationError(f"{location} keys must be text")
            if _PRIVATE_CONFIGURATION_KEY.search(key):
                raise ConfigurationError(
                    f"{location} contains a private configuration key"
                )
            _reject_private_configuration_keys(item, location=f"{location}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _reject_private_configuration_keys(item, location=f"{location}[{index}]")


@dataclass(frozen=True, slots=True)
class RegistryProfile:
    profile_id: str
    kind: str
    readiness: str
    implementation_revision: str
    weight_revision: str | None
    streaming: bool
    cancellation: str
    input_sample_rates: tuple[int, ...]
    output_sample_rates: tuple[int, ...]
    frame_ms: int
    minimum_context_ms: int
    voice_requirement: str
    resource_class: str
    adapter: str
    profile_hash: str
    configuration_hash: str

    @classmethod
    def parse(cls, value: object) -> RegistryProfile:
        if not isinstance(value, dict) or not (
            _PROFILE_REQUIRED_FIELDS <= set(value) <= _PROFILE_FIELDS
        ):
            raise ConfigurationError("registry profile fields do not match schema v1")
        profile_id = _require_text(value["profile_id"], "profile_id")
        if _PROFILE_ID.fullmatch(profile_id) is None:
            raise ConfigurationError(f"invalid profile_id: {profile_id!r}")
        if value["adapter_api_version"] != 1:
            raise ConfigurationError(f"{profile_id}: adapter_api_version must be 1")
        if type(value["streaming"]) is not bool:
            raise ConfigurationError(f"{profile_id}: streaming must be boolean")
        weight_revision = value["weight_revision"]
        if weight_revision is not None:
            weight_revision = _require_text(weight_revision, "weight_revision")
        runtime = value["runtime"]
        if not isinstance(runtime, dict) or not (
            _RUNTIME_REQUIRED_FIELDS <= set(runtime) <= _RUNTIME_FIELDS
        ):
            raise ConfigurationError(f"{profile_id}: runtime shape is invalid")
        worker_module = runtime.get("worker_module")
        if worker_module is not None and (
            not isinstance(worker_module, str)
            or _WORKER_MODULE.fullmatch(worker_module) is None
        ):
            raise ConfigurationError(f"{profile_id}: runtime.worker_module is invalid")
        configuration = runtime["configuration"]
        if not isinstance(configuration, dict):
            raise ConfigurationError(f"{profile_id}: configuration must be an object")
        _reject_private_configuration_keys(
            configuration, location=f"{profile_id}.runtime.configuration"
        )
        timeouts = value["timeouts"]
        if not isinstance(timeouts, dict) or set(timeouts) != {
            "first_output_ms",
            "stall_ms",
        }:
            raise ConfigurationError(f"{profile_id}: timeout shape is invalid")
        _require_int(timeouts["first_output_ms"], "first_output_ms", minimum=1)
        _require_int(timeouts["stall_ms"], "stall_ms", minimum=1)
        _require_int(runtime["max_vram_mb"], "max_vram_mb")
        promotion = value.get("promotion")
        if promotion is not None:
            if not isinstance(promotion, dict) or set(promotion) != _PROMOTION_FIELDS:
                raise ConfigurationError(f"{profile_id}: promotion shape is invalid")
            if promotion["status"] not in {"technical_validation", "approved"}:
                raise ConfigurationError(f"{profile_id}: promotion status is invalid")
            pack_id = promotion["pack_id"]
            if not isinstance(pack_id, str) or _PACK_ID.fullmatch(pack_id) is None:
                raise ConfigurationError(f"{profile_id}: promotion pack ID is invalid")
            for field in ("pack_sha256", "evidence_sha256", "endpoint_sha256"):
                digest = promotion[field]
                if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
                    raise ConfigurationError(
                        f"{profile_id}: promotion {field} is invalid"
                    )
        profile_for_hash = json.loads(json.dumps(value, allow_nan=False))
        profile_for_hash["runtime"].pop("worker_endpoint")
        if profile_for_hash["runtime"].get("worker_module") is None:
            profile_for_hash["runtime"].pop("worker_module", None)
        return cls(
            profile_id=profile_id,
            kind=_require_text(value["kind"], "kind"),
            readiness=_require_text(value["readiness"], "readiness"),
            implementation_revision=_require_text(
                value["implementation_revision"], "implementation_revision"
            ),
            weight_revision=weight_revision,
            streaming=value["streaming"],
            cancellation=_require_text(value["cancellation"], "cancellation"),
            input_sample_rates=_integer_list(
                value["input_sample_rates"], "input_sample_rates"
            ),
            output_sample_rates=_integer_list(
                value["output_sample_rates"], "output_sample_rates"
            ),
            frame_ms=_require_int(value["frame_ms"], "frame_ms", minimum=1),
            minimum_context_ms=_require_int(
                value["minimum_context_ms"], "minimum_context_ms"
            ),
            voice_requirement=_require_text(
                value["voice_requirement"], "voice_requirement"
            ),
            resource_class=_require_text(value["resource_class"], "resource_class"),
            adapter=_require_text(runtime["adapter"], "runtime.adapter"),
            profile_hash=_canonical_hash(profile_for_hash),
            configuration_hash=_canonical_hash(configuration),
        )

    def safe_metadata(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "kind": self.kind,
            "readiness": self.readiness,
            "implementation_revision": self.implementation_revision,
            "weight_revision": self.weight_revision,
            "streaming": self.streaming,
            "cancellation": self.cancellation,
            "frame_ms": self.frame_ms,
            "minimum_context_ms": self.minimum_context_ms,
            "voice_requirement": self.voice_requirement,
            "resource_class": self.resource_class,
            "profile_hash": self.profile_hash,
            "configuration_hash": self.configuration_hash,
        }


class ProfileRegistry:
    def __init__(self, profiles: Mapping[str, RegistryProfile], document_hash: str):
        self._profiles = dict(profiles)
        self.document_hash = document_hash

    @classmethod
    def load(cls, path: Path) -> ProfileRegistry:
        resolved = path.expanduser().resolve()
        if any(_SENSITIVE_FILENAME.search(part) for part in resolved.parts):
            raise ConfigurationError(
                "external profile registry path looks credential-bearing"
            )
        try:
            raw = resolved.read_bytes()
        except OSError as exc:
            raise ConfigurationError(
                "external profile registry is not readable"
            ) from exc
        try:
            document = json.loads(
                raw,
                object_pairs_hook=_object,
                parse_constant=_reject_constant,
                parse_float=_finite_float,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConfigurationError(
                "external profile registry is not valid JSON"
            ) from exc
        if not isinstance(document, dict) or set(document) != {
            "schema_version",
            "profiles",
        }:
            raise ConfigurationError("registry document fields do not match schema v1")
        if document["schema_version"] != 1:
            raise ConfigurationError("registry schema_version must be 1")
        values = document["profiles"]
        if not isinstance(values, list) or not values:
            raise ConfigurationError("registry profiles must be a non-empty array")
        profiles: dict[str, RegistryProfile] = {}
        for value in values:
            profile = RegistryProfile.parse(value)
            if profile.profile_id in profiles:
                raise ConfigurationError(f"duplicate profile_id: {profile.profile_id}")
            profiles[profile.profile_id] = profile
        return cls(profiles, _canonical_hash(document))

    def require_route_profiles(
        self, profile_ids: Sequence[str], *, voice_id_present: bool
    ) -> tuple[RegistryProfile, ...]:
        selected: list[RegistryProfile] = []
        for profile_id in profile_ids:
            profile = self._profiles.get(profile_id)
            if profile is None:
                raise ConfigurationError(
                    f"profile is absent from registry: {profile_id}"
                )
            if profile.readiness != "ready" or not profile.streaming:
                raise ConfigurationError(
                    f"profile is not ready and streaming: {profile_id}"
                )
            if profile.kind != "voice_conversion" or profile.adapter != "worker":
                raise ConfigurationError(
                    f"profile is not a worker-backed real VC route: {profile_id}"
                )
            if 48_000 not in profile.input_sample_rates or 48_000 not in (
                profile.output_sample_rates
            ):
                raise ConfigurationError(
                    f"profile lacks 48 kHz input/output: {profile_id}"
                )
            if profile.frame_ms != 20:
                raise ConfigurationError(
                    f"profile does not use 20 ms frames: {profile_id}"
                )
            if profile.voice_requirement == "authorized_target_required" and not (
                voice_id_present
            ):
                raise ConfigurationError(f"profile requires a voice ID: {profile_id}")
            selected.append(profile)
        return tuple(selected)


def finite_json(value: object) -> bool:
    """Used by tests to prove registry-derived metadata contains no NaN/Infinity."""

    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, Mapping):
        return all(finite_json(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return all(finite_json(item) for item in value)
    return True
