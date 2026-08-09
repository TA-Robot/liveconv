from __future__ import annotations

import asyncio
import contextlib
from typing import Protocol

from .config import RunConfiguration
from .launcher import DisposableGateway
from .route import Pacer, RvcGatewayRoute
from .trace import TraceRecorder
from .transport import GatewayApi, HttpAdapter, WebSocketConnector


class GatewayContext(Protocol):
    gateway_url: str
    token: str

    async def __aenter__(self) -> GatewayContext: ...

    async def __aexit__(self, *_: object) -> None: ...


async def _run_at_gateway(
    configuration: RunConfiguration,
    trace: TraceRecorder,
    *,
    gateway_url: str,
    token: str,
    http: HttpAdapter | None,
    websockets: WebSocketConnector | None,
    pacer: Pacer | None,
) -> TraceRecorder:
    api = GatewayApi(
        gateway_url,
        token,
        configuration.origin,
        timeout_seconds=configuration.timeout_seconds,
        http=http,
        websockets=websockets,
    )
    route: RvcGatewayRoute | None = None
    session_id: str | None = None
    try:
        total_timeout = (
            configuration.generation_ready_timeout_seconds * 2
            + configuration.timeout_seconds * 8
            + 0.020 * (25 + configuration.tail_frames + configuration.cancel_frames)
        )
        async with asyncio.timeout(total_timeout):
            identity = await api.catalog_identity(
                configuration.profile_id,
                expected_profile_hash=configuration.expected_profile_hash,
                expected_configuration_hash=configuration.expected_configuration_hash,
            )
            descriptor = await api.create_session(identity)
            session_id = descriptor.session_id
            route = await RvcGatewayRoute.attach(
                api,
                trace,
                descriptor,
                timeout_seconds=configuration.timeout_seconds,
                generation_ready_timeout_seconds=(
                    configuration.generation_ready_timeout_seconds
                ),
                pacer=pacer,
            )
            await route.run_full_batch_with_tail(configuration.tail_frames)
            await route.run_cancel(
                configuration.cancel_frames,
                stale_grace_seconds=configuration.stale_grace_seconds,
            )
            await route.close()
            route = None
            delete_status = await api.delete_session(session_id)
            if delete_status != 204:
                raise RuntimeError("Gateway session deletion did not return 204")
            after_delete_status = await api.get_session(session_id)
            if after_delete_status != 404:
                raise RuntimeError("Gateway session was visible after deletion")
            trace.add_result(
                "session_close_delete_404",
                passed=True,
                evidence={
                    "session_close_acknowledged": True,
                    "delete_http_status": delete_status,
                    "get_after_delete_http_status": after_delete_status,
                    "session_invalidated": True,
                },
            )
        trace.finish(True)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        trace.add_result(
            "harness_failure",
            passed=False,
            evidence={
                "failure_type": type(exc).__name__,
                "free_form_error_recorded": False,
            },
        )
        trace.finish(False)
        if route is not None:
            await route.abort()
        if session_id is not None:
            with contextlib.suppress(Exception):
                await api.delete_session(session_id)
    finally:
        await api.close()
    return trace


async def run_smoke(
    configuration: RunConfiguration,
    *,
    http: HttpAdapter | None = None,
    websockets: WebSocketConnector | None = None,
    pacer: Pacer | None = None,
) -> TraceRecorder:
    """Run the exact one-profile technical route and retain only safe metadata."""

    trace = TraceRecorder(
        git_commit=configuration.git_commit,
        profile_id=configuration.profile_id,
        persisted_evidence_verified=configuration.persisted_evidence_verified,
    )
    if not configuration.auto_launch:
        return await _run_at_gateway(
            configuration,
            trace,
            gateway_url=configuration.gateway_url or "",
            token=configuration.api_token,
            http=http,
            websockets=websockets,
            pacer=pacer,
        )
    if http is not None or websockets is not None:
        raise ValueError("fake transports require an explicit Gateway URL")
    async with DisposableGateway(configuration) as gateway:
        return await _run_at_gateway(
            configuration,
            trace,
            gateway_url=gateway.gateway_url,
            token=gateway.token,
            http=None,
            websockets=None,
            pacer=pacer,
        )
