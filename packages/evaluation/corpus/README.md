# LV-001 Japanese smoke corpus

`lv-001-ja-smoke-v1.json` is a text-and-metadata corpus containing 40 unique
Japanese utterances. It is not an expansion of a smaller prompt set and contains
no audio, customer data, reference voice, or recording checksum.

The expected spoken forms received an engineering review against JP-001 through
JP-008. This does not claim native-speaker validation, pitch-accent approval, or
recording approval; those remain later evidence gates.

## Revision integrity

The checksum covers the complete JSON document except the top-level `revision`
and `integrity` members. Canonicalization uses UTF-8 JSON with keys sorted,
non-ASCII characters preserved, and compact `,` and `:` separators. The first 16
hexadecimal checksum characters are embedded in `revision`.

Published revisions are immutable. Change any corpus content by creating a new
semantic version, recomputing the checksum, and updating the content-addressed
revision identifier. The deterministic checksum test is the executable contract.

The project-authored corpus text and metadata are declared CC0-1.0 so the
metadata fixture can run in CI and be redistributed. Audio generated later needs
its own engine, model, voice, provenance, authorization, and license record.
