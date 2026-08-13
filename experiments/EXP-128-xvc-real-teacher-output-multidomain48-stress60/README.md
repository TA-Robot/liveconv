# EXP-128: cross-corpus X-VC teacher on frozen stress60

Status: prepared; evaluation-only

EXP-124 introduced no gross loop beyond the two exact frozen fresh48 failures
already shared with base/control69, and it improved the separate ten-row
JVS/Hadou condition matrix. Render base, EXP-035 control69, and EXP-124 once on
the existing 60-row Common Voice condition matrix: twelve underlying inputs
each under clean, noise20, leading-silence300, tempo120, and pitch+3. Report
every group separately. Auxiliary ASR can expose content drift and gross loops;
it cannot select naturalness, target voice, or a winner.
