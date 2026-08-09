"""Deterministic Japanese transcript normalization and edit metrics."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

NORMALIZATION_REVISION = "liveconv-jp-nfkc-kana-v1"


@dataclass(frozen=True)
class TranscriptMetrics:
    reference: str
    hypothesis: str
    normalized_reference: str
    normalized_hypothesis: str
    substitutions: int
    insertions: int
    deletions: int
    reference_characters: int
    character_error_rate: float | None

    def to_dict(self) -> dict[str, str | int | float | None]:
        return asdict(self)


def _katakana_to_hiragana(character: str) -> str:
    codepoint = ord(character)
    if 0x30A1 <= codepoint <= 0x30F6:
        return chr(codepoint - 0x60)
    return character


def normalize_japanese(text: str, *, remove_punctuation: bool = True) -> str:
    """Normalize orthography without attempting to infer Kanji readings."""

    normalized = unicodedata.normalize("NFKC", text).lower()
    output: list[str] = []
    for character in normalized:
        category = unicodedata.category(character)
        if character.isspace() or category.startswith("Z"):
            continue
        if remove_punctuation and category.startswith("P"):
            continue
        output.append(_katakana_to_hiragana(character))
    return "".join(output)


def _edit_counts(reference: str, hypothesis: str) -> tuple[int, int, int]:
    # Each cell stores total cost followed by substitution, insertion, deletion.
    previous = [(index, 0, index, 0) for index in range(len(hypothesis) + 1)]
    for ref_index, ref_character in enumerate(reference, start=1):
        current = [(ref_index, 0, 0, ref_index)]
        for hyp_index, hyp_character in enumerate(hypothesis, start=1):
            if ref_character == hyp_character:
                current.append(previous[hyp_index - 1])
                continue

            diagonal = previous[hyp_index - 1]
            deletion = previous[hyp_index]
            insertion = current[hyp_index - 1]
            candidates = [
                (diagonal[0] + 1, 0, diagonal[1] + 1, diagonal[2], diagonal[3]),
                (deletion[0] + 1, 1, deletion[1], deletion[2], deletion[3] + 1),
                (insertion[0] + 1, 2, insertion[1], insertion[2] + 1, insertion[3]),
            ]
            cost, _, substitutions, insertions, deletions = min(
                candidates, key=lambda item: (item[0], item[1])
            )
            current.append((cost, substitutions, insertions, deletions))
        previous = current
    _, substitutions, insertions, deletions = previous[-1]
    return substitutions, insertions, deletions


def compare_transcripts(reference: str, hypothesis: str) -> TranscriptMetrics:
    normalized_reference = normalize_japanese(reference)
    normalized_hypothesis = normalize_japanese(hypothesis)
    substitutions, insertions, deletions = _edit_counts(
        normalized_reference, normalized_hypothesis
    )
    reference_characters = len(normalized_reference)
    errors = substitutions + insertions + deletions
    if reference_characters:
        cer: float | None = errors / reference_characters
    else:
        cer = 0.0 if not normalized_hypothesis else None
    return TranscriptMetrics(
        reference=reference,
        hypothesis=hypothesis,
        normalized_reference=normalized_reference,
        normalized_hypothesis=normalized_hypothesis,
        substitutions=substitutions,
        insertions=insertions,
        deletions=deletions,
        reference_characters=reference_characters,
        character_error_rate=cer,
    )


def compare_exact_entities(entities: Iterable[str], hypothesis: str) -> dict[str, Any]:
    """Check normalized literal entities independently from aggregate CER."""

    expected = list(entities)
    normalized_expected = [normalize_japanese(entity) for entity in expected]
    if any(not entity for entity in normalized_expected):
        raise ValueError("exact entities must not normalize to an empty string")
    if len(set(normalized_expected)) != len(normalized_expected):
        raise ValueError("exact entities must be unique after normalization")

    normalized_hypothesis = normalize_japanese(hypothesis)

    def contains_exact_entity(entity: str) -> bool:
        start = normalized_hypothesis.find(entity)
        while start >= 0:
            end = start + len(entity)
            left = normalized_hypothesis[start - 1] if start else ""
            right = (
                normalized_hypothesis[end] if end < len(normalized_hypothesis) else ""
            )
            left_continues = left.isascii() and left.isalnum()
            right_continues = right.isascii() and right.isalnum()
            if not left_continues and not right_continues:
                return True
            start = normalized_hypothesis.find(entity, start + 1)
        return False

    matched = [
        entity
        for entity, normalized in zip(expected, normalized_expected, strict=True)
        if contains_exact_entity(normalized)
    ]
    missing = [entity for entity in expected if entity not in matched]
    match_rate = len(matched) / len(expected) if expected else 1.0
    return {
        "expected": expected,
        "normalized_expected": normalized_expected,
        "matched": matched,
        "missing": missing,
        "exact_match_rate": match_rate,
    }
