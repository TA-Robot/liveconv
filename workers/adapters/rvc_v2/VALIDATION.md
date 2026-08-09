# RVC v2 validation record

Status: adapter technical validation complete; synthetic profile is not selectable

## v1.4 rolling residency and network isolation

The adapter's operational revision is
`liveconv-rvc-v2-worker-v1.4`. It retains the 25-frame (500 ms) RVC inference
batch and uses an explicit 50-frame total-residency contract: one batch in
flight and one pending batch. A 51st resident frame is rejected. Cancellation
immediately invalidates pending/stale output, while a canceled in-flight batch
continues to consume capacity until it exits; the next generation cannot exceed
the remaining capacity. The canonical configuration binds the 25-frame batch,
the frozen 25-frame Supervisor credit, and the 50-frame internal residency
settings.

Before any real model initialization, the worker entrypoint installs a
fail-closed Linux seccomp rule that denies `socket(2)` for every domain other
than `AF_UNIX`. Its shipped module digest is part of the retained-wheel identity.
The deterministic suite probes `AF_INET` and `AF_INET6` denial with `AF_UNIX`
retained, and the real smoke repeats that probe from the retained runtime with
`cwd=/tmp` and `PYTHONPATH` unset.

This operational change does not assess or improve RVC audio quality. The
synthetic profile remains technical and nonselectable.

## Scope

The corpus `liveconv-project-authored-synthetic-ja-v1` contains no human voice.
It is authorized for technical voice-conversion validation only. Results do not
approve imitation of a human target or establish production quality.

## Official-base checkpoint

The official `pretrained_v2/f0G40k.pth` generator was converted to the upstream
small inference format without fine-tuning. One Japanese source fixture produced
finite, non-identical PCM, proving that the real RVC v2 inference path executes
on the deployment GPU. It failed the content-preservation check and is not a
selectable target:

```text
input:  2.7227 s, 24 kHz, sha256:a012db445fb073d4...
output: 2.7000 s, 24 kHz, sha256:3cc07c740b12baf0...
cold elapsed: 10.9205 s
cold realtime factor: 4.011
peak allocated VRAM: 715560960 bytes
finite PCM: true
different sample fraction: 0.999537
source STT: はい、こちらの声は聞こえています。
output STT: はい、こちらのぽえはきぽえています。
```

Raw WAV, JSON, logs, model weights, and STT artifacts remain under ignored
`artifacts/rvc-v2/`. This document records aggregate technical evidence only.

## Authorized synthetic target

The official source was pinned at
`81eed5e8f68b6bed1789f682fe78cdd324495afc`. HuBERT, RMVPE, and RVC v2 base
weights came from the official README-linked model repository at revision
`e6d0c1a17da07c33557852f9dfa2bd44cc75737d`. The ignored
`artifacts/rvc-v2/manifest.json` records file sizes, SHA-256 values, origins,
training inputs, and evidence outputs.

The target training corpus contains 240 synthetic WAV files totaling
1372.429084 seconds. Official preprocessing produced 447 chunks; RMVPE pitch and
HuBERT v2 feature extraction succeeded for all 447. Training used the official
RVC v2 40 kHz pitch-guided configuration, batch size 16, seed 1234, and 200
epochs. The retained artifacts are:

```text
checkpoint: sha256:46b60b686a9f540aabc3788ac405dbdfb66e370c56751e592b496f8e6967789c
index:      sha256:1cec842c048757af4bc6dc7ab7ac9fa8e7ce7226b297c82c6837c8639ee04003
filelist:   sha256:c71cd7fa7d2b30d90ac7fca84c7ab86d5e2a82dd27dc3ae1de970a38fb6bb326
config:     sha256:5238c101a7925c86bab11b0eb53371f7ddbc9dd72dce35f410ac1c0d3e2984fe
```

### Full-corpus offline evidence

The final checkpoint with index rate 0.75 converted all 40 frozen source
utterances (176.44 seconds):

