from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runner import (
    AttemptObservation,
    EvidenceValidationError,
    ExperimentRun,
    ForcedFailureObservation,
    load_prompt_plan,
    load_roster,
    verify_clean_checkout,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a metadata-only EXP-005 manual evidence report."
    )
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--prompt-plan", type=Path, required=True)
    parser.add_argument("--manual-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        verify_clean_checkout(repository=args.repository, git_commit=args.git_commit)
        evidence = json.loads(args.manual_evidence.read_text(encoding="utf-8"))
        run = ExperimentRun(
            roster=load_roster(args.roster),
            prompt_plan=load_prompt_plan(args.prompt_plan),
            git_commit=args.git_commit,
            persisted_evidence_verified=True,
        )
        _record_manual_evidence(run, evidence)
        run.write(args.output, repository=args.repository)
    except (EvidenceValidationError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


def _record_manual_evidence(run: ExperimentRun, evidence: object) -> None:
    if not isinstance(evidence, dict) or set(evidence) != {
        "attempts",
        "forced_failure",
    }:
        raise EvidenceValidationError("manual evidence has unsupported metadata fields")
    attempts = evidence["attempts"]
    if not isinstance(attempts, dict):
        raise EvidenceValidationError("manual evidence attempts must be an object")
    for entry in run.roster.entries:
        value = attempts.get(entry.model_id)
        if not isinstance(value, dict) or set(value) != {
            "audible_changed_output",
            "end_triggered",
        }:
            raise EvidenceValidationError("manual evidence attempt is invalid")
        audible = value["audible_changed_output"]
        end_triggered = value["end_triggered"]
        if not isinstance(audible, bool) or not isinstance(end_triggered, bool):
            raise EvidenceValidationError("manual evidence values must be booleans")
        run.record_manual_attempt(
            entry.model_id,
            AttemptObservation(
                audible_changed_output=audible,
                end_triggered=end_triggered,
            ),
        )
    forced_failure = evidence["forced_failure"]
    if not isinstance(forced_failure, dict) or set(forced_failure) != {
        "native_fallback_observed",
        "native_remote_overlap_observed",
    }:
        raise EvidenceValidationError("manual forced-failure evidence is invalid")
    fallback = forced_failure["native_fallback_observed"]
    overlap = forced_failure["native_remote_overlap_observed"]
    if not isinstance(fallback, bool) or not isinstance(overlap, bool):
        raise EvidenceValidationError("manual forced-failure values must be booleans")
    run.record_forced_failure(
        ForcedFailureObservation(
            native_fallback_observed=fallback,
            native_remote_overlap_observed=overlap,
        )
    )
