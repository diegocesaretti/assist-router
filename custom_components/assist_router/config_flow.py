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
    DOMAIN,
    VIEW_ASSIST_AUTO_ENTITY,
)
from .routing import canonicalize_keywords, parse_keywords
from .view_routing import canonicalize_view_rules, parse_view_rules


def _agent_options(
    hass: HomeAssistant, forbidden_agent_ids: set[str] | None = None
) -> dict[str, str]:
    """Return loaded conversation agents as a classic dropdown mapping."""
    forbidden_agent_ids = forbidden_agent_ids or set()
    options: dict[str, str] = {}

    if (
        HOME_ASSISTANT_AGENT not in forbidden_agent_ids
        and async_get_agent(hass, HOME_ASSISTANT_AGENT) is not None
    ):
        options[HOME_ASSISTANT_AGENT] = "Home Assistant"

    try:
        manager = get_agent_manager(hass)
        for info in manager.async_get_agent_info():
            if info.id not in forbidden_agent_ids:
                options[info.id] = info.name or info.id
    except (AttributeError, KeyError, ValueError):
        pass

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


def _view_assist_entity_options(hass: HomeAssistant) -> dict[str, str]:
    """Return View Assist sensor entities plus automatic satellite detection."""
    options = {
        VIEW_ASSIST_AUTO_ENTITY: "Automático: usar el satélite que escuchó",
    }
    registry = er.async_get(hass)

    for entry in hass.config_entries.async_entries("view_assist"):
        for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if entity_entry.domain != "sensor":
                continue
            state = hass.states.get(entity_entry.entity_id)
            label = state.name if state is not None else entity_entry.entity_id
            options[entity_entry.entity_id] = label

    return options


def _required_with_default(
    key: str,
    value: Any,
    valid_values: dict[str, str],
    *,
    fallback: Any | None = None,
) -> vol.Required:
    """Create a required dropdown and preserve an existing valid selection."""
    if value in valid_values:
        return vol.Required(key, default=value)
    if fallback in valid_values:
        return vol.Required(key, default=fallback)
    return vol.Required(key)


def _schema(
    defaults: dict[str, Any],
    agent_options: dict[str, str],
    view_assist_options: dict[str, str],
) -> vol.Schema:
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
            vol.Required(
                CONF_VIEW_ASSIST_ENABLED,
                default=defaults.get(
                    CONF_VIEW_ASSIST_ENABLED,
                    DEFAULT_VIEW_ASSIST_ENABLED,
                ),
            ): bool,
            _required_with_default(
                CONF_VIEW_ASSIST_ENTITY,
                defaults.get(
                    CONF_VIEW_ASSIST_ENTITY,
                    DEFAULT_VIEW_ASSIST_ENTITY,
                ),
                view_assist_options,
                fallback=VIEW_ASSIST_AUTO_ENTITY,
            ): vol.In(view_assist_options),
            vol.Required(
                CONF_VIEW_RULES,
                default=defaults.get(CONF_VIEW_RULES, DEFAULT_VIEW_RULES),
            ): TextSelector(TextSelectorConfig(multiline=True)),
            vol.Required(
                CONF_VIEW_REVERT_TIMEOUT,
                default=defaults.get(
                    CONF_VIEW_REVERT_TIMEOUT,
                    DEFAULT_VIEW_REVERT_TIMEOUT,
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=120)),
            vol.Required(
                CONF_OPENCLAW_VIEW_PATH,
                default=defaults.get(
                    CONF_OPENCLAW_VIEW_PATH,
                    DEFAULT_OPENCLAW_VIEW_PATH,
                ),
            ): TextSelector(TextSelectorConfig(multiline=False)),
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
    """Validate selected agents, routing words and View Assist rules."""
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

    try:
        parse_view_rules(user_input[CONF_VIEW_RULES])
    except ValueError:
        errors[CONF_VIEW_RULES] = "invalid_view_rules"

    openclaw_path = user_input[CONF_OPENCLAW_VIEW_PATH].strip()
    if openclaw_path and not openclaw_path.startswith("/"):
        errors[CONF_OPENCLAW_VIEW_PATH] = "invalid_view_path"

    return errors


def _canonicalized_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return normalized values ready to store."""
    data = dict(user_input)
    data[CONF_KEYWORDS] = canonicalize_keywords(data[CONF_KEYWORDS])
    data[CONF_VIEW_RULES] = canonicalize_view_rules(data[CONF_VIEW_RULES])
    data[CONF_OPENCLAW_VIEW_PATH] = data[CONF_OPENCLAW_VIEW_PATH].strip()
    return data


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
        view_assist_options = _view_assist_entity_options(self.hass)
        errors: dict[str, str] = {}

        if len(agent_options) < 2:
            errors["base"] = "not_enough_agents"

        if user_input is not None:
            errors = _validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title="Assist Router",
                    data=_canonicalized_data(user_input),
                )

        defaults = user_input or {
            CONF_KEYWORDS: DEFAULT_KEYWORDS,
            CONF_OPENCLAW_ACK_MESSAGE: DEFAULT_OPENCLAW_ACK_MESSAGE,
            CONF_OPENCLAW_BACKGROUND_INSTRUCTION: (
                DEFAULT_OPENCLAW_BACKGROUND_INSTRUCTION
            ),
            CONF_VIEW_ASSIST_ENABLED: DEFAULT_VIEW_ASSIST_ENABLED,
            CONF_VIEW_ASSIST_ENTITY: DEFAULT_VIEW_ASSIST_ENTITY,
            CONF_VIEW_RULES: DEFAULT_VIEW_RULES,
            CONF_VIEW_REVERT_TIMEOUT: DEFAULT_VIEW_REVERT_TIMEOUT,
            CONF_OPENCLAW_VIEW_PATH: DEFAULT_OPENCLAW_VIEW_PATH,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(defaults, agent_options, view_assist_options),
            errors=errors,
        )


class AssistRouterOptionsFlow(OptionsFlow):
    """Edit agents, routing and View Assist behavior."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show editable routing options."""
        forbidden_agent_ids = _own_agent_ids(self.hass, self._entry)
        agent_options = _agent_options(self.hass, forbidden_agent_ids)
        view_assist_options = _view_assist_entity_options(self.hass)
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
                return self.async_create_entry(
                    title="",
                    data=_canonicalized_data(user_input),
                )

        current = {**self._entry.data, **self._entry.options}
        defaults = user_input or current
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(defaults, agent_options, view_assist_options),
            errors=errors,
        )
