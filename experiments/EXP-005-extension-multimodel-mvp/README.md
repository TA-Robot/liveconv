# EXP-005: ChatGPT tab multi-model Extension MVP

Status: draft until the deployment roster, client, prompts, profile identities,
and execution states are frozen.

This is the MS-2 hands-on gate. It tests the actual Extension, SSH local forward,
Gateway, and multiple real workers together before MS-3 selects a model.

The result is technical only. Poor quality is recorded, not hidden, and does not
invalidate executability. Native/remote overlap, stale output, missing fallback,
false model availability, sensitive-data retention, a missing attempt for any of
the four prepared models, or fewer than two audible live profiles invalidate the
run. OpenVoice must be invocable as a bounded End-triggered preview; a disabled
label does not satisfy “try every model.”

Manual Start, End, Interrupt, Next, and idle-boundary profile selection are the
supported ChatGPT lifecycle. The experiment does not scrape the DOM or infer
conversation boundaries.

Before changing `status` to `approved`:

1. freeze the complete four-model roster and safe execution/decision reason codes;
2. bind RVC, Beatrice 2, and X-VC live routes plus the OpenVoice buffered preview
   to exact identities, with no unavailable entry;
3. freeze the operator prompt sequence and non-sensitive environment fields;
4. implement the metadata-only runner/report and its schema;
5. run deterministic Extension, Gateway, switching, fallback, and secret tests;
6. obtain an independent Sol plan review.
