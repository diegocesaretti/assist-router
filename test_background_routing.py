"""Deterministic parsing helpers for the Stremio voice skill."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any

STREMIO_DOMAIN = "stremio_stream_bridge"
STREMIO_RESOLVE_SERVICE = "resolve"
STREMIO_PLAY_SERVICE = "play"

_PROFILE_DEFAULT = "default"
_PROFILE_LATIN = "latin"
_PROFILE_SPORTS = "sports"

_NUMBER_WORDS = {
    "cero": 0,
    "un": 1,
    "uno": 1,
    "una": 1,
    "primer": 1,
    "primero": 1,
    "primera": 1,
    "dos": 2,
    "segundo": 2,
    "segunda": 2,
    "tres": 3,
    "tercer": 3,
    "tercero": 3,
    "tercera": 3,
    "cuatro": 4,
    "cuarto": 4,
    "cuarta": 4,
    "cinco": 5,
    "quinto": 5,
    "quinta": 5,
    "seis": 6,
    "sexto": 6,
    "sexta": 6,
    "siete": 7,
    "septimo": 7,
    "septima": 7,
    "ocho": 8,
    "octavo": 8,
    "octava": 8,
    "nueve": 9,
    "noveno": 9,
    "novena": 9,
    "diez": 10,
    "decimo": 10,
    "decima": 10,
    "once": 11,
    "doce": 12,
    "trece": 13,
    "catorce": 14,
    "quince": 15,
    "dieciseis": 16,
    "diecisiete": 17,
    "dieciocho": 18,
    "diecinueve": 19,
    "veinte": 20,
}

_NORMALIZED_NUMBER_PATTERN = "(?:" + "|".join(
    sorted((re.escape(word) for word in _NUMBER_WORDS), key=len, reverse=True)
) + r"|\d+)"

_PLAY_PREFIX_RE = re.compile(
    r"^\s*(?:pon(?:e|é)(?:me)?|reproduc(?:e|í)(?:me)?|pas(?:a|á)(?:me)?|"
    r"abr(?:e|í)|quiero\s+(?:ver|mirar)|vamos\s+a\s+ver|"
    r"mostr(?:a|á)me|dale\s+play\s+a)\s+",
    re.IGNORECASE,
)
_STRONG_MARKER_RE = re.compile(
    r"\b(?:stremio|pel[ií]cula|serie|temporada|cap[ií]tulo|episodio|"
    r"audio\s+latino|en\s+latino|subtitulad[oa]s?|sin\s+subt[ií]tulos?|"
    r"con\s+subt[ií]tulos?|f[oó]rmula\s*1|f1|deportes?)\b",
    re.IGNORECASE,
)
_TV_MARKER_RE = re.compile(r"\b(?:tele|televisor|tv|android\s*tv)\b", re.IGNORECASE)
_MEDIA_VERB_RE = re.compile(
    r"^\s*(?:reproduc(?:e|í)|quiero\s+(?:ver|mirar)|vamos\s+a\s+ver)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class StremioRequest:
    """Parsed request sent to the Stream Bridge resolver."""

    query: str
    media_type: str = "all"
    profile: str = _PROFILE_DEFAULT
    season: int | None = None
    episode: int | None = None
    year: int | None = None
    disable_subtitles: bool = False
    media_player: str | None = None
    target_label: str | None = None
    strong: bool = False


@dataclass(slots=True)
class PendingStremioRequest:
    """Short-lived conversational state for ambiguity or episode follow-up."""

    kind: str
    request: StremioRequest
    results: list[dict[str, Any]]
    selected: dict[str, Any] | None
    expires_at: float


def normalize_text(value: str) -> str:
    """Normalize spoken text for matching while preserving numbers."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_marks).split())


def parse_tv_aliases(value: str) -> dict[str, str]:
    """Parse `alias, alias = media_player.entity` lines."""
    aliases: dict[str, str] = {}
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        names, entity_id = line.split("=", 1)
        entity_id = entity_id.strip()
        if not entity_id.startswith("media_player."):
            continue
        for name in names.split(","):
            normalized = normalize_text(name)
            if normalized:
                aliases[normalized] = entity_id
    return aliases


