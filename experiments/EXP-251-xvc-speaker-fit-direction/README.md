# EXP-251: cross-surface X-VC speaker-fit direction screen

Status: admitted auxiliary screen; no perceptual selection

## Question

Did replacing JSUT85 with SRC4VC85 move the EXP-244 outputs toward or away from
the same Amitaro runrun target, compared with EXP-238, across every established
evaluation surface?

## Why this screen exists

EXP-244 changed every paired output but did not improve content robustness
broadly. CER/ASR cannot tell whether those changed WAVs improved target voice
fit. Load the already verified local ECAPA model once, embed the paired
EXP-238/EXP-244 outputs across external7, fresh48, Hadou31, stress60, JSUT24,
and expanded144, and report only aggregate target/source cosine direction.

The target is the existing private, operator-authorized Amitaro runrun
`EMOTION100_003` material. The plan binds the admitted private corpus lineage,
the raw archive/member hashes, and the normalized listener target hash. No raw
audio or embedding is added to Git.

The formal speaker-evidence package locks a separate Torch 2.6 closure, while
the existing private CUDA batch runtime is Torch/TorchAudio 2.8.0, SpeechBrain
1.0.3, NumPy 2.1.2, SciPy 1.16.1, and HyperPyYAML 1.2.2. This screen pins and
records that exact installed tuple rather than weakening the formal package
lock. Consequently the result is auxiliary direction evidence only and cannot
satisfy a promote-tier speaker-evidence gate.

## Decision boundary

- If target similarity and target-over-source advantage improve consistently,
  retain SRC4VC substitution only as a target-fit candidate and choose the next
  one-variable training method from the identity path.
- If both are flat or regress, close the exact source substitution completely
  and return to EXP-238 for the next method change.
- Mixed results may select a failure surface for one diagnostic; they do not
  authorize a corpus-ratio or hyperparameter sweep.

This screen cannot identify a person, measure naturalness, prosody, or emotion,
select a perceptual winner, or promote a profile. Human hearing remains the
quality decision when an operator is available.
