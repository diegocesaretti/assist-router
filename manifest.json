"""Conversation platform for Assist Router."""

from __future__ import annotations

import asyncio
import inspect
from importlib import import_module
import logging
import time
from typing import Any, Literal
from uuid import uuid4

from homeassistant.components import conversation
from homeassistant.components.conversation.agent_manager import async_get_agent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DOMOTICS_AGENT,
    CONF_GENERAL_AGENT,
    CONF_END_PHRASES,
    CONF_END_RESPONSE,
    CONF_END_VIEW_HOME,
    CONF_FOLLOW_UP_ENABLED,
    CONF_KEYWORDS,
    CONF_OPENCLAW_ACK_MESSAGE,
    CONF_OPENCLAW_AGENT,
    CONF_OPENCLAW_BACKGROUND_INSTRUCTION,
    CONF_GENERAL_ROUTER_INSTRUCTION,
    CONF_FORCE_OPENCLAW_PHRASES,
    CONF_STREMIO_ENABLED,
    CONF_STREMIO_ENTRY_ID,
    CONF_STREMIO_DEFAULT_PLAYER,
    CONF_STREMIO_TV_ALIASES,
    CONF_STREMIO_RESULT_LIMIT,
    CONF_STREMIO_VIEW_ENABLED,
    CONF_STREMIO_VIEW_PATH,
    CONF_STREMIO_PLAY_ACK,
    CONF_STREMIO_PENDING_TIMEOUT,
    CONF_OPENCLAW_VIEW_ENABLED,
    CONF_OPENCLAW_VIEW_PATH_V2,
    CONF_VIEW_ASSIST_ENABLED,
    CONF_VIEW_ASSIST_ENTITY,
    CONF_VIEW_NAVIGATION_DELAY,
    CONF_VIEW_REVERT_TIMEOUT,
    CONF_RESPONSE_VIEW_ENABLED,
    CONF_RESPONSE_VIEW_PATH,
    CONF_RESPONSE_DISPLAY_TIME,
    CONF_RESPONSE_DISPLAY_MIN_TIME,
    CONF_RESPONSE_SECONDS_PER_WORD,
    CONF_RESPONSE_DISPLAY_MAX_TIME,
    CONF_RELATED_VIEW_DISPLAY_TIME,
    DEFAULT_END_PHRASES,
    DEFAULT_END_RESPONSE,
    DEFAULT_END_VIEW_HOME,
    DEFAULT_FOLLOW_UP_ENABLED,
    DEFAULT_KEYWORDS,
    DEFAULT_GENERAL_ROUTER_INSTRUCTION,
    DEFAULT_FORCE_OPENCLAW_PHRASES,
    DEFAULT_STREMIO_ENABLED,
    DEFAULT_STREMIO_ENTRY_ID,
    DEFAULT_STREMIO_DEFAULT_PLAYER,
    DEFAULT_STREMIO_TV_ALIASES,
    DEFAULT_STREMIO_RESULT_LIMIT,
    DEFAULT_STREMIO_VIEW_ENABLED,
    DEFAULT_STREMIO_VIEW_PATH,
    DEFAULT_STREMIO_PLAY_ACK,
    DEFAULT_STREMIO_PENDING_TIMEOUT,
    DEFAULT_OPENCLAW_ACK_MESSAGE,
    DEFAULT_OPENCLAW_BACKGROUND_INSTRUCTION,
    DEFAULT_OPENCLAW_VIEW_ENABLED,
    DEFAULT_OPENCLAW_VIEW_PATH,
    DEFAULT_VIEW_ASSIST_ENABLED,
    DEFAULT_VIEW_ASSIST_ENTITY,
    DEFAULT_VIEW_NAVIGATION_DELAY,
    DEFAULT_VIEW_REVERT_TIMEOUT,
    DEFAULT_RESPONSE_VIEW_ENABLED,
    DEFAULT_RESPONSE_VIEW_PATH,
    DEFAULT_RESPONSE_DISPLAY_MIN_TIME,
    DEFAULT_RESPONSE_SECONDS_PER_WORD,
    DEFAULT_RESPONSE_DISPLAY_MAX_TIME,
    DEFAULT_RELATED_VIEW_DISPLAY_TIME,
    LEGACY_DEFAULT_RELATED_VIEW_DISPLAY_TIME,
    LEGACY_DEFAULT_KEYWORDS_0_1_3,
    OPENCLAW_ROUTE_MARKER,
    ROUTE_STREMIO,
    ROUTE_DOMOTICS,
    ROUTE_GENERAL,
    ROUTE_OPENCLAW,
    VIEW_ASSIST_AUTO_ENTITY,
    STREMIO_AUTO_ENTRY,
)
from .stremio import (
    PendingStremioRequest,
    STREMIO_DOMAIN,
    STREMIO_PLAY_SERVICE,
    STREMIO_RESOLVE_SERVICE,
    StremioRequest,
    describe_results,
    parse_follow_up_episode,
    parse_single_number,
    parse_stremio_request,
    parse_tv_aliases,
    select_result_from_follow_up,
    selected_title,
)
from .routing import (
    matches_domotics,
    matches_end_phrase,
    matches_phrase_in_text,
    migrate_default_keywords,
    normalize_phrase,
)
from .view_routing import (
    apply_legacy_view_settings,
    calculate_response_display_time,
    match_view,
    resolve_view_path,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Assist Router conversation entity."""
    async_add_entities([AssistRouterConversationEntity(entry)])


class AssistRouterConversationEntity(conversation.ConversationEntity):
    """Route Assist requests to local skills, agents, or OpenClaw."""

    _attr_has_entity_name = True
    _attr_name = "Router"
    _attr_icon = "mdi:call-split"
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the router."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._view_sequence_generation: dict[str, int] = {}
        self._stremio_pending: dict[str, PendingStremioRequest] = {}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Support all languages accepted by the selected agents."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """Register the agent for legacy pipeline selectors too."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister the legacy agent."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Route a message to Stremio, domotics, a general agent, or OpenClaw."""
        settings = apply_legacy_view_settings({**self.entry.data, **self.entry.options})
        if (
            settings.get(CONF_RELATED_VIEW_DISPLAY_TIME)
            == LEGACY_DEFAULT_RELATED_VIEW_DISPLAY_TIME
        ):
            settings[CONF_RELATED_VIEW_DISPLAY_TIME] = (
                DEFAULT_RELATED_VIEW_DISPLAY_TIME
            )
        self._invalidate_view_sequence(
            user_input,
            settings.get(CONF_VIEW_ASSIST_ENTITY, DEFAULT_VIEW_ASSIST_ENTITY),
        )
        keyword_text = migrate_default_keywords(
            settings.get(CONF_KEYWORDS),
            LEGACY_DEFAULT_KEYWORDS_0_1_3,
            DEFAULT_KEYWORDS,
        )

        acknowledgement = str(
            settings.get(
                CONF_OPENCLAW_ACK_MESSAGE,
                DEFAULT_OPENCLAW_ACK_MESSAGE,
            )
        ).strip()

        # Defensive echo guard: some satellites can hear their own TTS when a
        # conversation remains open. Never route the OpenClaw acknowledgement
        # back into OpenClaw, otherwise it can repeat indefinitely.
        if (
            acknowledgement
            and normalize_phrase(user_input.text)
            == normalize_phrase(acknowledgement)
        ):
            _LOGGER.warning(
                "Discarded an OpenClaw acknowledgement echoed back by STT"
            )
            return self._silent_result(user_input)

        if matches_end_phrase(
            user_input.text,
            str(settings.get(CONF_END_PHRASES, DEFAULT_END_PHRASES)),
        ):
            self._clear_stremio_pending(user_input)
            if settings.get(CONF_END_VIEW_HOME, DEFAULT_END_VIEW_HOME):
                self._schedule_view_assist_navigation(
                    user_input=user_input,
                    settings=settings,
                    path="home",
                    category="conversation_end",
                )
            return self._speech_result(
                user_input,
                str(settings.get(CONF_END_RESPONSE, DEFAULT_END_RESPONSE)).strip(),
                conversation_id=None,
            )

        base_conversation_id = (
            user_input.conversation_id or f"assist_router_{uuid4().hex}"
        )

        force_openclaw_phrases = str(
            settings.get(
                CONF_FORCE_OPENCLAW_PHRASES,
                DEFAULT_FORCE_OPENCLAW_PHRASES,
            )
        )
        if matches_phrase_in_text(user_input.text, force_openclaw_phrases):
            _LOGGER.debug("Explicit OpenClaw phrase matched")
            self._clear_stremio_pending(user_input)
            return self._handoff_to_openclaw(
                user_input=user_input,
                settings=settings,
                base_conversation_id=base_conversation_id,
                acknowledgement=acknowledgement,
            )

        pending_result = await self._async_handle_stremio_pending(
            user_input=user_input,
            settings=settings,
            base_conversation_id=base_conversation_id,
        )
        if pending_result is not None:
            return pending_result

        stremio_result, suppress_domotics = await self._async_try_stremio(
            user_input=user_input,
            settings=settings,
            base_conversation_id=base_conversation_id,
        )
        if stremio_result is not None:
            return stremio_result

        if not suppress_domotics and matches_domotics(user_input.text, keyword_text):
            target_agent_id = settings[CONF_DOMOTICS_AGENT]
            if error := self._validate_target_agent(user_input, target_agent_id):
                return error

            downstream_conversation_id = (
                f"{base_conversation_id}:{ROUTE_DOMOTICS}"
            )
            _LOGGER.debug(
                "Routing Assist text to %s via agent %s",
                ROUTE_DOMOTICS,
                target_agent_id,
            )
            result = await self._async_converse(
                user_input=user_input,
                text=user_input.text,
                target_agent_id=target_agent_id,
                conversation_id=downstream_conversation_id,
            )
            self._schedule_result_view(
                user_input=user_input,
                settings=settings,
                result=result,
            )
            return self._wrap_downstream_result(
                result,
                base_conversation_id,
                continue_conversation=bool(
                    settings.get(CONF_FOLLOW_UP_ENABLED, DEFAULT_FOLLOW_UP_ENABLED)
                ),
            )

        # Everything outside the deterministic domotics filter is sent to a
        # fast general agent. It either answers normally or returns a private
        # marker that authorizes the slow OpenClaw handoff.
        general_agent_id = settings.get(CONF_GENERAL_AGENT) or settings.get(
            CONF_DOMOTICS_AGENT
        )
        if error := self._validate_target_agent(user_input, general_agent_id):
            return error

        general_result = await self._async_converse(
            user_input=user_input,
            text=user_input.text,
            target_agent_id=general_agent_id,
            conversation_id=f"{base_conversation_id}:{ROUTE_GENERAL}",
            extra_system_prompt=self._general_router_prompt(settings),
        )
        general_text = self._extract_response_text(general_result)

        if self._is_openclaw_marker(general_text):
            _LOGGER.info(
                "General agent classified the request for asynchronous OpenClaw"
            )
            return self._handoff_to_openclaw(
                user_input=user_input,
                settings=settings,
                base_conversation_id=base_conversation_id,
                acknowledgement=acknowledgement,
            )

        self._schedule_result_view(
            user_input=user_input,
            settings=settings,
            result=general_result,
        )
        return self._wrap_downstream_result(
            general_result,
            base_conversation_id,
            continue_conversation=bool(
                settings.get(CONF_FOLLOW_UP_ENABLED, DEFAULT_FOLLOW_UP_ENABLED)
            ),
        )

    async def _async_try_stremio(
        self,
        *,
        user_input: conversation.ConversationInput,
        settings: dict[str, Any],
        base_conversation_id: str,
    ) -> tuple[conversation.ConversationResult | None, bool]:
        """Try the local Stream Bridge skill before the domotics keyword route."""
        if not settings.get(CONF_STREMIO_ENABLED, DEFAULT_STREMIO_ENABLED):
            return None, False

        request = self._parse_stremio_request(user_input.text, settings)
        if request is None:
            return None, False

        _LOGGER.debug(
            "Routing Assist text to %s resolver: query=%s type=%s profile=%s",
            ROUTE_STREMIO,
            request.query,
            request.media_type,
            request.profile,
        )

        # A weak command such as "poné Calamaro en la tele" is still consumed
        # by the multimedia layer so the words "poné" and "tele" cannot route
        # it to the domotics agent. When Stremio has no match, the general agent
        # remains available for a future YouTube or Music Assistant skill.
        suppress_domotics = True
        if not self.hass.services.has_service(
            STREMIO_DOMAIN, STREMIO_RESOLVE_SERVICE
        ):
            _LOGGER.info(
                "Stremio request detected but %s.%s is unavailable",
                STREMIO_DOMAIN,
                STREMIO_RESOLVE_SERVICE,
            )
            if not request.strong:
                return None, suppress_domotics
            return (
                self._stremio_reply(
                    user_input=user_input,
                    settings=settings,
                    message=(
                        "La función de búsqueda de Stremio todavía no está "
                        "disponible en Stream Bridge."
                    ),
                    status="unavailable",
                    conversation_id=base_conversation_id,
                    continue_conversation=True,
                ),
                suppress_domotics,
            )

        response = await self._async_resolve_stremio(
            user_input=user_input,
            settings=settings,
            request=request,
        )
        result = await self._async_handle_stremio_resolution(
            user_input=user_input,
            settings=settings,
            base_conversation_id=base_conversation_id,
            request=request,
            response=response,
        )
        return result, suppress_domotics

    async def _async_handle_stremio_pending(
        self,
        *,
        user_input: conversation.ConversationInput,
        settings: dict[str, Any],
        base_conversation_id: str,
    ) -> conversation.ConversationResult | None:
        """Continue an ambiguity or series/episode dialogue."""
        pending = self._get_stremio_pending(user_input)
        if pending is None:
            return None

        # A complete new playback command replaces the previous question.
        new_request = self._parse_stremio_request(user_input.text, settings)
        if (
            new_request is not None
            and normalize_phrase(new_request.query)
            != normalize_phrase(pending.request.query)
        ):
            self._clear_stremio_pending(user_input)
            return None

        if pending.kind == "ambiguous":
            selected = select_result_from_follow_up(user_input.text, pending.results)
            if selected is None:
                message = (
                    "No pude identificar cuál elegiste. Decime el número, "
                    "el año o el título. "
                    + describe_results(pending.results)
                )
                return self._stremio_reply(
                    user_input=user_input,
                    settings=settings,
                    message=message,
                    status="ambiguous",
                    results=pending.results,
                    conversation_id=base_conversation_id,
                    continue_conversation=True,
                )

            media_type = str(selected.get("media_type") or "movie")
            if media_type != "series":
                return self._start_stremio_playback(
                    user_input=user_input,
                    settings=settings,
                    request=pending.request,
                    selected=selected,
                )

            season, episode = parse_follow_up_episode(user_input.text)
            request = StremioRequest(
                query=str(selected.get("title") or pending.request.query),
                media_type="series",
                profile=pending.request.profile,
                season=season,
                episode=episode,
                year=self._as_int(selected.get("year")),
                disable_subtitles=pending.request.disable_subtitles,
                media_player=pending.request.media_player,
                target_label=pending.request.target_label,
                strong=True,
            )
            response = await self._async_resolve_stremio(
                user_input=user_input,
                settings=settings,
                request=request,
            )
            return await self._async_handle_stremio_resolution(
                user_input=user_input,
                settings=settings,
                base_conversation_id=base_conversation_id,
                request=request,
                response=response,
                selected_hint=selected,
            )

        if pending.kind == "episode":
            season, episode = parse_follow_up_episode(user_input.text)
            single_number = parse_single_number(user_input.text)
            if season is None:
                season = pending.request.season
            if episode is None and season is not None and single_number is not None:
                # After asking only for a chapter, a terse "tres" means E03.
                episode = single_number

            selected = pending.selected or {}
            series_title = str(
                selected.get("series_title")
                or selected.get("title")
                or pending.request.query
            )
            updated_request = StremioRequest(
                query=series_title,
                media_type="series",
                profile=pending.request.profile,
                season=season,
                episode=episode,
                year=self._as_int(selected.get("year")) or pending.request.year,
                disable_subtitles=pending.request.disable_subtitles,
                media_player=pending.request.media_player,
                target_label=pending.request.target_label,
                strong=True,
            )

            if episode is None:
                self._set_stremio_pending(
                    user_input=user_input,
                    base_conversation_id=base_conversation_id,
                    pending=PendingStremioRequest(
                        kind="episode",
                        request=updated_request,
                        results=[],
                        selected=selected,
                        expires_at=self._stremio_expiration(settings),
                    ),
                )
                message = (
                    f"¿Qué capítulo de la temporada {season} querés ver?"
                    if season is not None
                    else "Decime la temporada y el capítulo."
                )
                return self._stremio_reply(
                    user_input=user_input,
                    settings=settings,
                    message=message,
                    status="series_needs_episode",
                    selected=selected,
                    conversation_id=base_conversation_id,
                    continue_conversation=True,
                )

            if season is None:
                return self._stremio_reply(
                    user_input=user_input,
                    settings=settings,
                    message="Decime también la temporada.",
                    status="series_needs_episode",
                    selected=selected,
                    conversation_id=base_conversation_id,
                    continue_conversation=True,
                )

            response = await self._async_resolve_stremio(
                user_input=user_input,
                settings=settings,
                request=updated_request,
            )
            return await self._async_handle_stremio_resolution(
                user_input=user_input,
                settings=settings,
                base_conversation_id=base_conversation_id,
                request=updated_request,
                response=response,
                selected_hint=selected,
            )

        self._clear_stremio_pending(user_input)
        return None

    async def _async_resolve_stremio(
        self,
        *,
        user_input: conversation.ConversationInput,
        settings: dict[str, Any],
        request: StremioRequest,
    ) -> dict[str, Any]:
        """Call the public Stream Bridge resolver service."""
        service_data: dict[str, Any] = {
            "query": request.query,
            "media_type": request.media_type,
            "profile": request.profile,
            "limit": max(
                1,
                min(
                    int(
                        settings.get(
                            CONF_STREMIO_RESULT_LIMIT,
                            DEFAULT_STREMIO_RESULT_LIMIT,
                        )
                    ),
                    10,
                ),
            ),
        }
        entry_id = str(
            settings.get(CONF_STREMIO_ENTRY_ID, DEFAULT_STREMIO_ENTRY_ID) or ""
        ).strip()
        if entry_id and entry_id != STREMIO_AUTO_ENTRY:
            service_data["entry_id"] = entry_id
        if request.year is not None:
            service_data["year"] = request.year
        if request.season is not None:
            service_data["season"] = request.season
        if request.episode is not None:
            service_data["episode"] = request.episode

        try:
            response = await self._async_call_service_with_response(
                domain=STREMIO_DOMAIN,
                service=STREMIO_RESOLVE_SERVICE,
                service_data=service_data,
                user_input=user_input,
            )
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001 - present a voice-friendly error.
            _LOGGER.exception("Stremio resolver call failed")
            return {
                "ok": False,
                "status": "error",
                "error": str(err),
                "results": [],
            }

        if not isinstance(response, dict):
            return {
                "ok": False,
                "status": "error",
                "error": "Stream Bridge did not return structured response data",
                "results": [],
            }
        return response

    async def _async_handle_stremio_resolution(
        self,
        *,
        user_input: conversation.ConversationInput,
        settings: dict[str, Any],
        base_conversation_id: str,
        request: StremioRequest,
        response: dict[str, Any],
        selected_hint: dict[str, Any] | None = None,
    ) -> conversation.ConversationResult | None:
        """Turn the resolver contract into a voice and View Assist response."""
        status = str(response.get("status") or "error").casefold()
        selected_value = response.get("selected")
        selected = selected_value if isinstance(selected_value, dict) else None
        results_value = response.get("results")
        results = (
            [item for item in results_value if isinstance(item, dict)]
            if isinstance(results_value, list)
            else []
        )
        limit = max(
            1,
            min(
                int(
                    settings.get(
                        CONF_STREMIO_RESULT_LIMIT,
                        DEFAULT_STREMIO_RESULT_LIMIT,
                    )
                ),
                10,
            ),
        )
        results = results[:limit]

        if status == "exact" and selected is not None:
            media_type = str(selected.get("media_type") or request.media_type)
            media_id = str(selected.get("media_id") or "")
            # A base series ID is not directly playable without an episode.
            if media_type == "series" and ":" not in media_id and not (
                selected.get("season") is not None
                and selected.get("episode") is not None
            ):
                status = "series_needs_episode"
            else:
                return self._start_stremio_playback(
                    user_input=user_input,
                    settings=settings,
                    request=request,
                    selected=selected,
                )

        if status == "ambiguous":
            if not results:
                status = "not_found"
            else:
                pending = PendingStremioRequest(
                    kind="ambiguous",
                    request=request,
                    results=results,
                    selected=None,
                    expires_at=self._stremio_expiration(settings),
                )
                self._set_stremio_pending(
                    user_input=user_input,
                    base_conversation_id=base_conversation_id,
                    pending=pending,
                )
                message = (
                    "Encontré varias opciones. "
                    + describe_results(results)
                    + ". Decime el número, el año o el título."
                )
                return self._stremio_reply(
                    user_input=user_input,
                    settings=settings,
                    message=message,
                    status="ambiguous",
                    results=results,
                    conversation_id=base_conversation_id,
                    continue_conversation=True,
                )

        if status == "series_needs_episode":
            series = selected or selected_hint or {
                "media_type": "series",
                "title": request.query,
                "year": request.year,
            }
            pending = PendingStremioRequest(
                kind="episode",
                request=request,
                results=[],
                selected=series,
                expires_at=self._stremio_expiration(settings),
            )
            self._set_stremio_pending(
                user_input=user_input,
                base_conversation_id=base_conversation_id,
                pending=pending,
            )
            title = str(
                series.get("series_title") or series.get("title") or request.query
            )
            message = (
                f"¿Qué capítulo de la temporada {request.season} de {title} querés ver?"
                if request.season is not None
                else f"Encontré {title}. Decime la temporada y el capítulo."
            )
            return self._stremio_reply(
                user_input=user_input,
                settings=settings,
                message=message,
                status="series_needs_episode",
                selected=series,
                conversation_id=base_conversation_id,
                continue_conversation=True,
            )

        if status == "episode_not_found":
            series = selected or selected_hint or {
                "media_type": "series",
                "title": request.query,
            }
            pending = PendingStremioRequest(
                kind="episode",
                request=StremioRequest(
                    query=request.query,
                    media_type="series",
                    profile=request.profile,
                    season=request.season,
                    episode=None,
                    year=request.year,
                    disable_subtitles=request.disable_subtitles,
                    media_player=request.media_player,
                    target_label=request.target_label,
                    strong=True,
                ),
                results=[],
                selected=series,
                expires_at=self._stremio_expiration(settings),
            )
            self._set_stremio_pending(
                user_input=user_input,
                base_conversation_id=base_conversation_id,
                pending=pending,
            )
            message = (
                "No encontré ese capítulo. Decime otra temporada y capítulo."
            )
            return self._stremio_reply(
                user_input=user_input,
                settings=settings,
                message=message,
                status="episode_not_found",
                selected=series,
                conversation_id=base_conversation_id,
                continue_conversation=True,
            )

        if status == "not_found":
            if not request.strong:
                return None
            return self._stremio_reply(
                user_input=user_input,
                settings=settings,
                message=f"No encontré {request.query} en Stremio.",
                status="not_found",
                conversation_id=base_conversation_id,
                continue_conversation=True,
            )

        if status == "unsupported":
            return self._stremio_reply(
                user_input=user_input,
                settings=settings,
                message="Esa búsqueda todavía no está soportada por Stream Bridge.",
                status="unsupported",
                conversation_id=base_conversation_id,
                continue_conversation=True,
            )

        error_text = str(response.get("error") or "").strip()
        _LOGGER.warning(
            "Stream Bridge resolver returned status=%s error=%s",
            status,
            error_text,
        )
        return self._stremio_reply(
            user_input=user_input,
            settings=settings,
            message="No pude consultar Stremio en este momento.",
            status="error",
            conversation_id=base_conversation_id,
            continue_conversation=True,
        )

    def _start_stremio_playback(
        self,
        *,
        user_input: conversation.ConversationInput,
        settings: dict[str, Any],
        request: StremioRequest,
        selected: dict[str, Any],
    ) -> conversation.ConversationResult:
        """Start playback in the background and close the noisy voice session."""
        media_id = str(selected.get("media_id") or "").strip()
        media_type = str(selected.get("media_type") or request.media_type).strip()
        if not media_id or media_type not in {
            "movie",
            "series",
            "anime",
            "tv",
            "channel",
            "sport",
        }:
            return self._stremio_reply(
                user_input=user_input,
                settings=settings,
                message="El resultado de Stremio no tiene un identificador reproducible.",
                status="error",
                conversation_id=user_input.conversation_id,
                continue_conversation=False,
            )

        if not self.hass.services.has_service(STREMIO_DOMAIN, STREMIO_PLAY_SERVICE):
            return self._stremio_reply(
                user_input=user_input,
                settings=settings,
                message="El servicio de reproducción de Stream Bridge no está disponible.",
                status="unavailable",
                conversation_id=user_input.conversation_id,
                continue_conversation=False,
            )

        service_data: dict[str, Any] = {
            "media_type": media_type,
            "media_id": media_id,
            "profile": request.profile,
            "disable_subtitles": request.disable_subtitles,
        }
        entry_id = str(
            settings.get(CONF_STREMIO_ENTRY_ID, DEFAULT_STREMIO_ENTRY_ID) or ""
        ).strip()
        if entry_id and entry_id != STREMIO_AUTO_ENTRY:
            service_data["entry_id"] = entry_id
        if request.media_player:
            service_data["media_player"] = request.media_player

        self._create_background_task(
            self._async_process_stremio_playback(
                user_input=user_input,
                service_data=service_data,
            ),
            "Stremio playback",
        )
        self._clear_stremio_pending(user_input)

        title = selected_title(selected)
        target = self._stremio_target_text(request)
        template = str(
            settings.get(CONF_STREMIO_PLAY_ACK, DEFAULT_STREMIO_PLAY_ACK)
        ).strip()
        try:
            message = template.format(title=title, target=target)
        except (KeyError, ValueError):
            _LOGGER.warning(
                "Invalid Stremio acknowledgement template %r; using default",
                template,
            )
            message = DEFAULT_STREMIO_PLAY_ACK.format(title=title, target=target)

        return self._stremio_reply(
            user_input=user_input,
            settings=settings,
            message=message,
            status="preparing",
            selected=selected,
            conversation_id=None,
            continue_conversation=False,
        )

    async def _async_process_stremio_playback(
        self,
        *,
        user_input: conversation.ConversationInput,
        service_data: dict[str, Any],
    ) -> None:
        """Call Stream Bridge without keeping the Assist pipeline open."""
        try:
            await self._async_call_service(
                domain=STREMIO_DOMAIN,
                service=STREMIO_PLAY_SERVICE,
                service_data=service_data,
                user_input=user_input,
                blocking=True,
            )
            _LOGGER.info(
                "Started Stremio playback for %s on %s",
                service_data.get("media_id"),
                service_data.get("media_player", "the configured default player"),
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - background errors must not leak into Assist.
            _LOGGER.exception("Stremio playback failed")

    def _stremio_reply(
        self,
        *,
        user_input: conversation.ConversationInput,
        settings: dict[str, Any],
        message: str,
        status: str,
        conversation_id: str | None,
        continue_conversation: bool,
        selected: dict[str, Any] | None = None,
        results: list[dict[str, Any]] | None = None,
    ) -> conversation.ConversationResult:
        """Create a Stremio speech response plus structured View Assist state."""
        if settings.get(CONF_VIEW_ASSIST_ENABLED, DEFAULT_VIEW_ASSIST_ENABLED):
            related_path = None
            if settings.get(CONF_STREMIO_VIEW_ENABLED, DEFAULT_STREMIO_VIEW_ENABLED):
                related_path = str(
                    settings.get(CONF_STREMIO_VIEW_PATH, DEFAULT_STREMIO_VIEW_PATH)
                ).strip()
            image = None
            if selected:
                image = selected.get("poster") or selected.get("background")
            elif results:
                first = results[0] if results else None
                if first:
                    image = first.get("poster") or first.get("background")
            state: dict[str, Any] = {
                "title": "Stremio",
                "message": message,
                "message_font_size": self._message_font_size(message),
                "stremio_status": status,
                "stremio_selected": selected or {},
                "stremio_results": results or [],
            }
            if image:
                state["image"] = image
            self._schedule_view_assist_sequence(
                user_input=user_input,
                settings=settings,
                response_text=message,
                related_path=related_path,
                category=f"stremio_{status}",
                related_state=state,
                follow_up_enabled_override=continue_conversation,
            )

        return self._speech_result(
            user_input,
            message,
            conversation_id=conversation_id,
            continue_conversation=continue_conversation,
        )

    def _parse_stremio_request(
        self, text: str, settings: dict[str, Any]
    ) -> StremioRequest | None:
        """Parse a request using configured TV aliases and default player."""
        aliases = parse_tv_aliases(
            str(settings.get(CONF_STREMIO_TV_ALIASES, DEFAULT_STREMIO_TV_ALIASES))
        )
        default_player = str(
            settings.get(
                CONF_STREMIO_DEFAULT_PLAYER,
                DEFAULT_STREMIO_DEFAULT_PLAYER,
            )
            or ""
        ).strip()
        return parse_stremio_request(
            text,
            aliases=aliases,
            default_player=default_player or None,
        )

    async def _async_call_service_with_response(
        self,
        *,
        domain: str,
        service: str,
        service_data: dict[str, Any],
        user_input: conversation.ConversationInput,
    ) -> dict[str, Any] | None:
        """Call a response-only service on supported Home Assistant versions."""
        supported = inspect.signature(self.hass.services.async_call).parameters
        if "return_response" not in supported:
            raise RuntimeError(
                "This Home Assistant version cannot request service response data"
            )
        call_kwargs: dict[str, Any] = {
            "domain": domain,
            "service": service,
            "service_data": service_data,
            "blocking": True,
            "context": user_input.context,
            "return_response": True,
        }
        response = await self.hass.services.async_call(
            **{
                key: value
                for key, value in call_kwargs.items()
                if key in supported
            }
        )
        if isinstance(response, dict):
            nested = response.get("service_response")
            if isinstance(nested, dict):
                return nested
            return response
        return None

    async def _async_call_service(
        self,
        *,
        domain: str,
        service: str,
        service_data: dict[str, Any],
        user_input: conversation.ConversationInput,
        blocking: bool,
    ) -> Any:
        """Call a regular Home Assistant service across API versions."""
        call_kwargs: dict[str, Any] = {
            "domain": domain,
            "service": service,
            "service_data": service_data,
            "blocking": blocking,
            "context": user_input.context,
        }
        supported = inspect.signature(self.hass.services.async_call).parameters
        return await self.hass.services.async_call(
            **{
                key: value
                for key, value in call_kwargs.items()
                if key in supported
            }
        )

    def _set_stremio_pending(
        self,
        *,
        user_input: conversation.ConversationInput,
        base_conversation_id: str,
        pending: PendingStremioRequest,
    ) -> None:
        """Store pending state under the conversation and device fallback keys."""
        self._clear_stremio_pending(user_input)
        keys = [
            *self._stremio_context_keys(user_input, base_conversation_id),
            *self._stremio_fallback_keys(user_input),
        ]
        for key in dict.fromkeys(keys):
            self._stremio_pending[key] = pending

    def _get_stremio_pending(
        self, user_input: conversation.ConversationInput
    ) -> PendingStremioRequest | None:
        """Return a non-expired pending dialogue for this conversation/device."""
        now = time.monotonic()
        for key in self._stremio_context_keys(user_input):
            pending = self._stremio_pending.get(key)
            if pending is None:
                continue
            if pending.expires_at <= now:
                self._clear_stremio_pending_object(pending)
                return None
            return pending
        return None

    def _clear_stremio_pending(
        self, user_input: conversation.ConversationInput
    ) -> None:
        """Clear every alias of this conversation's pending dialogue."""
        pending_ids = {
            id(pending)
            for key in self._stremio_context_keys(user_input)
            if (pending := self._stremio_pending.get(key)) is not None
        }
        if not pending_ids:
            return
        for key, pending in list(self._stremio_pending.items()):
            if id(pending) in pending_ids:
                self._stremio_pending.pop(key, None)

    def _clear_stremio_pending_object(self, pending: PendingStremioRequest) -> None:
        """Remove all dictionary keys pointing at one pending object."""
        for key, candidate in list(self._stremio_pending.items()):
            if candidate is pending:
                self._stremio_pending.pop(key, None)

    @staticmethod
    def _stremio_context_keys(
        user_input: conversation.ConversationInput,
        base_conversation_id: str | None = None,
    ) -> list[str]:
        """Use an exact conversation when available, otherwise device fallback."""
        conversation_id = base_conversation_id or user_input.conversation_id
        if conversation_id:
            return [f"conversation:{conversation_id}"]
        return AssistRouterConversationEntity._stremio_fallback_keys(user_input)

    @staticmethod
    def _stremio_fallback_keys(
        user_input: conversation.ConversationInput,
    ) -> list[str]:
        """Return satellite/device keys for pipelines that omit conversation IDs."""
        keys: list[str] = []
        satellite_id = getattr(user_input, "satellite_id", None)
        if satellite_id:
            keys.append(f"satellite:{satellite_id}")
        device_id = getattr(user_input, "device_id", None)
        if device_id:
            keys.append(f"device:{device_id}")
        if not keys:
            keys.append("default")
        return list(dict.fromkeys(keys))

    @staticmethod
    def _stremio_expiration(settings: dict[str, Any]) -> float:
        """Return an expiry timestamp for short-lived follow-up state."""
        timeout = max(
            30,
            min(
                int(
                    settings.get(
                        CONF_STREMIO_PENDING_TIMEOUT,
                        DEFAULT_STREMIO_PENDING_TIMEOUT,
                    )
                ),
                600,
            ),
        )
        return time.monotonic() + timeout

    @staticmethod
    def _stremio_target_text(request: StremioRequest) -> str:
        """Return a natural target phrase for the spoken acknowledgement."""
        label = (request.target_label or "").strip()
        if not label or label == "tele":
            return "la tele"
        masculine = {"living", "dormitorio", "quincho", "patio", "comedor"}
        feminine = {"pieza", "sala", "cocina", "habitación", "habitacion"}
        if label in masculine:
            return f"la tele del {label}"
        if label in feminine:
            return f"la tele de la {label}"
        return f"la tele de {label}"

    @staticmethod
    def _as_int(value: Any) -> int | None:
        """Coerce service response values without raising."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _validate_target_agent(
        self,
        user_input: conversation.ConversationInput,
        target_agent_id: str | None,
    ) -> conversation.ConversationResult | None:
        """Return an error result when a configured destination is unusable."""
        if not target_agent_id:
            return self._error_result(
                user_input,
                "No hay un agente configurado para este destino.",
            )
        if target_agent_id in {self.entry.entry_id, self.entity_id}:
            return self._error_result(
                user_input,
                "Assist Router no puede enviarse una consulta a sí mismo.",
            )
        if async_get_agent(self.hass, target_agent_id) is None:
            return self._error_result(
                user_input,
                f"El agente de destino '{target_agent_id}' no está disponible.",
            )
        return None

    def _handoff_to_openclaw(
        self,
        *,
        user_input: conversation.ConversationInput,
        settings: dict[str, Any],
        base_conversation_id: str,
        acknowledgement: str,
    ) -> conversation.ConversationResult:
        """Start OpenClaw in the background and immediately close voice Assist."""
        target_agent_id = settings.get(CONF_OPENCLAW_AGENT)
        if error := self._validate_target_agent(user_input, target_agent_id):
            return error

        instruction = str(
            settings.get(
                CONF_OPENCLAW_BACKGROUND_INSTRUCTION,
                DEFAULT_OPENCLAW_BACKGROUND_INSTRUCTION,
            )
        ).strip()
        openclaw_text = user_input.text
        if instruction:
            openclaw_text = f"{openclaw_text}\n\n{instruction}"

        self._create_background_task(
            self._async_process_openclaw_background(
                user_input=user_input,
                text=openclaw_text,
                target_agent_id=target_agent_id,
                conversation_id=f"{base_conversation_id}:{ROUTE_OPENCLAW}",
            ),
            "OpenClaw request",
        )

        openclaw_view_path = str(
            settings.get(
                CONF_OPENCLAW_VIEW_PATH_V2,
                DEFAULT_OPENCLAW_VIEW_PATH,
            )
        ).strip()
        if settings.get(CONF_VIEW_ASSIST_ENABLED, DEFAULT_VIEW_ASSIST_ENABLED):
            related_path = (
                openclaw_view_path
                if settings.get(
                    CONF_OPENCLAW_VIEW_ENABLED,
                    DEFAULT_OPENCLAW_VIEW_ENABLED,
                )
                and openclaw_view_path
                else None
            )
            self._schedule_view_assist_sequence(
                user_input=user_input,
                settings=settings,
                response_text=acknowledgement or DEFAULT_OPENCLAW_ACK_MESSAGE,
                related_path=related_path,
                category="openclaw",
            )

        return self._speech_result(
            user_input,
            acknowledgement or DEFAULT_OPENCLAW_ACK_MESSAGE,
            conversation_id=None,
            continue_conversation=False,
        )

    def _schedule_result_view(
        self,
        *,
        user_input: conversation.ConversationInput,
        settings: dict[str, Any],
        result: conversation.ConversationResult,
    ) -> None:
        """Show a normal agent answer and then its matching View Assist view."""
        if not settings.get(CONF_VIEW_ASSIST_ENABLED, DEFAULT_VIEW_ASSIST_ENABLED):
            return
        response_text = self._extract_response_text(result)
        view_match = match_view(response_text, user_input.text, settings)
        self._schedule_view_assist_sequence(
            user_input=user_input,
            settings=settings,
            response_text=response_text,
            related_path=view_match.path if view_match is not None else None,
            category=view_match.slug if view_match is not None else "response_only",
        )
        if view_match is not None:
            _LOGGER.debug(
                "Matched View Assist category %s: response hits=%s, "
                "request hits=%s, configured path=%s",
                view_match.slug,
                view_match.response_hits,
                view_match.request_hits,
                view_match.path,
            )

    @staticmethod
    def _is_openclaw_marker(response_text: str) -> bool:
        """Recognize only the private marker emitted by the general agent."""
        return OPENCLAW_ROUTE_MARKER.casefold() in response_text.casefold()

    @staticmethod
    def _general_router_prompt(settings: dict[str, Any]) -> str:
        """Build a fixed routing protocol plus the user's editable policy."""
        policy = str(
            settings.get(
                CONF_GENERAL_ROUTER_INSTRUCTION,
                DEFAULT_GENERAL_ROUTER_INSTRUCTION,
            )
        ).strip()
        return (
            "Sos el agente general rápido de un router de voz. "
            "Tenés dos comportamientos posibles. "
            "Si podés contestar la consulta directamente, respondela normalmente "
            "en el idioma del usuario y no menciones este protocolo. "
            "Si la consulta necesita OpenClaw, respondé únicamente con esta marca "
            f"exacta y sin ningún otro texto: {OPENCLAW_ROUTE_MARKER}\n\n"
            "Criterios configurados por el usuario:\n"
            f"{policy}"
        )

    def _create_background_task(self, coroutine: Any, task_label: str) -> None:
        """Schedule a background task without blocking the Assist pipeline."""
        name = f"Assist Router {task_label} {self.entry.entry_id}"
        entry_create_background_task = getattr(
            self.entry, "async_create_background_task", None
        )
        if entry_create_background_task is not None:
            entry_create_background_task(self.hass, coroutine, name)
            return

        create_background_task = getattr(
            self.hass, "async_create_background_task", None
        )
        if create_background_task is not None:
            create_background_task(coroutine, name)
            return

        self.hass.async_create_task(coroutine, name)

    def _schedule_view_assist_sequence(
        self,
        *,
        user_input: conversation.ConversationInput,
        settings: dict[str, Any],
        response_text: str,
        related_path: str | None,
        category: str,
        related_state: dict[str, Any] | None = None,
        follow_up_enabled_override: bool | None = None,
    ) -> None:
        """Show the written reply, then open the related View Assist view."""
        if not settings.get(
            CONF_VIEW_ASSIST_ENABLED,
            DEFAULT_VIEW_ASSIST_ENABLED,
        ):
            return

        response_enabled = bool(
            settings.get(
                CONF_RESPONSE_VIEW_ENABLED,
                DEFAULT_RESPONSE_VIEW_ENABLED,
            )
        )
        clean_response = response_text.strip()
        clean_related_path = related_path.strip() if related_path else None
        if not (response_enabled and clean_response) and not clean_related_path:
            return

        configured_entity = settings.get(
            CONF_VIEW_ASSIST_ENTITY,
            DEFAULT_VIEW_ASSIST_ENTITY,
        )
        sequence_key, sequence_generation = self._begin_view_sequence(
            user_input, configured_entity
        )

        self._create_background_task(
            self._async_show_response_then_view(
                user_input=user_input,
                configured_entity=configured_entity,
                sequence_key=sequence_key,
                sequence_generation=sequence_generation,
                response_enabled=response_enabled,
                response_path=str(
                    settings.get(
                        CONF_RESPONSE_VIEW_PATH,
                        DEFAULT_RESPONSE_VIEW_PATH,
                    )
                ).strip(),
                response_text=clean_response,
                response_display_min_time=settings.get(
                    CONF_RESPONSE_DISPLAY_MIN_TIME,
                    settings.get(
                        CONF_RESPONSE_DISPLAY_TIME,
                        DEFAULT_RESPONSE_DISPLAY_MIN_TIME,
                    ),
                ),
                response_seconds_per_word=settings.get(
                    CONF_RESPONSE_SECONDS_PER_WORD,
                    DEFAULT_RESPONSE_SECONDS_PER_WORD,
                ),
                response_display_max_time=settings.get(
                    CONF_RESPONSE_DISPLAY_MAX_TIME,
                    DEFAULT_RESPONSE_DISPLAY_MAX_TIME,
                ),
                related_path=clean_related_path,
                related_display_time=settings.get(
                    CONF_RELATED_VIEW_DISPLAY_TIME,
                    DEFAULT_RELATED_VIEW_DISPLAY_TIME,
                ),
                navigation_delay=settings.get(
                    CONF_VIEW_NAVIGATION_DELAY,
                    DEFAULT_VIEW_NAVIGATION_DELAY,
                ),
                follow_up_enabled=(
                    bool(settings.get(CONF_FOLLOW_UP_ENABLED, DEFAULT_FOLLOW_UP_ENABLED))
                    if follow_up_enabled_override is None
                    else follow_up_enabled_override
                ),
                related_state=related_state,
            ),
            f"View Assist response sequence ({category})",
        )

    async def _async_show_response_then_view(
        self,
        *,
        user_input: conversation.ConversationInput,
        configured_entity: str,
        sequence_key: str,
        sequence_generation: int,
        response_enabled: bool,
        response_path: str,
        response_text: str,
        response_display_min_time: float,
        response_seconds_per_word: float,
        response_display_max_time: float,
        related_path: str | None,
        related_display_time: int,
        navigation_delay: float,
        follow_up_enabled: bool,
        related_state: dict[str, Any] | None,
    ) -> None:
        """Display a written response and then a category-specific view."""
        try:
            delay = max(0.0, min(float(navigation_delay), 10.0))
            if delay:
                await asyncio.sleep(delay)
            if not self._view_sequence_is_current(
                sequence_key, sequence_generation
            ):
                return

            if not self.hass.services.has_service("view_assist", "navigate"):
                _LOGGER.warning(
                    "View Assist response sequence skipped: service "
                    "view_assist.navigate is not available"
                )
                return

            entity_id = self._resolve_view_assist_entity(
                user_input,
                configured_entity,
            )
            if entity_id is None:
                _LOGGER.warning(
                    "View Assist response sequence skipped: no satellite matched "
                    "the conversation device"
                )
                return

            entity_state = self.hass.states.get(entity_id)
            shown_response = False
            response_seconds = calculate_response_display_time(
                response_text,
                response_display_min_time,
                response_seconds_per_word,
                response_display_max_time,
            )
            related_seconds = max(0, min(int(related_display_time), 120))

            if response_enabled and response_text and response_path:
                resolved_response_path = resolve_view_path(
                    response_path, entity_state
                )
                if resolved_response_path:
                    await self._async_call_view_assist_service(
                        "navigate",
                        {
                            "device": entity_id,
                            "path": resolved_response_path,
                            "revert_timeout": 0,
                        },
                        user_input,
                    )
                    if self.hass.services.has_service(
                        "view_assist", "set_state"
                    ):
                        await self._async_call_view_assist_service(
                            "set_state",
                            {
                                "entity_id": entity_id,
                                "title": "Respuesta",
                                "message": response_text,
                                "message_font_size": self._message_font_size(
                                    response_text
                                ),
                            },
                            user_input,
                        )
                        shown_response = True
                        _LOGGER.info(
                            "Showing written response on %s at %s for %.1fs (%s words)",
                            entity_id,
                            resolved_response_path,
                            response_seconds,
                            len(response_text.split()),
                        )
                    else:
                        _LOGGER.warning(
                            "View Assist written response skipped: service "
                            "view_assist.set_state is not available"
                        )

            if shown_response and response_seconds:
                await asyncio.sleep(response_seconds)
                if not self._view_sequence_is_current(
                    sequence_key, sequence_generation
                ):
                    return

            if shown_response and self.hass.services.has_service(
                "view_assist", "set_state"
            ):
                await self._async_call_view_assist_service(
                    "set_state",
                    {
                        "entity_id": entity_id,
                        "title": "",
                        "message": "",
                        "message_font_size": "",
                    },
                    user_input,
                )

            if related_path:
                if related_state and self.hass.services.has_service(
                    "view_assist", "set_state"
                ):
                    await self._async_call_view_assist_service(
                        "set_state",
                        {"entity_id": entity_id, **related_state},
                        user_input,
                    )
                resolved_related_path = resolve_view_path(
                    related_path, entity_state
                )
                if resolved_related_path:
                    await self._async_call_view_assist_service(
                        "navigate",
                        {
                            "device": entity_id,
                            "path": resolved_related_path,
                            "revert_timeout": 0,
                        },
                        user_input,
                    )
                    _LOGGER.info(
                        "Showing related View Assist view on %s at %s for %ss",
                        entity_id,
                        resolved_related_path,
                        related_seconds,
                    )
                    if related_seconds == 0:
                        return
                    await asyncio.sleep(related_seconds)
                    if follow_up_enabled:
                        await self._async_wait_for_follow_up_turn(
                            entity_id, sequence_key, sequence_generation
                        )
                    if not self._view_sequence_is_current(
                        sequence_key, sequence_generation
                    ):
                        _LOGGER.debug(
                            "Keeping the newer View Assist sequence active on %s",
                            entity_id,
                        )
                        return
                    await self._async_call_view_assist_service(
                        "navigate",
                        {
                            "device": entity_id,
                            "path": "home",
                            "revert_timeout": 0,
                        },
                        user_input,
                    )
                    _LOGGER.info(
                        "Returned View Assist entity %s to home after follow-up window",
                        entity_id,
                    )
                    return

            if shown_response and self._view_sequence_is_current(
                sequence_key, sequence_generation
            ):
                await self._async_call_view_assist_service(
                    "navigate",
                    {
                        "device": entity_id,
                        "path": "home",
                        "revert_timeout": 0,
                    },
                    user_input,
                )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - visual feedback must not break TTS.
            _LOGGER.exception("View Assist response sequence failed")

    async def _async_wait_for_follow_up_turn(
        self,
        view_assist_entity: str,
        sequence_key: str,
        sequence_generation: int,
    ) -> None:
        """Keep the related view visible while the user is answering."""
        elapsed = 0.0
        while (
            elapsed < 15.0
            and self._view_sequence_is_current(
                sequence_key, sequence_generation
            )
            and self._view_assist_pipeline_is_active(view_assist_entity)
        ):
            await asyncio.sleep(0.25)
            elapsed += 0.25

    def _view_assist_pipeline_is_active(self, entity_id: str) -> bool:
        """Return whether the linked microphone is listening or processing."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return False
        mic_entity_id = state.attributes.get("mic_device")
        if not mic_entity_id:
            return False
        mic_state = self.hass.states.get(str(mic_entity_id))
        if mic_state is None:
            return False
        active_states = {
            "listening",
            "processing",
            "responding",
            "intent-processing",
            "stt",
            "stt-listening",
            "sst-listening",
            "vad",
            "start",
        }
        return str(mic_state.state).casefold() in active_states

    def _view_sequence_key(
        self,
        user_input: conversation.ConversationInput,
        configured_entity: str | None,
    ) -> str:
        """Return a stable key for one satellite's visual sequence."""
        if configured_entity and configured_entity != VIEW_ASSIST_AUTO_ENTITY:
            return f"entity:{configured_entity}"
        satellite_id = getattr(user_input, "satellite_id", None)
        if satellite_id:
            return f"satellite:{satellite_id}"
        device_id = getattr(user_input, "device_id", None)
        if device_id:
            return f"device:{device_id}"
        return "default"

    def _invalidate_view_sequence(
        self,
        user_input: conversation.ConversationInput,
        configured_entity: str | None,
    ) -> None:
        """Prevent an older sequence from returning the display to home."""
        key = self._view_sequence_key(user_input, configured_entity)
        self._view_sequence_generation[key] = (
            self._view_sequence_generation.get(key, 0) + 1
        )

    def _begin_view_sequence(
        self,
        user_input: conversation.ConversationInput,
        configured_entity: str | None,
    ) -> tuple[str, int]:
        """Start and identify the newest visual sequence for a satellite."""
        key = self._view_sequence_key(user_input, configured_entity)
        generation = self._view_sequence_generation.get(key, 0) + 1
        self._view_sequence_generation[key] = generation
        return key, generation

    def _view_sequence_is_current(self, key: str, generation: int) -> bool:
        """Return whether a delayed visual action still belongs to the latest turn."""
        return self._view_sequence_generation.get(key) == generation

    async def _async_call_view_assist_service(
        self,
        service: str,
        service_data: dict[str, Any],
        user_input: conversation.ConversationInput,
    ) -> None:
        """Call a View Assist service across Home Assistant API versions."""
        call_kwargs: dict[str, Any] = {
            "domain": "view_assist",
            "service": service,
            "service_data": service_data,
            "blocking": True,
            "context": user_input.context,
        }
        supported = inspect.signature(
            self.hass.services.async_call
        ).parameters
        await self.hass.services.async_call(
            **{
                key: value
                for key, value in call_kwargs.items()
                if key in supported
            }
        )

    @staticmethod
    def _message_font_size(message: str) -> str:
        """Match View Assist's standard text sizing for AI responses."""
        word_count = len(message.split())
        return ["10vw", "8vw", "6vw", "4vw"][min(word_count // 6, 3)]

    def _schedule_view_assist_navigation(
        self,
        *,
        user_input: conversation.ConversationInput,
        settings: dict[str, Any],
        path: str,
        category: str,
    ) -> None:
        """Navigate View Assist without delaying the spoken response."""
        if not settings.get(
            CONF_VIEW_ASSIST_ENABLED,
            DEFAULT_VIEW_ASSIST_ENABLED,
        ):
            return

        self._create_background_task(
            self._async_navigate_view_assist(
                user_input=user_input,
                configured_entity=settings.get(
                    CONF_VIEW_ASSIST_ENTITY,
                    DEFAULT_VIEW_ASSIST_ENTITY,
                ),
                path=path,
                revert_timeout=settings.get(
                    CONF_VIEW_REVERT_TIMEOUT,
                    DEFAULT_VIEW_REVERT_TIMEOUT,
                ),
                navigation_delay=settings.get(
                    CONF_VIEW_NAVIGATION_DELAY,
                    DEFAULT_VIEW_NAVIGATION_DELAY,
                ),
            ),
            f"View Assist navigation ({category})",
        )

    async def _async_navigate_view_assist(
        self,
        *,
        user_input: conversation.ConversationInput,
        configured_entity: str,
        path: str,
        revert_timeout: int,
        navigation_delay: float,
    ) -> None:
        """Navigate the View Assist satellite that originated the request."""
        try:
            delay = max(0.0, min(float(navigation_delay), 10.0))
            if delay:
                await asyncio.sleep(delay)
            if not self.hass.services.has_service("view_assist", "navigate"):
                _LOGGER.warning(
                    "View Assist navigation skipped: service view_assist.navigate "
                    "is not available"
                )
                return

            entity_id = self._resolve_view_assist_entity(
                user_input,
                configured_entity,
            )
            if entity_id is None:
                _LOGGER.warning(
                    "View Assist navigation skipped: no satellite matched the "
                    "conversation device. Select a fallback satellite in Assist "
                    "Router options if automatic detection is unavailable."
                )
                return

            entity_state = self.hass.states.get(entity_id)
            resolved_path = resolve_view_path(path, entity_state)
            if not resolved_path:
                _LOGGER.warning(
                    "View Assist navigation skipped: empty path for category request"
                )
                return

            service_data: dict[str, Any] = {
                "device": entity_id,
                "path": resolved_path,
                "revert_timeout": int(revert_timeout),
            }
            call_kwargs: dict[str, Any] = {
                "domain": "view_assist",
                "service": "navigate",
                "service_data": service_data,
                "blocking": True,
                "context": user_input.context,
            }
            supported = inspect.signature(
                self.hass.services.async_call
            ).parameters
            await self.hass.services.async_call(
                **{
                    key: value
                    for key, value in call_kwargs.items()
                    if key in supported
                }
            )
            _LOGGER.info(
                "Navigated View Assist entity %s to %s (configured as %s)",
                entity_id,
                resolved_path,
                path,
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - visual feedback must not break TTS.
            _LOGGER.exception(
                "View Assist navigation failed for configured path %s", path
            )

    def _resolve_view_assist_entity(
        self,
        user_input: conversation.ConversationInput,
        configured_entity: str,
    ) -> str | None:
        """Resolve the View Assist sensor associated with the voice device."""
        if configured_entity and configured_entity != VIEW_ASSIST_AUTO_ENTITY:
            if self.hass.states.get(configured_entity) is not None:
                return configured_entity
            _LOGGER.warning(
                "Configured View Assist entity %s is unavailable",
                configured_entity,
            )
            return None

        registry = er.async_get(self.hass)
        raw_device_id = getattr(user_input, "device_id", None)
        satellite_id = getattr(user_input, "satellite_id", None)
        candidate_device_ids: set[str] = set()
        candidate_entity_ids: set[str] = set()

        for candidate in (raw_device_id, satellite_id):
            if not candidate:
                continue
            registry_entry = registry.async_get(candidate)
            if registry_entry is not None:
                candidate_entity_ids.add(registry_entry.entity_id)
                if registry_entry.device_id:
                    candidate_device_ids.add(registry_entry.device_id)
            elif str(candidate).startswith(("sensor.", "assist_satellite.")):
                candidate_entity_ids.add(str(candidate))
            else:
                candidate_device_ids.add(str(candidate))

        # Prefer View Assist's own resolver when its integration is installed.
        # This keeps Assist Router aligned with changes in View Assist internals.
        try:
            helpers = import_module("custom_components.view_assist.helpers")
            resolver = getattr(
                helpers,
                "get_entity_id_from_conversation_device_id",
                None,
            )
            if callable(resolver):
                for device_id in candidate_device_ids:
                    resolved = resolver(self.hass, device_id)
                    if resolved and self.hass.states.get(resolved) is not None:
                        _LOGGER.debug(
                            "View Assist official resolver matched %s to %s",
                            device_id,
                            resolved,
                        )
                        return resolved
        except (ImportError, AttributeError, KeyError, TypeError):
            _LOGGER.debug(
                "View Assist official resolver unavailable; using local fallback",
                exc_info=True,
            )

        view_assist_sensors: list[str] = []
        for entry in self.hass.config_entries.async_entries("view_assist"):
            sensor_entity_id = None
            for entity_entry in er.async_entries_for_config_entry(
                registry, entry.entry_id
            ):
                if entity_entry.domain == "sensor":
                    sensor_entity_id = entity_entry.entity_id
                    view_assist_sensors.append(sensor_entity_id)
                    break

            if sensor_entity_id is None:
                continue
            if sensor_entity_id in candidate_entity_ids:
                return sensor_entity_id

            sensor_state = self.hass.states.get(sensor_entity_id)
            attributes = sensor_state.attributes if sensor_state is not None else {}
            for attribute_name in ("mic_device_id", "voice_device_id"):
                attribute_value = attributes.get(attribute_name)
                if attribute_value and str(attribute_value) in candidate_device_ids:
                    return sensor_entity_id

            mic_entity_id = attributes.get("mic_device") or entry.data.get("mic_device")
            runtime_data = getattr(entry, "runtime_data", None)
            core_data = getattr(runtime_data, "core", None)
            mic_entity_id = getattr(core_data, "mic_device", None) or mic_entity_id

            if mic_entity_id:
                mic_entity = registry.async_get(mic_entity_id)
                if mic_entity is not None:
                    if mic_entity.entity_id in candidate_entity_ids:
                        return sensor_entity_id
                    if (
                        mic_entity.device_id
                        and mic_entity.device_id in candidate_device_ids
                    ):
                        return sensor_entity_id

        # A single-satellite setup is unambiguous even when a browser microphone
        # does not propagate device_id through the conversation pipeline.
        unique_sensors = list(dict.fromkeys(view_assist_sensors))
        if len(unique_sensors) == 1:
            return unique_sensors[0]

        _LOGGER.warning(
            "Could not select a View Assist satellite automatically. "
            "conversation device_id=%s satellite_id=%s candidate devices=%s "
            "candidate entities=%s available View Assist sensors=%s",
            raw_device_id,
            satellite_id,
            sorted(candidate_device_ids),
            sorted(candidate_entity_ids),
            unique_sensors,
        )
        return None

    async def _async_process_openclaw_background(
        self,
        *,
        user_input: conversation.ConversationInput,
        text: str,
        target_agent_id: str,
        conversation_id: str,
    ) -> None:
        """Send a request to OpenClaw and deliberately discard its HA reply."""
        try:
            await self._async_converse(
                user_input=user_input,
                text=text,
                target_agent_id=target_agent_id,
                conversation_id=conversation_id,
            )
            _LOGGER.debug("OpenClaw background request completed")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - background jobs must never leak errors.
            _LOGGER.exception("OpenClaw background request failed")

    async def _async_converse(
        self,
        *,
        user_input: conversation.ConversationInput,
        text: str,
        target_agent_id: str,
        conversation_id: str,
        extra_system_prompt: str | None = None,
    ) -> conversation.ConversationResult:
        """Call a destination agent using parameters supported by this HA version."""
        supported = inspect.signature(conversation.async_converse).parameters
        merged_prompt = self._merge_system_prompts(
            getattr(user_input, "extra_system_prompt", None),
            extra_system_prompt,
        )
        effective_text = text
        if merged_prompt and "extra_system_prompt" not in supported:
            # Older Home Assistant releases do not expose extra_system_prompt.
            # Keep the classifier functional by placing the internal policy
            # before the user request instead of silently dropping it.
            effective_text = (
                f"INSTRUCCIONES INTERNAS DEL ROUTER:\n{merged_prompt}"
                f"\n\nSOLICITUD DEL USUARIO:\n{text}"
            )

        converse_kwargs = {
            "hass": self.hass,
            "text": effective_text,
            "conversation_id": conversation_id,
            "context": user_input.context,
            "language": user_input.language,
            "agent_id": target_agent_id,
            "device_id": getattr(user_input, "device_id", None),
            "satellite_id": getattr(user_input, "satellite_id", None),
            "extra_system_prompt": merged_prompt,
        }

        return await conversation.async_converse(
            **{
                key: value
                for key, value in converse_kwargs.items()
                if key in supported
            }
        )

    @staticmethod
    def _merge_system_prompts(
        original: str | None, additional: str | None
    ) -> str | None:
        """Combine an existing pipeline prompt with router instructions."""
        prompts = [
            prompt.strip()
            for prompt in (original, additional)
            if prompt and prompt.strip()
        ]
        return "\n\n".join(prompts) or None

    @staticmethod
    def _extract_response_text(result: conversation.ConversationResult) -> str:
        """Extract the final plain speech from old and new IntentResponse shapes."""
        response = result.response
        as_dict = getattr(response, "as_dict", None)
        if callable(as_dict):
            try:
                response_data = as_dict()
                text = AssistRouterConversationEntity._find_speech_text(
                    response_data.get("speech")
                    if isinstance(response_data, dict)
                    else response_data
                )
                if text:
                    return text
            except (AttributeError, TypeError, ValueError):
                pass

        return AssistRouterConversationEntity._find_speech_text(
            getattr(response, "speech", None)
        )

    @staticmethod
    def _find_speech_text(value: Any) -> str:
        """Recursively find a speech string in an IntentResponse structure."""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            preferred_keys = ("plain", "speech", "text", "ssml")
            for preferred_key in preferred_keys:
                for key, nested in value.items():
                    key_value = getattr(key, "value", key)
                    if str(key_value).casefold() == preferred_key:
                        text = AssistRouterConversationEntity._find_speech_text(nested)
                        if text:
                            return text
            for nested in value.values():
                text = AssistRouterConversationEntity._find_speech_text(nested)
                if text:
                    return text
        if isinstance(value, (list, tuple)):
            for nested in value:
                text = AssistRouterConversationEntity._find_speech_text(nested)
                if text:
                    return text
        return ""

    @staticmethod
    def _wrap_downstream_result(
        result: conversation.ConversationResult,
        base_conversation_id: str,
        *,
        continue_conversation: bool | None = None,
    ) -> conversation.ConversationResult:
        """Return a destination response while preserving the router session ID."""
        result_kwargs: dict[str, Any] = {
            "response": result.response,
            "conversation_id": base_conversation_id,
        }
        result_signature = inspect.signature(
            conversation.ConversationResult
        ).parameters
        if "continue_conversation" in result_signature:
            result_kwargs["continue_conversation"] = (
                getattr(result, "continue_conversation", False)
                if continue_conversation is None
                else continue_conversation
            )

        return conversation.ConversationResult(**result_kwargs)

    @staticmethod
    def _speech_result(
        user_input: conversation.ConversationInput,
        message: str,
        *,
        conversation_id: str | None,
        continue_conversation: bool = False,
    ) -> conversation.ConversationResult:
        """Create an immediate voice response with an explicit session state."""
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(message)
        result_kwargs: dict[str, Any] = {
            "response": response,
            "conversation_id": conversation_id,
        }
        result_signature = inspect.signature(
            conversation.ConversationResult
        ).parameters
        if "continue_conversation" in result_signature:
            result_kwargs["continue_conversation"] = continue_conversation
        return conversation.ConversationResult(**result_kwargs)

    @staticmethod
    def _silent_result(
        user_input: conversation.ConversationInput,
    ) -> conversation.ConversationResult:
        """End an echoed turn without producing another TTS response."""
        response = intent.IntentResponse(language=user_input.language)
        result_kwargs: dict[str, Any] = {
            "response": response,
            "conversation_id": None,
        }
        result_signature = inspect.signature(
            conversation.ConversationResult
        ).parameters
        if "continue_conversation" in result_signature:
            result_kwargs["continue_conversation"] = False
        return conversation.ConversationResult(**result_kwargs)

    @staticmethod
    def _error_result(
        user_input: conversation.ConversationInput, message: str
    ) -> conversation.ConversationResult:
        """Create a voice-friendly error result."""
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, message)
        return conversation.ConversationResult(
            response=response,
            conversation_id=user_input.conversation_id,
        )
