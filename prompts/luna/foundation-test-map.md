# Foundation test map

Read `AGENTS.md`, `docs/planning/critical-path.md`, the protocol contract, the
evaluation policy, and the current backlog.

Spawn four generic Luna children without selecting a custom model. Assign one
test-mapping question to each child:

1. gateway state, cancellation, deletion, and bounded-resource behavior
2. Extension capture, exclusive playout, fallback, and stale-generation behavior
3. worker lifecycle, crash, timeout, unload, and resource recovery
4. evaluation, STT provenance, entity preservation, and report completeness

This is test preparation, not independent review. Do not approve existing code or
edit production files. Return proposed test locations, deterministic fixtures,
expected failure conditions, and the dependency decision required before each
test-author task can start.
