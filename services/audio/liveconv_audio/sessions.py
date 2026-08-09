from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any
from uuid import uuid4

from liveconv_protocol import FrameOrderGuard, ParsedServerEvent


def _ticket_digest(ticket: str) -> bytes:
    return hashlib.sha256(ticket.encode("utf-8")).digest()


@dataclass(slots=True)
class CachedResponse:
    command_fingerprint: str
    response: ParsedServerEvent | None


@dataclass(slots=True)
class Session:
    session_id: str
    pipeline_id: str
    profile_id: str
    profile_hash: str
    configuration_hash: str
    voice_id: str | None
    ticket_digest: bytes
    ticket_expires_monotonic: float
    ingress_budget_ms: int
    max_ingress_frames: int
    created_monotonic: float
    expires_monotonic: float
    request_cache_limit: int
    status: str = "created"
    ticket_consumed: bool = False
    attached: bool = False
    deleted: bool = False
    order: FrameOrderGuard = field(default_factory=FrameOrderGuard)
    active_pipeline_id: str | None = None
    active_profile_id: str | None = None
    invalidated_generations: set[int] = field(default_factory=set)
    request_cache: dict[str, CachedResponse] = field(default_factory=dict)
    draining_generation_id: int | None = None
    last_source_monotonic_ns: int | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": 1,
            "session_id": self.session_id,
            "pipeline_id": self.pipeline_id,
            "profile_id": self.profile_id,
            "profile_hash": self.profile_hash,
            "configuration_hash": self.configuration_hash,
            "status": self.status,
            "active_generation_id": self.order.active_generation_id,
            "limits": {
                "ingress_budget_ms": self.ingress_budget_ms,
                "max_ingress_frames": self.max_ingress_frames,
            },
        }

    def remaining_lifetime(self) -> float:
        return max(0.0, self.expires_monotonic - time.monotonic())


class SessionCapacityError(RuntimeError):
    pass


class SessionStore:
    def __init__(
        self,
        ticket_ttl_seconds: float,
        ingress_budget_ms: int,
        max_sessions: int,
        session_lifetime_seconds: float,
        request_cache_limit: int,
    ) -> None:
        self._ticket_ttl_seconds = ticket_ttl_seconds
        self._ingress_budget_ms = ingress_budget_ms
        self._max_sessions = max_sessions
        self._session_lifetime_seconds = session_lifetime_seconds
        self._request_cache_limit = request_cache_limit
        self._sessions: dict[str, Session] = {}
        self._lock = RLock()

    def create(
        self,
        profile_id: str,
        profile_hash: str,
        configuration_hash: str,
        voice_id: str | None,
        frame_ms: int,
        ingress_budget_ms: int | None = None,
        max_ingress_frames: int | None = None,
    ) -> tuple[Session, str]:
        now = time.monotonic()
        ticket = secrets.token_urlsafe(32)
        with self._lock:
            self._prune_unusable_locked(now)
            if len(self._sessions) >= self._max_sessions:
                raise SessionCapacityError("maximum concurrent sessions reached")
            effective_ingress_budget_ms = max(
                self._ingress_budget_ms,
                ingress_budget_ms or self._ingress_budget_ms,
            )
            calculated_max_ingress_frames = max(
                1, effective_ingress_budget_ms // frame_ms
            )
            if max_ingress_frames is not None:
                if max_ingress_frames < 1:
                    raise ValueError("max_ingress_frames must be greater than zero")
                calculated_max_ingress_frames = min(
                    calculated_max_ingress_frames, max_ingress_frames
                )
            session = Session(
                session_id=str(uuid4()),
                pipeline_id=str(uuid4()),
                profile_id=profile_id,
                profile_hash=profile_hash,
                configuration_hash=configuration_hash,
                voice_id=voice_id,
                ticket_digest=_ticket_digest(ticket),
                ticket_expires_monotonic=now + self._ticket_ttl_seconds,
                ingress_budget_ms=effective_ingress_budget_ms,
                max_ingress_frames=calculated_max_ingress_frames,
                created_monotonic=now,
                expires_monotonic=now + self._session_lifetime_seconds,
                request_cache_limit=self._request_cache_limit,
            )
            self._sessions[session.session_id] = session
        return session, ticket

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None and self._is_unusable(session, time.monotonic()):
                self._sessions.pop(session_id, None)
                self._close_session(session)
                return None
            return session if session is not None and not session.deleted else None

    def consume_ticket(self, session_id: str, ticket: str) -> Session | None:
        candidate = _ticket_digest(ticket)
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.deleted or session.ticket_consumed:
                return None
            now = time.monotonic()
            if (
                now > session.ticket_expires_monotonic
                or now > session.expires_monotonic
            ):
                self._sessions.pop(session_id, None)
                self._close_session(session)
                return None
            if not secrets.compare_digest(session.ticket_digest, candidate):
                return None
            session.ticket_consumed = True
            session.ticket_digest = b""
            session.attached = True
            session.status = "attached"
            return session

    def delete(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is None:
                return None
            self._close_session(session)
            return session

    def expired_attached(self) -> list[Session]:
        now = time.monotonic()
        with self._lock:
            return [
                session
                for session in self._sessions.values()
                if session.attached and now >= session.expires_monotonic
            ]

    def _prune_unusable_locked(self, now: float) -> None:
        for session_id, session in list(self._sessions.items()):
            if self._is_unusable(session, now):
                self._sessions.pop(session_id, None)
                self._close_session(session)

    @staticmethod
    def _close_session(session: Session) -> None:
        session.deleted = True
        session.status = "closed"
        session.ticket_digest = b""
        session.attached = False
        session.request_cache.clear()
        session.invalidated_generations.clear()

    @staticmethod
    def _is_unusable(session: Session, now: float) -> bool:
        return (
            session.deleted
            or (not session.attached and now >= session.expires_monotonic)
            or (
                not session.attached
                and not session.ticket_consumed
                and now >= session.ticket_expires_monotonic
            )
            or (not session.attached and session.ticket_consumed)
        )

    @property
    def ticket_ttl_seconds(self) -> float:
        return self._ticket_ttl_seconds

    @property
    def count(self) -> int:
        with self._lock:
            self._prune_unusable_locked(time.monotonic())
            return len(self._sessions)
