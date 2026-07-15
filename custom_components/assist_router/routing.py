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


def canonicalize_keywords(value: str) -> str:
    """Return one normalized keyword per line."""
    return "\n".join(parse_keywords(value))


def matches_domotics(text: str, keyword_text: str) -> bool:
    """Return True when STT text contains any configured complete keyword."""
    keywords = set(parse_keywords(keyword_text))
    if not keywords:
        return False
    return bool(words_from_text(text) & keywords)
