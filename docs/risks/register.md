# Risk register

Status: Active

Scales: likelihood and impact are `Low`, `Medium`, or `High`.

| ID | Risk | Likelihood | Impact | Mitigation / evidence needed | Owner | State |
|---|---|---|---|---|---|---|
| R-001 | Timbre-only VC preserves unnatural source prosody. | High | High | Compare native and VC on blinded prosody lane before adoption. | Unassigned | Open |
| R-002 | External TTS damages full-duplex timing and interruption. | High | High | Measure commit, TTFA, overlap, and stop latency; keep native bypass. | Unassigned | Open |
| R-003 | Stale audio plays after interruption. | Medium | High | Generation IDs at every queue; cancellation and late-frame tests. | Unassigned | Open |
| R-004 | Original and transformed paths play together. | Medium | High | Single mode controller, state tests, and explicit comparison mode only. | Unassigned | Open |
| R-005 | DOM changes break the personal Web proof of concept. | High | Medium | Isolate DOM adapter and keep production on supported APIs. | Unassigned | Open |
| R-006 | Published latency is mistaken for end-to-end latency. | High | Medium | Record boundary timestamps and distinguish component claims. | Unassigned | Open |
| R-007 | Candidate code or weights cannot be used commercially. | Medium | High | Verify code, weights, data, and runtime licenses before integration. | Unassigned | Open |
| R-008 | Reference voice lacks authorization or exceeds permitted use. | Medium | High | Require provenance, permission, purpose, retention, and deletion metadata. | Unassigned | Open |
| R-009 | Private recordings or credentials enter Git or logs. | Medium | High | Ignore patterns, CI checks, redacted logging, and private artifact store. | Unassigned | Open |
| R-010 | DaaS or virtual audio routing creates duplicate capture or feedback. | Medium | High | Headphone-first tests, one audio route, loop detection, and routing diagram. | Unassigned | Open |
| R-011 | Japanese test set overfits one domain or speaker. | Medium | Medium | Versioned categories, held-out set, diverse raters, and failure slices. | Unassigned | Open |
| R-012 | Parallel agents create conflicting or unreviewed changes. | Medium | Medium | Disjoint ownership zones, worktrees, parent integration, final read-only review. | Primary agent | Mitigated |
| R-013 | GPU environment variation invalidates comparisons. | Medium | Medium | Freeze image, driver, GPU, precision, revision, warmup, and sample method. | Unassigned | Open |
| R-014 | Speech normalization changes semantic content. | Medium | High | Preserve display text, table tests, audit dictionary changes, and fallback. | Unassigned | Open |

## Risk process

Update this table when an experiment changes likelihood or impact. Closing a risk
requires evidence or an accepted ADR; absence of a recent incident is not enough.
