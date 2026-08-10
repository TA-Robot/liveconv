# Verified voice candidate matrix

Status: Research prioritization

Evidence snapshot: 2026-08-10

This document prioritizes experiments. It is not an experiment result, a product
decision, or legal approval. Published measurements below retain the authors'
measurement boundary and do not satisfy a liveconv phase gate. Pin an immutable
source and model revision before implementing an adapter.

## MS-3 youthful-feminine intake

The operator's real MS-2 listening result rejected the prepared voices. The
active preference is a youthful feminine Japanese voice, and the comparison now
uses immutable voice variants rather than one entry per model family. The
machine-readable intake is
[`config/ms3-voice-variant-candidates.json`](../../config/ms3-voice-variant-candidates.json).

| Candidate | Current official evidence | MS-3 disposition |
|---|---|---|
| [Qwen3-TTS 0.6B CustomVoice](https://github.com/QwenLM/Qwen3-TTS) | Apache-2.0; Japanese and streaming are listed. The official `Ono_Anna` preset is described as a playful Japanese female voice with a light, nimble timbre. CustomVoice has fixed presets; it is not arbitrary voice cloning. | High-value deferred TTS candidate. It cannot count in the protocol-v1 VC first wave; LV-063 must first accept a committed-text transport decision. |
| [Qwen3-TTS 0.6B Base](https://github.com/QwenLM/Qwen3-TTS#voice-clone) | Apache-2.0; Japanese, streaming, three-second rapid voice cloning, and fine-tuning are listed. | Deferred behind LV-063 and an authorized, content-addressed reference preparation. Keep its TTS input/claim separate from VC. |
| [Fun-CosyVoice3 0.5B](https://github.com/FunAudioLLM/CosyVoice) | Apache-2.0; Japanese, cross-lingual zero-shot cloning, and bi-streaming are listed. The repository's latency figure is a model/runtime claim, not Extension end to end. | Deferred second TTS family behind LV-063. Retain the Japanese normalizer because explicit phoneme control is documented for Chinese and English, not Japanese. |
| [MeanVC2](https://github.com/ASLP-lab/MeanVC2) | Its README claims Apache-2.0, but the reviewed snapshot has no LICENSE file or separate checkpoint terms. It is a small zero-shot VC with realtime mode and 16 kHz output; Japanese quality is unestablished. | License-review first-wave option only. Code/checkpoint terms, Japanese content preservation, and explicit 16-to-48 kHz route handling must all close before it becomes runnable. |
| [Amitaro voice material](https://amitaro.net/voice/voice_rule/) | Current creator terms permit AI/model training and RVC with attribution; business product/service use has a notice requirement. | Candidate reference/style source for `yofukashi`, `runrun`, and `punsuka`. Each prepared style needs its own authorization identity; no audio enters Git. |
| [MOSS-TTS-Nano](https://github.com/OpenMOSS/MOSS-TTS-Nano) | Japanese, streaming/cloning, small and CPU/ONNX options are documented, but repository and model-card license statements are not yet aligned. | License-review only; no artifact acquisition or implementation. |
| [FasterSVC](https://github.com/uthree/fastersvc) | JVS-pretrained weights are published, but the executable repository lacks a clear license and calls itself experimental. | Excluded until code and training-data terms are resolved. |
| [Seed-VC](https://github.com/Plachtaa/seed-vc) | GPL-3.0, archived upstream, zero-shot and accent-conversion paths. | Later comparison-only lane if first-wave evidence shows that accent/prosody preservation is the limiting defect. |

[JVS](https://sites.google.com/site/shinnosuketakamichi/research-topics/jvs_corpus)
and [JSUT](https://sites.google.com/site/shinnosuketakamichi/publication/jsut)
remain useful research corpora, but their audio terms are
research/non-commercial/personal-use unless separately licensed. They may not be
silently treated as unrestricted training data.

## Candidate evidence

| Candidate | Japanese evidence | Code, weight, and data terms | Runtime and latency claim | Target preparation | Integration risk and research priority |
|---|---|---|---|---|---|
| [RVC v2](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) | Target-specific, text-free VC makes a Japanese smoke test practical, but the official project publishes no Japanese quality benchmark or supported-language guarantee. | **Code:** MIT. **Weights:** no separate pretrained-weight license was found; audit ContentVec, RMVPE, and each target checkpoint. **Data:** the project says its base pretraining uses about 50 hours of VCTK; [VCTK 0.92 is CC BY 4.0](https://datashare.ed.ac.uk/items/30e7453c-9ea8-48b4-8e18-f96d0dc62928/full). User target recordings retain their own authorization and use restrictions. | Common v2 checkpoints use 40 kHz; the adapter must read the actual checkpoint rate. The official realtime GUI reports 170 ms end-to-end, or 90 ms with ASIO, and states that this is highly driver and hardware dependent. That claim covers local capture, conversion, and playback, not liveconv network transport. GPU is the practical path; CPU and DirectML paths exist. | Train one checkpoint and retrieval index per target. The project recommends at least about 10 minutes of low-noise target speech. | Most mature first real model and the recommended streaming baseline. Freeze a checkpoint, pitch extractor, index, sample rate, and dependency manifest before EXP-003. |
| [Beatrice 2](https://prj-beatrice.com/) | Strongest direct Japanese provenance in this set. The [trainer](https://huggingface.co/fierce-cats/beatrice-trainer) pretraining uses ReazonSpeech, and its published test assets include Japanese Common Voice utterances. This is provenance, not a published Japanese quality score. | **Code:** trainer and [VST host code](https://github.com/prj-beatrice/beatrice-vst) are MIT. **Weights:** the trainer card declares its included pretrained models MIT. **Inference library:** [`beatrice.lib` use is separately restricted](https://github.com/aq2r/beatrice-client#license---beatrice); an independent server integration requires Project Beatrice permission. **Data:** [ReazonSpeech is CDLA-Sharing-1.0 with an Article 30-4-only condition](https://huggingface.co/datasets/reazon-research/reazonspeech); [LibriTTS-R is CC BY 4.0](https://www.openslr.org/141/); bundled DNS noise includes CC BY, CC0, and CC BY-SA sources. VocalSet rights and every target corpus need separate review. | Streaming VC. The trainer states a target of less than 30 MB, RTF below 0.2 on one i7-1165G7 thread, and about 50 ms measured through external recording equipment with the official VST. These are project claims, not liveconv measurements. Inference needs no GPU; default training uses about 9 GB VRAM and reportedly takes about 40 minutes on RTX 4090. A fixed public sample-rate contract was not found. | Supervised target-speaker training produces a `paraphernalia` model directory. The official material gives no minimum target duration. | Best lightweight Japanese candidate if server use is licensed. Run a permission and packaging spike before adapter work; if approved, promote it ahead of X-VC. |
| [X-VC](https://github.com/Jerrister/X-VC) | Official training and evaluation cover English and Chinese only. Cross-lingual English/Chinese results do not establish Japanese content preservation. | **Code:** MIT. **Weights:** [official model card](https://huggingface.co/chenxie95/X-VC) says MIT. **Data:** the [paper](https://arxiv.org/abs/2604.12456) reports Emilia plus LibriTTS and additional pairs generated with Seed-VC. Emilia access terms say CC BY-NC 4.0 and disclaim ownership of source audio; [LibriTTS is CC BY 4.0](https://www.openslr.org/60/). Commercial status and the GLM-4-Voice tokenizer, ERes2Net, SAC, and generated-data chain require review despite the model card's MIT label. | 16 kHz, 539M total parameters and 44M converter parameters. On one RTX 3090, the paper reports 240 ms model-induced latency (120 ms current, 20 ms overlap, 100 ms future) plus 58.17 ms average online compute. It excludes network, playout, and one-time target conditioning. The offline RTF claim is 0.014. Streaming uses a non-causal 2.4-second processing window and emits only the current region. | Zero-shot reference WAV. Mel conditions and a speaker embedding are precomputed once and reused; the official sources do not specify a recommended reference duration. | Recommended quality candidate after an offline Japanese gate. Require Japanese STT preservation and boundary-continuity evidence before enabling its streaming path. |
| [Seed-VC](https://github.com/Plachtaa/seed-vc) | The tiny model uses XLSR and other variants use Whisper-derived content features, but the official repository publishes no Japanese evaluation. Multilingual encoders alone are not Japanese evidence. | **Code:** GPL-3.0. **Weights:** [official Hugging Face repository](https://huggingface.co/Plachta/Seed-VC) labels the weights GPL-3.0. **Data:** the official repository and model card do not disclose a complete training-data inventory or license chain. | The realtime tiny model is 25M parameters at 22.05 kHz. On an RTX 3060 Laptop GPU, the official table reports 430 ms latency and 150 ms inference per 180 ms block. The repository also describes approximately 300 ms algorithm delay plus 100 ms device delay. V2 is 67M CFM plus 90M AR at 22.05 kHz and is positioned for stronger offline voice and accent conversion, not the realtime GUI. GPU is strongly recommended. | Zero-shot with 1 to 30 seconds of reference speech. Optional one-shot or few-shot fine-tuning is supported. | Useful diffusion-family comparator, but the repository was archived in November 2025, GPL isolation is required, and data provenance and Japanese behavior remain unresolved. Keep behind RVC and X-VC. |
| [MeanVC2](https://github.com/ASLP-lab/MeanVC2) | Not yet a Japanese candidate. The [paper](https://arxiv.org/abs/2606.09050) trained on 10,000 hours of Mandarin Emilia, uses a Mandarin Fast-U2++ content encoder, and evaluates on Mandarin Seed-TTS pairs only. | **Code:** README claims Apache-2.0, but the repository snapshot has no license file. **Weights:** Google Drive checkpoints have no separately stated terms. **Data:** original Emilia is CC BY-NC 4.0 with source-rights disclaimers; Fast-U2++ and WenetSpeech add another provenance chain. | 18M VC parameters, 16 kHz output, 40 ms chunk plus 40 ms future context. On single-threaded, single-core AMD EPYC 7542, the paper reports 109.88 ms full-pipeline first-packet latency and total RTF 0.633. This excludes liveconv network and playout. | Zero-shot target WAV with optional speaker-specific fine-tuning. The official sources give no recommended reference duration. | Hold. Its low CPU cost is attractive, but a Japanese smoke test and explicit code/checkpoint terms are prerequisites. Do not describe it as the first Japanese streaming VC. |
| [OpenVoice V2](https://github.com/myshell-ai/OpenVoice) | The official README explicitly lists Japanese as natively supported in V2. It provides no Japanese streaming benchmark. | **Code and weights:** the project declares V1 and V2 MIT and free for commercial and research use. **Data:** the official README and model distribution do not provide a complete training-data license inventory. Reference voices still require authorization. | Tone-color conversion with zero-shot cross-lingual cloning. The official documentation gives no streaming contract, latency benchmark, hardware boundary, or stable adapter sample-rate contract. | Extract a target speaker embedding from reference audio. The source flow is commonly TTS plus tone-color conversion rather than transparent realtime conversion of an arbitrary stream. | Use as an offline Japanese control, not as the first streaming adapter. It can distinguish a Japanese-capable tone converter from the direct streaming VC candidates. |

## Recommended variant order

1. Keep native, the retained quality-failed RVC profile, and the lower-voice
   Beatrice profile as controls. Do not spend first-wave tuning time on them.
2. Prepare separately authorized Amitaro `yofukashi`, `runrun`, and `punsuka`
   variants across RVC, MeanVC2, X-VC, and OpenVoice for the counted protocol-v1
   VC first wave.
3. Route-qualify 9-12 VC variants across at least four families through the exact Extension path before using
   their output in the listening screen.
4. Keep Qwen3-TTS `Ono_Anna`, Qwen Base, and CosyVoice3 as the preferred TTS
   branch, but implement them only after LV-063 accepts a committed-text
   transport and interruption contract.
5. Start new Japanese checkpoint training only if the bounded first wave cannot
   produce a useful shortlist and its data license plus one-GPU-day plan are
   approved.
6. Keep Seed-VC, MOSS-TTS-Nano, FasterSVC, and research-only corpora outside the
   critical path until their explicit blockers close.

Run each third-party runtime in its own worker process or container. This keeps
Python and CUDA dependencies, copyleft boundaries, model residency, failure
isolation, and GPU eviction observable at the adapter boundary.

## Open decisions

- Who will provide legal review for model-derived weights and training-data
  restrictions, especially Beatrice inference, Emilia derivatives, and RVC
  dependency checkpoints?
- Which exact Amitaro styles or other youthful-feminine references pass the
  authorization, attribution, and business-notice review?
- Does X-VC pass Japanese offline preservation before any streaming work is
  funded?
- Does the first-wave authorized-reference VC comparison justify funding any new
  Japanese checkpoint training at all?
- Which immutable repository commits, weight hashes, and container digests will
  define each experiment variant?

## Evidence rules

- Treat published latency as a prioritization signal only. liveconv reports
  capture, network, queue, model, return, and playout timing separately.
- Do not infer Japanese support from a multilingual encoder, a translated
  README, or English/Chinese cross-lingual results.
- Record code, pretrained-weight, training-data, target-voice, and generated-
  artifact terms independently.
- Freeze input fixtures, revisions, model hashes, parameters, warmup, and sample
  count before comparisons.
- Only results produced by the approved liveconv experiment harness can satisfy
  a phase gate.
