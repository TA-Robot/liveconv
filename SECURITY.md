# Security and responsible voice use

## Reporting

Do not open a public issue containing credentials, private recordings, customer
data, or exploitable deployment details. Contact the repository owner privately.

## Project rules

- Use only voice references for which the project has explicit authorization.
- Record voice provenance, permitted purposes, retention, and deletion rules.
- Treat recordings, embeddings, indexes, and trained checkpoints as sensitive.
- Keep sensitive artifacts under ignored `artifacts/`, `embeddings/`, `indexes/`,
  `models/`, `weights/`, `data/private/`, or `data/raw/` directories. The repository
  check also rejects common raw-audio, embedding, index, and weight extensions.
- Keep credentials outside Git and rotate any credential that appears in a log,
  issue, commit, or remote URL.
- Use synthetic or clearly redistributable fixtures in CI.
- Authenticate and encrypt all non-local audio streams.
- Bound retention and avoid server-side audio storage unless an experiment
  explicitly requires it.
- Maintain an immediate bypass and stop path for transformed audio.

The project must not be used to impersonate a person without authorization or to
mislead listeners about the origin of generated speech.
