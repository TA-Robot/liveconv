# EXP-106: real-source frozen-teacher semantic rehearsal

Status: ready method pilot; waiting for EXP-100--105 closure

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

