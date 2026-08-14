# EXP-149: hard-negative curriculum on untouched JSUT24

Status: conditional; evaluation-only

If and only if EXP-146 survives fresh48 and Hadou31, render the unchanged
candidate on the frozen JSUT24 category-balanced set from EXP-144. Do not tune
the model, sampling, or threshold from JSUT output. Reject candidate-added
gross corruption or broad cross-category content regression; do not select a
perceptual winner automatically.
