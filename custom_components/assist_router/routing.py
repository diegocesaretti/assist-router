"""Pure routing helpers for Assist Router."""

from __future__ import annotations

import re
import unicodedata

_WORD_RE = re.compile(r"[a-z0-9_]+")


def normalize_text(value: str) -> str:
    """Normalize text for accent-insensitive, case-insensitive matching."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def words_from_text(value: str) -> set[str]:
    """Extract normalized complete words from text."""
    return set(_WORD_RE.findall(normalize_text(value)))


def parse_keywords(value: str) -> list[str]:
    """Parse a user-editable keyword string into unique normalized words.

    Spaces, new lines, commas and semicolons are treated as separators. Only
    complete words are stored, so this intentionally does not support phrases.
    """
    normalized = normalize_text(value)
    words = _WORD_RE.findall(normalized)
    return list(dict.fromkeys(words))



def normalize_phrase(value: str) -> str:
    """Normalize a phrase while preserving word order."""
    return " ".join(_WORD_RE.findall(normalize_text(value)))


def parse_phrases(value: str) -> list[str]:
    """Parse one configurable closing phrase per line.

    Commas and semicolons are also accepted as separators. Phrases keep their
    internal spaces so entries such as ``hasta luego`` can be matched exactly.
    """
    phrases: list[str] = []
    for raw_item in re.split(r"[\n,;]+", value):
        phrase = normalize_phrase(raw_item)
        if phrase and phrase not in phrases:
            phrases.append(phrase)
    return phrases


def canonicalize_phrases(value: str) -> str:
    """Return one normalized phrase per line."""
    return "\n".join(parse_phrases(value))


def matches_end_phrase(text: str, phrase_text: str) -> bool:
    """Return True only when the complete utterance is a closing phrase."""
    spoken = normalize_phrase(text)
    return bool(spoken and spoken in set(parse_phrases(phrase_text)))

def canonicalize_keywords(value: str) -> str:
    """Return one normalized keyword per line."""
    return "\n".join(parse_keywords(value))


def matches_domotics(text: str, keyword_text: str) -> bool:
    """Return True when STT text contains any configured complete keyword."""
    keywords = set(parse_keywords(keyword_text))
    if not keywords:
        return False
    return bool(words_from_text(text) & keywords)


def migrate_default_keywords(
    value: str | None, legacy_default: str, current_default: str
) -> str:
    """Upgrade an untouched legacy default while preserving custom lists."""
    if value is None or not parse_keywords(value):
        return canonicalize_keywords(current_default)
    if canonicalize_keywords(value) == canonicalize_keywords(legacy_default):
        return canonicalize_keywords(current_default)
    return canonicalize_keywords(value)
