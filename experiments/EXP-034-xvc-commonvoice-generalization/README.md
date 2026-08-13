# EXP-034: X-VC Common Voice unseen-speaker generalization

Status: ready external evaluation; no training

## Question

Does EXP-033's generated-source-diversity adapter retain its auxiliary content
advantage on six Japanese speakers that were not used as training targets,
training sources, or JVS donors?

This is the shortest check against donor overfitting. It renders the immutable
base, the legacy Hadou-human87 control69-e12 adapter, and the new JVS3-generated
adapter on six named Mozilla Common Voice 25.0 Japanese test clips. It does not
update any model.

The official Common Voice catalog identifies Japanese Scripted Speech 25.0 as
CC0. The exact files used here came from the named read-only Hugging Face mirror
revision in [`inputs.json`](inputs.json). Raw client IDs are not retained in
Git; only hashes are recorded to prove the six rows are distinct speakers.

## Done and stop

- Six distinct speakers and known texts produce 18 comparison candidates on
  `http://127.0.0.1:8878/`.
- The pinned auxiliary ASR reports both known-text and source-relative content
  distance plus gross repetition.
- Real utterances shorter than X-VC's fixed 2.4-second model window are
  right-padded with silence; longer utterances are truncated at 2.4 seconds.
- Stop after one render. This screen cannot choose naturalness, target-voice
  fit, or a product winner.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_commonvoice.py \
  --inputs experiments/EXP-034-xvc-commonvoice-generalization/inputs.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --target-reference artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs/EMOTION100_003/target-48k.wav \
  --legacy-adapter artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/adapter-1044 \
  --new-adapter artifacts/xvc-source-diversity/exp033-jvs3-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp034-commonvoice-v2 \
  --listener-dir artifacts/ms3/listening/exp034-xvc-commonvoice-v2 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