def canonicalize_tv_aliases(value: str) -> str:
    """Normalize whitespace without changing user-visible aliases."""
    lines: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "=" not in line:
            lines.append(line)
            continue
        names, entity_id = line.split("=", 1)
        clean_names = ", ".join(
            name.strip() for name in names.split(",") if name.strip()
        )
        lines.append(f"{clean_names} = {entity_id.strip()}")
    return "\n".join(lines)


def parse_stremio_request(
    text: str,
    *,
    aliases: dict[str, str] | None = None,
    default_player: str | None = None,
) -> StremioRequest | None:
    """Parse a natural Spanish request without stealing ordinary domotics."""
    aliases = aliases or {}
    normalized = normalize_text(text)
    has_prefix = bool(_PLAY_PREFIX_RE.search(text))
    strong = bool(_STRONG_MARKER_RE.search(text))
    has_tv = bool(_TV_MARKER_RE.search(text))
    has_alias_target = _find_target_alias(normalized, aliases) is not None
    media_verb = bool(_MEDIA_VERB_RE.search(text))

    # A media noun alone is not an action. This prevents questions such as
    # “¿Quién actuó en la película Matrix?” from being stolen from the general
    # agent. Explicit play/view wording is always required.
    if not (has_prefix or media_verb):
        return None
    if not strong and not (has_tv or has_alias_target or media_verb):
        return None

    media_type = "all"
    if re.search(r"\b(?:serie|temporada|capitulo|episodio)\b", normalized):
        media_type = "series"
    elif re.search(r"\bpelicula\b", normalized):
        media_type = "movie"

    profile = _PROFILE_DEFAULT
    if re.search(
        r"\b(?:latino|audio latino|doblad[oa] (?:al|en) latino)\b",
        normalized,
    ):
        profile = _PROFILE_LATIN
    elif re.search(r"\b(?:f1|formula 1|deporte|deportes)\b", normalized):
        profile = _PROFILE_SPORTS

    disable_subtitles = bool(
        re.search(r"\b(?:sin subtitulos|sin subtitulado|sin subtitular)\b", normalized)
    ) or profile in {_PROFILE_LATIN, _PROFILE_SPORTS}

    season = _number_after(normalized, ("temporada",))
    episode = _number_after(normalized, ("capitulo", "episodio"))
    year = _extract_requested_year(normalized)

    target_label, media_player = _resolve_target(
        normalized,
        aliases,
        default_player=default_player,
    )

    query = _extract_query(text, aliases)
    if not query or not _query_has_content(query):
        return None

    return StremioRequest(
        query=query,
        media_type=media_type,
        profile=profile,
        season=season,
        episode=episode,
        year=year,
        disable_subtitles=disable_subtitles,
        media_player=media_player,
        target_label=target_label,
        strong=strong,
    )


def parse_single_number(text: str) -> int | None:
    """Return the first standalone spoken or numeric value."""
    normalized = normalize_text(text)
    for token in normalized.split():
        value = _parse_number(token)
        if value is not None:
            return value
    return None


def parse_follow_up_episode(text: str) -> tuple[int | None, int | None]:
    """Extract a season and episode from a follow-up answer."""
    normalized = normalize_text(text)
    season = _number_after(normalized, ("temporada",))
    episode = _number_after(normalized, ("capitulo", "episodio"))

    # A terse "dos, tres" means season 2, episode 3 when both are absent.
    if season is None and episode is None:
        values = [_parse_number(token) for token in normalized.split()]
        numbers = [value for value in values if value is not None]
        if len(numbers) >= 2:
            return numbers[0], numbers[1]
    return season, episode


