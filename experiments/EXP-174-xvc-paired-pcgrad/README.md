# EXP-174: paired hard-repair and retention PCGrad

Status: admitted for one bounded gpu0 listen-now lane

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

