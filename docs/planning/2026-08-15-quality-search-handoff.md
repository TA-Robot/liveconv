# Quality-search handoff — 2026-08-15

Status: paused intentionally before EXP-346 CUDA execution.

## Outcome

The X-VC quality campaign produced a reproducible broad evaluation loop and a
large unheard listening library, but the latest method branches did not improve
robustness enough to retain. No machine metric is a naturalness, target-voice,
keeper, or product-selection decision. The operator is still unavailable for
hearing, so every candidate on port 8878 remains unselected.

The next admitted method is EXP-346: target-specific Beatrice 2 training on the
authorized Amitaro `runrun` corpus. Its plan and CPU runner are implemented and
tested, but no EXP-346 smoke, 10,000-step training, checkpoint, render, or new
audio has been produced.

## Important corrections and fixed boundaries

- The retained 8.17-second `隣の客はよく柿食う客だ` recording is a local
  tongue-twister diagnostic, not ChatGPT browser audio. Do not optimize it as an
  actual ChatGPT-input proxy.
- Human hearing is unavailable. Sequential committed GPU jobs and coarse
  corruption/content screens are allowed; automatic naturalness or voice winner
  claims are not.
- VC and external TTS remain separate comparisons. Do not mix TTS output into a
  VC training corpus.
- EXP-024 DTW retry and the same human87 horizon/LR/LoRA-scope walk stay closed.
- All generated/private WAVs, archives, checkpoints, and model weights stay in
  ignored artifact locations.

## Current X-VC result

The retained technical reference is EXP-238 source-aligned pseudoparallel
training. It is not a keeper. It survived the broad coarse gate better than the
later short branches and remains useful as a comparison control.

The latest tested method, EXP-340, added only rank-8 LoRA at
`prenet.linear_pre` to the existing EXP-238 adapter contract. Training completed
170 updates in 178.34 seconds and all 314 candidate WAVs changed. Across the
external and five broad surfaces:

- gross repetition moved `2 -> 3`;
- decoder instability moved `60 -> 66` with nine new and three recovered rows;
- 242 jointly stable/non-gross rows were `14W/220T/8L`;
- mean source-relative content distance moved `0.241776 -> 0.238999`.

The small aggregate content gain does not offset the new corruption and
instability. The exact prenet topology and nearby rank/alpha/location walk are
closed. The preceding EXP-334 feature-statistics branch also stopped at
external7 after instability moved `1 -> 3` and common-stable content regressed.

The complete EXP-340 closure is commit `e7aca97`; its method commit is
`c69d9a8`. The listening UI received 1,570 EXP-340 WAVs. They remain unheard and
unselected.

## Evaluation assets already available

The reusable frozen surfaces are external7, fresh48, Hadou31, stress60,
balanced JSUT24, expanded144, and the separate heldout SRC4VC30 surface. These
cover different speakers, texts, lengths, F0, tempo, noise, and silence. Do not
redesign evaluation before the next training job or return to one-phrase
optimization.

Port 8878 remains the only listening publication target. Existing audio may be
heard later, but a listen-now choice is not a product promotion.

## EXP-346 prepared state

The runner and plan are:

- `experiments/EXP-346-beatrice-amitaro-train334/README.md`
- `tools/beatrice-target-training/run.py`
- `tools/beatrice-target-training/test_run.py`

Frozen inputs:

- trainer revision: `f34836de014b86956096878aecb8d3b17feaaa0b`;
- manifest declared SHA-256:
  `2f35e75f169c7cb5664f9f9cc201ff7e79c4d5ba2e700f5c769c6ba1f22f351a`;
- Amitaro archive SHA-256:
  `1fc131f18554625038aaa9876bab0d75660f266ff5e9e18d74cdbb3e6e0df000`;
- selected target set: exactly 334 `split=train` WAVs, 20.73 minutes;
- excluded from training: 36 validation and 54 heldout target WAVs.

The runner validates the split, member and WAV hashes, mono PCM16/48 kHz
format, trainer revision, runtime, auxiliary assets, and commit-before-CUDA
boundary. It preserves the upstream 10,000-step method; `--smoke` is the only
one-step override. Focused CPU validation passed six tests plus `py_compile` and
`git diff --check`.

No renderer is implemented yet. A trained one-speaker checkpoint must be loaded
through the pinned MIT trainer graph and rendered on named Japanese inputs before
EXP-346 can satisfy the listening-loop outcome.

## Paused runtime state

- No EXP-346 CUDA job was started; GPU 0 was idle at pause.
- The `liveconv-exp346-assets` download tmux session was stopped.
- The `liveconv-grok-auditor` 30-minute audit tmux session was stopped.
- `artifacts/beatrice-2/trainer-smoke-assets/` contains one verified official
  IR, one noise file, and one Japanese test WAV. This is sufficient only for the
  one-step execution smoke.
- The separate ignored `trainer-run-source` checkout is incomplete: 703 IR
  files materialized, no real noise/test files, and the trainer module is not
  checked out. Do not use it for the 10,000-step job in this state.
- The complete original pinned trainer module and pretrained checkpoints remain
  under `artifacts/beatrice-2/trainer-source/`; its missing auxiliary directories
  can be supplied with the runner's explicit asset flags.

## Exact restart order

1. Recreate the read-only Grok 30-minute audit before the next large resource
   commitment.
2. Complete a separate ignored set of the official Beatrice IR/noise/test
   assets. Verify real audio content, not Git LFS pointer files. Upstream HEAD
   contains 1,000 IR, 1,000 noise, and eight Japanese test files.
3. Re-run the six focused CPU tests and `git diff --check`.
4. Use a fresh ignored smoke work directory and the committed handoff HEAD.
   Run exactly one `--smoke` job with `--confirm-gpu-lease gpu0` and
   `--commit-before-cuda <HANDOFF_HEAD>`.
5. If the smoke produces a finite checkpoint and paraphernalia, use a different
   fresh work directory for the unchanged upstream 10,000-step job. Do not tune
   steps, LR, batch size, loss weights, or seed after seeing the smoke.
6. While the full job runs, implement the smallest checkpoint renderer for the
   seven frozen external Japanese inputs. Compare trained Beatrice with its
   pinned pretrained Beatrice control; X-VC may be shown as a separate VC
   control, not as a mixed training target.
7. Publish only on 8878, run coarse content/corruption screening, leave the
   collection unselected, and replan. If technically viable, Beatrice output may
   later be evaluated as an independent same-content teacher hypothesis for
   X-VC; it is not admitted automatically.

## Last independent audit

The 2026-08-14 23:52 UTC Grok audit returned `CONTINUE`. Its high-level advice
was adopted: stop the prenet neighbor walk, reuse the fixed diverse evaluation
surfaces, and move immediately to a genuinely different sequential training
method. Its specific suggestion to return to EXP-305/306 was rejected because
that lane had already completed external7 and increased decoder instability;
the snapshot had repeated an older board paragraph.
