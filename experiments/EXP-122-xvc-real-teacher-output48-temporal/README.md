# EXP-122: X-VC full-output teacher with temporal-difference loss

Status: prepared; one bounded gpu0 lane

## Question

Can aligned local waveform-motion supervision retain EXP-116's broad content
signal without its adapter-added repetition?

## Independent variable

Keep EXP-116's train48, 835 standard and 209 full-output teacher positions,
1,044 updates, control69 standard LoRA, LR, rank, alpha, seed, zero frame
condition, and Amitaro target fixed. Change only the teacher-row objective by
adding weight-1000 L1 distance between adjacent-sample differences of the model
reconstruction and the exact frozen teacher waveform. The 835 standard rows
retain the original composite loss.

This is aligned pointwise motion matching, not the previously rejected
pretrained waveform discriminator. Run one weight only.

## Stop

Commit method and focused tests before gpu0. Pass one real-model backward smoke,
then train once. Render external7 and frozen fresh48. Stop before stress60 on
any added gross loop or broad common-non-loop regression. Machine metrics cannot
select naturalness, target voice, or a winner.
