# EXP-122: X-VC full-output teacher with temporal-difference loss

Status: completed; rejected on frozen fresh48

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

## Runtime admission

Commit `bbca644` passed 57 focused tests and exact CPU admission. Its committed
real-model smoke produced a 38,400-sample teacher target, total loss `169.1617`
versus the `161.0455` standard composite baseline, finite pre-clip gradient norm
`24.8603`, and 3.30 GiB peak GPU allocation with exit status zero. The temporal
term contributes about 8.12 loss units at initialization; no weight neighbor is
admitted.

## Result

Commit `d3b774a` completed 1,044 updates in 335.44 seconds at 4.77 GiB peak.
Standard loss moved `144.22 -> 131.22`; temporal-plus-composite teacher loss
moved `169.12 -> 82.12`. External7 had no loop and improved control69
source-relative `0.360 -> 0.279` and known-text `0.399 -> 0.383`.

EXP-123 rejected the method on frozen fresh48. It retained control69's
catastrophic repeated-family row and reproduced the separate 12-character
repeated-`ぷ` failure. On 45 common non-loop rows it essentially tied control
at 11/23/11, mean `0.316` versus `0.319`, median `0.267` versus `0.250`, while
known-text mean improved `0.610 -> 0.585`. Stop temporal weights and move to
training-source domain composition rather than another nearby loss.
