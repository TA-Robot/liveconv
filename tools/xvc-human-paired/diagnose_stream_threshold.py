#!/usr/bin/env python3
"""Run EXP-030, the e8 minimum-lookahead threshold diagnostic."""

from __future__ import annotations

from collections.abc import Sequence

import diagnose_stream_position as diagnostic

FUTURE_VALUES_MS = (100, 200, 250, 300)
EXPECTED_CONTROL_HASHES = {
    100: "cedff001ee6254ea91efdc9f1b41ad42e7367ddab98ec5944f5e26d59261ab9e",
    300: "5840ad12ec0e66b6cb7788edd07440a9b5ebd7d7896f833b7f434d0c89f50707",
}


def main(argv: Sequence[str] | None = None) -> int:
    diagnostic.FUTURE_VALUES_MS = FUTURE_VALUES_MS
    diagnostic.EXPERIMENT_NUMBER = 30
    diagnostic.EXPECTED_CONTROL_HASHES = EXPECTED_CONTROL_HASHES
    return diagnostic.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
