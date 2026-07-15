"""Standalone smoke test for immediate OpenClaw acknowledgement behavior."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import sys
import types

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Minimal Home Assistant stubs so the integration can be smoke-tested without
# installing the full Home Assistant package.
homeassistant = types.ModuleType("homeassistant")
sys.modules["homeassistant"] = homeassistant

components = types.ModuleType("homeassistant.components")
sys.modules["homeassistant.components"] = components
conversation = types.ModuleType("homeassistant.components.conversation")
sys.modules["homeassistant.components.conversation"] = conversation
components.conversation = conversation


class ConversationEntity:
    async def async_added_to_hass(self):
        return None

    async def async_will_remove_from_hass(self):
        return None


class ConversationEntityFeature:
    CONTROL = 1


@dataclass
class ConversationInput:
    text: str
    conversation_id: str | None = None
    context: object | None = None
    language: str = "es"
    device_id: str | None = None
    satellite_id: str | None = None
    extra_system_prompt: str | None = None


@dataclass
class ConversationResult:
    response: object
    conversation_id: str | None
    continue_conversation: bool = False


conversation.ConversationEntity = ConversationEntity
conversation.ConversationEntityFeature = ConversationEntityFeature
conversation.ConversationInput = ConversationInput
conversation.ConversationResult = ConversationResult
conversation.async_set_agent = lambda *args: None
conversation.async_unset_agent = lambda *args: None

CALLS: list[dict[str, object]] = []


async def async_converse(
    hass,
    text,
    conversation_id,
    context,
    language,
    agent_id,
    device_id=None,
    satellite_id=None,
    extra_system_prompt=None,
):
    CALLS.append(
        {
            "text": text,
            "conversation_id": conversation_id,
            "agent_id": agent_id,
        }
    )
    if agent_id == "openclaw":
        await asyncio.sleep(0.05)
    response = IntentResponse(language)
    response.async_set_speech(f"respuesta de {agent_id}")
    return ConversationResult(response, conversation_id)


conversation.async_converse = async_converse

agent_manager = types.ModuleType(
    "homeassistant.components.conversation.agent_manager"
)
sys.modules[
    "homeassistant.components.conversation.agent_manager"
] = agent_manager
agent_manager.async_get_agent = lambda hass, agent_id: object()

config_entries = types.ModuleType("homeassistant.config_entries")
sys.modules["homeassistant.config_entries"] = config_entries


class ConfigEntry:
    def __init__(self):
        self.entry_id = "router-entry"
        self.data = {
            "domotics_agent": "gemini",
            "openclaw_agent": "openclaw",
            "keywords": "luz\naire",
        }
        self.options = {}


config_entries.ConfigEntry = ConfigEntry

const = types.ModuleType("homeassistant.const")
sys.modules["homeassistant.const"] = const
const.MATCH_ALL = "*"


class Platform:
    CONVERSATION = "conversation"


const.Platform = Platform

core = types.ModuleType("homeassistant.core")
sys.modules["homeassistant.core"] = core
core.HomeAssistant = object

helpers = types.ModuleType("homeassistant.helpers")
sys.modules["homeassistant.helpers"] = helpers
intent = types.ModuleType("homeassistant.helpers.intent")
sys.modules["homeassistant.helpers.intent"] = intent
helpers.intent = intent


class IntentResponseErrorCode:
    UNKNOWN = "unknown"


class IntentResponse:
    def __init__(self, language):
        self.language = language
        self.speech = None
        self.error = None

    def async_set_speech(self, message):
        self.speech = message

    def async_set_error(self, code, message):
        self.error = (code, message)
        self.speech = message


intent.IntentResponse = IntentResponse
intent.IntentResponseErrorCode = IntentResponseErrorCode

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform
entity_platform.AddEntitiesCallback = object

from custom_components.assist_router.conversation import (  # noqa: E402
    AssistRouterConversationEntity,
)


class FakeHass:
    def __init__(self):
        self.tasks = []

    def async_create_background_task(self, coroutine, name):
        task = asyncio.create_task(coroutine, name=name)
        self.tasks.append(task)
        return task

    def async_create_task(self, coroutine, name=None):
        task = asyncio.create_task(coroutine, name=name)
        self.tasks.append(task)
        return task


async def main():
    hass = FakeHass()
    router = AssistRouterConversationEntity(ConfigEntry())
    router.hass = hass
    router.entity_id = "conversation.assist_router"

    openclaw_result = await router.async_process(
        ConversationInput(text="Revisame los correos")
    )
    assert (
        openclaw_result.response.speech
        == "Dejame trabajar en eso y te aviso por WhatsApp."
    )
    assert len(hass.tasks) == 1
    assert not hass.tasks[0].done(), "OpenClaw task should still be running"

    await asyncio.gather(*hass.tasks)
    assert CALLS[-1]["agent_id"] == "openclaw"
    assert "enviá el resultado al usuario por WhatsApp" in CALLS[-1]["text"]

    domotics_result = await router.async_process(
        ConversationInput(text="Prendé la luz")
    )
    assert domotics_result.response.speech == "respuesta de gemini"
    assert CALLS[-1]["agent_id"] == "gemini"

    print("Background routing smoke tests: OK")


asyncio.run(main())
