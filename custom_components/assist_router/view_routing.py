"""View Assist response classification and path helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .routing import canonicalize_keywords, parse_keywords, words_from_text


@dataclass(frozen=True, slots=True)
class ViewDefinition:
    """Configuration metadata for one View Assist destination."""

    slug: str
    label: str
    default_enabled: bool
    default_path: str
    default_keywords: str
    legacy_categories: tuple[str, ...] = ()

    @property
    def enabled_key(self) -> str:
        return f"view_{self.slug}_enabled"

    @property
    def path_key(self) -> str:
        return f"view_{self.slug}_path"

    @property
    def keywords_key(self) -> str:
        return f"view_{self.slug}_keywords"


@dataclass(frozen=True, slots=True)
class ViewMatch:
    """Matched View Assist profile."""

    slug: str
    label: str
    path: str
    response_hits: tuple[str, ...]
    request_hits: tuple[str, ...]


VIEW_DEFINITIONS: tuple[ViewDefinition, ...] = (
    ViewDefinition(
        slug="weather",
        label="Clima y tiempo",
        default_enabled=True,
        default_path="weather",
        default_keywords=(
            "tiempo\nclima\npronostico\nlluvia\nllueve\nsoleado\ndespejado\n"
            "nublado\nviento\nhumedad\ntormenta\ntemperatura"
        ),
        legacy_categories=("clima", "weather", "tiempo"),
    ),
    ViewDefinition(
        slug="climate",
        label="Aire y calefacción",
        default_enabled=False,
        default_path="thermostat",
        default_keywords=(
            "aire\naires\ncalor\nfrio\nventilador\nextractor\ncalefaccion\n"
            "temperatura\ntermostato\nclimatizacion\ngrados"
        ),
        legacy_categories=("termostato", "climate", "climatizacion"),
    ),
    ViewDefinition(
        slug="camera",
        label="Cámaras",
        default_enabled=True,
        default_path="camera",
        default_keywords=(
            "camara\ncamaras\nportero\ntimbre\nentrada\nvigilancia\nvideo"
        ),
        legacy_categories=("camara", "camera", "camaras"),
    ),
    ViewDefinition(
        slug="alarm",
        label="Alarmas y recordatorios",
        default_enabled=False,
        default_path="alarm",
        default_keywords=(
            "alarma\nalarmas\nrecordatorio\nrecordatorios\ntemporizador\n"
            "temporizadores\naviso"
        ),
        legacy_categories=("alarma", "alarm", "recordatorio"),
    ),
    ViewDefinition(
        slug="music",
        label="Música y multimedia",
        default_enabled=True,
        default_path="music",
        default_keywords=(
            "musica\ncancion\ncanciones\nradio\nvolumen\nreproduciendo\n"
            "multimedia"
        ),
        legacy_categories=("musica", "music", "multimedia"),
    ),
    ViewDefinition(
        slug="list",
        label="Listas y tareas",
        default_enabled=False,
        default_path="list",
        default_keywords=(
            "lista\nlistas\ncompras\ntareas\npendientes\nitem\nitems"
        ),
        legacy_categories=("lista", "list", "tareas"),
    ),
    ViewDefinition(
        slug="sports",
        label="Deportes",
        default_enabled=False,
        default_path="sports",
        default_keywords=(
            "futbol\npartido\npartidos\nresultado\nresultados\ncampeonato\n"
            "equipo\ngol\ngoles"
        ),
        legacy_categories=("deportes", "sports", "futbol"),
    ),
    ViewDefinition(
        slug="domotics",
        label="Domótica general",
        default_enabled=True,
        default_path="intent",
        default_keywords=(
            "luz\nluces\nlampara\nlamparas\npersiana\npersianas\ncortina\n"
            "cortinas\nporton\npuerta\nventana\nriego\nbomba\nenchufe\n"
            "televisor\ntele\n"
            "prender\nencender\napagar\nabrir\ncerrar\nsubir\nbajar\npone\n"
            "pieza\ndormitorio\ncocina\npatio\nliving\nencendido\nencendida\n"
            "apagado\napagada\nabierto\nabierta\ncerrado\ncerrada"
        ),
        legacy_categories=("domotica", "intent", "casa"),
    ),
)

VIEW_DEFINITIONS_BY_SLUG = {definition.slug: definition for definition in VIEW_DEFINITIONS}


def view_defaults() -> dict[str, Any]:
    """Return default flat settings for every visual category."""
    defaults: dict[str, Any] = {}
    for definition in VIEW_DEFINITIONS:
        defaults[definition.enabled_key] = definition.default_enabled
        defaults[definition.path_key] = definition.default_path
        defaults[definition.keywords_key] = definition.default_keywords
    return defaults


def canonicalize_view_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Normalize paths and keyword lists without discarding unrelated settings."""
    normalized = dict(settings)
    for definition in VIEW_DEFINITIONS:
        normalized[definition.enabled_key] = bool(
            normalized.get(definition.enabled_key, definition.default_enabled)
        )
        normalized[definition.path_key] = normalize_view_path(
            str(normalized.get(definition.path_key, definition.default_path))
        )
        normalized[definition.keywords_key] = canonicalize_keywords(
            str(normalized.get(definition.keywords_key, definition.default_keywords))
        )
    return normalized


