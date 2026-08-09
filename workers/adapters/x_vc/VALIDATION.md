# X-VC adapter validation record

Status: worker technical smoke passes; Japanese quality fails; profile remains
research-only and nonselectable.

## Scope

The adapter loads the pinned official X-VC graph and local GLM/ERes2Net models,
precomputes one authorized target condition, and executes official bounded
streaming windows through `WorkerSupervisor`. The real smoke uses the existing
project-authored synthetic Japanese source and target reference. The target's
non-sensitive GOV-001 record is linked in the ignored report and covers owner,
authorization record, permitted purpose, retention policy, deletion path,
classification, and exact target digest. It does not create a new quality
comparison or grant production-target approval.

Upstream full-file source normalization cannot be identical in a bounded live
stream. The adapter's explicitly bound `xvc-bounded-official-functions-v1`
variant applies the pinned upstream volume normalization and high-pass functions
to each 2.4 s model window. This deviation has technical execution evidence only,
not a quality pass. Output uses per-generation left state plus model right context
(`torchaudio-sinc-hann-overlap-v1`) rather than resetting a one-shot resampler at
each 120 ms boundary.

This record separates worker correctness from model quality. Worker conformance
cannot clear the Japanese content, speaker, license, training-data, or selection
gates.

## Pinned runtime

```text
source revision:     49df8c591eafc48b096e466d96f9839f9c0dd739
X-VC checkpoint:     sha256:1ba0ca3187d2a6753a1529db18c5490e5cb20c8874dc067b92935ff39cfed687
local config:        sha256:5f9aae0487ffcf1b69f5833317d068bfe62c6de1a12b0921abebe742b39c3be7
GLM weights:         sha256:2800bd503f52b51e45f0c53cfd5c31dcfe8ef7f13d22b396aa3d53e0280dd1e4
ERes2Net weights:    sha256:d8941f5952e31820173c8854562cb6d7897aaa58cd65c18f30d5a2e52d30847d
runtime:             CPython 3.12.3, torch/torchaudio 2.8.0+cu128
runtime closure:     123 hash-locked packages + liveconv worker wheel
device:              NVIDIA GeForce RTX 5090
runtime lock:        sha256:e5e5ccbb88ad3c49eac8d6ed0cd1f17120cbbbdea9183905be2fc120fbd66f14
interpreter:         sha256:1d3cf64f97cadc79fdc6fe2496a21b7b456cb94211978cfef5a65f616af74fd5
adapter source:      recorded in the final ignored Supervisor report
worker wheel:        recorded in the final ignored Supervisor report
worker config hash:  recorded in the final ignored Supervisor report
```

Both the Supervisor and child worker verify declared file artifacts. The child
also rejects tracked, untracked, and ignored differences in the upstream source;
verifies the installed adapter, retained wheel, interpreter, complete lock, and
worker distribution; and binds all digests into its canonical configuration.
The Supervisor and worker independently verify the target-authorization record.
An inherited fail-closed seccomp filter is installed before model imports and
denies IPv4 and IPv6 socket creation at the OS boundary. Offline environment
flags are retained only as defense in depth.

## Worker protocol evidence

Focused deterministic suite:

```text
26 passed, 1 real test skipped
```

Coverage includes fixed-window assembly and bounded history, partial end drain,
exact frame identity/order, finite normalized PCM, monotonic lifecycle IDs,
500 ms queue overflow, end sealing, immediate cancel during blocked inference,
stale PCM/completion suppression, canceled-to-next-generation handoff, fatal
invalid backend output, Supervisor health/round trip/cancel, protocol-only stdout,
configuration identity binding, ignored/untracked source rejection, strict
authorization schema/target linkage, complete hashed-lock coverage, and
AF_INET/AF_INET6 denial with AF_UNIX retained.

The final ignored evidence is generated only by the installed wheel from `/tmp`
with `PYTHONPATH`/`PYTHONHOME` unset and `-I -B` active. Its runtime inventory must
equal all 123 lock entries plus `liveconv-worker-runtime==0.1.0`, and its worker
module path must be inside `artifacts/x-vc/runtime-py312`. The report records the
exact wheel, adapter, interpreter, lock, authorization, configuration, output,
and artifact digests plus these real GPU observations:

```text
chunked-vs-continuous resampler:   maximum absolute error <= 1e-6
output:                            25 frames / 24,000 samples / 0.5 s at 48 kHz
finite normalized PCM:             true
Supervisor-visible stale output:   false
post-cancel generation completed:   true
AF_INET / AF_INET6 sockets:         denied with EPERM
AF_UNIX socket creation:            allowed
```

The aggregate record is
`artifacts/x-vc/evidence/worker-supervisor-smoke-v2.json`. Its exact timings
combine Supervisor artifact hashing, scheduling, resampling, model load, and
output consumption on a short technical fixture. They are not a preregistered
latency experiment and do not replace the earlier standalone measurements.

The report additionally binds the source-fixture and target-reference digests,
the production adapter-source hash, preprocessing/resampler revisions, and exact
runtime package versions. GPU replay determinism was not assessed; the output
digest identifies this run rather than promising bit-exact reproduction.

The real stale-output observation is made through `WorkerSupervisor`, which also
filters canceled generations. Direct worker epoch suppression is independently
covered by the deterministic blocked-inference test; post-cancel generation 3 in
the real smoke proves the process remains live without cross-generation output.

## Frozen model-quality evidence

The prior evidence remains unchanged and controls selectability:

```text
standalone streaming inference:  P50 19.1773 ms / P95 22.9904 ms
Japanese source CER:             0.00
X-VC offline output CER:         0.20 (fails proposed maximum 0.10)
X-VC streaming output CER:       0.80 (fails proposed maximum 0.10)
offline speaker gain/advantage: -0.03489 / -0.00635 (both fail 0.05)
stream speaker gain/advantage:  -0.00359 /  0.02712 (both fail 0.05)
streaming interruption/failover: previously unassessed; worker cancel now only a
                                technical smoke, not a Gateway failover trace
```

The real worker smoke intentionally did not run STT or speaker scoring on its
0.5-second excerpt. It provides no new Japanese quality result and must not be
described as one.

## Decision boundary

The adapter demonstrates that the pinned model can satisfy the private worker-v1
transport contract on the validated GPU. It does not establish Japanese content
preservation, target-speaker success, acceptable end-to-end latency, production
interruption/fallback, license approval, or product eligibility. X-VC remains a
research-only, nonselectable candidate. No quality pass is claimed.
