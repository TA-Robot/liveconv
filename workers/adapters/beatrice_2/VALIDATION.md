# Beatrice 2 validation record

Status: adapter technical validation complete; enabled only for the personal GPT
Live trial and not production-approved

## Current personal GPT Live trial route (2026-08-10)

The historical validation below used pretrained speaker 37. The personal GPT
Live trial now pins pretrained speaker 46 because it is substantially lower than
the other evaluated bundled identities and makes an audible A/B check easier.
On the same converted Japanese candidate, speaker 46 measured a median F0 of
103.7 Hz, while speakers 37 and 83 measured 247.4 Hz and 252.6 Hz. This is a
technical trial of a bundled pretrained identity, not an authorized cloned human
voice or a product-quality approval.

The deployed Gateway accepted a realtime-paced 30.0 second stream through the
actual HTTP and WebSocket route and returned all 1,500 input frames as 1,500
finite output frames. Every returned frame differed from its input counterpart;
there were no `fallback.required` or `error` events, and generation completion
and session close both succeeded. This proves that the current worker drains the
400-frame ingress queue continuously. It does not by itself establish subjective
voice quality.

## Scope

The implementation uses the official MIT Beatrice Trainer source and its bundled
pretrained models directly, without `beatrice.lib`. The pretrained converter has
200 LibriTTS-R speaker identities. These identities are useful for execution and
Japanese-content preservation checks only; they are not authorized liveconv target
voices and do not satisfy the product speaker gate.

The Japanese input is `LV001-JA-001.wav` from the project-authored synthetic
corpus. Source and generated WAVs, STT bundles, and raw runtime artifacts remain
under ignored `artifacts/`.

## Pinned runtime

```text
trainer revision: f34836de014b86956096878aecb8d3b17feaaa0b
trainer module:   sha256:c191a4fabdb63730b749fc2fbbe27384223fc27862a06a0d9db713bdee688e83
phone model:      sha256:46e2d609825ace2158c83672cfc9cc1dcb3c2b7c8d294ee911fcb6840a592bae
pitch model:      sha256:174e5411009e0e4f6ee8a8c97c4cd2f646791eae1b9aa2b425acb797e0353ef4
converter model:  sha256:14ecdb01e51cf22b80664973daa3dedeeb0bada48bbf5262e58950c818cdcb1a
worker identity:  v3 complete wheel, RECORD, source-tree, and execution manifests
runtime:          Python 3.12.3, torch/torchaudio 2.8.0+cu128
device:           NVIDIA GeForce RTX 5090
```

The runtime is a fresh venv with `include-system-site-packages = false`. Every
transitive dependency is pinned with an archive hash in the packaged
`requirements-runtime.lock.txt`; the liveconv worker runtime itself is installed
as versioned wheel `liveconv-worker-runtime==0.1.0`. The final wheel, lock,
configuration, source, and model identity are recorded outside Git in
`artifacts/beatrice-2/identity.json` and `identity.env`.

The worker derives all identity digests from installed bytes before readiness. It
verifies the retained wheel, both `RECORD` files, every installed wheel member,
the exact packaged-lock dependency inventory, the complete installed-distribution
manifest, and the manifest of every executed project module, including
`workers.runtime.codec`. A source import root must be an exact clean pinned Git
tree or match a complete source-tree manifest; top-level `torch.py` and
`numpy.py` shadow regressions are rejected before the source root is inserted.

## Worker protocol evidence

The real backend loaded all three official checkpoints with strict state-dict
matching. The pinned Japanese source was resampled to 48 kHz, padded to a whole
20 ms frame, and sent through `WorkerSupervisor` in 500 ms batches. Target speaker
37 produced:

```text
startup: 9.4998 s
output: 137/137 frames, 2.74 s at 48 kHz
batch latency P50 / P95: 0.0401 s / 0.7688 s
cold first batch / maximum: 0.9601 s / 0.9601 s
cancel acknowledgment: 0.00119 s
stale output after cancel: false
finite / normalized PCM: true / true
peak / RMS: 0.499148 / 0.058223
different sample fraction: 0.977410
output: sha256:35a043230bcb2d04ab694fe2a0ef2621b3748fb3630f16d94d9f9de83ee08389
```

An additional real-checkpoint race regression cancels a 500 ms generation while
its inference is live, immediately starts the next generation, and waits for that
new generation's output. Since backend inference is serialized, observing the new
output proves the test waited beyond completion of the canceled call; no stale
frame was observable before or afterward. Separate real 20 ms and 40 ms final
drains validate minimum-safe 60 ms padding and exact original-length trimming.

The v3 packaging smoke invoked the installed module from `/tmp`, with
`PYTHONPATH` unset, through an actual `WorkerSupervisor` handshake. The profile
pre-verified the source module, all three checkpoints, and worker wheel as
`ArtifactSpec` values. `worker.ready` returned the worker-derived canonical
configuration hash and one 20 ms output frame; this is technical execution
evidence only.

The P95 uses inclusive linear interpolation over six sequential batches, one of
which was the cold first call and one a 240 ms final drain. This is a smoke
measurement, not a preregistered latency experiment.

Pinned `faster-whisper==1.2.1` recognized the source as
`はい こちらの声は聞こえています` and the Supervisor output as
`はい、そちらの声が聞こえています。`. Japanese content remains intelligible,
but the two substitutions mean exact content preservation does not pass.

The deterministic suite covers full 500 ms batching, 20/40/60 ms partial end
drains, PCM
shape/range validation, queue bounds, monotonic lifecycle identifiers, immediate
cancel during inference, the end/cancel race, stale-result suppression, safe
canceled-to-next-generation handoff, cancel-then-unexpected-backend-failure
fatal handling, backend output validation, Supervisor health, protocol-only
stdout, and clean close.

```text
deterministic focused suite: 31 passed, 1 real test skipped
real installed-worker Supervisor smoke: 1 passed
```

## Decision boundary

A passing adapter and Japanese smoke prove that the implementation executes and
preserves the worker contract. They do not establish an authorized target,
speaker similarity, acceptable Japanese quality, CPU latency, training-data
approval, or product selectability. Those model-pack gates remain blocked until
their own accepted evidence exists.
