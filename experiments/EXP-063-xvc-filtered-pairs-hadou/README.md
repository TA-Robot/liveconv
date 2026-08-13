# EXP-063: filtered-pair X-VC on 31 clean Hadou heldout sentences

Status: completed; mixed Hadou result with one new gross loop

Render EXP-060 on all 31 rows frozen by
`EXP-060-xvc-filtered-pairs-hadou-evaluation/hadou-evaluation.json`. Materialize
the exact first endpoint-complete 2.4 seconds before rendering. Machine ASR is
relative to the exact source window and may only screen corruption; it cannot
select naturalness, speaker identity, or voice quality.

The candidate published 93 comparison WAVs across 31 unseen Hadou sentences.
Relative to control69 it produced three lower, twenty-five equal, and three
higher source-relative distances. Excluding its one gross-loop row, candidate
versus control means were 0.171 versus 0.185 and medians were 0.080 versus
0.097, but the balanced 3/24/3 changes do not show a broad method gain. The
official full-utterance text is not used for a 2.4-second-window decision. The
new loop and EXP-061 regression close filtered6x2; audio remains unheard.

```bash
.venv/bin/python tools/xvc-source-diversity/prepare_hadou_evaluation.py \
  --selection experiments/EXP-060-xvc-filtered-pairs-hadou-evaluation/hadou-evaluation.json \
  --source-manifest artifacts/xvc-human-paired/runrun-human-paired.manifest.json \
  --pronunciation-audit artifacts/xvc-human-paired/audit/hadou-runrun/pronunciation-triage-2f35e75f.json \
  --source-root artifacts/xvc-human-paired/source-audio/hadou-ita \
  --output-root artifacts/xvc-source-diversity/exp060-hadou31-inputs-v1

HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind content-filtered6x2-hadou \
  --evaluation-set artifacts/xvc-source-diversity/exp060-hadou31-inputs-v1/evaluation.json \
  --source-root artifacts/xvc-source-diversity/exp060-hadou31-inputs-v1 \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp060-content-filtered6x2-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp063-content-filtered-hadou31-v1 \
  --listener-dir artifacts/ms3/listening/exp063-content-filtered-hadou31-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
