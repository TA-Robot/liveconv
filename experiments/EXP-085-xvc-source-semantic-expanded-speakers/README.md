# EXP-085: source-semantic on 33 unused Common Voice speakers

Status: completed; one gross loop; operator hearing deferred

Render `--candidate-kind source-semantic-expanded` on the already-frozen
EXP-055 expanded evaluation: 33 locally unused utterances from 33 speakers.
This broader screen is mandatory because the earlier seven-row set missed a
gross repetition in EXP-064. It is evaluation-only and cannot rank naturalness
or target-voice similarity.

Across all 33 rows the candidate produced nine wins, 16 ties, and eight losses,
and mean source-relative distance moved from `1.084` to `0.942`. It nevertheless
gross-looped `フ` on `cv45113065u`, whose source ASR was empty. Control69 and
base gross-looped a different low-quality row. Excluding those two source IDs,
the candidate mean was `0.511` versus control69 `0.724` across 31 rows. The
loop prevents a clean technical pass; these exclusions are diagnostic only.
