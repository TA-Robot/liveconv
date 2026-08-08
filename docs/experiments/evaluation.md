# Evaluation plan

Status: Draft

## Evaluation lanes

Evaluate each candidate in four independent lanes.

1. **Japanese correctness:** readings, omissions, substitutions, mora timing,
   phrase boundaries, and pitch-accent acceptability.
2. **Audio integrity:** gaps, duplicated regions, clicks, clipping, loudness,
   bandwidth, and speaker consistency.
3. **Conversation behavior:** response start, interruption stop, overlap,
   backchannel timing, and stale-generation playback.
4. **Operations:** startup, warmup, throughput, failure recovery, privacy, cost,
   and reproducibility.

## Corpus design

Start with a versioned 40-utterance smoke set, then expand toward roughly 200
utterances before a production decision.

| Category | Smoke target | Full target | Examples |
|---|---:|---:|---|
| Ordinary conversation | 6 | 25 | questions, acknowledgements, repairs |
| Contact-center language | 5 | 25 | verification and procedure guidance |
| Telephone and postal numbers | 5 | 20 | mobile, landline, extension, postal code |
| Addresses | 4 | 20 | prefecture, block, building name |
| Dates, times, money, and units | 5 | 25 | era, weekday, currency, percent, storage |
| Proper nouns and polyphonic kanji | 5 | 30 | people, products, companies, contextual readings |
| Code switching and identifiers | 4 | 20 | Latin names, APIs, alphanumeric IDs |
| Interruption scenarios | 4 | 20 | beginning, middle, and end of response |
| Noise and degraded transport | 2 | 15 | call audio, DaaS, packet jitter |

Use synthetic or redistributable fixtures in CI. Restricted customer or voice
data belongs only in an authorized evaluation environment.

## Core metrics

### Timing

- capture to gateway ingress
- gateway ingress to model first output
- model steady-state real-time factor
- gateway output to playout
- end-to-end time to first audible output
- interruption detection to audible stop
- buffer depth over time

Report P50 and P95 after warmup with sample count and hardware.

For added-latency claims, use paired runs in the same environment and subtract
the matching native loopback duration per fixture. For defect rate, divide turns
with at least one verified integrity defect by all eligible completed turns;
report category-specific counts and every exclusion separately.

### Correctness

- kana-normalized error rate
- exact match for telephone numbers, addresses, and identifiers
- proper-noun correct-reading rate
- omission and insertion counts
- blinded native-speaker pairwise preference
- native-speaker MOS with a fixed rubric
- pitch-accent acceptability using trained review when available

### Integrity and reliability

- turns with a gap, click, duplicate, stall, or clipping
- stale-generation frames accepted or played
- queue overflow and fallback count
- failed session start and recovery time
- memory and GPU growth over a fixed-duration conversation

## Blinding and randomization

- Normalize loudness before preference tests without hiding clipping.
- Randomize variant labels and order.
- Keep raters unaware of model identity.
- Include repeated anchors to estimate rater consistency.
- Do not use a target speaker as the sole quality rater.

## Minimum report

Every analyzed experiment reports configuration, corpus version, exclusions,
timing distribution, quality distribution, failure examples, privacy class,
artifact locator, uncertainty, and whether the pre-registered decision rule was
met.
