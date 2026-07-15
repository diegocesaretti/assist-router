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
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DOMOTICS_AGENT,
    CONF_KEYWORDS,
    CONF_OPENCLAW_ACK_MESSAGE,
    CONF_OPENCLAW_AGENT,
    CONF_OPENCLAW_BACKGROUND_INSTRUCTION,
    DEFAULT_KEYWORDS,
    DEFAULT_OPENCLAW_ACK_MESSAGE,
    DEFAULT_OPENCLAW_BACKGROUND_INSTRUCTION,
    ROUTE_DOMOTICS,
    ROUTE_OPENCLAW,
)
from .routing import matches_domotics

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

        # Keep one router-level conversation ID for the voice pipeline, but give
        # each destination a separate history so Gemini and OpenClaw never mix.
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

            # Fire-and-forget: close the voice pipeline immediately while
            # OpenClaw continues working and reports the result through WhatsApp.
            self._create_background_task(
                self._async_process_openclaw_background(
                    user_input=user_input,
                    text=openclaw_text,
                    target_agent_id=target_agent_id,
                    conversation_id=downstream_conversation_id,
                )
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
        return self._wrap_downstream_result(result, base_conversation_id)

    def _create_background_task(self, coroutine: Any) -> None:
        """Schedule a background task without blocking the Assist pipeline."""
        name = f"Assist Router OpenClaw request {self.entry.entry_id}"
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

        # Compatibility fallback for older Home Assistant Core versions.
        self.hass.async_create_task(coroutine, name)

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

        # Home Assistant added some async_converse parameters over time. Only
        # send arguments supported by the installed Core version.
        supported = inspect.signature(conversation.async_converse).parameters
        return await conversation.async_converse(
            **{
                key: value
                for key, value in converse_kwargs.items()
                if key in supported
            }
        )

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
