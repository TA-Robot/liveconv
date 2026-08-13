# EXP-106: real-source frozen-teacher semantic rehearsal

Status: completed; strongest broad robustness signal, one pathological loop

## Question

Can X-VC retain content on varied real Japanese inputs by rehearsing the frozen
base model's semantic behavior, without teaching the adapter to reconstruct a
donor speaker's voice?

## One method change

Keep EXP-072's exact 835/209 schedule positions, twelve admitted Common Voice
donors, 87 Amitaro targets, control69 rank-8 LoRA, LR `1e-4`, seed, zero frame
condition, and 1,044 updates. The 835 standard rows remain generated-source to
Amitaro conversion with the normal composite loss. On the 209 rehearsal rows,
feed the real donor waveform and tokens with an Amitaro target-speaker waveform,
then supervise only the semantic prediction against the immutable base X-VC's
prediction for that exact input and target-speaker context.

This differs from EXP-072: the real donor waveform is never a waveform or
speaker target. It also differs from EXP-081: the target is a frozen X-VC
teacher prediction, not the source waveform's Whisper hidden state. Do not
sweep the 20% share or the teacher weight.

## Done and stop

- Commit the method, exact schedule, focused tests, and EXP-107--111 render
  policies before one GPU run.
- Publish 7 + 12 + 10 + 31 + 33 + 60 frozen rows on port 8878.
- Machine checks may reject empty output, gross repetition, copying, or broad
  source-relative ASR regression. They cannot rank naturalness or target voice.
- A new loop or robust changed-utterance/stress regression rejects the method.

## Result

Training completed 1,044 updates in 270.33 seconds at 4.77 GiB peak; loss moved
`144.22 -> 134.13`. External7 was 2/4/1 with mean `0.360 -> 0.367` and no loop.
Changed12 improved `0.184 -> 0.146` (4/5/3). Conditions10 improved `0.153 ->
0.060` (3/6/1). Stress60 improved every group mean and macro `0.320 -> 0.254`
(27/18/15), with no loop. Expanded33 removed the control's loop and reduced
the raw mean `1.084 -> 0.620`, but that mean was driven by three known failure
sources; excluding them regressed `0.514 -> 0.607`. Hadou31 added one gross
number-loop on `RECITATION324_138` despite improving its mean.

Retain this as an unheard, technically promising candidate. It is not a clean
technical pass or perceptual winner. Do not sweep the teacher share or weight;
test the same checkpoint on fresh disjoint speakers next.