def select_result_from_follow_up(
    text: str, results: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Select an ambiguous result by ordinal, year, type, or title."""
    if not results:
        return None
    normalized = normalize_text(text)

    ordinal = _ordinal_index(normalized)
    if ordinal is not None and 0 <= ordinal < len(results):
        return results[ordinal]

    year = _extract_year(normalized)
    if year is not None:
        matching_year = [
            item for item in results if _coerce_int(item.get("year")) == year
        ]
        if len(matching_year) == 1:
            return matching_year[0]

    requested_type: str | None = None
    if "pelicula" in normalized:
        requested_type = "movie"
    elif "serie" in normalized:
        requested_type = "series"
    if requested_type:
        matching_type = [
            item for item in results if str(item.get("media_type")) == requested_type
        ]
        if len(matching_type) == 1:
            return matching_type[0]

    exact_title = [
        item
        for item in results
        if normalize_text(str(item.get("title") or "")) == normalized
    ]
    if len(exact_title) == 1:
        return exact_title[0]

    contained = [
        item
        for item in results
        if normalize_text(str(item.get("title") or ""))
        and normalize_text(str(item.get("title") or "")) in normalized
    ]
    if len(contained) == 1:
        return contained[0]
    return None


def describe_results(results: list[dict[str, Any]], limit: int = 4) -> str:
    """Create a compact voice-friendly ambiguity prompt."""
    choices: list[str] = []
    for index, item in enumerate(results[:limit], start=1):
        title = str(item.get("title") or item.get("media_id") or "resultado")
        year = _coerce_int(item.get("year"))
        media_type = str(item.get("media_type") or "")
        type_label = "serie" if media_type == "series" else "película"
        suffix = f", {year}" if year else ""
        choices.append(f"{index}: {title}{suffix}, {type_label}")
    return "; ".join(choices)


def selected_title(selected: dict[str, Any]) -> str:
    """Return a useful display title for a movie or episode."""
    series_title = str(selected.get("series_title") or "").strip()
    title = str(
        selected.get("title") or selected.get("media_id") or "contenido"
    ).strip()
    season = _coerce_int(selected.get("season"))
    episode = _coerce_int(selected.get("episode"))
    if series_title and season is not None and episode is not None:
        return f"{series_title}, temporada {season}, capítulo {episode}: {title}"
    return title



def _query_has_content(query: str) -> bool:
    """Reject commands that only name the TV and contain no media title."""
    tokens = set(normalize_text(query).split())
    filler = {
        "a",
        "al",
        "android",
        "el",
        "en",
        "la",
        "las",
        "los",
        "tele",
        "televisor",
        "tv",
        "un",
        "una",
    }
    return bool(tokens - filler)

def _resolve_target(
    normalized_text: str,
    aliases: dict[str, str],
    *,
    default_player: str | None,
) -> tuple[str | None, str | None]:
    alias = _find_target_alias(normalized_text, aliases)
    if alias is not None:
        return alias, aliases[alias]
    if _TV_MARKER_RE.search(normalized_text):
        return "tele", default_player or None
    return None, default_player or None


def _find_target_alias(
    normalized_text: str, aliases: dict[str, str]
) -> str | None:
    """Find a configured room/TV alias only in a target-like phrase."""
    for alias in sorted(aliases, key=len, reverse=True):
        escaped = re.escape(alias)
        patterns = (
            rf"\b(?:tele|televisor|tv|android tv)\s+(?:de|del|de la)\s+{escaped}\b",
            rf"\ben\s+(?:el|la)?\s*{escaped}\s*$",
        )
        if any(re.search(pattern, normalized_text) for pattern in patterns):
            return alias
    return None


def _extract_query(text: str, aliases: dict[str, str]) -> str:
    query = _PLAY_PREFIX_RE.sub("", text, count=1)
    cleanup_patterns = (
        r"\b(?:en|por)\s+stremio\b",
        r"\bstremio\b",
        r"\b(?:la|una)\s+pel[ií]cula\s+(?:de|llamada)?\s*",
        r"\b(?:la|una)\s+serie\s+(?:de|llamada)?\s*",
        r"\bpel[ií]cula\b",
        r"\bserie\b",
        r"\b(?:en|con\s+audio|doblad[oa]\s+(?:al|en))\s+latino\b",
        r"\b(?:con|sin)\s+subt[ií]tulos?\b",
        r"\bsubtitulad[oa]s?\b",
        r"\ben\s+(?:la\s+)?(?:tele|tv|televisor|android\s*tv)\b.*$",
        r"\b(?:tele|tv|televisor|android\s*tv)\s+(?:del?|de\s+la)\s+[^,.;!?]+$",
    )
    for pattern in cleanup_patterns:
        query = re.sub(pattern, " ", query, flags=re.IGNORECASE)
    query = _remove_labeled_numbers(query)
    # "Dune de 2021" uses the year as a discriminator, not as title text.
    query = re.sub(
        r"\b(?:de|del\s+año|del\s+ano|año|ano|versi[oó]n(?:\s+de)?)\s+"
        r"(?:19\d{2}|20\d{2})\b",
        " ",
        query,
        flags=re.IGNORECASE,
    )
    for alias in sorted(aliases, key=len, reverse=True):
        query = re.sub(
            rf"\b(?:en\s+(?:el|la)\s+|(?:de|del|de la)\s+){re.escape(alias)}\s*$",
            " ",
            query,
            flags=re.IGNORECASE,
        )
    query = re.sub(
        r"\b(?:del?|en)\s+(?:el|la)\s+(?:living|dormitorio|pieza|sala)\b.*$",
        " ",
        query,
        flags=re.IGNORECASE,
    )
    query = query.strip(" \t\r\n,.;:!?¿¡\"'")
    query = re.sub(r"\s+", " ", query)
    return query



def _remove_labeled_numbers(value: str) -> str:
    """Remove valid season/episode phrases without eating ordinary words."""
    label = r"(?:temporada|cap[ií]tulo|episodio)"
    token = r"(?:\d+|[a-záéíóúñ]+)"

    def replace_if_number(match: re.Match[str]) -> str:
        spoken = normalize_text(match.group("number"))
        return " " if _parse_number(spoken) is not None else match.group(0)

    value = re.sub(
        rf"\b(?P<number>{token})\s+{label}\b",
        replace_if_number,
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(
        rf"\b{label}\s+(?P<number>{token})\b",
        replace_if_number,
        value,
        flags=re.IGNORECASE,
    )

def _number_after(normalized: str, labels: tuple[str, ...]) -> int | None:
    """Return the number belonging to a season/episode label."""
    tokens = normalized.split()
    label_set = set(labels)
    all_labels = {"temporada", "capitulo", "episodio"}
    for index, token in enumerate(tokens):
        if token not in label_set:
            continue
        before = _parse_number(tokens[index - 1]) if index > 0 else None
        after = _parse_number(tokens[index + 1]) if index + 1 < len(tokens) else None
        if before is not None and after is not None:
            before_is_previous_label_value = (
                index >= 2 and tokens[index - 2] in all_labels
            )
            after_is_next_label_value = (
                index + 2 < len(tokens) and tokens[index + 2] in all_labels
            )
            if before_is_previous_label_value and not after_is_next_label_value:
                return after
            if after_is_next_label_value and not before_is_previous_label_value:
                return before
            return after
        if after is not None:
            return after
        if before is not None:
            return before
    return None


def _parse_number(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    return _NUMBER_WORDS.get(value)



def _extract_requested_year(normalized: str) -> int | None:
    """Extract a release year only when the user marks it as a discriminator."""
    match = re.search(
        r"\b(?:de|del año|del ano|año|ano|version|version de)\s+"
        r"(19\d{2}|20\d{2})\b",
        normalized,
    )
    return int(match.group(1)) if match else None

def _extract_year(normalized: str) -> int | None:
    match = re.search(r"\b(19\d{2}|20\d{2})\b", normalized)
    return int(match.group(1)) if match else None


def _ordinal_index(normalized: str) -> int | None:
    for token in normalized.split():
        value = _parse_number(token)
        if value is not None and 1 <= value <= 10:
            return value - 1
    return None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
