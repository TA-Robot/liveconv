from __future__ import annotations

import os

import pytest

from liveconv_exp004_rvc_gateway_smoke.config import RunConfiguration
from liveconv_exp004_rvc_gateway_smoke.suite import run_smoke


@pytest.mark.live
@pytest.mark.asyncio
async def test_disposable_retained_rvc_gateway_smoke() -> None:
    if os.environ.get("LIVECONV_EXP004_RUN_REAL") != "1":
        pytest.skip("set LIVECONV_EXP004_RUN_REAL=1 for the disposable RVC route")
    configuration = RunConfiguration.from_environment()
    trace = await run_smoke(configuration)
    trace.write(configuration.trace_path)
    document = trace.document()
    assert document["technical_outcome"] == "passed"
    assert document["decision_status"] == "inconclusive"
    assert document["claims"]["voice_conversion_established"] is False
