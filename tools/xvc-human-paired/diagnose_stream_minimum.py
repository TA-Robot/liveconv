#!/usr/bin/env python3
"""Run EXP-031, the minimum useful e8 streaming lookahead diagnostic."""

from __future__ import annotations

from collections.abc import Sequence

import diagnose_stream_position as diagnostic

FUTURE_VALUES_MS = (125, 150, 175, 200)
EXPECTED_CONTROL_HASHES = {
    200: "1e9debb9672c0a5e3353a98e465c980fac829a105e8319c040cba93c9c9b0321"
}


def main(argv: Sequence[str] | None = None) -> int:
    diagnostic.FUTURE_VALUES_MS = FUTURE_VALUES_MS
    diagnostic.EXPERIMENT_NUMBER = 31
    diagnostic.EXPECTED_CONTROL_HASHES = EXPECTED_CONTROL_HASHES
    return diagnostic.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
