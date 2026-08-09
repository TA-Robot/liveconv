# Model pack registry

This directory is the LV-022 preparation registry for isolated model workers. A
model pack is research and integration metadata, not installed code, downloaded
weights, a legal approval, or evidence that a model works in liveconv.

## Current order

| Priority | Pack | Intended role | Current gate |
|---:|---|---|---|
| 1 | `rvc-v2` | First streaming adapter candidate | Pin and approve source, weights, dependencies, and target artifacts |
| 2 | `x-vc` | Quality-oriented candidate | Pass the frozen Japanese offline gate before streaming work |
| 3 | `beatrice-2` | Lightweight Japanese candidate | Obtain written permission for independent server inference |
| 4 | `openvoice-v2` | Japanese-capable offline control | Keep streaming out of scope until separately approved |

The order is research prioritization. Beatrice may move ahead of X-VC only after
the server-use permission and dependent-data review are cleared.

## Layout

- `model-pack.schema.json` defines the machine-readable pack contract.
- `packs/*.json` records one candidate and its unresolved gates.
- `runbook.md` describes approval, artifact, and acceptance handling.
- `tests/test_model_packs.py` validates every manifest and registry invariant.

No manifest contains an artifact path. Runtime paths are supplied only through
the named `LIVECONV_*` environment variables. Do not put their values in Git,
logs, reports, or issue text.

A component license status of `declared` records an upstream statement only. It
is not legal approval; runtime use remains blocked until the separate approval
record and immutable artifact identities exist.

## Validation

From the repository root:

```bash
python -m unittest discover -s workers/tests -v
uvx ruff check workers/tests
```
