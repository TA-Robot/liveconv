# EXP-025: X-VC whole-short human-paired adaptation

Status: **draft; 87-pair inventory may be used as listen-now**.

EXP-025 is a separate post-failure draft. It does not retry EXP-024 or alter
its gates. It does not train RVC or mix external TTS into the human corpus.

Process update 2026-08-13: [`docs/planning/lab-operating-model.md`](../../docs/planning/lab-operating-model.md)
supersedes the hash/plumbing admission wall. The 87 train / 16 heldout complete
short pairs may be stretch+padded, trained briefly, and published on port 8878
as a listen-now probe. Abbreviated identities, dirty-tree digests, and
independent review do not block that probe. The probe still cannot select a
model, route, or voice. A serious 334/36/54 adaptation experiment remains a
later, separately registered promote-or-cited comparison.

## Scope and classification

The current 87-pair inventory is a listen-now training subset, not a plumbing
cathedral. Its purpose is to get a handful of whole-short adapted WAVs to the
operator. It is not serious adaptation evidence and cannot select a model,
route, or voice.

A separately registered serious adaptation experiment is required before any
quality conclusion. It must use **all admitted exact pairs**: 334 train, 36
validation, and 54 heldout. It must record the actual receipt-bound aligned
seconds, windows, and update count rather than carrying forward `87`, one
window, or `348` as a proxy. It must not use a generic 30-minute gate, RVC, or
any TTS path. EXP-025 neither approves nor runs that later experiment.

## Listen-now run

Question: Does one short X-VC adaptation over the inventoried human whole-short
pairs sound better than the frozen base strongly enough to deserve a promote
pass?

Change (one variable): replace the rejected synthetic micro-corpus with the 87
eligible human Hadou-to-Amitaro runrun train pairs. Stretch each complete source
once, right-pad source and target to 2.4 seconds, then run four fixed epochs
(348 updates) with expanded79 LoRA r8, AdamW `1e-4`, gradient clip 5, and zero
target conditioning.

Inputs: the sealed 424-row manifest, Hadou public source WAVs, the already
operator-authorized Amitaro runrun archive, pinned X-VC base, and three public
heldout source-only utterances. Rendering uses one different-text train-role
target reference. The runner never opens a heldout target.

Run from the commit containing this note and
`tools/xvc-human-paired/listen_now.py`; the result records `git rev-parse HEAD`:

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-human-paired/listen_now.py \
  --manifest artifacts/xvc-human-paired/runrun-human-paired.manifest.json \
  --source-root artifacts/xvc-human-paired/source-audio/hadou-ita \
  --target-archive /tmp/liveconv-ms3-intake/amitaro-full-data/downloads/ITAcorpus_amitaro_runrun.zip \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-human-paired/listen-now/exp025-whole-short-87-v2 \
  --listener-dir artifacts/ms3/listening/exp025-whole-short-87-listen-now-v2 \
  --confirm-gpu-lease gpu0 --device cuda:0
```

Where it appears: the fixed listener `http://127.0.0.1:8878/`, collection
`EXP-025: whole-short 87-pair listen-now`.

Operator action: choose the adapted candidate only if it is clearly preferable
to base, then record `keep`; record `rejected` for a base win, tie, or both bad.
`keep` only admits a promote pass.

Kill rule: stop on wrong eligible count, input drift, nonfinite loss/gradient,
OOM, malformed audio, any heldout-target access, or failure to publish exactly
three base/adapted comparisons. Do not retry by changing the corpus, schedule,
rank, learning rate, or render sources.

Not claimed: serious 334/36/54 adaptation, heldout evaluation, model selection,
route qualification, realtime suitability, or product readiness.

Repair note: the original `v1` launch stopped before model load or any update
because the runner imported `process_audio` from `utils.audio`; pinned X-VC
exports it from `models.codec.sac.utils`. The `v2` launch changes only that
import boundary and the fresh output locator. All scientific conditions and
the one-run quality question remain unchanged.

## Question and hypothesis

Can the pinned preprocessing boundary produce reproducible training tensors
from complete short exact human pairs, and can a GPU smoke consume those tensors
without changing their identity or format?

The hypothesis is deliberately operational: separating evidence materialization
from model-specific tensorization can make the source/target inputs auditable.
It is falsified by any unmatched hash, forbidden conversion in the materializer,
nonfinite/noncontiguous tensor, wrong tensor shape, or GPU failure to consume
the sealed tensor. It makes no claim about perceived quality.

