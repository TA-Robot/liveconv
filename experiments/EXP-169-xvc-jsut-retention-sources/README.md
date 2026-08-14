# EXP-169: disjoint category-balanced JSUT retention sources

Status: target render ready

## Goal

Prepare a genuinely different Japanese retention-data branch while preserving
the EXP-163 method that survived coarse cross-corpus gates. This is training
data preparation, not evaluation or a quality decision.

Exclude all 24 frozen JSUT evaluation IDs, then select 85 remaining utterances
by transcript-order equal-bin centers without reading text, audio, or model
output: basic 29; onomatopoeia, counter/suffix, loanword, and travel 14 each.
Bind them in order to EXP-150's existing 85 easy curriculum slots. The hard 85
positions, target IDs, total 170 updates, LoRA69, real-reference adversarial
objective, optimizer, LR, clip, zero condition, and upstream EMA remain fixed.

The next GPU preparation renders control69 on these 85 sources. Any gross
control output stops before training; no output-dependent replacement is
allowed. If all survive, only the easy retention source/teacher domain changes
in the next training lane. Raw JSUT audio remains ignored and uncommitted.

The committed target renderer reads every row exactly once, uses the frozen
control69 adapter and existing target assignment, and writes a training-only
pool plus target identities. The generated targets must pass the existing
source-relative ASR/gross-repetition screen before a curriculum is admitted.
Sources shorter than X-VC's 2.4-second model window are right-zero-padded, and
longer sources use the leading 2.4 seconds, matching the existing runner's
window. The frozen source row is not replaced after preprocessing.
