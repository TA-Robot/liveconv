#!/usr/bin/env python3
"""Validate one or more JSON instances against a JSON Schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import FormatChecker
from jsonschema.validators import validator_for


def format_path(parts: list[object]) -> str:
    if not parts:
        return "$"
    return "$" + "".join(
        f"[{part}]" if isinstance(part, int) else f".{part}" for part in parts
    )


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: validate-json.py schema.json instance.json [...]", file=sys.stderr)
        return 2

    schema_path = Path(sys.argv[1])
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    validator = validator_class(schema, format_checker=FormatChecker())

    failed = False
    for raw_path in sys.argv[2:]:
        instance_path = Path(raw_path)
        instance = json.loads(instance_path.read_text(encoding="utf-8"))
        errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
        if not errors:
            print(f"ok   schema: {instance_path}")
            continue

        failed = True
        for error in errors:
            location = format_path(list(error.absolute_path))
            print(f"fail schema: {instance_path}:{location}: {error.message}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
