# EXP-077: final waveform-decoder stage adaptation

Status: committed method; waiting for one GPU run

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
