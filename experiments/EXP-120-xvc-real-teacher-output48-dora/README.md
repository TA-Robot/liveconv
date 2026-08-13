# EXP-120: X-VC full-output teacher with DoRA

Status: completed; rejected on frozen fresh48

## Question

Can direction/magnitude-decoupled adaptation retain EXP-116's broad content
signal without its adapter-added local repetition?

## Independent variable

Keep EXP-116's frozen train48 pool, complete converted-output teacher targets,
835 standard and 209 teacher positions, 1,044 updates, control69 topology, LR,
rank, alpha, seed, zero frame condition, and Amitaro target fixed. Change only
PEFT parameterization from standard LoRA to DoRA. The 69 targets remain exact;
DoRA adds 52,224 magnitude parameters for 887,808 trainable parameters total.

This is one parameterization point. Do not add LoRA+, rsLoRA, rank, alpha,
optimizer, or DoRA-neighbor points.

## Stop

Commit method and focused tests before gpu0. Pass one real-model full-output
backward smoke, then train once. Render external7 and frozen fresh48. Stop before
stress60 on any added gross loop or broad common-non-loop regression. Machine
metrics cannot select naturalness, target voice, or a winner.

## Runtime admission

Commit `4606474` passed 54 focused tests and exact CPU admission. Its committed
real-model smoke exposed all 69 DoRA magnitude vectors and exactly 887,808
trainable parameters, produced a 38,400-sample teacher target, full composite
loss `161.0455`, finite pre-clip gradient norm `32.0441`, and 3.34 GiB peak GPU
allocation with exit status zero.

## Result

Commit `effa73d` completed 1,044 updates in 337.18 seconds at 4.77 GiB peak.
Standard loss moved `144.22 -> 130.92`; teacher loss moved `160.97 -> 72.12`.
External7 was the strongest small-set content result so far, with no loop and
control69 improvements from `0.360 -> 0.270` source-relative and `0.399 ->
0.359` known-text.

EXP-121 nevertheless rejected DoRA on frozen fresh48. It retained control69's
catastrophic repeated-family row and reproduced EXP-116's separate repeated-`ぷ`
failure. On the common 45 non-loop rows DoRA improved control mean `0.319 ->
0.296`, median `0.250 -> 0.200`, and known-text mean `0.610 -> 0.581`, with
12/23/10 W/T/L. This is useful content signal but unsafe generation stability.
Close PEFT parameterization neighbors and move to a loss that directly penalizes
temporal collapse.
