from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from .config import RunConfiguration
from .errors import HarnessError
from .registry import ProfileRegistry
from .suite import run_route_suite


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the metadata-redacted EXP-003 technical real-model Gateway route"
        )
    )
    parser.add_argument("--gateway-url")
    parser.add_argument("--origin")
    parser.add_argument("--profile-registry", type=Path)
    parser.add_argument(
        "--profiles",
        help="comma-separated distinct registry profile IDs (at least two)",
    )
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--batch-frames", type=int)
    parser.add_argument("--partial-frames", type=int)
    parser.add_argument("--cancel-frames", type=int)
    return parser


def _configuration(arguments: argparse.Namespace) -> RunConfiguration:
    environment = dict(os.environ)
    overrides = {
        "LIVECONV_EXP003_GATEWAY_URL": arguments.gateway_url,
        "LIVECONV_EXP003_ORIGIN": arguments.origin,
        "LIVECONV_EXP003_PROFILE_REGISTRY": (
            str(arguments.profile_registry) if arguments.profile_registry else None
        ),
        "LIVECONV_EXP003_PROFILE_IDS": arguments.profiles,
        "LIVECONV_EXP003_TRACE": str(arguments.trace) if arguments.trace else None,
        "LIVECONV_EXP003_TIMEOUT_SECONDS": arguments.timeout_seconds,
        "LIVECONV_EXP003_BATCH_FRAMES": arguments.batch_frames,
        "LIVECONV_EXP003_PARTIAL_FRAMES": arguments.partial_frames,
        "LIVECONV_EXP003_CANCEL_FRAMES": arguments.cancel_frames,
    }
    for name, value in overrides.items():
        if value is not None:
            environment[name] = str(value)
    return RunConfiguration.from_environment(environment)


async def _run(configuration: RunConfiguration) -> int:
    registry = ProfileRegistry.load(configuration.registry_path)
    trace = await run_route_suite(configuration, registry)
    destination = trace.write(configuration.trace_path)
    outcome = trace.document()["technical_outcome"]
    print(
        f"EXP-003 technical_outcome={outcome} decision_status=inconclusive "
        f"trace={destination}"
    )
    return 0 if outcome == "passed" else 1


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        return asyncio.run(_run(_configuration(arguments)))
    except (HarnessError, OSError, ValueError) as exc:
        print(f"EXP-003 configuration/transport failure: {exc}", file=sys.stderr)
        return 2
