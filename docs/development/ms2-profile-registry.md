# MS-2 profile registry

`scripts/build-ms2-profile-registry.py` produces the technical, four-profile
Gateway registry for the fixed MS-2 roster. It consumes only the reviewed local
profile materials and the current bytes of each corresponding model pack. It
does not discover models, promote a model, or change the roster's execution or
decision state.

The material JSONs are external deployment/source inputs, not worker-wheel
package resources. Each records identity data for the corresponding wheel,
including a wheel digest, so embedding it in that wheel would create a
self-reference. The four `--*-material` options accept staged external copies;
when omitted they use the reviewed paths in this repository.

Each invocation needs the absolute executable endpoint for every isolated
worker. The endpoint is included only as `runtime.worker_endpoint`, and its
current SHA-256 is recorded in the profile promotion binding. Model artifacts,
target references, paths to either of them, credentials, and tokens remain
private worker-environment inputs and are not accepted in the generated
configuration.

```bash
uv run python scripts/build-ms2-profile-registry.py \
  --rvc-endpoint /opt/liveconv/rvc/bin/python \
  --beatrice-endpoint /opt/liveconv/beatrice/bin/python \
  --xvc-endpoint /opt/liveconv/xvc/bin/python \
  --openvoice-endpoint /opt/liveconv/openvoice/bin/python \
  --output /srv/liveconv/model-profiles-ms2.json
```

The default destination is
`/tmp/liveconv-ms2-profile-registry.json`, so an unqualified invocation does
not write a generated deployment artifact into the repository. A supplied
`--output` chooses the explicit destination. The script writes a same-directory
temporary file, loads it with
`ProfileRegistry.load(..., allow_technical_profiles=True,
model_pack_directory=workers/packs)`, and replaces the destination only after
that validation succeeds.

All four profiles retain `technical_validation` promotion status. They are
nonselectable under normal Gateway settings; the registry is intended for the
explicit technical opt-in required by the MS-2 operator run. OpenVoice remains
`end_buffered` and non-streaming.

## Material bindings

- RVC uses `workers/adapters/rvc_v2/ms2-profile-material.json`. Its reviewed
  legacy `worker_module` remains inside `runtime.configuration`, preserving the
  accepted `sha256:004eeb4db6d2f4a9df05b4c0e4eb05c330afd14ea6922af4ef08cc4459e4dbfb`
  configuration hash. The shared adapter registry explicitly supports this
  compatibility exception.
- Beatrice uses `workers/adapters/beatrice_2/profile-material.json`, X-VC uses
  `workers/adapters/x_vc/technical-profile.json`, and OpenVoice uses
  `workers/adapters/openvoice_v2/canonical-profile.json`. Their worker modules
  are separate `runtime.worker_module` values rather than configuration keys.
- The OpenVoice material still names
  `vc.openvoice-v2.technical.v1`; the MS-2 roster fixes the generated public
  ID at `vc.openvoice-v2.synthetic-ja.v1`. The builder preserves the retained
  technical configuration, evidence, buffered mode, and non-approval status
  while applying that roster identity.

The builder recalculates each model pack digest and endpoint digest every time.
It also rejects mismatched pack evidence, non-absolute or non-executable
endpoints, secret-like output values, and any artifact or target path in the
serialized configuration.
