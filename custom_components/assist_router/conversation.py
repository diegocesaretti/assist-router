"""Conversation platform for Assist Router."""

from __future__ import annotations

import inspect
import logging
from typing import Literal
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
    CONF_OPENCLAW_AGENT,
    DEFAULT_KEYWORDS,
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

        converse_kwargs = {
            "hass": self.hass,
            "text": user_input.text,
            "conversation_id": downstream_conversation_id,
            "context": user_input.context,
            "language": user_input.language,
            "agent_id": target_agent_id,
            "device_id": getattr(user_input, "device_id", None),
            "satellite_id": getattr(user_input, "satellite_id", None),
            "extra_system_prompt": getattr(user_input, "extra_system_prompt", None),
        }

        # Home Assistant added some async_converse parameters over time. Only
        # send arguments supported by the installed Core version.
        supported = inspect.signature(conversation.async_converse).parameters
        result = await conversation.async_converse(
            **{key: value for key, value in converse_kwargs.items() if key in supported}
        )

        result_kwargs = {
            "response": result.response,
            "conversation_id": base_conversation_id,
        }
        result_signature = inspect.signature(conversation.ConversationResult).parameters
        if "continue_conversation" in result_signature:
            result_kwargs["continue_conversation"] = getattr(
                result, "continue_conversation", False
            )

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
