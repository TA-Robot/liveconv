from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence

from .config import RunConfiguration
from .errors import SmokeError
from .suite import run_smoke


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Run the opt-in EXP-004 one-profile RVC Gateway technical smoke"
    )


async def _run() -> int:
    configuration = RunConfiguration.from_environment()
    trace = await run_smoke(configuration)
    destination = trace.write(configuration.trace_path)
    outcome = trace.document()["technical_outcome"]
    print(
        f"EXP-004 technical_outcome={outcome} decision_status=inconclusive "
        f"trace={destination}"
    )
    return 0 if outcome == "passed" else 1


def main(argv: Sequence[str] | None = None) -> int:
    _parser().parse_args(argv)
    if os.environ.get("LIVECONV_EXP004_RUN_REAL") != "1":
        print(
            "EXP-004 is opt-in; set LIVECONV_EXP004_RUN_REAL=1 to run it",
            file=sys.stderr,
        )
        return 2
    try:
        return asyncio.run(_run())
    except (OSError, SmokeError, ValueError) as exc:
        print(
            f"EXP-004 configuration/route failure: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 2
