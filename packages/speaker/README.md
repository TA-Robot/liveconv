# liveconv-speaker

`liveconv-speaker` emits independent source/target/output speaker-embedding
evidence. It does not store embeddings or infer a person's identity. Its concrete
backend is the revision-pinned SpeechBrain ECAPA-TDNN VoxCeleb model, loaded from
a verified local tree with Hugging Face offline mode enabled. The model revision
must end in that tree digest, and the full installed SpeechBrain closure is
checked against the packaged hash-locked requirements before model import.

The CLI records all three pairwise cosine similarities. A speaker-change lane
passes only when the caller supplies a minimum output-to-target similarity, a
minimum gain over the original source-to-target similarity, and a minimum
target-over-source preference for the output. These values must be labeled
`proposed` until they are calibrated on authorized pilot voices; proposed
evidence cannot make the overall evaluation pass.

```bash
liveconv-speaker compare source.wav target.wav output.wav \
  --model-artifact /approved/spkrec-ecapa-voxceleb \
  --model-sha256 "$MODEL_SHA" \
  --model-revision speechbrain-ecapa@sha256:"$MODEL_SHA" \
  --device cuda \
  --policy-label technical-pilot-v1 \
  --policy-status proposed \
  --min-target-similarity 0.20 \
  --min-target-gain 0.05 \
  --min-target-advantage 0.05 \
  --synthetic-corpus-manifest /authorized/synthetic-corpus.manifest.json \
  --output speaker-evidence.json
```

Both authorization inputs must resolve to a record in the package-tracked
`authorizations/reviewed-targets.json` registry. The registry binds the exact
target WAV digest, owner, purpose, retention, deletion terms, and a canonical
record digest. A caller-created JSON record is never sufficient by itself. The
initial registry member is the project-authored synthetic Japanese target with
digest `a92aaa78a600be0afa2425e55a8adb57dc0630789ce9a50284bf467345631ff7`.

Use `--target-authorization` for a reviewed GOV-001 record copied from that
registry and carrying valid canonical integrity metadata. Use
`--synthetic-corpus-manifest` for the fully populated, integrity-bound manifest
emitted by `scripts/generate-synthetic-ja-corpus.py`; its target must also be a
reviewed registry member. Exactly one authorization input is required. Adding a
human or replacement synthetic target therefore requires a code-reviewed
registry change before evidence can be produced or consumed.

Model weights, generated audio, caches, and evidence containing local artifact
metadata stay outside Git. Commit only immutable revisions, digests, aggregate
results, and approved reproduction instructions.
