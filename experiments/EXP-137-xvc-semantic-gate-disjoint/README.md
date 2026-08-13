# EXP-137: disjoint low-semantic-token safety validation

Status: completed; fixed low-token rule rejected

## Question

Does EXP-093's pre-existing `unique semantic tokens <= 5` rule identify the
adapter-added gross-loop inputs in frozen fresh48 and Hadou31 without being
refit to their outputs?

## Method

Extract frozen-base X-VC source representation statistics for all 79 exact
fresh48 and Hadou31 model windows. Apply the threshold `<= 5` unchanged.
Report candidate-added loop true positives, false negatives, and false
positives separately by dataset and combined. The loop labels come from the
already-completed EXP-135/136 screens; no threshold search is allowed.

## Definition of done and stop

If the fixed rule misses any candidate-added loop, reject it and move to a
different training objective or explicit hard-input rehearsal. If it catches
all added loops, retain a separately reviewed fallback-routing hypothesis; do
not bind a production gate from this diagnostic alone. This cannot select
naturalness, target identity, or a quality winner and produces no promotion.

## Result

All 79 rows completed in `94.77` seconds at `2.40 GiB` peak. The fixed rule
flagged zero rows and missed both adapter-added failures: `cv30615849f` had 24
unique tokens and `RECITATION324_138` had 29, versus a dataset median of 28.
Reject the low-token safety rule; do not fit a replacement threshold on these
outputs. The failures are not explained by frozen source-token collapse.

Next, change the amount of distinct real model-window supervision rather than
another gate or coverage heuristic: keep 209 teacher positions fixed but use a
near-one-pass pool spanning all quality-admitted training-only Hadou utterances,
all 48 disjoint Common Voice teachers, and JVS3. Frozen fresh48/Hadou31 remain
evaluation-only.
