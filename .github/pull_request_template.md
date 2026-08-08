## Question or behavior

<!-- What user outcome, defect, decision, or experiment does this address? -->

## Traceability

<!-- Link FR/NFR/JP/GOV, ADR, EXP, LV, risk, or issue identifiers. -->

## Changes

<!-- Describe the implementation and its ownership zone. -->

## Intentional non-scope

<!-- State what this change deliberately does not solve. -->

## Evidence

<!-- Commands, tests, experiment results, screenshots, or aggregate measurements. -->

```text
make check
```

## Audio and conversation impact

<!-- Include sample rate, chunking, warmup, P50/P95 latency, interruption, and audio failure evidence when applicable. -->

## Privacy, security, and voice authorization

<!-- State data classification, artifact location, retention, and target-voice authorization impact. -->

## Risks and rollback

<!-- Describe residual risk, bypass, rollback, and follow-up work. -->

## Checklist

- [ ] Scope is traceable to a source-of-truth record.
- [ ] Focused tests and `make check` pass.
- [ ] No credential, private audio, model weight, or generated artifact is tracked.
- [ ] Timing and quality claims include reproducible evidence.
- [ ] An independent review covered correctness and regressions.
- [ ] Relevant experiment, ADR, backlog, and risk records are current.