def normalize_view_path(path: str) -> str:
    """Normalize a user-entered absolute or dashboard-relative path."""
    value = path.strip()
    if not value:
        return ""
    if value == "home":
        return value
    if value.startswith("view-assist/"):
        return f"/{value}"
    return value.rstrip("/") if value != "/" else value


def validate_view_path(path: str) -> bool:
    """Return whether a path is suitable for View Assist navigation."""
    value = normalize_view_path(path)
    if not value:
        return False
    if any(char.isspace() for char in value):
        return False
    return value == "home" or value.startswith("/") or "/" not in value


def resolve_view_path(configured_path: str, entity_state: Any | None) -> str:
    """Resolve a relative view name against the satellite dashboard base path."""
    path = normalize_view_path(configured_path)
    if not path or path == "home" or path.startswith("/"):
        return path

    base_path = "/view-assist"
    attributes = getattr(entity_state, "attributes", {}) if entity_state else {}
    if isinstance(attributes, dict):
        dashboard = attributes.get("dashboard")
        if isinstance(dashboard, str) and dashboard.strip():
            base_path = dashboard.strip()
        else:
            home_screen = attributes.get("home_screen")
            if isinstance(home_screen, str) and home_screen.startswith("/"):
                parent, _, _ = home_screen.rstrip("/").rpartition("/")
                if parent:
                    base_path = parent

    if not base_path.startswith("/"):
        base_path = f"/{base_path}"
    return f"{base_path.rstrip('/')}/{path.lstrip('/')}"


def _legacy_rule_lines(value: str) -> list[tuple[str, str, str]]:
    """Parse legacy 0.1.x rules leniently for automatic migration."""
    rules: list[tuple[str, str, str]] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|", 2)]
        if len(parts) == 3 and parts[0] and parts[1] and parts[2]:
            rules.append((parts[0].casefold(), parts[1], parts[2]))
    return rules


def apply_legacy_view_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Populate new per-view keys from old combined rules when necessary."""
    migrated = {**view_defaults(), **settings}
    old_rules = settings.get("view_rules")
    if isinstance(old_rules, str):
        for category, path, keywords in _legacy_rule_lines(old_rules):
            for definition in VIEW_DEFINITIONS:
                if category in definition.legacy_categories:
                    if definition.path_key not in settings:
                        migrated[definition.path_key] = path
                    if definition.keywords_key not in settings:
                        migrated[definition.keywords_key] = keywords
                    if definition.enabled_key not in settings:
                        migrated[definition.enabled_key] = True
                    break

    old_openclaw_path = settings.get("openclaw_view_path")
    if (
        "view_openclaw_path" not in settings
        and isinstance(old_openclaw_path, str)
        and old_openclaw_path.strip()
    ):
        migrated["view_openclaw_path"] = old_openclaw_path.strip()
        migrated["view_openclaw_enabled"] = True

    return canonicalize_view_settings(migrated)


def match_view(
    response_text: str,
    request_text: str,
    settings: dict[str, Any],
) -> ViewMatch | None:
    """Select the best enabled view, preferring words in the final response.

    A response hit is weighted more heavily than a request hit. The original
    STT text acts as a fallback for terse downstream responses such as "Listo".
    """
    response_words = words_from_text(response_text)
    request_words = words_from_text(request_text)

    best: tuple[int, int, ViewMatch] | None = None
    for order, definition in enumerate(VIEW_DEFINITIONS):
        if not settings.get(definition.enabled_key, definition.default_enabled):
            continue

        path = normalize_view_path(
            str(settings.get(definition.path_key, definition.default_path))
        )
        keywords = set(
            parse_keywords(
                str(settings.get(definition.keywords_key, definition.default_keywords))
            )
        )
        if not path or not keywords:
            continue

        response_hits = tuple(sorted(response_words & keywords))
        request_hits = tuple(sorted(request_words & keywords))
        if not response_hits and not request_hits:
            continue

        score = len(response_hits) * 10 + len(request_hits)
        candidate = ViewMatch(
            slug=definition.slug,
            label=definition.label,
            path=path,
            response_hits=response_hits,
            request_hits=request_hits,
        )
        ranking = (score, -order, candidate)
        if best is None or ranking[:2] > best[:2]:
            best = ranking

    return best[2] if best else None
