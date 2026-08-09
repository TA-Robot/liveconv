# liveconv-stt

`liveconv-stt` turns one bounded mono PCM16 WAV file into reproducible Japanese
STT evidence. It is an evidence generator, not an audio-quality verdict: a good
transcript does not prove naturalness, speaker identity, or artifact-free audio.
The pinned inference runtime requires CPython 3.12 or newer.

The runner is backend-neutral and accepts an injected backend in Python. The
only concrete CLI backend is an optional, exact-version adapter for
`faster-whisper==1.2.1`. No model weights are bundled or downloaded.

## Outputs

Each run writes two required JSON artifacts and one optional text artifact:

- `--bundle-out` records the input WAV SHA-256 and format, raw and normalized
  transcript, exact-entity results, engine/model revisions, and model digest.
- `--evidence-out` contains exactly the six fields accepted by
  `liveconv_evaluation.SttEvidence`; pass this file to
  `liveconv-eval --source-stt-evidence` or `--output-stt-evidence`.
- `--transcript-out` is the explicit transcript input for `liveconv-eval`.

The CLI writes transcript-bearing artifacts with mode `0600` and emits no
transcript or audio path on successful `transcribe`. Run it separately with
`--role source` and `--role output`; do not infer source evidence from output or
vice versa. `liveconv-jp-nfkc-kana-v1` applies NFKC, lowercases ASCII, converts
Katakana to Hiragana, and removes whitespace and punctuation. It does not infer
Kanji readings.

## Real-run prerequisites

All of these must exist before a real run:

1. An approved Japanese-capable CTranslate2 Whisper model in a local directory,
   including `model.bin`, `config.json`, and `tokenizer.json`. Requiring a local
   tokenizer prevents the engine's tokenizer fallback from reaching a model
   hub.
2. An immutable, reviewed model provenance record and license approval. The
   recorded model revision must be `NAME@sha256:DIGEST`, where `DIGEST` is the
   package's deterministic tree digest.
3. The complete inference closure installed from the packaged, hash-locked
   `real-run-requirements.txt`. The adapter verifies every active package in
   that lock before loading the model and records both the full version map and
   lock SHA-256 in each evidence decode config. The optional extra declares the
   direct runtime dependencies, but is not by itself an evidence environment.
4. An explicit JSON decode configuration and an authorized local PCM16 mono WAV
   no longer than the configured bound (300 seconds and 32 MiB by default).

The official faster-whisper API accepts a local converted model path, exposes
`local_files_only`, returns lazy transcript segments, and requires iterating
those segments to run inference. The adapter fixes those behaviors explicitly;
see the [official README](https://github.com/SYSTRAN/faster-whisper/blob/master/README.md)
and [official `WhisperModel` source](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py).

```bash
uv pip install --require-hashes \
  -r packages/stt/src/liveconv_stt/real-run-requirements.txt
uv pip install --no-deps ./packages/stt

MODEL_SHA=$(liveconv-stt model-digest /approved/models/whisper-ja-ct2)

cat >decode.json <<'JSON'
{"beam_size": 5, "temperature": 0.0, "condition_on_previous_text": false}
JSON

liveconv-stt transcribe source.wav \
  --role source \
  --backend faster-whisper \
  --engine-revision 'faster-whisper==1.2.1' \
  --model-artifact /approved/models/whisper-ja-ct2 \
  --model-sha256 "$MODEL_SHA" \
  --model-revision "approved-whisper-ja@sha256:$MODEL_SHA" \
  --decode-config decode.json \
  --exact-entity 09012345678 \
  --bundle-out source.stt.json \
  --evidence-out source.evidence.json \
  --transcript-out source.txt
```

`model-digest` hashes the digest-algorithm revision, sorted relative paths, file
sizes, and file bytes. Symlinks and non-regular entries are rejected.
Output paths must be distinct from the input WAV, decode configuration, and
model tree. All requested outputs are staged before publication and rolled back
as one run if publication fails.

## Current blocker

This repository does not contain an approved Japanese STT model artifact,
immutable model digest/provenance decision, or authorized rendered corpus. Until
those external inputs are supplied, only deterministic fake-backend tests can
run. No real transcription or Japanese accuracy claim is made by this package.

## Development

```bash
pytest
ruff check .
ruff format --check .
python -m build
```
