from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

_CHROME_EXTENSION_ORIGIN = re.compile(r"^chrome-extension://[a-p]{32}$")
MIN_TOKEN_BYTES = 32
MIN_TOKEN_UNIQUE_CHARACTERS = 16


def _default_profile_path() -> Path:
    return Path(str(files("liveconv_audio").joinpath("default-model-profiles.json")))


def _default_roster_path() -> Path:
    return Path(str(files("liveconv_audio").joinpath("default-model-roster.json")))


def _positive_number(name: str, default: str, *, integer: bool = False) -> float | int:
    raw = os.environ.get(name, default)
    try:
        value = int(raw) if integer else float(raw)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if (not integer and not math.isfinite(value)) or value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _boolean(name: str, default: str = "0") -> bool:
    raw = os.environ.get(name, default)
    if raw not in {"0", "1"}:
        raise ValueError(f"{name} must be 0 or 1")
    return raw == "1"


@dataclass(frozen=True, slots=True)
class Settings:
    api_token: str
    allowed_origins: frozenset[str]
    profile_config: Path
    roster_config: Path | None = None
    deployment_bundle_config: Path | None = None
    ticket_ttl_seconds: float = 30.0
    attach_timeout_seconds: float = 5.0
    ingress_budget_ms: int = 500
    max_sessions: int = 64
    max_pending_attachments: int = 32
    session_lifetime_seconds: float = 1800.0
    request_cache_max: int = 1024
    send_timeout_seconds: float = 1.0
    allow_technical_profiles: bool = False
    bind_host: str = "127.0.0.1"
    bind_port: int = 8765

    @classmethod
    def from_env(cls) -> Settings:
        origins = frozenset(
            origin.strip()
            for origin in os.environ.get("LIVECONV_ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        )
        deployment_bundle = os.environ.get("LIVECONV_DEPLOYMENT_BUNDLE")
        return cls(
            api_token=os.environ.get("LIVECONV_API_TOKEN", ""),
            allowed_origins=origins,
            profile_config=Path(
                os.environ.get("LIVECONV_PROFILE_CONFIG", _default_profile_path())
            ).resolve(),
            roster_config=Path(
                os.environ.get("LIVECONV_ROSTER_CONFIG", _default_roster_path())
            ).resolve(),
            deployment_bundle_config=(
                Path(deployment_bundle).resolve() if deployment_bundle else None
            ),
            ticket_ttl_seconds=float(
                _positive_number("LIVECONV_TICKET_TTL_SECONDS", "30")
            ),
            attach_timeout_seconds=float(
                _positive_number("LIVECONV_ATTACH_TIMEOUT_SECONDS", "5")
            ),
            ingress_budget_ms=int(
                _positive_number("LIVECONV_INGRESS_BUDGET_MS", "500", integer=True)
            ),
            max_sessions=int(
                _positive_number("LIVECONV_MAX_SESSIONS", "64", integer=True)
            ),
            max_pending_attachments=int(
                _positive_number("LIVECONV_MAX_PENDING_ATTACHMENTS", "32", integer=True)
            ),
            session_lifetime_seconds=float(
                _positive_number("LIVECONV_SESSION_LIFETIME_SECONDS", "1800")
            ),
            request_cache_max=int(
                _positive_number("LIVECONV_REQUEST_CACHE_MAX", "1024", integer=True)
            ),
            send_timeout_seconds=float(
                _positive_number("LIVECONV_SEND_TIMEOUT_SECONDS", "1")
            ),
            allow_technical_profiles=_boolean("LIVECONV_ALLOW_TECHNICAL_PROFILES"),
            bind_host=os.environ.get("LIVECONV_BIND_HOST", "127.0.0.1"),
            bind_port=int(_positive_number("LIVECONV_BIND_PORT", "8765", integer=True)),
        )

    @property
    def configuration_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        token_bytes = self.api_token.encode("utf-8")
        if len(token_bytes) < MIN_TOKEN_BYTES:
            errors.append(
                f"LIVECONV_API_TOKEN must contain at least {MIN_TOKEN_BYTES} bytes"
            )
        if len(set(self.api_token)) < MIN_TOKEN_UNIQUE_CHARACTERS:
            errors.append(
                "LIVECONV_API_TOKEN must contain at least "
                f"{MIN_TOKEN_UNIQUE_CHARACTERS} distinct characters"
            )
        if not all(0x21 <= ord(character) <= 0x7E for character in self.api_token):
            errors.append("LIVECONV_API_TOKEN must use visible ASCII characters")
        if not self.allowed_origins:
            errors.append("LIVECONV_ALLOWED_ORIGINS is not configured")
        invalid_origins = sorted(
            origin
            for origin in self.allowed_origins
            if _CHROME_EXTENSION_ORIGIN.fullmatch(origin) is None
        )
        if invalid_origins:
            errors.append(
                "every allowed Origin must be an exact Chrome Extension origin"
            )
        if self.ingress_budget_ms < 20:
            errors.append("ingress budget must hold at least one v1 frame")
        if self.allow_technical_profiles and self.bind_host not in {
            "127.0.0.1",
            "::1",
            "localhost",
        }:
            errors.append("technical profiles require a loopback bind host")
        if self.allow_technical_profiles and self.max_sessions != 1:
            errors.append("technical profiles require max_sessions=1")
        return tuple(errors)

    @property
    def token_is_acceptable(self) -> bool:
        return (
            len(self.api_token.encode("utf-8")) >= MIN_TOKEN_BYTES
            and len(set(self.api_token)) >= MIN_TOKEN_UNIQUE_CHARACTERS
            and all(0x21 <= ord(character) <= 0x7E for character in self.api_token)
        )

    @property
    def origins_are_acceptable(self) -> bool:
        return bool(self.allowed_origins) and all(
            _CHROME_EXTENSION_ORIGIN.fullmatch(origin) is not None
            for origin in self.allowed_origins
        )
