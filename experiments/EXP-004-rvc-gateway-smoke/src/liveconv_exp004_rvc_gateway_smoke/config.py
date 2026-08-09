from __future__ import annotations

import ipaddress
import math
import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from liveconv_audio.profiles import ProfileDocument, ProfileRegistry

from .errors import ConfigurationError

_CHROME_EXTENSION_ORIGIN = re.compile(r"^chrome-extension://[a-p]{32}$")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_RVC_PROFILE_ID = re.compile(r"^vc\.rvc\.[a-z0-9][a-z0-9.-]*\.v1$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_SENSITIVE_FILENAME = re.compile(
    r"(^key$|^\.env($|\.)|credential|private.?key|secret|token)", re.IGNORECASE
)

DEFAULT_ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
DEFAULT_PROFILE_ID = "vc.rvc.synthetic-ja.v1"
FULL_BATCH_FRAMES = 25
DEFAULT_TAIL_FRAMES = 3
DEFAULT_CANCEL_FRAMES = 1
DEFAULT_GENERATION_READY_TIMEOUT_SECONDS = 180.0


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} is required")
    return value


def _positive_float(environment: Mapping[str, str], name: str, default: float) -> float:
    raw = environment.get(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be numeric") from exc
    if not math.isfinite(value) or value <= 0:
        raise ConfigurationError(f"{name} must be a finite positive number")
    return value


def _positive_int(environment: Mapping[str, str], name: str, default: int) -> int:
    raw = environment.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return value


def _is_loopback(hostname: str | None) -> bool:
    if hostname is None:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def validate_gateway_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigurationError("Gateway URL must be an http(s) origin")
    if parsed.username or parsed.password:
        raise ConfigurationError("Gateway URL must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ConfigurationError(
            "Gateway URL must not include a path, query, or fragment"
        )
    if not _is_loopback(parsed.hostname):
        raise ConfigurationError("Gateway URL must use a loopback host")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def _repository_root() -> Path:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError(
            "cannot resolve the Git repository for persisted evidence"
        ) from exc
    return Path(completed.stdout.strip()).resolve()


def _verify_clean_commit(expected_commit: str) -> Path:
    if _GIT_COMMIT.fullmatch(expected_commit) is None:
        raise ConfigurationError(
            "LIVECONV_EXP004_GIT_COMMIT must be a lowercase 40-hex commit"
        )
    root = _repository_root()
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError(
            "cannot verify the Git commit for persisted evidence"
        ) from exc
    if head != expected_commit:
        raise ConfigurationError("LIVECONV_EXP004_GIT_COMMIT does not equal HEAD")
    if status:
        raise ConfigurationError(
            "persisted EXP-004 evidence requires a clean Git worktree"
        )
    return root


def _safe_profile_config(value: str) -> Path:
    candidate = Path(value).expanduser().resolve()
    if _SENSITIVE_FILENAME.search(candidate.name):
        raise ConfigurationError("profile configuration filename is not allowed")
    if not candidate.is_file():
        raise ConfigurationError("LIVECONV_EXP004_PROFILE_CONFIG must name a file")
    return candidate


def _generation_ready_timeout_from_envelope(first_output_ms: int | None) -> float:
    """Keep model cold start bounded, even when no profile envelope is supplied."""

    first_output_seconds = 0.0 if first_output_ms is None else first_output_ms / 1_000
    return max(DEFAULT_GENERATION_READY_TIMEOUT_SECONDS, first_output_seconds)


@dataclass(frozen=True, slots=True)
class RetainedProfileBinding:
    profile_hash: str
    configuration_hash: str
    first_output_ms: int


def load_retained_profile_binding(
    profile_config: Path, profile_id: str
) -> RetainedProfileBinding:
    try:
        document = ProfileDocument.model_validate_json(
            profile_config.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise ConfigurationError(
            "cannot read the retained RVC profile timeout envelope"
        ) from exc
    if len(document.profiles) != 1 or document.profiles[0].profile_id != profile_id:
        raise ConfigurationError(
            "profile configuration must contain exactly the selected RVC profile"
        )
    try:
        registry = ProfileRegistry.load(
            profile_config,
            allow_technical_profiles=True,
        )
    except (OSError, ValueError) as exc:
        raise ConfigurationError("cannot validate the retained RVC profile") from exc
    profile = registry.get_selectable(profile_id)
    if (
        profile is None
        or profile.kind != "voice_conversion"
        or profile.runtime.adapter != "worker"
        or profile.promotion is None
        or profile.promotion.status != "technical_validation"
    ):
        raise ConfigurationError(
            "profile configuration must contain one technical RVC worker profile"
        )
    return RetainedProfileBinding(
        profile_hash=profile.profile_hash,
        configuration_hash=profile.configuration_hash,
        first_output_ms=profile.timeouts.first_output_ms,
    )


@dataclass(frozen=True, slots=True)
class RunConfiguration:
    gateway_url: str | None
    profile_id: str
    origin: str
    trace_path: Path
    git_commit: str
    api_token: str = field(repr=False)
    profile_config: Path | None = field(repr=False)
    expected_profile_hash: str = field(repr=False)
    expected_configuration_hash: str = field(repr=False)
    timeout_seconds: float = 10.0
    generation_ready_timeout_seconds: float = DEFAULT_GENERATION_READY_TIMEOUT_SECONDS
    tail_frames: int = DEFAULT_TAIL_FRAMES
    cancel_frames: int = DEFAULT_CANCEL_FRAMES
    stale_grace_seconds: float = 0.2
    persisted_evidence_verified: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if self.gateway_url is not None:
            object.__setattr__(
                self, "gateway_url", validate_gateway_url(self.gateway_url)
            )
        if _RVC_PROFILE_ID.fullmatch(self.profile_id) is None:
            raise ConfigurationError("profile_id must be one retained RVC profile")
        if self.profile_config is None:
            raise ConfigurationError(
                "LIVECONV_EXP004_PROFILE_CONFIG is required for EXP-004"
            )
        binding = load_retained_profile_binding(self.profile_config, self.profile_id)
        if _SHA256.fullmatch(self.expected_profile_hash) is None:
            raise ConfigurationError("expected_profile_hash must be a sha256 identity")
        if _SHA256.fullmatch(self.expected_configuration_hash) is None:
            raise ConfigurationError(
                "expected_configuration_hash must be a sha256 identity"
            )
        if (
            self.expected_profile_hash != binding.profile_hash
            or self.expected_configuration_hash != binding.configuration_hash
        ):
            raise ConfigurationError(
                "expected hashes must match the retained RVC profile configuration"
            )
        if _CHROME_EXTENSION_ORIGIN.fullmatch(self.origin) is None:
            raise ConfigurationError("origin must be an exact Chrome Extension origin")
        if self.timeout_seconds <= 0 or not math.isfinite(self.timeout_seconds):
            raise ConfigurationError("timeout_seconds must be finite and positive")
        if (
            self.generation_ready_timeout_seconds
            < _generation_ready_timeout_from_envelope(binding.first_output_ms)
            or not math.isfinite(self.generation_ready_timeout_seconds)
        ):
            raise ConfigurationError(
                "generation_ready_timeout_seconds must cover the retained profile"
            )
        if not 0 < self.tail_frames < FULL_BATCH_FRAMES:
            raise ConfigurationError("tail_frames must be from 1 through 24")
        if not 0 < self.cancel_frames < FULL_BATCH_FRAMES:
            raise ConfigurationError("cancel_frames must be from 1 through 24")
        if self.stale_grace_seconds <= 0 or not math.isfinite(self.stale_grace_seconds):
            raise ConfigurationError("stale_grace_seconds must be finite and positive")
        if self.gateway_url is not None and not self.api_token:
            raise ConfigurationError(
                "LIVECONV_API_TOKEN is required for an external Gateway"
            )

    @property
    def auto_launch(self) -> bool:
        return self.gateway_url is None

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> RunConfiguration:
        values = os.environ if environment is None else environment
        trace_path = (
            Path(_required(values, "LIVECONV_EXP004_TRACE")).expanduser().resolve()
        )
        root = _verify_clean_commit(_required(values, "LIVECONV_EXP004_GIT_COMMIT"))
        try:
            trace_path.relative_to(root)
        except ValueError:
            pass
        else:
            raise ConfigurationError(
                "LIVECONV_EXP004_TRACE must be outside the repository"
            )

        gateway_url = values.get("LIVECONV_EXP004_GATEWAY_URL", "").strip() or None
        profile_config = _safe_profile_config(
            _required(values, "LIVECONV_EXP004_PROFILE_CONFIG")
        )
        profile_id = values.get(
            "LIVECONV_EXP004_PROFILE_ID", DEFAULT_PROFILE_ID
        ).strip()
        binding = load_retained_profile_binding(profile_config, profile_id)
        return cls(
            gateway_url=gateway_url,
            profile_id=profile_id,
            origin=values.get("LIVECONV_EXP004_ORIGIN", DEFAULT_ORIGIN).strip(),
            trace_path=trace_path,
            git_commit=_required(values, "LIVECONV_EXP004_GIT_COMMIT"),
            api_token=values.get("LIVECONV_API_TOKEN", ""),
            profile_config=profile_config,
            expected_profile_hash=binding.profile_hash,
            expected_configuration_hash=binding.configuration_hash,
            timeout_seconds=_positive_float(
                values, "LIVECONV_EXP004_TIMEOUT_SECONDS", 10.0
            ),
            generation_ready_timeout_seconds=_generation_ready_timeout_from_envelope(
                binding.first_output_ms
            ),
            tail_frames=_positive_int(
                values,
                "LIVECONV_EXP004_TAIL_FRAMES",
                DEFAULT_TAIL_FRAMES,
            ),
            cancel_frames=_positive_int(
                values, "LIVECONV_EXP004_CANCEL_FRAMES", DEFAULT_CANCEL_FRAMES
            ),
            stale_grace_seconds=_positive_float(
                values, "LIVECONV_EXP004_STALE_GRACE_SECONDS", 0.2
            ),
            persisted_evidence_verified=True,
        )
