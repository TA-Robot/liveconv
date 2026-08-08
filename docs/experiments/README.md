# Experiment system

Status: Accepted process

## Lifecycle

```text
draft -> approved -> running -> analyzed -> decided -> archived
             |          |
             +-> invalidated
```

- **draft:** hypothesis and method are editable
- **approved:** fixtures, configuration, metrics, and decision rule are frozen
- **running:** data collection is in progress
- **analyzed:** aggregate results and failure analysis are complete
- **decided:** the parent records the consequence and updates linked records
- **invalidated:** a confounder or protocol change prevents comparison; record an
  `inconclusive` decision with its rationale even when no usable result exists
- **archived:** retained for history but no longer active

## Directory layout

```text
experiments/
  registry.json
  EXP-NNN-short-name/
    experiment.json
    notes.md
    results.json       optional aggregate metrics
    report.md          optional human analysis
```

Raw or restricted artifacts live outside Git. Record their access-controlled URI,
checksum, retention, and authorization class in local experiment storage; publish
only a non-sensitive locator or redacted identifier when appropriate.

## Before approval

An experiment must define:

- one primary question and falsifiable hypothesis
- control and variants
- frozen fixture manifest
- environment and model revisions
- independent, controlled, and observed variables
- warmup and sampling method
- primary and guardrail metrics
- expected failure modes
- decision rule
- privacy classification and artifact policy

## During execution

- Run from a clean commit or record the dirty diff hash.
- Use monotonic clocks for durations.
- Keep warmup outside the reported sample set.
- Record every failed and retried run.
- Stop and invalidate when the frozen plan changes.
- Do not tune a variant against the final evaluation set.

## After execution

- Report distributions, not only averages.
- Include P50, P95, sample count, exclusions, and confidence method.
- Preserve negative results and representative failures.
- Link the conclusion to a requirement, ADR, risk, or backlog change.
- A model that improves MOS but fails interruption or safety guardrails does not
  pass the product gate.

See `evaluation.md` for the common corpus and metrics.
