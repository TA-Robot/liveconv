from __future__ import annotations

import os

import pytest

from liveconv_real_model_route.config import RunConfiguration
from liveconv_real_model_route.registry import ProfileRegistry
from liveconv_real_model_route.suite import run_route_suite


@pytest.mark.live
@pytest.mark.asyncio
async def test_disposable_real_model_gateway_route() -> None:
    if os.environ.get("LIVECONV_EXP003_RUN_REAL") != "1":
        pytest.skip("set LIVECONV_EXP003_RUN_REAL=1 for the disposable real route")
    configuration = RunConfiguration.from_environment()
    registry = ProfileRegistry.load(configuration.registry_path)
    trace = await run_route_suite(configuration, registry)
    trace.write(configuration.trace_path)
    document = trace.document()
    assert document["technical_outcome"] == "passed"
    assert document["decision_status"] == "inconclusive"
    assert document["claims"]["voice_conversion_established"] is False
