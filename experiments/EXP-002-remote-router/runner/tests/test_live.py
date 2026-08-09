from __future__ import annotations

import os

import pytest

from liveconv_router_experiment.suite import RunnerConfig, run_experiment
from liveconv_router_experiment.trace import TraceRecorder


@pytest.mark.live
@pytest.mark.asyncio
async def test_optional_disposable_live_gateway(tmp_path) -> None:
    gateway_url = os.environ.get("LIVECONV_LIVE_GATEWAY_URL")
    token = os.environ.get("LIVECONV_API_TOKEN")
    origin = os.environ.get(
        "LIVECONV_LIVE_ORIGIN",
        "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
    )
    if not gateway_url or not token:
        pytest.skip(
            "set LIVECONV_LIVE_GATEWAY_URL and LIVECONV_API_TOKEN for live fault smoke"
        )

    trace = TraceRecorder("pytest-live-client")
    result = await run_experiment(
        RunnerConfig(gateway_url=gateway_url, token=token, origin=origin),
        trace=trace,
    )
    trace.write(tmp_path / "router-trace.json")
    assert result.route_smoke_passed
