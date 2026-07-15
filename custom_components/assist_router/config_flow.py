"""Config flow for Assist Router."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.conversation.agent_manager import (
    async_get_agent,
    get_agent_manager,
)
from homeassistant.components.conversation.const import (
    DATA_COMPONENT,
    HOME_ASSISTANT_AGENT,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

try:
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # Compatibility with older Home Assistant releases.
    ConfigFlowResult = dict[str, Any]  # type: ignore[misc,assignment]

from .const import (
    CONF_DOMOTICS_AGENT,
    CONF_KEYWORDS,
    CONF_OPENCLAW_AGENT,
    CONF_OPENCLAW_ACK_MESSAGE,
    CONF_OPENCLAW_BACKGROUND_INSTRUCTION,
    DEFAULT_KEYWORDS,
    DEFAULT_OPENCLAW_ACK_MESSAGE,
    DEFAULT_OPENCLAW_BACKGROUND_INSTRUCTION,
    DOMAIN,
)
from .routing import canonicalize_keywords, parse_keywords


def _agent_options(
    hass: HomeAssistant, forbidden_agent_ids: set[str] | None = None
) -> dict[str, str]:
    """Return loaded conversation agents as a classic dropdown mapping.

    A plain voluptuous dropdown is intentionally used instead of the newer
    ConversationAgentSelector. Some Home Assistant frontend versions do not
    render that selector and show an empty form with only the Submit button.
    """
    forbidden_agent_ids = forbidden_agent_ids or set()
    options: dict[str, str] = {}

    # Built-in Home Assistant agent.
    if (
        HOME_ASSISTANT_AGENT not in forbidden_agent_ids
        and async_get_agent(hass, HOME_ASSISTANT_AGENT) is not None
    ):
        options[HOME_ASSISTANT_AGENT] = "Home Assistant"

    # Legacy/config-entry based agents (used by several LLM integrations).
    try:
        manager = get_agent_manager(hass)
        for info in manager.async_get_agent_info():
            if info.id not in forbidden_agent_ids:
                options[info.id] = info.name or info.id
    except (AttributeError, KeyError, ValueError):
        # Entity-based agents below are enough on newer installations.
        pass

    # Entity-based agents, including modern Gemini/OpenClaw integrations.
    component = hass.data.get(DATA_COMPONENT)
    if component is not None:
        for entity in component.entities:
            entity_id = getattr(entity, "entity_id", None)
            if not entity_id or entity_id in forbidden_agent_ids:
                continue
            state = hass.states.get(entity_id)
            name = state.name if state is not None else getattr(entity, "name", None)
            options[entity_id] = name or entity_id

    return options


def _required_with_default(key: str, value: Any, valid_values: dict[str, str]) -> vol.Required:
    """Create a required dropdown field and preserve an existing selection."""
    if value in valid_values:
        return vol.Required(key, default=value)
    return vol.Required(key)


def _schema(defaults: dict[str, Any], agent_options: dict[str, str]) -> vol.Schema:
    """Build a frontend-compatible configuration schema."""
    return vol.Schema(
        {
            _required_with_default(
                CONF_DOMOTICS_AGENT,
                defaults.get(CONF_DOMOTICS_AGENT),
                agent_options,
            ): vol.In(agent_options),
            _required_with_default(
                CONF_OPENCLAW_AGENT,
                defaults.get(CONF_OPENCLAW_AGENT),
                agent_options,
            ): vol.In(agent_options),
            vol.Required(
                CONF_KEYWORDS,
                default=defaults.get(CONF_KEYWORDS, DEFAULT_KEYWORDS),
            ): TextSelector(TextSelectorConfig(multiline=True)),
            vol.Required(
                CONF_OPENCLAW_ACK_MESSAGE,
                default=defaults.get(
                    CONF_OPENCLAW_ACK_MESSAGE,
                    DEFAULT_OPENCLAW_ACK_MESSAGE,
                ),
            ): TextSelector(TextSelectorConfig(multiline=False)),
            vol.Required(
                CONF_OPENCLAW_BACKGROUND_INSTRUCTION,
                default=defaults.get(
                    CONF_OPENCLAW_BACKGROUND_INSTRUCTION,
                    DEFAULT_OPENCLAW_BACKGROUND_INSTRUCTION,
                ),
            ): TextSelector(TextSelectorConfig(multiline=True)),
        }
    )


def _own_agent_ids(hass: HomeAssistant, entry: ConfigEntry) -> set[str]:
    """Return every agent ID belonging to this router entry."""
    own_ids = {entry.entry_id}
    registry = er.async_get(hass)
    own_ids.update(
        entity_entry.entity_id
        for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity_entry.domain == "conversation"
    )
    return own_ids


def _validate(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    forbidden_agent_ids: set[str] | None = None,
) -> dict[str, str]:
    """Validate selected agents and keywords."""
    errors: dict[str, str] = {}
    forbidden_agent_ids = forbidden_agent_ids or set()

    if user_input[CONF_DOMOTICS_AGENT] == user_input[CONF_OPENCLAW_AGENT]:
        errors["base"] = "agents_must_differ"

    for field in (CONF_DOMOTICS_AGENT, CONF_OPENCLAW_AGENT):
        agent_id = user_input[field]
        if agent_id in forbidden_agent_ids:
            errors[field] = "recursive_agent"
        elif async_get_agent(hass, agent_id) is None:
            errors[field] = "agent_not_found"

    if not parse_keywords(user_input[CONF_KEYWORDS]):
        errors[CONF_KEYWORDS] = "keywords_required"

    if not user_input[CONF_OPENCLAW_ACK_MESSAGE].strip():
        errors[CONF_OPENCLAW_ACK_MESSAGE] = "ack_message_required"

    if not user_input[CONF_OPENCLAW_BACKGROUND_INSTRUCTION].strip():
        errors[CONF_OPENCLAW_BACKGROUND_INSTRUCTION] = (
            "background_instruction_required"
        )

    return errors


class AssistRouterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Assist Router config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "AssistRouterOptionsFlow":
        """Return the options flow."""
        return AssistRouterOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the router."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        agent_options = _agent_options(self.hass)
        errors: dict[str, str] = {}

        if len(agent_options) < 2:
            errors["base"] = "not_enough_agents"

        if user_input is not None:
            errors = _validate(self.hass, user_input)
            if not errors:
                data = dict(user_input)
                data[CONF_KEYWORDS] = canonicalize_keywords(data[CONF_KEYWORDS])
                return self.async_create_entry(title="Assist Router", data=data)

        defaults = user_input or {
            CONF_KEYWORDS: DEFAULT_KEYWORDS,
            CONF_OPENCLAW_ACK_MESSAGE: DEFAULT_OPENCLAW_ACK_MESSAGE,
            CONF_OPENCLAW_BACKGROUND_INSTRUCTION: (
                DEFAULT_OPENCLAW_BACKGROUND_INSTRUCTION
            ),
        }
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(defaults, agent_options),
            errors=errors,
        )


class AssistRouterOptionsFlow(OptionsFlow):
    """Edit agents and keyword list."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show editable routing options."""
        forbidden_agent_ids = _own_agent_ids(self.hass, self._entry)
        agent_options = _agent_options(self.hass, forbidden_agent_ids)
        errors: dict[str, str] = {}

        if len(agent_options) < 2:
            errors["base"] = "not_enough_agents"

        if user_input is not None:
            errors = _validate(
                self.hass,
                user_input,
                forbidden_agent_ids=forbidden_agent_ids,
            )
            if not errors:
                data = dict(user_input)
                data[CONF_KEYWORDS] = canonicalize_keywords(data[CONF_KEYWORDS])
                return self.async_create_entry(title="", data=data)

        current = {**self._entry.data, **self._entry.options}
        defaults = user_input or current
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(defaults, agent_options),
            errors=errors,
        )
