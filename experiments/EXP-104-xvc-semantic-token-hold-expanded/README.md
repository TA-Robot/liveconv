# EXP-104: semantic-token hold on 33 unused speakers

Status: completed; catastrophic expanded-speaker corruption

Render EXP-100 on the frozen 33-speaker Common Voice set, including the five
in-sample low-token-diversity rows identified by EXP-093. Any candidate gross
loop rejects a clean technical pass; this set alone cannot prove robustness.

The candidate produced seven wins, eight ties, and eighteen losses. Mean
source-relative distance regressed `1.084 -> 3.612`, and seven of 33 candidate
rows gross-looped versus one control row. This decisively rejects the method.
