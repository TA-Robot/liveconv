# EXP-333: source-speaker GRL target/source direction screen

Status: admitted auxiliary batch screen; no perceptual selection

## Question

Did EXP-326's training-only source-speaker GRL actually reduce source-speaker
fit or improve authorized Amitaro target-speaker fit relative to the exact
matched EXP-325 control across external7 and all six frozen broad surfaces?

The coarse content screen already rejects a generic broad-content improvement:
337 broad rows were `15W/303T/19L` and expanded144 was `4W/126T/14L`, although
aggregate decoder instability improved `70 -> 67`. The GRL method should not be
retrained or tuned. This single existing-audio screen tests whether the observed
content/stability tradeoff corresponds to its intended speaker-direction
mechanism or merely perturbs the decoder.

## Fixed batch

Use the exact EXP-325/326 matched listener rows on external7, fresh48, Hadou31,
stress60, balanced JSUT24, expanded144, and SRC4VC-heldout30. Bind the existing
operator-authorized Amitaro runrun target lineage and the already-pinned local
ECAPA batch runtime/model. Load the model once, cache embeddings by WAV hash,
and report target-to-output cosine, source-to-output cosine, and target-over-
source advantage for all 344 matched rows.

## Decision boundary

- A consistent target-similarity increase together with source-similarity
  decrease retains EXP-326 only as an unheard speaker-direction alternative;
  it does not reopen GRL coefficients or override the content regression.
- Flat, regressed, or mixed direction means the fixed GRL failed to generalize
  its intended mechanism and closes it completely as a technical method.
- No result selects naturalness, prosody, emotion, personal identity, keep,
  winner, promotion, or realtime route quality.

No new audio, embedding, private target, or model weight is committed. The
aggregate JSON remains below ignored `artifacts/`.

## Command

```bash
HF_HUB_OFFLINE=1 artifacts/shared/speaker/runtime/bin/python \
  tools/xvc-source-diversity/screen_speaker_fit.py \
  --surface-plan experiments/EXP-333-xvc-grl-speaker-fit-direction/surface-pairs.json \
  --target-manifest artifacts/xvc-human-paired/runrun-human-paired.manifest.json \
  --model-artifact artifacts/shared/speaker/ecapa-runtime-model \
  --model-sha256 8addaeebdfb312b55d9f7c020f4e6529c65ce4e4fb0772af40398a66b9aa6ea8 \
  --device cuda \
  --output artifacts/xvc-source-diversity/exp333-grl-speaker-fit-direction-v1/speaker-fit-screen.json
```
