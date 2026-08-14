# EXP-176: paired hard-repair and retention PCGrad

Status: technically rejected on frozen Hadou31; human diagnosis optional

## Goal

Test whether EXP-150's hard-repair and easy-retention objectives interfere at
the gradient level. EXP-171 improved ordinary aggregate content screens but
added a catastrophic Hadou number loop; changing the retention corpus again
would not explain that failure.

## One method change

Reuse EXP-150's frozen manifest and every one of its 85 hard repair and 85 easy
control69-retention source/target pairs. Keep control69 initialization, the
standard upstream generative loss, AdamW, LR `1e-4`, norm-5 clipping, LoRA69
scope, target references, and zero frame condition.

The manifest already alternates `hard, easy`. Evaluate each adjacent pair at
one shared parameter state. When the two task gradients have negative inner
product, apply symmetric two-task PCGrad projection, then sum them into one
optimizer step. Non-conflicting gradients are summed unchanged. This yields 85
pair optimizer steps from all 170 unchanged training examples. The changed
step geometry and count are recorded explicitly; they are a consequence of the
standard paired method, not a hidden sweep.

PCGrad method reference: Yu et al., *Gradient Surgery for Multi-Task Learning*,
NeurIPS 2020:
<https://proceedings.neurips.cc/paper/2020/file/3fe78a8acf5fda99de95303940a2420c-Paper.pdf>

## Definition of done and stop

Commit the runner and this plan before GPU use. A hard/easy smoke must show
finite task and merged gradients. Run exactly one full lane and publish
external7 comparison audio on port 8878. Record the number and cosine range of
conflicting pairs.

If external7 adds gross corruption, reject. Otherwise continue the unchanged
checkpoint through frozen fresh48, Hadou31, stress60, and then JSUT24, stopping
on the first candidate-added gross failure or broad common-non-gross content
regression. Auxiliary ASR screens content/corruption only; it cannot select
naturalness, target identity, a keeper, or promotion. Do not tune projection,
pairing, task weights, LR, scope, data ratio, or horizon from this result.

## Result

The finite two-row smoke found a real conflict on its first hard/easy pair:
gradient cosine `-0.0134`, dot product `-205.5`, and merged pre-clip norm
`180.2`. The canonical committed lane then processed all 170 examples in 85
pair optimizer steps. It found negative gradient conflict in 74/85 pairs, with
cosine min/mean/max `-0.498/-0.207/0.236`. Loss moved `227.88 -> 46.31`, peak
CUDA allocation was 5.19 GB, and the adapter was reproduced bit-exactly after
correcting a provisional experiment-ID collision.

External7 added no gross repetition but slightly regressed both auxiliary
means versus control69 (`0.360 -> 0.367` source-relative and `0.399 -> 0.431`
known-text). Frozen fresh48 added no gross row beyond the same two control
failures. On the 46 common non-gross rows, source-relative mean improved
`0.341 -> 0.299` with W/T/L `13/25/8`, while its median slightly regressed
`0.275 -> 0.293`; known-text mean improved `0.618 -> 0.606`.

Hadou31 rejects the method. Control69 had no gross row, while the candidate
again collapsed on `RECITATION324_138`, repeating `三、四` through a long
numeric run. Excluding that failure, the other 30 rows looked favorable
(`0.185 -> 0.171`, W/T/L `6/22/2`), demonstrating why aggregate content scores
cannot override the corruption gate. Do not run stress60 or JSUT24 and do not
tune projection, pairing, or task weights. The 430 canonical comparison WAVs
remain on port 8878 for later human diagnosis; this is not a perceptual verdict.
