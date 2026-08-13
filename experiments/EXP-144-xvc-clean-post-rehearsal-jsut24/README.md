# EXP-144: clean post-rehearsal on untouched JSUT24

Status: prepared; evaluation-only

## Goal

Test the EXP-141 X-VC candidate outside Common Voice, Hadou, and the local
tongue-twister diagnostic. Render base, EXP-035 control69, and EXP-141 on 24
heldout JSUT 1.1 utterances spanning ordinary sentences, onomatopoeia,
counter-suffix sequences, loanwords, and travel phrases.

## Frozen evaluation

The official archive was bound at SHA-256
`081da547f63fd2868184d3a5b488ff325b7ea88464fec2168222b8aeacb20faf`.
Within each category, split transcript order into equal-width bins and select
the center of each bin without reading model outputs: basic5000 8,
onomatopee300 4, countersuffix26 4, loanword128 4, and travel1000 4.

- Manifest: `artifacts/xvc-source-diversity/exp144-jsut24-inputs-v1/evaluation.json`
- Manifest SHA-256: `556ce43a85798fe18ec19f60922db4483ba3f9d55de6134413bd6d5987d03118`
- Speaker count: 1
- Window: first 2.4 seconds, right-pad if short

The official audio and archive remain excluded from Git and result bundles.
The corpus license and category-specific text attributions remain bound to the
official JSUT `LICENCE.txt`.

## Stop and boundary

Do not run this evaluation before EXP-141 finishes the frozen external7,
fresh48, and Hadou31 corruption screens. Reject on candidate-added gross
repetition or broad cross-category content regression. Auxiliary ASR cannot
select naturalness, target identity, a keeper, or promotion; all outputs stay
unheard and unselected until the operator returns.
