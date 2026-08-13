# EXP-130: X-VC quality-filtered kana-coverage teacher pool

Status: prepared; one bounded gpu0 lane

## Question

Does replacing EXP-124's metadata-first Hadou subset with a quality-filtered,
kana-coverage and length-balanced subset reduce corruption and improve broad
content preservation?

## One change

Keep EXP-124's CV24, JVS3, 48-source total, 209 full-output teacher positions,
835 standard positions, 1,044 updates, target data, objective, control69 LoRA,
LR, and seed. Replace only Hadou21: select seven rows from each deterministic
official-kana length tertile after excluding all 87 target IDs and frozen
Hadou31, require the existing source ASR audit CER to be at most 0.15, and
greedily maximize new official-katakana unigram, bigram, and trigram coverage.

This does not retry teacher count, share, horizon, LR, LoRA scope, or EXP-024
DTW. It does not fit the selection to any downstream evaluation row.

## Stop

Commit and bind the selection before one smoke and one training run. Render
external7, frozen fresh48, and Hadou31. Reject on an added gross loop or broad
common-non-loop regression. Machine ASR cannot select naturalness, target
voice, or a winner.
