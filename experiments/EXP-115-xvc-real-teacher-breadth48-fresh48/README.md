# EXP-115: X-VC teacher breadth48 on frozen fresh48

Status: blocked on one EXP-114 checkpoint; no separate training

## Question

Does EXP-114 preserve content and avoid adapter-added repetition on the 48
speakers held entirely outside both its real-teacher pool and all earlier local
Common Voice data?

## Boundary and stop

Render base, EXP-035 control69, and the single EXP-114 checkpoint on the exact
EXP-112 manifest. Stop the method on an adapter-added gross loop or broad
regression across common non-loop rows. If it survives, admit the already-fixed
balanced stress matrix next. Do not move fresh48 into training, select rows,
tune teacher share/weight, or claim naturalness from auxiliary ASR.
