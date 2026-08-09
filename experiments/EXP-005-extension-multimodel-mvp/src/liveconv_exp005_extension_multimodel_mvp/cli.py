from __future__ import annotations

import argparse
from pathlib import Path

from .runner import (
    EvidenceValidationError,
    ExperimentRun,
    load_manual_audible_judgments,
    load_prompt_plan,
    load_roster,
    load_runtime_receipt,
    verify_clean_checkout,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Write an EXP-005 report from an Extension/Gateway runtime receipt "
            "and separately bound manual audible judgments."
        )
    )
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--prompt-plan", type=Path, required=True)
    parser.add_argument("--runtime-receipt", type=Path, required=True)
    parser.add_argument("--manual-audible-judgments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        verify_clean_checkout(repository=args.repository, git_commit=args.git_commit)
        roster = load_roster(args.roster)
        prompt_plan = load_prompt_plan(args.prompt_plan)
        receipt = load_runtime_receipt(
            args.runtime_receipt,
            roster=roster,
            prompt_plan=prompt_plan,
        )
        judgments = load_manual_audible_judgments(
            args.manual_audible_judgments,
            receipt=receipt,
        )
        run = ExperimentRun(
            roster=roster,
            prompt_plan=prompt_plan,
            git_commit=args.git_commit,
            persisted_evidence_verified=True,
        )
        run.attach_runtime_evidence(receipt, judgments)
        run.write(args.output, repository=args.repository)
    except (EvidenceValidationError, OSError) as error:
        parser.error(str(error))
    return 0
