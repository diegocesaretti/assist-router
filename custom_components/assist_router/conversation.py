"""Conversation platform for Assist Router."""

from __future__ import annotations

import asyncio
import inspect
from importlib import import_module
import logging
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
    CONF_KEYWORDS,
    CONF_OPENCLAW_ACK_MESSAGE,
    CONF_OPENCLAW_AGENT,
    CONF_OPENCLAW_BACKGROUND_INSTRUCTION,
    CONF_GENERAL_ROUTER_INSTRUCTION,
    CONF_FORCE_OPENCLAW_PHRASES,
    CONF_OPENCLAW_VIEW_ENABLED,
    CONF_OPENCLAW_VIEW_PATH_V2,
    CONF_VIEW_ASSIST_ENABLED,
    CONF_VIEW_ASSIST_ENTITY,
    CONF_VIEW_NAVIGATION_DELAY,
    CONF_VIEW_REVERT_TIMEOUT,
    CONF_RESPONSE_VIEW_ENABLED,
    CONF_RESPONSE_VIEW_PATH,
    CONF_RESPONSE_DISPLAY_TIME,
    CONF_RELATED_VIEW_DISPLAY_TIME,
    DEFAULT_END_PHRASES,
    DEFAULT_END_RESPONSE,
    DEFAULT_END_VIEW_HOME,
    DEFAULT_KEYWORDS,
    DEFAULT_GENERAL_ROUTER_INSTRUCTION,
    DEFAULT_FORCE_OPENCLAW_PHRASES,
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
    DEFAULT_RESPONSE_DISPLAY_TIME,
    DEFAULT_RELATED_VIEW_DISPLAY_TIME,
    LEGACY_DEFAULT_KEYWORDS_0_1_3,
    OPENCLAW_ROUTE_MARKER,
    ROUTE_DOMOTICS,
    ROUTE_GENERAL,
    ROUTE_OPENCLAW,
    VIEW_ASSIST_AUTO_ENTITY,
)
from .routing import (
    matches_domotics,
    matches_end_phrase,
    matches_phrase_in_text,
    migrate_default_keywords,
    normalize_phrase,
)
from .view_routing import apply_legacy_view_settings, match_view, resolve_view_path

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Assist Router conversation entity."""
    async_add_entities([AssistRouterConversationEntity(entry)])


class AssistRouterConversationEntity(conversation.ConversationEntity):
    """Route Assist requests to domotics, general, or OpenClaw agents."""

    _attr_has_entity_name = True
    _attr_name = "Router"
    _attr_icon = "mdi:call-split"
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the router."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id

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
        """Route a message to domotics, a fast general agent, or OpenClaw."""
        settings = apply_legacy_view_settings({**self.entry.data, **self.entry.options})
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
            return self._handoff_to_openclaw(
                user_input=user_input,
                settings=settings,
                base_conversation_id=base_conversation_id,
                acknowledgement=acknowledgement,
            )

        if matches_domotics(user_input.text, keyword_text):
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
            return self._wrap_downstream_result(result, base_conversation_id)

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
        return self._wrap_downstream_result(general_result, base_conversation_id)

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

        self._create_background_task(
            self._async_show_response_then_view(
                user_input=user_input,
                configured_entity=settings.get(
                    CONF_VIEW_ASSIST_ENTITY,
                    DEFAULT_VIEW_ASSIST_ENTITY,
                ),
                response_enabled=response_enabled,
                response_path=str(
                    settings.get(
                        CONF_RESPONSE_VIEW_PATH,
                        DEFAULT_RESPONSE_VIEW_PATH,
                    )
                ).strip(),
                response_text=clean_response,
                response_display_time=settings.get(
                    CONF_RESPONSE_DISPLAY_TIME,
                    DEFAULT_RESPONSE_DISPLAY_TIME,
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
            ),
            f"View Assist response sequence ({category})",
        )

    async def _async_show_response_then_view(
        self,
        *,
        user_input: conversation.ConversationInput,
        configured_entity: str,
        response_enabled: bool,
        response_path: str,
        response_text: str,
        response_display_time: float,
        related_path: str | None,
        related_display_time: int,
        navigation_delay: float,
    ) -> None:
        """Display a written response and then a category-specific view."""
        try:
            delay = max(0.0, min(float(navigation_delay), 10.0))
            if delay:
                await asyncio.sleep(delay)

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
            response_seconds = max(0.0, min(float(response_display_time), 30.0))
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
                            "Showing written response on %s at %s for %.1fs",
                            entity_id,
                            resolved_response_path,
                            response_seconds,
                        )
                    else:
                        _LOGGER.warning(
                            "View Assist written response skipped: service "
                            "view_assist.set_state is not available"
                        )

            if shown_response and response_seconds:
                await asyncio.sleep(response_seconds)

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
                resolved_related_path = resolve_view_path(
                    related_path, entity_state
                )
                if resolved_related_path:
                    await self._async_call_view_assist_service(
                        "navigate",
                        {
                            "device": entity_id,
                            "path": resolved_related_path,
                            "revert_timeout": related_seconds,
                        },
                        user_input,
                    )
                    _LOGGER.info(
                        "Showing related View Assist view on %s at %s for %ss",
                        entity_id,
                        resolved_related_path,
                        related_seconds,
                    )
                    return

            if shown_response:
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
            result_kwargs["continue_conversation"] = getattr(
                result, "continue_conversation", False
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
