# EXP-137: disjoint low-semantic-token safety validation

Status: admitted; one read-only gpu0 diagnostic

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
