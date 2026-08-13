# EXP-130: X-VC quality-filtered kana-coverage teacher pool

Status: admitted; one bounded gpu0 lane

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

## Bound input

- Manifest: `artifacts/xvc-source-diversity/exp130-phonetic-teacher48-inputs-v1/training.json`
- SHA-256: `52879c2cfd492f075400913c9ee377d7b4347343eba520cf495fc11daecceb6b`
- Composition: Common Voice 24, Hadou 21, JVS 3
- Hadou bins: short 7, medium 7, long 7; maximum admitted audit CER `0.148148`
- Method commit: `94fb2d1`

## Stop

Commit and bind the selection before one smoke and one training run. Render
external7, frozen fresh48, and Hadou31. Reject on an added gross loop or broad
common-non-loop regression. Machine ASR cannot select naturalness, target
voice, or a winner.
