"""View Assist response classification helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .routing import parse_keywords, words_from_text


@dataclass(frozen=True, slots=True)
class ViewRule:
    """A response category mapped to a View Assist path."""

    category: str
    path: str
    keywords: tuple[str, ...]


def parse_view_rules(value: str) -> list[ViewRule]:
    """Parse one rule per line.

    Syntax:
        category | /view-assist/path | word1, word2, word3

    Empty lines and lines beginning with # are ignored. Matching is performed
    with complete normalized words, exactly like the main domotics filter.
    """
    rules: list[ViewRule] = []
    for line_number, raw_line in enumerate(value.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [part.strip() for part in line.split("|", 2)]
        if len(parts) != 3:
            raise ValueError(
                f"La línea {line_number} debe tener: categoria | ruta | palabras"
            )

        category, path, keyword_text = parts
        if not category:
            raise ValueError(f"La línea {line_number} no tiene categoría")
        if not path.startswith("/"):
            raise ValueError(
                f"La ruta de la línea {line_number} debe comenzar con /"
            )

        keywords = tuple(parse_keywords(keyword_text))
        if not keywords:
            raise ValueError(f"La línea {line_number} no tiene palabras")

        rules.append(ViewRule(category=category, path=path, keywords=keywords))

    if not rules:
        raise ValueError("Ingresá al menos una categoría de View Assist")

    return rules


def canonicalize_view_rules(value: str) -> str:
    """Return normalized rules in a stable editable format."""
    return "\n".join(
        f"{rule.category}|{rule.path}|{', '.join(rule.keywords)}"
        for rule in parse_view_rules(value)
    )


def match_view_rule(response_text: str, rules_text: str) -> ViewRule | None:
    """Return the first View Assist rule matching the final response."""
    response_words = words_from_text(response_text)
    if not response_words:
        return None

    for rule in parse_view_rules(rules_text):
        if response_words.intersection(rule.keywords):
            return rule
    return None
