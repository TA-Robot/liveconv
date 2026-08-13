# EXP-020: Actual input x existing human-trained RVC

This is the quality reset after the synthetic eSpeak/X-VC lane. It compares the
existing human-trained RVC profiles on the audio that the live system actually
receives: the pre-VC ChatGPT audio path. It does not train a new model.

Listen-now: Stage 0 is already published on port 8878. Hear it before opening
another experiment. A `continue` is not a quality pass; a `rejected` drops
that profile from later actual-input listens.

Operator availability update (2026-08-13): human hearing is temporarily
unavailable, while the active instruction is to keep one bounded GPU quality
lane moving. The existing Stage-0 auxiliary ASR distances were 0.725 for
Hakihaki, 0.650 for Runrun, and 0.775 for Yofukashi; these are content triage,
not perceptual rankings. Existing Sasayaki presets ranged from 0.537 to 0.780
on the identical source hash, showing that preset choice materially changes
content behavior. One committed live-Gateway comparison therefore renders the
already-deployed Runrun standard plus four presets, with standard Sasayaki as
a cross-style reference. It does not train RVC or select a winner.

```bash
set -a
. /root/.config/liveconv/gateway.env
set +a
uv run --frozen --all-packages python \
  tools/rvc-actual-compare/render_runrun_presets.py \
  --deployment artifacts/ms3/current \
  --source-original "画面録画 2026-08-11 114251.mp4" \
  --source-f32 /tmp/liveconv-source-20260811-114251.f32 \
  --source-wav artifacts/ms3/listening/exp020-human-rvc-smoke-8s-plain-20260812/00-native-source.wav \
  --work-dir artifacts/rvc-actual-compare/exp020-runrun-presets-actual-v1 \
  --listener-dir artifacts/ms3/listening/exp020-runrun-presets-actual-v1 \
  --gateway-url http://127.0.0.1:8877
```

The Runrun comparison already used the live Gateway and realtime 20 ms pacing;
do not rerender its standard arm merely to call it a system-path probe. The
coarse machine screen found no new Runrun preset better than the cross-style
Sasayaki reference and gross repetition in girl-bright.

One follow-up compares the exact deployed Sasayaki standard and clean-bright
presets on three public Hadou heldout utterances already used as source-only
X-VC controls: `EMOTION100_002`, `EMOTION100_004`, and `EMOTION100_017`.
The single actual-input screen had favored clean-bright among RVC candidates,
so this bounded run tests whether that content behavior generalizes instead of
adding another preset or rerendering the same 8.17-second source. The fixed
Japanese STT screen may close a profile for gross corruption, but cannot select
sound quality. The six outputs remain unselected until human hearing.

Clean-bright preserved auxiliary content on all three rows. One next offline
diagnostic therefore holds its checkpoint, pitch, index, RMS mix, protection,
and source rows fixed and changes only F0 extraction from RMVPE to PM. Existing
full-utterance evidence improved content only slightly over the Gateway anchor,
so block-size points are not admitted first. PM is closed on a gross/content
regression; an improvement only admits later human hearing and does not qualify
a Gateway profile.

## The quantity split

Target-data quantity and source/evaluation-data quantity are separate facts:

| Item | Quantity recorded for admission | Role |
| --- | --- | --- |
| RVC A: hakihaki | 757 target utterances, about 42 raw minutes | Existing target profile; duration is approximate raw-total metadata |
| RVC B: runrun | 652 target utterances, 35.80 raw minutes | 20 ms RMS activity: 22.95 min at -45 dBFS / 23.77 min at -50 dBFS |
| RVC C: yofukashi | 652 target utterances, 34.34 raw minutes | 20 ms RMS activity: 21.22 min at -45 dBFS / 22.65 min at -50 dBFS |
| Actual pre-VC ChatGPT source | 10-15 minutes and 80-120 utterances required | New evaluation capture gate |

