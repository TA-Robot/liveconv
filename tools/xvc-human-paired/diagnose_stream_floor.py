#!/usr/bin/env python3
"""Run EXP-032, the final 100-to-125 ms e8 lookahead floor diagnostic."""

from __future__ import annotations

from collections.abc import Sequence

import diagnose_stream_position as diagnostic

FUTURE_VALUES_MS = (100, 110, 120, 125)
EXPECTED_CONTROL_HASHES = {
    100: "cedff001ee6254ea91efdc9f1b41ad42e7367ddab98ec5944f5e26d59261ab9e",
    125: "53f38f2702eaa7a84b282c7894d6dc532f4a9d9ce42580b37728f76879dfd1e2",
}


def main(argv: Sequence[str] | None = None) -> int:
    diagnostic.FUTURE_VALUES_MS = FUTURE_VALUES_MS
    diagnostic.EXPERIMENT_NUMBER = 32
    diagnostic.EXPECTED_CONTROL_HASHES = EXPECTED_CONTROL_HASHES
    return diagnostic.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
