from __future__ import annotations

import ipaddress
import math
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .errors import ConfigurationError

_CHROME_EXTENSION_ORIGIN = re.compile(r"^chrome-extension://[a-p]{32}$")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SENSITIVE_FILENAME = re.compile(
    r"(^key$|^\.env($|\.)|credential|private.?key|secret|token)", re.IGNORECASE
)


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} is required")
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


def _positive_float(environment: Mapping[str, str], name: str, default: float) -> float:
    raw = environment.get(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be numeric") from exc
    if not math.isfinite(value) or value <= 0:
        raise ConfigurationError(f"{name} must be finite and greater than zero")
    return value


def _loopback(hostname: str | None) -> bool:
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
            "Gateway URL must not contain a path, query, or fragment"
        )
    if parsed.scheme == "http" and not _loopback(parsed.hostname):
        raise ConfigurationError("plain HTTP is allowed only for a loopback Gateway")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def _profile_ids(raw: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    if len(values) < 2:
        raise ConfigurationError(
            "LIVECONV_EXP003_PROFILE_IDS must name at least two profiles"
        )
    if len(set(values)) != len(values):
        raise ConfigurationError("profile IDs must be distinct")
    return values


def _verify_git_state(expected_commit: str) -> None:
    try:
        head = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ("git", "status", "--porcelain", "--untracked-files=normal"),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ConfigurationError("EXP-003 requires a readable Git worktree") from exc
    if head != expected_commit:
        raise ConfigurationError("LIVECONV_EXP003_GIT_COMMIT differs from Git HEAD")
    if dirty:
        raise ConfigurationError("persisted EXP-003 runs require a clean worktree")


@dataclass(frozen=True, slots=True)
class RunConfiguration:
    gateway_url: str
    origin: str
    registry_path: Path
    profile_ids: tuple[str, ...]
    trace_path: Path
    api_token: str = field(repr=False)
    voice_id: str | None = field(default=None, repr=False)
    timeout_seconds: float = 10.0
    batch_frames: int = 25
    partial_frames: int = 3
    cancel_frames: int = 2
    git_commit: str = "unrecorded"
    worktree_clean: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "gateway_url", validate_gateway_url(self.gateway_url))
        if not self.api_token:
            raise ConfigurationError("Gateway bearer credential must not be empty")
        if _CHROME_EXTENSION_ORIGIN.fullmatch(self.origin) is None:
            raise ConfigurationError("Origin must be an exact Chrome Extension origin")
        if len(self.profile_ids) < 2 or len(set(self.profile_ids)) != len(
            self.profile_ids
        ):
            raise ConfigurationError("at least two distinct profile IDs are required")
        if self.batch_frames < 2:
            raise ConfigurationError("batch_frames must be at least two")
        if self.batch_frames > 500:
            raise ConfigurationError("batch_frames must not exceed 500")
        if not 0 < self.partial_frames < self.batch_frames:
            raise ConfigurationError(
                "partial_frames must be between zero and batch_frames"
            )
        if not 0 < self.cancel_frames < self.batch_frames:
            raise ConfigurationError(
                "cancel_frames must be between zero and batch_frames"
            )
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ConfigurationError("timeout_seconds must be positive and finite")
        if (
            self.git_commit != "unrecorded"
            and _GIT_COMMIT.fullmatch(self.git_commit) is None
        ):
            raise ConfigurationError("git_commit must be a lowercase 40-hex SHA")
        registry = self.registry_path.expanduser().resolve()
        trace = self.trace_path.expanduser().resolve()
        if registry == trace:
            raise ConfigurationError("trace destination must differ from registry")
        if any(_SENSITIVE_FILENAME.search(part) for part in trace.parts):
            raise ConfigurationError("trace destination looks credential-bearing")

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> RunConfiguration:
        env = os.environ if environment is None else environment
        registry_path = Path(
            _required(env, "LIVECONV_EXP003_PROFILE_REGISTRY")
        ).expanduser()
        voice_id = env.get("LIVECONV_EXP003_VOICE_ID") or None
        clean_value = _required(env, "LIVECONV_EXP003_WORKTREE_CLEAN").lower()
        if clean_value not in {"0", "1", "false", "true"}:
            raise ConfigurationError(
                "LIVECONV_EXP003_WORKTREE_CLEAN must be true/false or 1/0"
            )
        if clean_value not in {"1", "true"}:
            raise ConfigurationError("persisted EXP-003 runs require a clean worktree")
        git_commit = _required(env, "LIVECONV_EXP003_GIT_COMMIT")
        trace_path = Path(_required(env, "LIVECONV_EXP003_TRACE")).expanduser()
        configuration = cls(
            gateway_url=_required(env, "LIVECONV_EXP003_GATEWAY_URL"),
            origin=_required(env, "LIVECONV_EXP003_ORIGIN"),
            registry_path=registry_path,
            profile_ids=_profile_ids(_required(env, "LIVECONV_EXP003_PROFILE_IDS")),
            trace_path=trace_path,
            api_token=_required(env, "LIVECONV_API_TOKEN"),
            voice_id=voice_id,
            timeout_seconds=_positive_float(
                env, "LIVECONV_EXP003_TIMEOUT_SECONDS", 10.0
            ),
            batch_frames=_positive_int(env, "LIVECONV_EXP003_BATCH_FRAMES", 25),
            partial_frames=_positive_int(env, "LIVECONV_EXP003_PARTIAL_FRAMES", 3),
            cancel_frames=_positive_int(env, "LIVECONV_EXP003_CANCEL_FRAMES", 2),
            git_commit=git_commit,
            worktree_clean=True,
        )
        _verify_git_state(configuration.git_commit)
        return configuration

    def with_overrides(
        self,
        *,
        gateway_url: str | None = None,
        origin: str | None = None,
        registry_path: Path | None = None,
        profile_ids: Sequence[str] | None = None,
        trace_path: Path | None = None,
    ) -> RunConfiguration:
        return RunConfiguration(
            gateway_url=gateway_url or self.gateway_url,
            origin=origin or self.origin,
            registry_path=registry_path or self.registry_path,
            profile_ids=tuple(profile_ids) if profile_ids else self.profile_ids,
            trace_path=trace_path or self.trace_path,
            api_token=self.api_token,
            voice_id=self.voice_id,
            timeout_seconds=self.timeout_seconds,
            batch_frames=self.batch_frames,
            partial_frames=self.partial_frames,
            cancel_frames=self.cancel_frames,
            git_commit=self.git_commit,
            worktree_clean=self.worktree_clean,
        )
