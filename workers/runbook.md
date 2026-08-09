# Model pack approval runbook

## Scope

These manifests prepare LV-022 worker isolation and later adapter experiments.
They do not authorize cloning, downloading, training, or running a model. This
runbook never changes a pack directly to runtime-ready; the runtime profile and
experiment approval remain separate decisions.

## Promotion sequence

1. Confirm the canonical upstream and record a reviewed immutable commit.
2. Resolve code, weight, training-data, and inference-runtime licenses
   independently. Store the approval record outside Git and link only a
   non-sensitive HTTPS record locator.
3. Acquire artifacts through an approved process, verify each expected origin,
   and record a separate SHA-256 digest and non-sensitive provenance record for
   every checkpoint, index, model directory, reference, or corpus bundle. Never
   commit those artifacts.
4. Provision artifact locations through the manifest's `LIVECONV_*` variables.
   Keep values in the worker supervisor's secret environment, not command lines.
5. Freeze sample-rate conversion, context, target preparation, and the CPU/GPU
   budget as experiment configuration. Current budgets are hypotheses.
6. Run offline adapter conformance and Japanese STT, speaker, and integrity
   gates. Streaming work begins only when its manifest gate allows it.
7. Exercise warmup, immediate generation cancellation, unload, worker crash,
   repeated reload, and VRAM/RAM recovery. Record aggregate evidence externally.
8. Update checklist evidence links only after the owning experiment accepts the
   results. A missing required lane is inconclusive, never a pass.

## Candidate rules

- **RVC v2:** first adapter. Freeze checkpoint sample rate, pitch extractor,
  retrieval index, dependencies, and authorized target corpus before testing.
- **X-VC:** run Japanese offline preservation and boundary tests first. Its
  streaming gate stays blocked until that decision passes.
- **Beatrice 2:** do not integrate the inference library on the server without
  written Project Beatrice permission covering the intended deployment.
- **OpenVoice V2:** use only as an offline Japanese control in this phase. Its
  tone-color conversion flow is not evidence of a realtime streaming contract.

## Artifact handling

Each artifact entry names an environment variable, never a filesystem path. A
blocked pack keeps its artifact digest and provenance URL null. Before starting
an approved worker, the supervisor must verify that required variables are
present, resolve to approved locations, and match each entry's `sha256`. Error
messages may name the variable but must not print its value.

## Gate changes

While `immutability_gate.status` is `blocked`, both `source_revision` and
`weight_sha256` must remain `null`. Approval requires both immutable values and a
non-sensitive approval-record URL. `ready_for_runtime` remains false in this
research schema; runtime readiness belongs to the curated profile registry after
all acceptance evidence is reviewed.
