"""The frozen Japanese normalization used by liveconv evaluation."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from typing import Any

NORMALIZATION_REVISION = "liveconv-jp-nfkc-kana-v1"


def _katakana_to_hiragana(character: str) -> str:
    codepoint = ord(character)
    if 0x30A1 <= codepoint <= 0x30F6:
        return chr(codepoint - 0x60)
    return character


def normalize_japanese(text: str, *, remove_punctuation: bool = True) -> str:
    """Normalize orthography without inferring Kanji readings."""

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


def compare_exact_entities(entities: Iterable[str], transcript: str) -> dict[str, Any]:
    """Match normalized entities with evaluation-compatible ASCII boundaries."""

    expected = list(entities)
    normalized_expected = [normalize_japanese(entity) for entity in expected]
    if any(not entity for entity in normalized_expected):
        raise ValueError("exact entities must not normalize to an empty string")
    if len(set(normalized_expected)) != len(normalized_expected):
        raise ValueError("exact entities must be unique after normalization")

    normalized_transcript = normalize_japanese(transcript)

    def contains_exact_entity(entity: str) -> bool:
        start = normalized_transcript.find(entity)
        while start >= 0:
            end = start + len(entity)
            left = normalized_transcript[start - 1] if start else ""
            right = (
                normalized_transcript[end] if end < len(normalized_transcript) else ""
            )
            left_continues = left.isascii() and left.isalnum()
            right_continues = right.isascii() and right.isalnum()
            if not left_continues and not right_continues:
                return True
            start = normalized_transcript.find(entity, start + 1)
        return False

    matched = [
        entity
        for entity, normalized in zip(expected, normalized_expected, strict=True)
        if contains_exact_entity(normalized)
    ]
    missing = [entity for entity in expected if entity not in matched]
    return {
        "expected": expected,
        "normalized_expected": normalized_expected,
        "matched": matched,
        "missing": missing,
        "exact_match_rate": len(matched) / len(expected) if expected else 1.0,
    }
