from __future__ import annotations

import asyncio
import contextlib

from .config import RunConfiguration
from .registry import ProfileRegistry, RegistryProfile
from .route import GatewayRoute, Pacer
from .trace import MonotonicClock, TraceRecorder
from .transport import GatewayApi, HttpAdapter, SessionDescriptor, WebSocketConnector


def _bootstrap_profile(profiles: tuple[RegistryProfile, ...]) -> RegistryProfile:
    """Bootstrap with the largest context so static credit is sufficient."""

    return max(profiles, key=lambda profile: profile.minimum_context_ms)


async def run_route_suite(
    configuration: RunConfiguration,
    registry: ProfileRegistry,
    *,
    http: HttpAdapter | None = None,
    websockets: WebSocketConnector | None = None,
    pacer: Pacer | None = None,
    trace_clock: MonotonicClock | None = None,
) -> TraceRecorder:
    profiles = registry.require_route_profiles(
        configuration.profile_ids,
        voice_id_present=configuration.voice_id is not None,
    )
    trace = TraceRecorder(
        profiles,
        registry.document_hash,
        clock=trace_clock,
        git_commit=configuration.git_commit,
        worktree_clean=configuration.worktree_clean,
    )
    api = GatewayApi(
        configuration.gateway_url,
        configuration.api_token,
        configuration.origin,
        trace,
        timeout_seconds=configuration.timeout_seconds,
        http=http,
        websockets=websockets,
    )
    route: GatewayRoute | None = None
    descriptor: SessionDescriptor | None = None
    try:
        paced_seconds = (
            len(profiles)
            * (configuration.batch_frames + configuration.partial_frames)
            * 0.020
            + configuration.cancel_frames * 0.020
        )
        control_budget = configuration.timeout_seconds * (len(profiles) * 4 + 8)
        async with asyncio.timeout(paced_seconds + control_budget):
            await api.validate_catalog(profiles)
            bootstrap = _bootstrap_profile(profiles)
            descriptor = await api.create_session(bootstrap, configuration.voice_id)
            route = await GatewayRoute.attach(
                api,
                trace,
                descriptor,
                timeout_seconds=configuration.timeout_seconds,
                batch_frames=configuration.batch_frames,
                pacer=pacer,
            )
            generation_id = 1
            for index, profile in enumerate(profiles):
                if route.profile_id != profile.profile_id:
                    await route.select_model(profile)
                await route.run_partial_flush(
                    profile,
                    generation_id,
                    configuration.partial_frames,
                )
                generation_id += 1
                if index == 0:
                    await route.run_cancel(
                        profile,
                        generation_id,
                        configuration.cancel_frames,
                    )
                    generation_id += 1
            await route.close()
            await route.finish_stale_exclusion()
            route = None
            await api.delete_session(descriptor)
            descriptor = None
        trace.finish(True)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        trace.add_result(
            "harness.failure",
            passed=False,
            evidence={
                "failure_type": type(exc).__name__,
                "sensitive_failure_message_recorded": False,
            },
        )
        trace.finish(False)
        if route is not None:
            await route.abort()
        if descriptor is not None:
            with contextlib.suppress(Exception):
                await api.delete_session(descriptor)
    finally:
        await api.close()
    return trace