```text
finite outputs: 40/40
minimum different sample fraction: 0.865864
maximum clipped fraction: 0
minimum RMS: 0.017545
latency P50 / P95: 0.6893 s / 0.9356 s
RTF P50 / P95: 0.1721 / 0.3016
peak allocated VRAM: 1067571712 bytes
```

PCM integrity and transformation evidence pass technically. Content
preservation does not: pinned `faster-whisper==1.2.1` produced 0/40 exact
source-to-output transcripts and total normalized character edit distance 666.
The source synthetic speech itself matched display text on only 1/40 fixtures,
so this corpus is a weak quality benchmark, but it does not explain the clear
output failures and repetitions. Exact-entity state was preserved on 26/27
entity-bearing cases. Removing the index yielded 1/40 exact transcripts but a
worse total edit distance of 862 and 25/27 entity-state preservation.

## Worker protocol evidence

The final adapter was packaged as `liveconv-worker-runtime==0.1.0`, installed on
top of the complete hash-locked RVC runtime, and run through `WorkerSupervisor`.
The child started with `cwd=/tmp`, no `PYTHONPATH`, and imported the adapter from
the retained environment's `site-packages`, not the repository. Runtime binding:

The current ignored smoke report and manifest bind the exact retained wheel,
archive `RECORD`, installed package inventory, configuration hash, cold/warm
timing, output digest, and the three socket-isolation probes. It exercises a
137-frame continuous generation through the frozen 25-frame Supervisor credit;
worker health continues to report the separate 50-frame resident bound. The
report records cancellation latency and confirms stale output is absent. Its
results are operational evidence only, not an audio-quality assessment.

Before accepting `worker.hello`, the worker recomputed the full canonical
identity from effective settings, adapter and source revisions, the six model
artifact digests, and six independently derived runtime digests: wheel, archive
`RECORD`, worker module, backend module, network-isolation module, and packaged
dependency lock.
It verifies the wheel hash and version, every installed distribution file
against the wheel, the installed `RECORD`, and exact installed inventory against
the packaged lock. The deterministic suite additionally covers mismatch
rejection, framing, lifecycle, drain, total resident capacity while inference
is in flight, cancellation during blocked inference, canceled-to-new-generation
exclusion, fatal unexpected failure from a canceled epoch, explicit cooperative
cancellation, health, clean close, lock parsing, OS socket isolation, and
repository-independent profile construction. It passes 19/19 tests with Ruff
format and lint clean.

## Independent evidence

The wheel-bound operational output is not substituted into the content or
speaker evaluation lanes.
The canonical resampling-aware STT runner transcribed the representative source
as `はい、こちらの声は聞こえています。` and that output as
`はい、こちらの開発に変えています。`, a normalized character error rate
of 0.2667. This fails the manual technical preservation check and supports the
non-selection decision even though no product CER threshold is approved.

The previously retained output
`sha256:840b71c1275ff26faaafaee7513b2a212770f42d75a38dcf2679f83551f8b0d2`
failed the historical proposed SpeechBrain ECAPA speaker policy:

```text
source to target: 0.783153
source to output: 0.492509
target to output: 0.410235
target similarity gain: -0.372917
target advantage: -0.082274
```

That speaker result is historical and is not attached to the final output. The
shared synthetic authorization contract is being revised, so speaker change for
the final digest is explicitly `unassessed` and requires re-evaluation. The
render-bound canonical evaluation marks streaming operations `pass`; speaker
change, transformation, content, and audio-integrity policy lanes remain
`unassessed`. The transcript comparison above is retained separately as direct
technical evidence, not silently promoted to a product threshold.

## Decision

The adapter, canonical identity contract, reproducible runtime, and evidence
harness are ready for integration and independent review. This synthetic target
profile is not ready for product selection. A future candidate needs an
authorized target corpus whose source and target audio are independently
intelligible, then must pass frozen content-preservation and speaker-change
rules before registration.
