# liveconv evaluation package

This package compares existing PCM WAV renders without running a voice model. It
keeps five questions separate:

1. Did the waveform change in a way that exceeds nuisance transformations?
2. Was the Japanese spoken content preserved?
3. Does a calibrated speaker evaluator show the intended speaker change?
4. Is the output audio structurally and acoustically intact?
5. Did the streaming system preserve interruption and generation safety?

Waveform difference is evidence of signal transformation only. It is never
reported as proof of successful voice conversion or target-speaker similarity.
Speaker evidence belongs to an independently approved evaluator.
The two-file CLI cannot produce speaker or streaming evidence, so both lanes are
explicitly `unassessed`. Library callers may inject a calibrated `LaneVerdict`
for speaker change and a separately measured streaming verdict.

## CLI

From this directory:

```bash
python -m liveconv_evaluation compare source.wav output.wav \
  --reference-transcript 'ご注文番号はABC123です' \
  --output-transcript 'ご注文番号はABC123です' \
  --exact-entity 'ABC123'
```

The command emits a render report on stdout. With no threshold policy, every
lane remains `unassessed`; measurements are still emitted. Pass a JSON policy
only when its provenance and status are known:

```json
{
  "label": "EXP-NNN proposed smoke thresholds",
  "status": "proposed",
  "values": {
    "min_aligned_nrmse_for_waveform_difference": 0.03,
    "max_output_clipped_fraction": 0.0001,
    "max_reference_cer": 0.1
  }
}
```

A `proposed` policy may produce per-lane measurements and failures, but it can
never produce an overall `pass`. Overall pass requires an `approved` policy and
all five lanes. Content pass additionally requires non-empty reference/source
and reference/output transcripts plus source and output STT provenance using the
current normalization revision. A caller-supplied speaker or streaming `pass`
must contain non-empty evidence. The integrity lane requires clipping, silence,
duration, non-finite-sample, adjacent-sample discontinuity, interior-gap, and
adjacent-repetition guardrails together; a partial policy remains `unassessed`
unless one of its supplied guardrails fails.

```bash
python -m liveconv_evaluation compare source.wav output.wav \
  --thresholds proposed-thresholds.json --report render.json
```

Detector parameters such as the silence floor describe how a metric is measured;
they are included in every report. They are not product acceptance thresholds.
Exact entities are normalized and compared independently from aggregate CER so
a one-character identifier error cannot disappear inside a good average score.

When transcripts come from STT, attach separate source/output evidence JSON with
`--source-stt-evidence` and `--output-stt-evidence`. Each record contains the
provider, immutable model revision, decode configuration, language,
timezone-aware transcription timestamp, and normalization revision. Missing
evidence is represented as `null`, not silently inferred.

The gap detector reports interior runs of silent analysis frames, excluding
leading and trailing silence. The repetition detector reports exact, immediately
adjacent replays of one or more non-silent analysis frames. These deterministic
checks expose possible gap and queue-replay defects; they do not judge speaker
identity, natural pauses, or perceptual quality. Their acceptance thresholds
must be preregistered by the owning experiment rather than inferred here.

## Japanese normalization

The transcript normalizer applies Unicode NFKC, lowercases ASCII, converts
Katakana code points to Hiragana, and removes configured whitespace and
punctuation. It deliberately does not guess Kanji readings. For kana error rate,
the fixture must supply a reviewed canonical kana transcript or an independently
versioned reading normalizer must run before this package. The executable and
fixture manifest identify this behavior as `liveconv-jp-nfkc-kana-v1`.

## Artifacts

The package contains no recordings. Tests synthesize arrays and temporary WAV
files. Rendered audio remains in the experiment's authorized artifact store;
reports should reference it by a non-sensitive locator and checksum.

Aggregate reports currently provide deterministic descriptive summaries only.
They intentionally retain `decision: unassessed`; bootstrap confidence intervals
and a preregistered aggregate decision procedure must be supplied by the owning
experiment before promotion.

`fixtures/router-speech-v1.json` tracks EXP-002's ten reviewed text cases and
four synthesis conditions. Its Cartesian expansion defines 40 fixtures and 15
repetitions define 600 eligible turns per variant. The manifest remains `draft`
until the synthesis engine, model, and every voice revision are immutable. The
schema rejects a `frozen` status while any of those revision fields is absent.
Rendered artifact locators and checksums remain in render reports and the
authorized experiment artifact index; this fixture schema currently has no
per-artifact checksum or provenance field to freeze.
