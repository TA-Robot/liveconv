# EXP-006: Young-feminine Japanese voice variant bake-off

Status: draft. This is the MS-3 discovery plan created after the actual
Extension became usable but the prepared MS-2 voices sounded unacceptable to
the operator. The preferred direction is a youthful feminine Japanese voice.

Current implementation checkpoint: eight Extension-visible variants across
RVC, OpenVoice, and X-VC are bound in one generated deployment. All eight have
passed a bounded Gateway technical route smoke; this is not an audio-quality
pass. One additional candidate from a fourth family is still required before
the nine-variant screen can start.

## Comparison unit

A variant is not just a model name. It is an immutable combination of model
family, checkpoint or preset, training-data lineage, authorized reference/style,
inference configuration, and route identity. Any material change creates a new
`variant_id`, `profile_id`, and configuration identity. A new checkpoint never
silently repairs an older quality-failed profile.

The candidate intake is
[`config/ms3-voice-variant-candidates.json`](../../config/ms3-voice-variant-candidates.json).
It contains honest `intake`, `license-review`, `deferred`, `excluded`, and
existing-control states; it is not itself a deployable profile registry.

## First wave

The counted first wave stays inside accepted protocol v1: audio-to-audio voice
conversion only. It prepares distinct authorized youthful-feminine styles such
as `yofukashi`, `runrun`, and `punsuka` across bounded RVC, MeanVC2, X-VC, and
OpenVoice variants where exact provenance and terms permit. Each style gets its
own authorization and content identity; one approval never implicitly
authorizes a different style, model family, or checkpoint.

Qwen3-TTS 0.6B `Ono_Anna`, Qwen Base clones, and Fun-CosyVoice3 remain valuable
second-wave research candidates. They do not count toward the nine-variant
gate because accepted protocol v1 transports captured PCM, not committed spoken
text. No TTS runtime enters the chooser until an accepted ADR defines the text
commit, transport, interruption, and played-text accounting contract.

Longer Japanese adaptation/training is second wave only. X-VC Japanese training,
JVS/JSUT-based work, archived GPL candidates, missing-code-license candidates,
and conflicting-license candidates cannot consume the first-wave critical path.

## Route qualification

Terminal and direct-worker renders are useful diagnostics but never count as
listening evidence. A user-visible variant must be loaded from one generated,
content-addressed deployment bundle and traverse the normal authenticated
Gateway and Extension capture/playout path. The terminal launcher, Gateway,
Extension, and receipt must all bind the same bundle, profile, configuration,
pack, authorization, and variant identities.

Any mismatch produces `route_parity_failed`, hides the variant from the chooser,
and excludes it from screening. This directly addresses the previous case where
terminal-side setup and the actual Extension behaved differently.

The public manifest carries only an authorization-record digest. Bundle
activation separately resolves it against an operator-controlled private
registry and requires an approved, nonexpired record bound to the same variant,
family, profile, source material, terms, and external lineage manifest. A hash
that merely has the right syntax cannot make a voice runnable.

## Bounded flow

1. Review licenses and authorization before downloading or preparing material.
2. Build isolated, statically approved variants and one deployment bundle.
3. Route-qualify each variant through Gateway to the installed Extension.
4. Exclude one cold warmup and screen every eligible variant on the same 10
   Japanese utterances.
5. Score intelligibility, naturalness, youthful-feminine fit, artifacts,
   conversational usefulness, and keep/reject separately from route failures.
6. Freeze at most four variants, at most two per family, for the MS-4
   40-utterance comparison plus native control.

Screening does not select a winner. When fewer than two variants are worth
continuing, approve one bounded second wave instead of starting an unlimited
checkpoint or training sweep.

## Evidence boundary

No raw captured/reference/output audio, target identifiers, credentials, host
paths, weights, or private free-form notes enter Git or the public deployment
manifest. TTS and VC may eventually share the chooser and listening form, but
their input contracts and claims remain separate, and only VC is in the counted
MS-3 first wave.
