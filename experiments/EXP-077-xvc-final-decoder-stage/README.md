# EXP-077: final waveform-decoder stage adaptation

Status: completed; technically rejected; operator hearing deferred

Train only the 297,890 full parameters in `acoustic_decoder.model.4`, `.5`, and
`.6`: the final upsampling block, Snake activation, and waveform output conv.
EXP-035 data, all-standard roles, generative loss, LR `1e-4`, seed, zero
condition, and 1,044 updates stay fixed. An inert zero-delta `proj_out` LoRA is
used only so PEFT can serialize the full saved modules; it is frozen throughout.
This tests the actual high-resolution waveform generator, not an adjacent
converter scope count. Publish 7 + 12 + 10 + 31 and reject any gross loop. Do
not sweep decoder depth or LR.

Command: `run_role_mix.py --training-policy all-standard --lora-scope decoder-final`
with the same paths as EXP-072 and work/listener slug `exp077-decoder-final-v1`.

## Result

All 1,044 updates completed in 234.13 seconds at 5.13 GB peak allocation. The
training loss rose from 144.22 to 165.58. On the seven external rows the final
decoder lost all seven source-relative comparisons against control69 and moved
the mean from `0.360` to `0.446`, with the maximum worsening from `0.571` to
`1.000`. No gross repetition was detected, but the frozen downstream screens
also regressed. This method is rejected without a decoder-depth or LR sweep.
The published audio remains an unheard listen-now candidate, not a winner.
