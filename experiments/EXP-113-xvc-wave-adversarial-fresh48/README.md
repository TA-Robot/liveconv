# EXP-113: frozen waveform-adversarial X-VC on fresh48

Status: ready fixed-checkpoint screen; no training

## Question

Does EXP-064's restored pretrained waveform-adversarial objective generalize
more safely than the rejected EXP-106 teacher method on 48 genuinely fresh
Common Voice speakers and sentences?

## Boundary

Render the unchanged EXP-064 adapter against the same base and EXP-035
control69 arms on EXP-112's frozen, evaluation-only manifest. Run once on
gpu0 and publish on port 8878. Auxiliary ASR can reject content collapse or
adapter-added repetition only; it cannot rank naturalness, target voice, or a
winner. Do not tune the adversarial weight or train from fresh48.
