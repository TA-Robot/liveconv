# EXP-093: X-VC loop-source representation audit

Status: completed; universal input gate rejected; narrower hypothesis retained

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

## Result

All 33 rows completed in 75.56 seconds at 2.58 GB peak after a report-key fix.
The best single one-sided statistic that covered all three historically
loop-prone sources was high waveform active-sample fraction; it flagged eleven
rows, eight of them non-loop. Frozen Whisper-hidden rules were weaker. No
single semantic-token rule separated all three because `cv41748688u`, which
loops in base/control69, had 30 unique tokens across 30 frames.

A narrower exploratory signal remains: the two inputs on which retrained
adapters introduced a new loop had only 4 and 5 unique tokens and token runs of
27 and 13 frames. A `unique_tokens <= 5` rule would also flag three non-loop
rows in this same set. This in-sample observation does not authorize a runtime
threshold. Validate it on disjoint failure data before any bypass binding.

Decision: reject a universal pre-VC input-validity gate from this evidence.
Retain low token diversity as a separate safety hypothesis. Because the three
failures are model-dependent, move the next training point to the still-open
X-VC conditioning contract rather than training against this fitted gate.
