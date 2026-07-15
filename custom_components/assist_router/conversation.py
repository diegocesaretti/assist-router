"""Conversation platform for Assist Router."""

from __future__ import annotations

import asyncio
import inspect
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
    CONF_KEYWORDS,
    CONF_OPENCLAW_ACK_MESSAGE,
    CONF_OPENCLAW_AGENT,
    CONF_OPENCLAW_BACKGROUND_INSTRUCTION,
    CONF_OPENCLAW_VIEW_PATH,
    CONF_VIEW_ASSIST_ENABLED,
    CONF_VIEW_ASSIST_ENTITY,
    CONF_VIEW_REVERT_TIMEOUT,
    CONF_VIEW_RULES,
    DEFAULT_KEYWORDS,
    DEFAULT_OPENCLAW_ACK_MESSAGE,
    DEFAULT_OPENCLAW_BACKGROUND_INSTRUCTION,
    DEFAULT_OPENCLAW_VIEW_PATH,
    DEFAULT_VIEW_ASSIST_ENABLED,
    DEFAULT_VIEW_ASSIST_ENTITY,
    DEFAULT_VIEW_REVERT_TIMEOUT,
    DEFAULT_VIEW_RULES,
    ROUTE_DOMOTICS,
    ROUTE_OPENCLAW,
    VIEW_ASSIST_AUTO_ENTITY,
)
from .routing import matches_domotics
from .view_routing import match_view_rule

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Assist Router conversation entity."""
    async_add_entities([AssistRouterConversationEntity(entry)])


class AssistRouterConversationEntity(conversation.ConversationEntity):
    """Route Assist requests to one of two existing conversation agents."""

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
        """Route a message to Gemini/Home Assistant or OpenClaw."""
        settings = {**self.entry.data, **self.entry.options}
        keyword_text = settings.get(CONF_KEYWORDS, DEFAULT_KEYWORDS)

        if matches_domotics(user_input.text, keyword_text):
            target_agent_id = settings[CONF_DOMOTICS_AGENT]
            route = ROUTE_DOMOTICS
        else:
            target_agent_id = settings[CONF_OPENCLAW_AGENT]
            route = ROUTE_OPENCLAW

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

        base_conversation_id = (
            user_input.conversation_id or f"assist_router_{uuid4().hex}"
        )
        downstream_conversation_id = f"{base_conversation_id}:{route}"

        _LOGGER.debug(
            "Routing Assist text to %s via agent %s",
            route,
            target_agent_id,
        )

        if route == ROUTE_OPENCLAW:
            acknowledgement = settings.get(
                CONF_OPENCLAW_ACK_MESSAGE,
                DEFAULT_OPENCLAW_ACK_MESSAGE,
            ).strip()
            instruction = settings.get(
                CONF_OPENCLAW_BACKGROUND_INSTRUCTION,
                DEFAULT_OPENCLAW_BACKGROUND_INSTRUCTION,
            ).strip()

            openclaw_text = user_input.text
            if instruction:
                openclaw_text = f"{openclaw_text}\n\n{instruction}"

            self._create_background_task(
                self._async_process_openclaw_background(
                    user_input=user_input,
                    text=openclaw_text,
                    target_agent_id=target_agent_id,
                    conversation_id=downstream_conversation_id,
                ),
                "OpenClaw request",
            )

            openclaw_view_path = settings.get(
                CONF_OPENCLAW_VIEW_PATH,
                DEFAULT_OPENCLAW_VIEW_PATH,
            ).strip()
            if openclaw_view_path:
                self._schedule_view_assist_navigation(
                    user_input=user_input,
                    settings=settings,
                    path=openclaw_view_path,
                    category="openclaw",
                )

            return self._speech_result(
                user_input,
                acknowledgement or DEFAULT_OPENCLAW_ACK_MESSAGE,
                conversation_id=base_conversation_id,
            )

        result = await self._async_converse(
            user_input=user_input,
            text=user_input.text,
            target_agent_id=target_agent_id,
            conversation_id=downstream_conversation_id,
        )

        if settings.get(
            CONF_VIEW_ASSIST_ENABLED,
            DEFAULT_VIEW_ASSIST_ENABLED,
        ):
            response_text = self._extract_response_text(result)
            if response_text:
                try:
                    rule = match_view_rule(
                        response_text,
                        settings.get(CONF_VIEW_RULES, DEFAULT_VIEW_RULES),
                    )
                except ValueError:
                    _LOGGER.exception("Invalid View Assist response rules")
                    rule = None

                if rule is not None:
                    self._schedule_view_assist_navigation(
                        user_input=user_input,
                        settings=settings,
                        path=rule.path,
                        category=rule.category,
                    )
                    _LOGGER.debug(
                        "Matched View Assist response category %s for path %s",
                        rule.category,
                        rule.path,
                    )

        return self._wrap_downstream_result(result, base_conversation_id)

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
    ) -> None:
        """Navigate the View Assist satellite that originated the request."""
        try:
            if not self.hass.services.has_service("view_assist", "navigate"):
                _LOGGER.debug(
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

            service_data: dict[str, Any] = {
                "device": entity_id,
                "path": path,
                "revert_timeout": int(revert_timeout),
            }
            call_kwargs: dict[str, Any] = {
                "domain": "view_assist",
                "service": "navigate",
                "service_data": service_data,
                "blocking": False,
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
            _LOGGER.debug(
                "Navigated View Assist entity %s to %s",
                entity_id,
                path,
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - visual feedback must not break TTS.
            _LOGGER.exception("View Assist navigation failed for path %s", path)

    def _resolve_view_assist_entity(
        self,
        user_input: conversation.ConversationInput,
        configured_entity: str,
    ) -> str | None:
        """Resolve the View Assist sensor associated with the voice device."""
        if configured_entity and configured_entity != VIEW_ASSIST_AUTO_ENTITY:
            return configured_entity

        registry = er.async_get(self.hass)
        device_id = getattr(user_input, "device_id", None)

        if not device_id:
            satellite_id = getattr(user_input, "satellite_id", None)
            if satellite_id:
                satellite_entry = registry.async_get(satellite_id)
                if satellite_entry is not None:
                    device_id = satellite_entry.device_id
                elif not satellite_id.startswith(("sensor.", "assist_satellite.")):
                    device_id = satellite_id

        view_assist_sensors: list[str] = []
        for entry in self.hass.config_entries.async_entries("view_assist"):
            sensor_entity_id = None
            for entity_entry in er.async_entries_for_config_entry(
                registry,
                entry.entry_id,
            ):
                if entity_entry.domain == "sensor":
                    sensor_entity_id = entity_entry.entity_id
                    view_assist_sensors.append(entity_entry.entity_id)
                    break

            if not device_id or sensor_entity_id is None:
                continue

            mic_entity_id = entry.data.get("mic_device")
            runtime_data = getattr(entry, "runtime_data", None)
            core_data = getattr(runtime_data, "core", None)
            mic_entity_id = getattr(core_data, "mic_device", None) or mic_entity_id

            if not mic_entity_id:
                continue
            mic_entity = registry.async_get(mic_entity_id)
            if mic_entity is not None and mic_entity.device_id == device_id:
                return sensor_entity_id

        # A single-satellite setup is unambiguous even when the pipeline did not
        # provide a device_id (for example, some browser-based microphones).
        unique_sensors = list(dict.fromkeys(view_assist_sensors))
        if len(unique_sensors) == 1:
            return unique_sensors[0]

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
    ) -> conversation.ConversationResult:
        """Call a destination agent using parameters supported by this HA version."""
        converse_kwargs = {
            "hass": self.hass,
            "text": text,
            "conversation_id": conversation_id,
            "context": user_input.context,
            "language": user_input.language,
            "agent_id": target_agent_id,
            "device_id": getattr(user_input, "device_id", None),
            "satellite_id": getattr(user_input, "satellite_id", None),
            "extra_system_prompt": getattr(
                user_input, "extra_system_prompt", None
            ),
        }

        supported = inspect.signature(conversation.async_converse).parameters
        return await conversation.async_converse(
            **{
                key: value
                for key, value in converse_kwargs.items()
                if key in supported
            }
        )

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
    ) -> conversation.ConversationResult:
        """Create an immediate voice response."""
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(message)
        return conversation.ConversationResult(
            response=response,
            conversation_id=conversation_id,
        )

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
