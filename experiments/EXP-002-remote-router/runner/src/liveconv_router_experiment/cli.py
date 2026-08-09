from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from .errors import ExperimentFailure
from .launcher import LocalGateway
from .suite import ExperimentResult, RunnerConfig, run_experiment
from .trace import TraceRecorder

DEFAULT_ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="liveconv-router-experiment",
        description=(
            "Run the bounded EXP-002 route smoke against a launched or existing "
            "audio gateway. This does not produce an EXP-002 decision."
        ),
    )
    parser.add_argument(
        "--scope",
        choices=("route-smoke-v1",),
        default="route-smoke-v1",
    )
    parser.add_argument(
        "--gateway-url",
        help="Existing gateway origin. When omitted, launch a loopback gateway.",
    )
    parser.add_argument(
        "--token-env",
        default="LIVECONV_API_TOKEN",
        help="Environment variable containing the bearer credential.",
    )
    parser.add_argument("--origin", default=DEFAULT_ORIGIN)
    parser.add_argument("--profile-config", type=Path)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument(
        "--trace",
        type=Path,
        default=Path(tempfile.gettempdir()) / "liveconv-exp-002-router-trace.json",
    )
    return parser


def _local_credential() -> str:
    required_alphabet = "0123456789abcdefghijklmnopqrstuvwxyz-"
    return f"{required_alphabet}{secrets.token_urlsafe(32)}"


def _repository_state() -> tuple[str, bool]:
    try:
        commit = subprocess.run(  # noqa: S603 - fixed local Git inspection
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        status = subprocess.run(  # noqa: S603 - fixed local Git inspection
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return "unrecorded", False
    return commit if len(commit) == 40 else "unrecorded", not status


async def _execute(args: argparse.Namespace, trace: TraceRecorder) -> ExperimentResult:
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")
    if args.gateway_url:
        token = os.environ.get(args.token_env, "")
        if not token:
            raise ExperimentFailure(
                "existing gateway mode requires the configured "
                "token environment variable"
            )
        return await run_experiment(
            RunnerConfig(
                gateway_url=args.gateway_url,
                token=token,
                origin=args.origin,
                timeout_seconds=args.timeout,
            ),
            trace=trace,
        )

    token = _local_credential()
    async with LocalGateway(
        token=token,
        origin=args.origin,
        profile_config=args.profile_config,
    ) as gateway:
        return await run_experiment(
            RunnerConfig(
                gateway_url=gateway.base_url,
                token=token,
                origin=args.origin,
                timeout_seconds=args.timeout,
            ),
            trace=trace,
        )


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    git_commit, worktree_clean = _repository_state()
    trace = TraceRecorder(
        f"client-{uuid4().hex}",
        git_commit=git_commit,
        worktree_clean=worktree_clean,
    )
    exit_code = 2
    result: ExperimentResult | None = None
    try:
        result = asyncio.run(_execute(args, trace))
        exit_code = 0 if result.route_smoke_passed else 1
    except (ExperimentFailure, ValueError) as exc:
        trace.add_result(
            "runner.failure",
            passed=False,
            evidence={"failure_type": type(exc).__name__},
        )
        print(f"runner failed: {type(exc).__name__}", file=sys.stderr)
    finally:
        destination = trace.write(args.trace)
        print(f"trace: {destination}")

    if result is not None:
        for case in result.cases:
            status = "ROUTE_SMOKE_PASS" if case.passed else "ROUTE_SMOKE_FAIL"
            print(f"{status} {case.case_id}")
        print("EXP-002 decision: INCONCLUSIVE (full evidence was not collected)")
    raise SystemExit(exit_code)
