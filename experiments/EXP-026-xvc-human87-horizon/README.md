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

The extension completed 2,088 updates in 262.54 seconds and reproduced every
base/epoch-12 control. Loss continued down at epochs 12/18/24:
`367.1953 / 356.9258 / 310.8828`. However, auxiliary faster-whisper-small on
the three source-only rows showed content degradation rather than improvement.
At epoch 24, `EMOTION100_004` became a largely nonsensical transcript and
`EMOTION100_017` became `ああああああ`; epoch 18 also changed the latter to
`あ、やばいやばい`. The same screen transcribed the frozen base nearly
correctly on all three rows. Lower train loss is therefore not a reason to
extend this expanded79 trajectory again.

The next one-variable comparison changes only the LoRA target scope from all
79 acoustic-converter Linear modules to the established 69 attention/FFN
modules. Corpus, ordering, seed, rank/alpha, learning rate, gradient clip,
zero frame condition, target reference, source rows, and epochs 4/8/12 remain
fixed. This tests whether the additional ten projections were damaging content
preservation on human-paired adaptation.

The control69 run completed 1,044 updates in 172.95 seconds. Loss at epochs
4/8/12 was `441.6620 / 410.2230 / 396.1591`. On the same auxiliary transcript
distance calculation, mean normalized content error at control69 epochs
4/8/12 was `0.329 / 0.346 / 0.198`, versus `0.568` for expanded79 epoch 12.
Control69 epoch 12 preserved the short third sentence as
`あっ、ヘルが鳴ってる` rather than expanded79's `あ、ありがとう。`.
This admits one control69-only 12/18/24 horizon extension; it is not an audible
quality selection.

That extension also completed and reproduced its epoch-12 controls. Loss at
12/18/24 was `396.1591 / 373.4965 / 365.7220`, but auxiliary mean content error
worsened from `0.198` to `0.531 / 0.496`. The short third sentence again
collapsed to `あ!いらない!` and then `ああああああ`. Both scopes therefore
put the useful horizon at or before epoch 12. The next bounded run keeps
control69 and halves only AdamW learning rate from `1e-4` to `5e-5`, rendering
epochs 12/18/24 to test whether slower adaptation preserves content longer.

The half-LR run completed 2,088 updates in 247.54 seconds. Loss at epochs
12/18/24 was `420.1410 / 403.3412 / 390.5418`, while auxiliary mean content
error was `0.255 / 0.348 / 0.441`. It therefore shifted the degradation later
but did not beat the standard-LR control69 epoch-12 error of `0.198`. Further
human87 horizon and learning-rate refinement is closed. The next comparison
reuses the existing exact adapters on the 8.17-second actual ChatGPT input,
with no new training, to check whether control69's heldout content advantage
generalizes before spending a system-path run on it.

That actual-input comparison completed in 80.11 seconds and published the
source plus three offline outputs. Against the source's own auxiliary ASR
transcript, normalized character distance was `0.317` for base, `0.463` for
expanded79 epoch 12, and `0.439` for control69 epoch 12. Neither adapted state
beats base on content and neither is a machine-selected quality winner.
Control69 did retain its small relative advantage over expanded79 without the
gross repetition seen in shorter-lookahead streaming runs. This admits exactly
one reuse of control69 epoch 12 through the established future-120 worker and
cancellation probe; failure there closes this machine-screened branch.

The control69 system-path probe completed safely at the transport boundary:
generation cancel acknowledgement was 0.016 ms, stale output was zero, and the
retained generation produced contiguous `409/409` frames with no model-call
failure. The audio nevertheless failed the coarse screen: auxiliary ASR ended
in a long `ななな...` repetition that was absent offline. Control69 is closed
for further machine-only work. One final base/future-120 system control now
separates an adaptation interaction from a base streaming failure; it changes
no geometry or worker behavior.

The base future-120 control also completed with zero stale frames and contiguous
`409/409` output. It did not grossly repeat. Its source-relative ASR distance
was `0.512`, modestly better than expanded79 epoch-8 system output at `0.561`
but worse than offline base at `0.317`. This isolates the control69 repetition
to the adaptation/stream interaction while confirming that the streaming
window still loses content without LoRA. The already-established 200-ms
lookahead endpoint is reused once with base; no new intermediate point is
opened. Failure to improve closes this X-VC machine-screened stream search.

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

## Control69 actual-input system-path command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-human-paired/system_path_smoke.py \
  --candidate control69-e12 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --adapter-dir artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/adapter-1044 \
  --target-reference artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs/EMOTION100_003/target-48k.wav \
  --actual-source artifacts/ms3/listening/exp020-human-rvc-smoke-8s-plain-20260812/00-native-source.wav \
  --work-dir artifacts/xvc-human-paired/listen-now/exp026-control69-e12-system-path-v1 \
  --listener-dir artifacts/ms3/listening/exp026-control69-e12-system-path-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```

## Control69 content-preservation command

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
  --lora-scope control69 --checkpoint-epochs 4,8,12 \
  --work-dir artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1 \
  --listener-dir artifacts/ms3/listening/exp026-human87-control69-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```

## Control69 extended horizon command

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
  --lora-scope control69 --checkpoint-epochs 12,18,24 \
  --work-dir artifacts/xvc-human-paired/listen-now/exp026-human87-control69-extended-v1 \
  --listener-dir artifacts/ms3/listening/exp026-human87-control69-extended-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```

## Control69 half-LR command

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
  --lora-scope control69 --learning-rate 5e-5 --checkpoint-epochs 12,18,24 \
  --work-dir artifacts/xvc-human-paired/listen-now/exp026-human87-control69-half-lr-v1 \
  --listener-dir artifacts/ms3/listening/exp026-human87-control69-half-lr-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```

## Actual-input scope comparison command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-human-paired/compare_actual_scopes.py \
  --manifest artifacts/xvc-human-paired/runrun-human-paired.manifest.json \
  --source-root artifacts/xvc-human-paired/source-audio/hadou-ita \
  --target-archive /tmp/liveconv-ms3-intake/amitaro-full-data/downloads/ITAcorpus_amitaro_runrun.zip \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --expanded-work-dir artifacts/xvc-human-paired/listen-now/exp026-human87-horizon-v1 \
  --control69-work-dir artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1 \
  --actual-source artifacts/ms3/listening/exp020-human-rvc-smoke-8s-plain-20260812/00-native-source.wav \
  --work-dir artifacts/xvc-human-paired/listen-now/exp026-actual-scope-offline-v1 \
  --listener-dir artifacts/ms3/listening/exp026-actual-scope-offline-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```

## Base actual-input system control command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-human-paired/system_path_smoke.py \
  --candidate base \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --target-reference artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs/EMOTION100_003/target-48k.wav \
  --actual-source artifacts/ms3/listening/exp020-human-rvc-smoke-8s-plain-20260812/00-native-source.wav \
  --work-dir artifacts/xvc-human-paired/listen-now/exp026-base-system-path-v1 \
  --listener-dir artifacts/ms3/listening/exp026-base-system-path-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```

## Base future-200 content control command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-human-paired/system_path_smoke.py \
  --candidate base-future200 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --target-reference artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs/EMOTION100_003/target-48k.wav \
  --actual-source artifacts/ms3/listening/exp020-human-rvc-smoke-8s-plain-20260812/00-native-source.wav \
  --work-dir artifacts/xvc-human-paired/listen-now/exp026-base-future200-system-path-v1 \
  --listener-dir artifacts/ms3/listening/exp026-base-future200-system-path-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
