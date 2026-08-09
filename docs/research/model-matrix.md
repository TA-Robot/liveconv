# Verified voice-conversion candidate matrix

Status: Research prioritization

Evidence snapshot: 2026-08-09

This document prioritizes experiments. It is not an experiment result, a product
decision, or legal approval. Published measurements below retain the authors'
measurement boundary and do not satisfy a liveconv phase gate. Pin an immutable
source and model revision before implementing an adapter.

## Candidate evidence

| Candidate | Japanese evidence | Code, weight, and data terms | Runtime and latency claim | Target preparation | Integration risk and research priority |
|---|---|---|---|---|---|
| [RVC v2](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) | Target-specific, text-free VC makes a Japanese smoke test practical, but the official project publishes no Japanese quality benchmark or supported-language guarantee. | **Code:** MIT. **Weights:** no separate pretrained-weight license was found; audit ContentVec, RMVPE, and each target checkpoint. **Data:** the project says its base pretraining uses about 50 hours of VCTK; [VCTK 0.92 is CC BY 4.0](https://datashare.ed.ac.uk/items/30e7453c-9ea8-48b4-8e18-f96d0dc62928/full). User target recordings retain their own authorization and use restrictions. | Common v2 checkpoints use 40 kHz; the adapter must read the actual checkpoint rate. The official realtime GUI reports 170 ms end-to-end, or 90 ms with ASIO, and states that this is highly driver and hardware dependent. That claim covers local capture, conversion, and playback, not liveconv network transport. GPU is the practical path; CPU and DirectML paths exist. | Train one checkpoint and retrieval index per target. The project recommends at least about 10 minutes of low-noise target speech. | Most mature first real model and the recommended streaming baseline. Freeze a checkpoint, pitch extractor, index, sample rate, and dependency manifest before EXP-003. |
| [Beatrice 2](https://prj-beatrice.com/) | Strongest direct Japanese provenance in this set. The [trainer](https://huggingface.co/fierce-cats/beatrice-trainer) pretraining uses ReazonSpeech, and its published test assets include Japanese Common Voice utterances. This is provenance, not a published Japanese quality score. | **Code:** trainer and [VST host code](https://github.com/prj-beatrice/beatrice-vst) are MIT. **Weights:** the trainer card declares its included pretrained models MIT. **Inference library:** [`beatrice.lib` use is separately restricted](https://github.com/aq2r/beatrice-client#license---beatrice); an independent server integration requires Project Beatrice permission. **Data:** [ReazonSpeech is CDLA-Sharing-1.0 with an Article 30-4-only condition](https://huggingface.co/datasets/reazon-research/reazonspeech); [LibriTTS-R is CC BY 4.0](https://www.openslr.org/141/); bundled DNS noise includes CC BY, CC0, and CC BY-SA sources. VocalSet rights and every target corpus need separate review. | Streaming VC. The trainer states a target of less than 30 MB, RTF below 0.2 on one i7-1165G7 thread, and about 50 ms measured through external recording equipment with the official VST. These are project claims, not liveconv measurements. Inference needs no GPU; default training uses about 9 GB VRAM and reportedly takes about 40 minutes on RTX 4090. A fixed public sample-rate contract was not found. | Supervised target-speaker training produces a `paraphernalia` model directory. The official material gives no minimum target duration. | Best lightweight Japanese candidate if server use is licensed. Run a permission and packaging spike before adapter work; if approved, promote it ahead of X-VC. |
| [X-VC](https://github.com/Jerrister/X-VC) | Official training and evaluation cover English and Chinese only. Cross-lingual English/Chinese results do not establish Japanese content preservation. | **Code:** MIT. **Weights:** [official model card](https://huggingface.co/chenxie95/X-VC) says MIT. **Data:** the [paper](https://arxiv.org/abs/2604.12456) reports Emilia plus LibriTTS and additional pairs generated with Seed-VC. Emilia access terms say CC BY-NC 4.0 and disclaim ownership of source audio; [LibriTTS is CC BY 4.0](https://www.openslr.org/60/). Commercial status and the GLM-4-Voice tokenizer, ERes2Net, SAC, and generated-data chain require review despite the model card's MIT label. | 16 kHz, 539M total parameters and 44M converter parameters. On one RTX 3090, the paper reports 240 ms model-induced latency (120 ms current, 20 ms overlap, 100 ms future) plus 58.17 ms average online compute. It excludes network, playout, and one-time target conditioning. The offline RTF claim is 0.014. Streaming uses a non-causal 2.4-second processing window and emits only the current region. | Zero-shot reference WAV. Mel conditions and a speaker embedding are precomputed once and reused; the official sources do not specify a recommended reference duration. | Recommended quality candidate after an offline Japanese gate. Require Japanese STT preservation and boundary-continuity evidence before enabling its streaming path. |
| [Seed-VC](https://github.com/Plachtaa/seed-vc) | The tiny model uses XLSR and other variants use Whisper-derived content features, but the official repository publishes no Japanese evaluation. Multilingual encoders alone are not Japanese evidence. | **Code:** GPL-3.0. **Weights:** [official Hugging Face repository](https://huggingface.co/Plachta/Seed-VC) labels the weights GPL-3.0. **Data:** the official repository and model card do not disclose a complete training-data inventory or license chain. | The realtime tiny model is 25M parameters at 22.05 kHz. On an RTX 3060 Laptop GPU, the official table reports 430 ms latency and 150 ms inference per 180 ms block. The repository also describes approximately 300 ms algorithm delay plus 100 ms device delay. V2 is 67M CFM plus 90M AR at 22.05 kHz and is positioned for stronger offline voice and accent conversion, not the realtime GUI. GPU is strongly recommended. | Zero-shot with 1 to 30 seconds of reference speech. Optional one-shot or few-shot fine-tuning is supported. | Useful diffusion-family comparator, but the repository was archived in November 2025, GPL isolation is required, and data provenance and Japanese behavior remain unresolved. Keep behind RVC and X-VC. |
| [MeanVC2](https://github.com/ASLP-lab/MeanVC2) | Not yet a Japanese candidate. The [paper](https://arxiv.org/abs/2606.09050) trained on 10,000 hours of Mandarin Emilia, uses a Mandarin Fast-U2++ content encoder, and evaluates on Mandarin Seed-TTS pairs only. | **Code:** README claims Apache-2.0, but the repository snapshot has no license file. **Weights:** Google Drive checkpoints have no separately stated terms. **Data:** original Emilia is CC BY-NC 4.0 with source-rights disclaimers; Fast-U2++ and WenetSpeech add another provenance chain. | 18M VC parameters, 16 kHz output, 40 ms chunk plus 40 ms future context. On single-threaded, single-core AMD EPYC 7542, the paper reports 109.88 ms full-pipeline first-packet latency and total RTF 0.633. This excludes liveconv network and playout. | Zero-shot target WAV with optional speaker-specific fine-tuning. The official sources give no recommended reference duration. | Hold. Its low CPU cost is attractive, but a Japanese smoke test and explicit code/checkpoint terms are prerequisites. Do not describe it as the first Japanese streaming VC. |
| [OpenVoice V2](https://github.com/myshell-ai/OpenVoice) | The official README explicitly lists Japanese as natively supported in V2. It provides no Japanese streaming benchmark. | **Code and weights:** the project declares V1 and V2 MIT and free for commercial and research use. **Data:** the official README and model distribution do not provide a complete training-data license inventory. Reference voices still require authorization. | Tone-color conversion with zero-shot cross-lingual cloning. The official documentation gives no streaming contract, latency benchmark, hardware boundary, or stable adapter sample-rate contract. | Extract a target speaker embedding from reference audio. The source flow is commonly TTS plus tone-color conversion rather than transparent realtime conversion of an arbitrary stream. | Use as an offline Japanese control, not as the first streaming adapter. It can distinguish a Japanese-capable tone converter from the direct streaming VC candidates. |

## Recommended adapter order

1. Keep `passthrough` and a deterministic DSP transform as protocol and
   evaluation controls. They validate routing, cancellation, waveform analysis,
   and STT without introducing a model variable.
2. Implement RVC v2 as the first model adapter. It has the most mature realtime
   path and exposes the target-training and model-switching lifecycle early.
3. Prove X-VC offline on the frozen Japanese corpus. Add streaming only if the
   preregistered STT, discontinuity, latency, and voice-similarity checks pass.
4. In parallel, obtain written permission for Beatrice server inference and
   audit its data chain. If approved, move Beatrice ahead of X-VC as the
   lightweight Japanese adapter.
5. Add OpenVoice V2 as an offline Japanese comparison.
6. Add Seed-VC only as an isolated GPL worker when a diffusion comparison is
   worth its maintenance cost. Keep MeanVC2 on hold until Japanese and license
   blockers are resolved.

Run each third-party runtime in its own worker process or container. This keeps
Python and CUDA dependencies, copyleft boundaries, model residency, failure
isolation, and GPU eviction observable at the adapter boundary.

## Open decisions

- Who will provide legal review for model-derived weights and training-data
  restrictions, especially Beatrice inference, Emilia derivatives, and RVC
  dependency checkpoints?
- Which authorized target voice and minimum recording protocol will be frozen
  for supervised RVC and Beatrice comparison?
- Does X-VC pass Japanese offline preservation before any streaming work is
  funded?
- Is Beatrice server permission obtainable, and does it permit the intended
  remote service and redistribution model?
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
