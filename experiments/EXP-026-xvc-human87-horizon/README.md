# EXP-026: X-VC human87 training-horizon listen-now

Status: **listen-now completed; operator selection pending**.

The committed run completed 1,044 updates in 181.74 seconds. Loss at epochs
4/8/12 was 420.9482/393.7865/367.1953; epoch 4 reproduced EXP-025 exactly,
heldout-target access remained zero, and 12 labeled candidates were published.
Loss is not a quality verdict, so the operator still chooses or rejects by ear.

Operator availability update (2026-08-13): listening cannot happen during the
current work window, and the active instruction is to keep the GPU producing
comparison candidates. Because the original curve is still decreasing, one
bounded extension reruns the exact trajectory through epochs 12/18/24. Epoch
12 must reproduce all three completed EXP-026 WAV hashes before the new
collection can publish. No other training variable changes.

## Goal and stop condition

Use the otherwise-idle GPU to answer one audible question: with the exact
EXP-025 human whole-short 87-pair data and model settings, does extending the
same trajectory from 4 epochs to 8 or 12 epochs sound clearly better?

Done means exactly three source-only heldout rows appear on the fixed listener
at `http://127.0.0.1:8878/`, each with explicit base, 4-epoch, 8-epoch, and
12-epoch labels. The 4-epoch base/adapted hashes must reproduce EXP-025 exactly
before publication. The operator may then nominate a clearly preferred horizon
or reject the set.

Stop before publication on input drift, nonfinite loss or gradient, OOM,
malformed audio, heldout-target access, a mismatched 4-epoch control, or any
candidate count other than three rows by four variants. Do not change the
corpus, LoRA scope/rank, seed, learning rate, gradient clip, conditioning,
reference, or render sources to rescue the run.

## One change

The only independent variable is training duration: epochs `4`, `8`, and `12`
at 87 updates per epoch. Everything else reuses the committed EXP-025 boundary:
expanded79 LoRA r8/alpha8, AdamW `1e-4`, gradient clip 5, zero target
conditioning, the same 87 train pairs, three public heldout source-only inputs,
and a different-text train-role target reference. Heldout target audio is never
opened.

This listen-now run is authorized by the active-thread instruction to keep the
GPU productive while operator listening remains pending. It does not override
the listen-now/promote boundary and cannot select a model, route, or product.

## Command

Run only after this runner and note are committed:

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-human-paired/listen_now_horizon.py \
  --manifest artifacts/xvc-human-paired/runrun-human-paired.manifest.json \
  --source-root artifacts/xvc-human-paired/source-audio/hadou-ita \
  --target-archive /tmp/liveconv-ms3-intake/amitaro-full-data/downloads/ITAcorpus_amitaro_runrun.zip \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-human-paired/listen-now/exp026-human87-horizon-v1 \
  --listener-dir artifacts/ms3/listening/exp026-human87-horizon-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```

The original v1 did not include more than 12 epochs. Neither v1 nor the bounded
extension includes a second learning rate or rank, a new model family, serious
334/36/54 evidence, route qualification, realtime suitability, or product
readiness.

## Extended horizon command

This is the sole exception to the original 12-epoch scope, authorized by the
active instruction above. It remains listen-now and unselected.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-human-paired/listen_now_horizon.py \
  --manifest artifacts/xvc-human-paired/runrun-human-paired.manifest.json \
  --source-root artifacts/xvc-human-paired/source-audio/hadou-ita \
  --target-archive /tmp/liveconv-ms3-intake/amitaro-full-data/downloads/ITAcorpus_amitaro_runrun.zip \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --checkpoint-epochs 12,18,24 \
  --work-dir artifacts/xvc-human-paired/listen-now/exp026-human87-horizon-extended-v1 \
  --listener-dir artifacts/ms3/listening/exp026-human87-horizon-extended-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
