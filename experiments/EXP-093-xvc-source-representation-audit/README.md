# EXP-093: X-VC loop-source representation audit

Status: ready exploratory diagnostic

## Question

Do source-side waveform, semantic-token, or frozen Whisper-hidden statistics
separate the three Common Voice inputs that triggered gross loops across base,
control69, waveform-adversarial, source-semantic, and denoising-semantic arms?

## Boundary

Extract every metric from all 33 frozen EXP-055 sources before applying the
existing loop labels from EXP-058, EXP-076, EXP-085, and EXP-091. Report only
exploratory ranks and one-sided separability. Do not fit or authorize a runtime
bypass threshold on the same 33 rows, do not use ASR as an input feature, and
do not claim naturalness, target-voice quality, or a causal explanation.

## Definition of Done

- Commit the extractor and pure metric tests before GPU admission.
- Extract the same source representation for all 33 rows with the frozen base
  X-VC checkpoint on the exclusive `gpu0` lane.
- Record whether any simple statistic covers all three loop-prone sources and
  how many non-loop sources it also flags.
- Use the result to admit one distinct retraining or safe-bypass hypothesis, or
  reject input-validity gating if the source representations do not separate.

## Not in this experiment

No adapter training, threshold sweep, new ASR pass, human quality decision,
hash/receipt promotion work, or retry of closed human87/EXP-024 axes.
