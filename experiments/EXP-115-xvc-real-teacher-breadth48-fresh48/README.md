# EXP-115: X-VC teacher breadth48 on frozen fresh48

Status: completed; technical reject

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

## Result

Commit `23f9d6b` produced 144 model outputs in 124.01 seconds at 4.77 GiB
peak. EXP-114 had four gross-repetition rows total and added two failures not
present in control69. Across the common 44 non-loop rows it was 10/22/12 and
regressed both source-relative mean and median. Stop; do not render stress60.
All audio remains unheard and unselected on port 8878.
