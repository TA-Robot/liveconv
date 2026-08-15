# EXP-346 — Beatrice 2 target-specific train (334 rows)

Status: **listen-now preparation slice; no CUDA run has been started**.

Pause snapshot (2026-08-15): the runner is CPU-tested, but the ignored full
trainer-asset checkout is incomplete and the checkpoint renderer is not yet
implemented. One official IR/noise/test triplet exists only for the one-step
execution smoke. See
[`../../docs/planning/2026-08-15-quality-search-handoff.md`](../../docs/planning/2026-08-15-quality-search-handoff.md)
before resuming. Do not treat this preparation as a completed training run or
new audio.

## Goal

Train the pinned Beatrice 2 MIT trainer on the operator-authorized Amitaro
`runrun` targets from exactly the 334 manifest rows whose `split` is `train`
(about 20.73 minutes of target audio).  This is a method-level pivot after the
short X-VC adaptation branches stopped producing a stable broad result.  The
first deliverable is a reproducible one-speaker training directory and a
checkpoint trajectory that can later be rendered for listening.

The immutable inputs are:

- trainer checkout revision
  `f34836de014b86956096878aecb8d3b17feaaa0b`;
- paired manifest declared self-SHA-256
  `2f35e75f169c7cb5664f9f9cc201ff7e79c4d5ba2e700f5c769c6ba1f22f351a`;
- target archive SHA-256
  `1fc131f18554625038aaa9876bab0d75660f266ff5e9e18d74cdbb3e6e0df000`.

The runner verifies the manifest self-hash, archive hash, every selected target
member's SHA-256, and strict mono PCM16/48 kHz WAV framing.  It materializes
only `dataset/amitaro/*.wav`; validation (36) and heldout (54) rows are read
only for split-count integrity and are never extracted or passed to the
trainer.

## Definition of done

1. `tools/beatrice-target-training/run.py` passes its CPU-only focused tests.
2. A committed runner invocation materializes exactly 334 verified WAVs under
   an ignored work directory and writes a config derived from the upstream
   defaults (`n_steps=10000`).
3. The runner accepts a separate complete trainer worktree and isolated Python,
   and validates IR/noise/test directories plus phone, pitch, and pretrained
   checkpoint paths before execution.
4. A future GPU run is launched only with `--confirm-gpu-lease gpu0` and an
   explicit `--commit-before-cuda <workspace-HEAD>` that matches `git rev-parse
   HEAD`.  `--smoke` is the only permitted one-step override; ordinary training
   remains the upstream 10,000-step method.
5. Any resulting checkpoint is retained as an unheard listen-now candidate;
   no product winner, route qualification, Japanese quality claim, or human
   listening decision is made by this experiment.

CPU checks:

```bash
python3 -m unittest discover -s tools/beatrice-target-training -p 'test_*.py'
python3 -m py_compile tools/beatrice-target-training/run.py
git diff --check -- tools/beatrice-target-training experiments/EXP-346-beatrice-amitaro-train334
```

After this directory and runner are committed, prepare the ignored work area
with the pinned trainer assets (the three auxiliary directories must be
complete and nonempty):

```bash
python3 tools/beatrice-target-training/run.py prepare \
  --trainer-root artifacts/beatrice-2/trainer-run-source \
  --python artifacts/beatrice-2/runtime-isolated-v2/bin/python \
  --manifest artifacts/xvc-human-paired/runrun-human-paired.manifest.json \
  --target-archive /tmp/liveconv-ms3-intake/amitaro-full-data/downloads/ITAcorpus_amitaro_runrun.zip \
  --work-dir artifacts/beatrice-2/exp346-train334
```

The exact commit-before-CUDA boundary is the output of `git rev-parse HEAD`
after the prepare runner and plan have been committed.  Only then may the
training command be used, with the captured value substituted literally:

```bash
python3 tools/beatrice-target-training/run.py train \
  --trainer-root artifacts/beatrice-2/trainer-run-source \
  --python artifacts/beatrice-2/runtime-isolated-v2/bin/python \
  --manifest artifacts/xvc-human-paired/runrun-human-paired.manifest.json \
  --target-archive /tmp/liveconv-ms3-intake/amitaro-full-data/downloads/ITAcorpus_amitaro_runrun.zip \
  --work-dir artifacts/beatrice-2/exp346-train334 \
  --confirm-gpu-lease gpu0 \
  --commit-before-cuda <COMMITTED_WORKSPACE_HEAD>
```

## Not in scope

This slice does not use validation or heldout targets, RVC, external TTS,
synthetic replacement data, a hyperparameter sweep, a second seed, an
unregistered renderer, or production route integration.  The upstream trainer
has no standalone checkpoint-to-WAV CLI in the pinned checkout, so this slice
reports rendering as pending rather than inventing a new inference boundary.
No CUDA, download, or audio publication is part of the CPU preparation change.