## Frozen identity and admission status

The restricted source manifest remains
`artifacts/xvc-human-paired/runrun-human-paired.manifest.json` with manifest
SHA-256
`2f35e75f169c7cb5664f9f9cc201ff7e79c4d5ba2e700f5c769c6ba1f22f351a`.
Candidate IDs are frozen in manifest order before human review. Validation is
never training or heldout input, and the EXP-024 validation16 denylist remains
excluded from final evaluation.

The following upstream identities remain incomplete labels. They are required
for a later promote or cited comparison. They do not block a listen-now
stretch+pad train. Abbreviated values are labels only and are not expanded
by this draft:

- X-VC revision: `49df8c...`
- `utils/audio.py` SHA-256:
  `1194cb8c71892e7f2850c051888da46f925a00a6f168736548f8b3dcc2e2302f`
- codec-utils SHA-256:
  `2cadf52f1a3a8b29d26d2ff7d1a02f672d6d39c9fe1b8abaf8f467f5b47eb94c`
- local config: `5f9aae...`
- runtime lock: `e5e5cc...`

The golden fixture is also admission_pending until its complete receipt is
sealed: materialized PCM SHA-256 `101d073c...`, WAV SHA-256 `d33dbe398...`,
and tensor SHA-256 `f066b8c1...`. This draft does not invent the missing suffixes
or treat an abbreviated value as a verified identity.

## Stage 1: CPU evidence materializer

The deterministic, offline CPU materializer is the only stage that establishes
source/target audio evidence. For every exact-ID, exact-text, exact-kana,
authorized pair it:

1. Derives complete guarded active intervals using the frozen 20 ms RMS and
   edge-guard predicate; interior silence is preserved.
2. Requires the complete target interval to be 1.8 through 2.4 seconds and the
   target/source factor to be 0.50 through 2.00, inclusive.
3. Stretches the complete source interval exactly once with the pinned CPU
   pitch-preserving implementation; it never uses DTW, token/phoneme alignment,
   silence deletion, stitching, random crop, pitch shift, truncation, tiling,
   or a replacement candidate.
4. Places source and target at `t=0` and right-pads both to exactly 115200
   samples at 48 kHz.
5. Seals only the source and target evidence as mono PCM16, 48 kHz,
   115200-sample payloads and their row-level hashes, format proof, active
   seconds, stretch factor, interior silence, padding, and failure reason.

The materializer does not run model preprocessing and does not output 16 kHz
PCM, model tensors, or training-ready audio. A materializer receipt therefore
cannot claim tensor production. Failed rows stop the applicable admission; they
are retained as failures and are never repaired by changing the predicate or
substituting a nearby ID.

## Stage 2: separately pinned CPU tensorizer

Only after Stage 1 evidence is sealed may a separately pinned CPU tensorizer
run the actual upstream X-VC `process_audio` implementation exactly once for
each sealed source PCM16 payload and exactly once for its sealed target PCM16
payload. It consumes the sealed PCM16 bytes, not a regenerated WAV or an
alternate resample.

The tensorizer seals one finite, C-contiguous, little-endian `float32` tensor
of shape `38400` for each input, together with the input PCM hash, output tensor
hash, golden-fixture comparison, invocation count, and the
admission-pending upstream identity set above. It must reject nonfinite values,
wrong dtype, endian, contiguity, or shape, any duplicate invocation, and any
unbound implementation/configuration/runtime identity. Training consumes these
sealed tensors directly; it may not rerun preprocessing or consume 16 kHz PCM.

## Admission and smoke rules

Listen-now: the operator has already authorized the Amitaro runrun target.
Hadou is the pinned public source. Spot-check a pair if a source sounds wrong.
A missing formal pronunciation disposition, abbreviated hash, or golden-fixture
suffix does not stop a stretch+pad train and 8878 render. No frozen candidate
is replaced.

A later promote or cited comparison still needs named dispositions, source and
target authorization, and the PCM-to-tensor mapping. That pass must not
interpret the listen-now probe as adaptation-quality or product evidence.

## Boundaries and privacy

Raw human audio, PCM evidence, WAVs, tensors, review and authorization records,
model artifacts, renders, private paths, and receipts remain below ignored
restricted roots. Git contains this draft and, only after a valid future record,
redacted aggregate evidence. `result` and `decision` remain null while this
draft is unexecuted.
