# EXP-023: Qwen3-TTS Ono_Anna Japanese gross-rejection screen

## Purpose

This is a bounded offline TTS diagnostic for the fixed
`Qwen3-TTS-12Hz-1.7B-CustomVoice` model and its official `Ono_Anna` Japanese
preset. It renders the 12 ordered texts in
[`fixtures/texts.v1.json`](fixtures/texts.v1.json), with one discarded warmup
and one retained output per text. It has no training, fine-tuning, parameter
sweep, changed-setting retry, blind labels, randomized order, score, rank, or
winner.

The experiment is linked to [FR-003](../../docs/product/requirements.md),
[FR-005](../../docs/product/requirements.md), [FR-007](../../docs/product/requirements.md),
[FR-015](../../docs/product/requirements.md), and the deferred TTS planning
items [LV-013 and LV-063](../../docs/planning/backlog.md). It does not satisfy
the counted voice-conversion gate or the committed-text transport decision.

## Frozen input and model

- Fixture: `experiments/EXP-023-qwen3-tts-japanese-gross-screen/fixtures/texts.v1.json`
- Fixture SHA-256: `7461e2b9645d63b672da0e6d805f701475db63c60b5adbd7f229eb868c951e4d`
- Model: `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`
- Model revision: `0c0e3051f131929182e2c023b9537f8b1c68adfe`
- Model SHA-256: `38b1d5971bdbd982b561cccec982669a53b0537c3cf5e9bd4778ed07bb2f5137`
- Speech-tokenizer SHA-256: `836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258`
- Configuration SHA-256: `17a07f527a1c25ea30b4e023a184482a23d3e279d697b1dc81b1bde498d29cf9`
- `qwen-tts==0.1.1` wheel SHA-256: `11a290d8dabc7ef91a90c54478c8ab19b3edb1d85c0882313721892bdc4af15d`
- Runtime-lock SHA-256: `3c79211ad238b057ab5350731e8714b513eb99f52baf0f9d89f62747d7725208`

- Runner SHA-256: `798aa0ba6031156d5958cfbb4915c0e0afab7c736e5ca8c85ed4956c39642395`
- Synthesis-child SHA-256: `3d3ed59e96b9e00594a75edab6957e068df7f9308e06a96acf2cb264b8654303`

These exact values passed the CPU-only admission check before model import.

## Admission

The runner and synthesis child are sealed at the two hashes above. The
CPU-only admission check passed before model import, and the single approved
GPU attempt completed successfully.

## Procedure

The runner first verifies every identity without importing Torch or Qwen. It
then requires one exclusive GPU 0 lease, offline execution, BF16 on `cuda:0`,
and SDPA attention. Generation uses the official fixed settings:

```text
speaker=Ono_Anna, language=Japanese, instruct=""
do_sample=true, repetition_penalty=1.05, temperature=0.9
top_p=1.0, top_k=50
subtalker_dosample=true, subtalker_temperature=0.9
subtalker_top_p=1.0, subtalker_top_k=50
max_new_tokens=2048, non_streaming_mode=true
```

The discarded warmup is TTS001 with seed `8878`. Retained TTS001 through
TTS012 use seeds `8879` through `8890` in the frozen order. Every retained
output must be finite, nonempty mono PCM16 WAV at 24 kHz, under 30 seconds, and
free of full-scale samples. Model-generation and PCM-postprocess timings are
reported separately as P50/P95 component measurements. Optional listener
text-submit-to-first-audible timing is not a required metric and does not
become an end-to-end claim; do not subtract timestamps from different clocks.

Outputs are published with plain model/text labels and fixed order on the
existing listener at `http://127.0.0.1:8878/`; no new port, blind mapping, or
randomization is used. The listener action for each text is only `continue` or
`rejected`:

- `rejected`: immediately missing, unintelligible, strongly repetitive, or
  recurrently gross artifacts;
- `continue`: no immediate gross failure, permitting only a later larger TTS
  comparison.

The family-level `continue` gate requires all 12 texts to be marked `continue`;
one rejected text prevents that admission. This is not a quality pass or
winner.

Technical failure is failed-closed or inconclusive and is never repaired by a
retry or fallback in this experiment.

## Technical result

The one execution completed exactly one discarded TTS001 warmup with seed
`8878`, then exactly 12 retained renders in TTS001..TTS012 order with seeds
`8879`..`8890`. All 12 outputs are finite, nonempty mono PCM16 WAV files at
24 kHz, with durations from 1.52 to 7.60 seconds and zero full-scale samples.
The published inventory contains exactly 12 WAVs, 12 per-text `index.json`
records, and `research-receipt.json`; no failure receipt was created. Retry,
fallback, and training counts are all zero.

Measured component timings, excluding model load and the discarded warmup, are:

- model generation: P50 `2168.335503898561` ms, P95 `4440.004950296133` ms;
- PCM postprocess: P50 `16.276775859296322` ms, P95 `25.64452616497874` ms;
- text-submit-to-first-audible: not measured.

The GPU cleanup check found 2 MiB, 0% utilization, and no remaining process.
The fixed `8878` collection is present in TTS001..TTS012 order with explicit
input-text and model labels. The receipt is
[`research-receipt.json`](../../artifacts/ms3/listening/exp023-qwen3-tts-ono-anna-ja12-plain-20260812/research-receipt.json)
with file SHA-256
`0c30890f6e4257a98057adb13683a41ae4da38490e4652811e2729152172fd83`.

A supplemental fixed Japanese `faster-whisper-small` pass completed for all
12 outputs without retry, setting change, or rerender. Ten rows were either an
exact lexical match after punctuation/script normalization or close enough to
leave no specific token alert. Two rows need deliberate operator attention:
TTS008 transcribed `メモ` as `目も`, and TTS009 transcribed `realtime` as
`ヒリライン`. This is content-support evidence only, not an automatic quality
or pronunciation decision. Its ignored receipt SHA-256 is
`5a8377ec35b2390578607d294306d1e95f1eb3305611437e3791234edd289c40`.

`operator_judgment` remains `unreviewed` and `quality_status` remains
`not_assessed`. The next action is operator listening on the fixed collection;
until that happens, no per-text `continue`/`rejected` action, quality pass,
winner, route qualification, realtime claim, or end-to-end claim is recorded.

## Natural-conversation listen-now probe

While operator hearing is unavailable, one independent one-axis listen-now
probe compares the completed default outputs with one new candidate. The model,
speaker, language, 12 display/spoken texts, sampling settings, and retained
seeds stay fixed. Only `instruct` changes from empty to:

```text
自然な日常会話として、明るく親しみやすく、過剰に演技せずに話してください。
```

The runner publishes all 12 default/style pairs on port 8878 and then the fixed
Japanese `faster-whisper-small` screen checks for content corruption. A gross
loop or aggregate content regression closes this instruction. Otherwise it is
only an accumulated hearing candidate; machine metrics cannot select its
perceptual quality. This probe adds no training, TTS transport, route binding,
or product claim.

## Explicit exclusions

This direct offline render does not measure or qualify streaming, first-packet
latency, interruption, cancellation, Gateway behavior, Extension playout,
route safety, or end-to-end conversational latency. It is not a product voice
selection, quality pass, or winner. Raw audio, model artifacts, runtime files,
and private receipts remain outside Git.
