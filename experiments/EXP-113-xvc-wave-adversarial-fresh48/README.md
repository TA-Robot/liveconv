# EXP-113: frozen waveform-adversarial X-VC on fresh48

Status: completed; rejected on fresh48 corruption

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

## Result and decision

Commit `bf45dd3` rendered 144 model outputs in 115.65 seconds at 4.77 GiB
peak. The candidate inherited control69's catastrophic repeated-`家族` row and
added a separate repeated-vowel failure. Its raw mean was `1.306`, versus
control69 `1.001` and base `0.414`.

On the 45 rows where no arm looped, the candidate was effectively a control
tie: W/T/L `6/33/6`, mean `0.321` versus `0.326`, and median `0.200` versus
`0.250`. That tiny non-loop difference does not compensate for an added gross
failure. Reject the method as a generic keeper and do not tune its adversarial
weight. Audio remains unheard and unselected on port 8878.