The target durations are raw source-file totals, not post-clean speech totals.
The active-time values above are reproducible RMS activity diagnostics, not
post-clean usable-speech totals and not an automatic training gate. A later
training plan must run and record a fixed VAD/cleaning rule and report both raw
total and usable post-clean duration. The existing 8.170667-second
source recording is only a plumbing check. It is not enough to make a quality
claim. The target quantities above do not satisfy the source gate, and the
source gate does not describe model training data.

The source capture uses the exact 100 known utterances in
`source-evaluation-script.v1.json`. They cover short replies, ordinary speech,
long explanations, numbers and entities, English terms, repairs and boundaries,
questions, and extended speech. Read only each `text` value in order, preferably
in ten consecutive blocks of ten, with about one second of silence between
items. The script contains 4,096 Japanese characters; the spoken audio and
pauses are expected to land near the 10-15 minute source gate, while the corpus
builder decides admission from the decoded audio rather than that estimate.
The recorded utterance order must remain bound to these known texts; do not use
an unknown free-form transcript for the dev/confirmation quality result.

## Stage 0: immediate rejection smoke

There is an immediate plain-label smoke artifact at
`artifacts/ms3/listening/exp020-human-rvc-smoke-8s-plain-20260812`. It uses one
8.170667-second actual-input sample and four visible labels:

| Label | Route |
| --- | --- |
| `Native (no conversion)` | Original pre-VC source |
| `RVC A: hakihaki` | Existing standard profile |
| `RVC B: runrun` | Existing standard profile |
| `RVC C: yofukashi` | Existing standard profile |

This stage is deliberately tiny. It may only reject a profile that is
obviously broken, such as missing output, severe repeated artifacts, or
unintelligible speech. It cannot pass, select, rank, or establish quality. Any
converted profile that fails can be dropped immediately; survivors proceed to
the 10-15 minute / 80-120 utterance source gate below. If all converted
profiles fail, stop this comparison and replan the model/data route. Native
remains the audible reference either way.

## Frozen comparison

Once the source gate is reached for the Stage 0 survivors, freeze the aggregate source manifest and split
it into two disjoint labelled sets:

- `dev24`: 24 utterances for the first direct usability pass.
- `confirmation24`: 24 different utterances for confirmation.

The remaining admitted utterances are held back for failure coverage or a later
replan. Every item is rendered through the same four plainly labelled routes:

| Label | Route |
| --- | --- |
| `Native (no conversion)` | Original pre-VC source |
| `RVC A: hakihaki` | Existing human-trained hakihaki profile |
| `RVC B: runrun` | Existing human-trained runrun profile |
| `RVC C: yofukashi` | Existing human-trained yofukashi profile |

Labels are intentionally plain and visible. This experiment does not use blind
or randomized labels. A listener may stop a candidate during `dev24` when it
has missing output, repeated gross artifacts, or unintelligible content; the
reason is recorded and the candidate is not silently dropped.

## Admission and stop rules

The experiment remains `draft` until the source capture and exact profile
identity receipt are available. No quality result is valid before both source
thresholds are met: 10-15 minutes and 80-120 utterances. Target quantity is
reported separately per profile.

Use the settings and identity hashes discoverable in `experiment.json`. If an
identity cannot be verified at admission, mark that profile as pending rather
than inventing a value. Do not add a training run, eSpeak data, parameter sweep,
or hidden label mapping to this experiment. If a later replan admits new
training, it must report raw source-file totals and usable post-clean speech
duration under a frozen VAD/cleaning rule; raw duration alone is insufficient.

The direct usability gate requires completed renders, intelligible content,
absence of repeated gross artifacts, and intact native fallback/playout. A
profile that passes `dev24` is checked on disjoint `confirmation24`; disagreement
or universal failure produces an inconclusive result and a separate replan.

Raw audio, model files, and private runtime paths remain outside Git. The
repository record contains only the plan, aggregate quantities, judgments,
failure reasons, and non-sensitive identity hashes.
