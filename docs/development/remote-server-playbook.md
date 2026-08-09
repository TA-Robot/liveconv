# Remote server delivery playbook

Status: Accepted process

## Delivery order

1. Freeze ADR-0002 and protocol version 1.
2. Implement shared frame/control contracts and golden fixtures.
3. Implement session auth, state, profile registry, passthrough, and deterministic
   DSP profiles.
4. Implement signal/STT report contracts and synthetic detector tests.
5. Connect the Extension while retaining local exclusive native fallback.
6. Run EXP-002 for transport, switching, cancellation, and evaluation plumbing.
7. Add one isolated real model worker at a time.
8. Run adapter conformance, frozen fixtures, and independent review before making
   a profile selectable outside an experiment.

## Ownership

| Zone | Owner role | Shared boundary |
|---|---|---|
| `packages/protocol` | protocol worker | ADR-0002 and golden fixtures |
| `services/audio` | audio worker | protocol package only |
| `packages/evaluation` | evaluation worker | render/report schemas |
| `apps/extension` | extension worker | protocol package only |
| `workers/<profile>` | one model worker | adapter SPI and profile manifest |
| `deploy/remote` | deployment worker | Caddy TLS/WSS and hardened Compose boundary |

No model worker edits the gateway, Extension, protocol, experiment registry, or
another model worker. The parent owns shared schemas, ADRs, backlog state, and
integration.

## Profile onboarding checklist

- canonical repository/model-card URLs and immutable revisions
- separate code, weight, training-data, runtime, and redistribution licenses
- voice authorization and target-data provenance
- isolated environment or container lock
- required GPU/CPU memory, precision, sample rate, context, and warmup
- streaming, cancellation, batching, and failure behavior
- readiness, load, unload, health, and GPU release tests
- adapter conformance and deterministic cancellation tests
- frozen offline Japanese fixture report before WSS exposure
- resource caps, timeouts, logs, and rollback

`ready` means technically loadable and contract-conformant. It does not mean a
model passed Japanese quality or is approved for every use.

## Server deployment

- Bind the application to loopback behind TLS termination until ingress is
  explicitly configured.
- For trusted development clients, keep both application endpoints on loopback
  and use the accepted OpenSSH local-forwarding procedure in
  `docs/development/ssh-tunnel-client-setup.md`.
- Expose only gateway HTTP/WSS ports. Bind worker protocols to Unix sockets or a
  private network.
- Store API credentials, session-ticket keys, model credentials, and artifact
  credentials outside Git.
- Redact bearer credentials, one-use tickets, query strings, raw text, and audio
  from proxy and application logs.
- Require explicit allowed Extension origins in any non-development environment.
- Pin worker image, code, weights, driver, CUDA, and configuration in experiment
  records.
- Cap per-session frames, queued milliseconds, session duration, concurrent GPU
  workers, and model-resident VRAM.

## Multi-model policy

The registry is curated, not a user-installable marketplace. Use stable profile
IDs such as `vc.rvc.jp.<revision>` and never expose arbitrary import paths or
command lines. A profile revision is immutable. A new weight or configuration
creates a new revision.

The RTX 5090 has 32 GB VRAM, but the resident set is chosen from measured peak
memory plus a reserve. Start with one GPU worker active at a time, keep the
deterministic CPU profiles resident, and add LRU/on-demand loading only after
warmup and eviction behavior are measured. Never rely on an out-of-memory error
as normal scheduling.

## Agent task brief

Every implementation brief includes:

```text
Backlog ID and requirement IDs:
Owned directory:
Frozen protocol/schema revision:
Inputs and golden fixtures:
Expected success and failure tests:
Resource and artifact policy:
Do not change:
Stop condition:
Return evidence:
```

Run an independent protocol/security review after gateway integration and an
independent audio/evaluation review after every real model adapter.
