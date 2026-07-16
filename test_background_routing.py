"""Standalone smoke tests for background routing and View Assist navigation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import sys
import types

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Minimal Home Assistant stubs so the integration can be tested without the
# full Home Assistant package.
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
        speech = "La tarea de OpenClaw terminó"
    else:
        speech = "La luz del living quedó encendida"
    response = IntentResponse(language)
    response.async_set_speech(speech)
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
            "view_assist_enabled": True,
            "view_assist_entity": "__auto__",
            "view_rules": (
                "domotica|/view-assist/intent|luz, encendida, apagada\n"
                "clima|/view-assist/weather|clima, lluvia"
            ),
            "view_revert_timeout": 20,
            "view_navigation_delay": 0,
            "openclaw_view_path": "/view-assist/info",
            "end_phrases": "chau\ngracias\nok\nbueno\nhasta luego",
            "end_response": "Hasta luego.",
            "end_view_home": True,
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
        self.speech = {"plain": {"speech": message}}

    def async_set_error(self, code, message):
        self.error = (code, message)
        self.speech = {"plain": {"speech": message}}

    def as_dict(self):
        return {"speech": self.speech}


intent.IntentResponse = IntentResponse
intent.IntentResponseErrorCode = IntentResponseErrorCode

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform
entity_platform.AddEntitiesCallback = object

entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
sys.modules["homeassistant.helpers.entity_registry"] = entity_registry
helpers.entity_registry = entity_registry


@dataclass
class RegistryEntry:
    entity_id: str
    domain: str
    device_id: str | None = None


class FakeRegistry:
    def __init__(self):
        self.entries = {
            "assist_satellite.kitchen": RegistryEntry(
                "assist_satellite.kitchen", "assist_satellite", "device-kitchen"
            ),
            "sensor.viewassist_kitchen": RegistryEntry(
                "sensor.viewassist_kitchen", "sensor", "view-device-kitchen"
            ),
        }

    def async_get(self, entity_id):
        return self.entries.get(entity_id)


REGISTRY = FakeRegistry()
entity_registry.async_get = lambda hass: REGISTRY
entity_registry.async_entries_for_config_entry = lambda registry, entry_id: (
    [REGISTRY.entries["sensor.viewassist_kitchen"]]
    if entry_id == "va-entry"
    else []
)

from custom_components.assist_router.conversation import (  # noqa: E402
    AssistRouterConversationEntity,
)


class FakeVAEntry:
    entry_id = "va-entry"
    data = {"mic_device": "assist_satellite.kitchen"}
    runtime_data = None


class FakeConfigEntries:
    def async_entries(self, domain):
        return [FakeVAEntry()] if domain == "view_assist" else []


class FakeServices:
    def __init__(self):
        self.calls = []

    def has_service(self, domain, service):
        return domain == "view_assist" and service == "navigate"

    async def async_call(
        self,
        domain,
        service,
        service_data=None,
        blocking=False,
        context=None,
    ):
        self.calls.append(
            {
                "domain": domain,
                "service": service,
                "service_data": service_data,
                "blocking": blocking,
            }
        )


class FakeState:
    def __init__(self, attributes=None):
        self.attributes = attributes or {}
        self.name = "View Assist Kitchen"


class FakeStates:
    def get(self, entity_id):
        if entity_id == "sensor.viewassist_kitchen":
            return FakeState({
                "dashboard": "/view-assist",
                "mic_device": "assist_satellite.kitchen",
                "mic_device_id": "device-kitchen",
                "voice_device_id": "device-kitchen",
            })
        return None


class FakeHass:
    def __init__(self):
        self.tasks = []
        self.services = FakeServices()
        self.config_entries = FakeConfigEntries()
        self.states = FakeStates()

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
        ConversationInput(
            text="Revisame los correos",
            device_id="device-kitchen",
        )
    )
    assert router._extract_response_text(openclaw_result) == (
        "Dejame trabajar en eso y te aviso por WhatsApp."
    )
    assert len(hass.tasks) == 2  # OpenClaw plus View Assist navigation.
    assert any(not task.done() for task in hass.tasks)

    await asyncio.gather(*hass.tasks)
    assert CALLS[-1]["agent_id"] == "openclaw"
    assert "enviá el resultado al usuario por WhatsApp" in CALLS[-1]["text"]
    assert hass.services.calls[-1]["service_data"]["path"] == "/view-assist/info"
    assert hass.services.calls[-1]["service_data"]["device"] == (
        "sensor.viewassist_kitchen"
    )

    previous_task_count = len(hass.tasks)
    domotics_result = await router.async_process(
        ConversationInput(
            text="Prendé la luz",
            device_id="device-kitchen",
        )
    )
    assert router._extract_response_text(domotics_result) == (
        "La luz del living quedó encendida"
    )
    assert CALLS[-1]["agent_id"] == "gemini"

    new_tasks = hass.tasks[previous_task_count:]
    await asyncio.gather(*new_tasks)
    assert hass.services.calls[-1]["service_data"]["path"] == (
        "/view-assist/intent"
    )
    assert hass.services.calls[-1]["service_data"]["revert_timeout"] == 20


    previous_call_count = len(CALLS)
    previous_task_count = len(hass.tasks)
    closing_result = await router.async_process(
        ConversationInput(
            text="¡Gracias!",
            conversation_id="conversation-follow-up",
            device_id="device-kitchen",
        )
    )
    assert router._extract_response_text(closing_result) == "Hasta luego."
    assert closing_result.conversation_id is None
    assert closing_result.continue_conversation is False
    assert len(CALLS) == previous_call_count
    closing_tasks = hass.tasks[previous_task_count:]
    await asyncio.gather(*closing_tasks)
    assert hass.services.calls[-1]["service_data"]["path"] == "home"

    print("Background routing and View Assist smoke tests: OK")


asyncio.run(main())
