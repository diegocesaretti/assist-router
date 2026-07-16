"""Config flow for Assist Router."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.conversation.agent_manager import (
    async_get_agent,
    get_agent_manager,
)
from homeassistant.components.conversation.const import DATA_COMPONENT, HOME_ASSISTANT_AGENT
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
    CONF_OPENCLAW_VIEW_PATH,
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
    CONF_VIEW_RULES,
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
    DEFAULT_RESPONSE_DISPLAY_MIN_TIME,
    DEFAULT_RESPONSE_SECONDS_PER_WORD,
    DEFAULT_RESPONSE_DISPLAY_MAX_TIME,
    DEFAULT_RELATED_VIEW_DISPLAY_TIME,
    DOMAIN,
    LEGACY_DEFAULT_KEYWORDS_0_1_3,
    VIEW_ASSIST_AUTO_ENTITY,
)
from .routing import (
    canonicalize_keywords,
    canonicalize_phrases,
    migrate_default_keywords,
    parse_keywords,
    parse_phrases,
)
from .view_routing import (
    VIEW_DEFINITIONS,
    VIEW_DEFINITIONS_BY_SLUG,
    apply_legacy_view_settings,
    canonicalize_view_settings,
    normalize_view_path,
    validate_view_path,
    view_defaults,
)


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
    options = {VIEW_ASSIST_AUTO_ENTITY: "Automático: usar el satélite que escuchó"}
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


def _effective_settings(entry: ConfigEntry) -> dict[str, Any]:
    """Return merged settings with automatic 0.1.x migrations."""
    settings = apply_legacy_view_settings({**entry.data, **entry.options})
    settings[CONF_KEYWORDS] = migrate_default_keywords(
        settings.get(CONF_KEYWORDS),
        LEGACY_DEFAULT_KEYWORDS_0_1_3,
        DEFAULT_KEYWORDS,
    )
    legacy_response_time = settings.get(
        CONF_RESPONSE_DISPLAY_TIME, DEFAULT_RESPONSE_DISPLAY_TIME
    )
    settings.setdefault(CONF_RESPONSE_DISPLAY_MIN_TIME, legacy_response_time)
    settings.setdefault(
        CONF_RESPONSE_SECONDS_PER_WORD, DEFAULT_RESPONSE_SECONDS_PER_WORD
    )
    settings.setdefault(
        CONF_RESPONSE_DISPLAY_MAX_TIME, DEFAULT_RESPONSE_DISPLAY_MAX_TIME
    )
    return settings


def _base_defaults() -> dict[str, Any]:
    """Return defaults for a new installation."""
    return {
        CONF_KEYWORDS: DEFAULT_KEYWORDS,
        CONF_END_PHRASES: DEFAULT_END_PHRASES,
        CONF_END_RESPONSE: DEFAULT_END_RESPONSE,
        CONF_END_VIEW_HOME: DEFAULT_END_VIEW_HOME,
        CONF_GENERAL_ROUTER_INSTRUCTION: DEFAULT_GENERAL_ROUTER_INSTRUCTION,
        CONF_FORCE_OPENCLAW_PHRASES: DEFAULT_FORCE_OPENCLAW_PHRASES,
        CONF_OPENCLAW_ACK_MESSAGE: DEFAULT_OPENCLAW_ACK_MESSAGE,
        CONF_OPENCLAW_BACKGROUND_INSTRUCTION: DEFAULT_OPENCLAW_BACKGROUND_INSTRUCTION,
        CONF_VIEW_ASSIST_ENABLED: DEFAULT_VIEW_ASSIST_ENABLED,
        CONF_VIEW_ASSIST_ENTITY: DEFAULT_VIEW_ASSIST_ENTITY,
        CONF_VIEW_NAVIGATION_DELAY: DEFAULT_VIEW_NAVIGATION_DELAY,
        CONF_RESPONSE_VIEW_ENABLED: DEFAULT_RESPONSE_VIEW_ENABLED,
        CONF_RESPONSE_VIEW_PATH: DEFAULT_RESPONSE_VIEW_PATH,
        CONF_RESPONSE_DISPLAY_TIME: DEFAULT_RESPONSE_DISPLAY_TIME,
        CONF_RESPONSE_DISPLAY_MIN_TIME: DEFAULT_RESPONSE_DISPLAY_MIN_TIME,
        CONF_RESPONSE_SECONDS_PER_WORD: DEFAULT_RESPONSE_SECONDS_PER_WORD,
        CONF_RESPONSE_DISPLAY_MAX_TIME: DEFAULT_RESPONSE_DISPLAY_MAX_TIME,
        CONF_RELATED_VIEW_DISPLAY_TIME: DEFAULT_RELATED_VIEW_DISPLAY_TIME,
        CONF_OPENCLAW_VIEW_ENABLED: DEFAULT_OPENCLAW_VIEW_ENABLED,
        CONF_OPENCLAW_VIEW_PATH_V2: DEFAULT_OPENCLAW_VIEW_PATH,
        **view_defaults(),
    }


def _routing_schema(
    defaults: dict[str, Any], agent_options: dict[str, str]
) -> vol.Schema:
    """Build the routing and agent form."""
    return vol.Schema(
        {
            _required_with_default(
                CONF_DOMOTICS_AGENT,
                defaults.get(CONF_DOMOTICS_AGENT),
                agent_options,
            ): vol.In(agent_options),
            _required_with_default(
                CONF_GENERAL_AGENT,
                defaults.get(CONF_GENERAL_AGENT, defaults.get(CONF_DOMOTICS_AGENT)),
                agent_options,
                fallback=defaults.get(CONF_DOMOTICS_AGENT),
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
        }
    )


def _conversation_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build conversation ending behavior form."""
    return vol.Schema(
        {
            vol.Required(
                CONF_END_PHRASES,
                default=defaults.get(CONF_END_PHRASES, DEFAULT_END_PHRASES),
            ): TextSelector(TextSelectorConfig(multiline=True)),
            vol.Required(
                CONF_END_RESPONSE,
                default=defaults.get(CONF_END_RESPONSE, DEFAULT_END_RESPONSE),
            ): TextSelector(TextSelectorConfig(multiline=False)),
            vol.Required(
                CONF_END_VIEW_HOME,
                default=defaults.get(CONF_END_VIEW_HOME, DEFAULT_END_VIEW_HOME),
            ): bool,
        }
    )


def _validate_conversation(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate closing phrases."""
    errors: dict[str, str] = {}
    if not parse_phrases(user_input[CONF_END_PHRASES]):
        errors[CONF_END_PHRASES] = "end_phrases_required"
    return errors


def _normalize_conversation(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize closing phrases and response."""
    normalized = dict(user_input)
    normalized[CONF_END_PHRASES] = canonicalize_phrases(
        normalized[CONF_END_PHRASES]
    )
    normalized[CONF_END_RESPONSE] = normalized[CONF_END_RESPONSE].strip()
    return normalized


def _general_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the general-agent classifier policy form."""
    return vol.Schema(
        {
            vol.Required(
                CONF_GENERAL_ROUTER_INSTRUCTION,
                default=defaults.get(
                    CONF_GENERAL_ROUTER_INSTRUCTION,
                    DEFAULT_GENERAL_ROUTER_INSTRUCTION,
                ),
            ): TextSelector(TextSelectorConfig(multiline=True)),
            vol.Required(
                CONF_FORCE_OPENCLAW_PHRASES,
                default=defaults.get(
                    CONF_FORCE_OPENCLAW_PHRASES,
                    DEFAULT_FORCE_OPENCLAW_PHRASES,
                ),
            ): TextSelector(TextSelectorConfig(multiline=True)),
        }
    )


def _validate_general(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate the general-agent routing policy."""
    errors: dict[str, str] = {}
    if not user_input[CONF_GENERAL_ROUTER_INSTRUCTION].strip():
        errors[CONF_GENERAL_ROUTER_INSTRUCTION] = "general_instruction_required"
    return errors


def _normalize_general(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize the general-agent policy and explicit OpenClaw phrases."""
    normalized = dict(user_input)
    normalized[CONF_GENERAL_ROUTER_INSTRUCTION] = normalized[
        CONF_GENERAL_ROUTER_INSTRUCTION
    ].strip()
    normalized[CONF_FORCE_OPENCLAW_PHRASES] = canonicalize_phrases(
        normalized[CONF_FORCE_OPENCLAW_PHRASES]
    )
    return normalized


def _openclaw_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build OpenClaw behavior form."""
    return vol.Schema(
        {
            vol.Required(
                CONF_OPENCLAW_ACK_MESSAGE,
                default=defaults.get(
                    CONF_OPENCLAW_ACK_MESSAGE, DEFAULT_OPENCLAW_ACK_MESSAGE
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
                CONF_OPENCLAW_VIEW_ENABLED,
                default=defaults.get(
                    CONF_OPENCLAW_VIEW_ENABLED, DEFAULT_OPENCLAW_VIEW_ENABLED
                ),
            ): bool,
            vol.Required(
                CONF_OPENCLAW_VIEW_PATH_V2,
                default=defaults.get(
                    CONF_OPENCLAW_VIEW_PATH_V2, DEFAULT_OPENCLAW_VIEW_PATH
                ),
            ): TextSelector(TextSelectorConfig(multiline=False)),
        }
    )


def _view_assist_schema(
    defaults: dict[str, Any], view_assist_options: dict[str, str]
) -> vol.Schema:
    """Build general View Assist form."""
    return vol.Schema(
        {
            vol.Required(
                CONF_VIEW_ASSIST_ENABLED,
                default=defaults.get(
                    CONF_VIEW_ASSIST_ENABLED, DEFAULT_VIEW_ASSIST_ENABLED
                ),
            ): bool,
            _required_with_default(
                CONF_VIEW_ASSIST_ENTITY,
                defaults.get(CONF_VIEW_ASSIST_ENTITY, DEFAULT_VIEW_ASSIST_ENTITY),
                view_assist_options,
                fallback=VIEW_ASSIST_AUTO_ENTITY,
            ): vol.In(view_assist_options),
            vol.Required(
                CONF_RESPONSE_VIEW_ENABLED,
                default=defaults.get(
                    CONF_RESPONSE_VIEW_ENABLED, DEFAULT_RESPONSE_VIEW_ENABLED
                ),
            ): bool,
            vol.Required(
                CONF_RESPONSE_VIEW_PATH,
                default=defaults.get(
                    CONF_RESPONSE_VIEW_PATH, DEFAULT_RESPONSE_VIEW_PATH
                ),
            ): TextSelector(TextSelectorConfig(multiline=False)),
            vol.Required(
                CONF_RESPONSE_DISPLAY_MIN_TIME,
                default=defaults.get(
                    CONF_RESPONSE_DISPLAY_MIN_TIME,
                    defaults.get(
                        CONF_RESPONSE_DISPLAY_TIME, DEFAULT_RESPONSE_DISPLAY_MIN_TIME
                    ),
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=60)),
            vol.Required(
                CONF_RESPONSE_SECONDS_PER_WORD,
                default=defaults.get(
                    CONF_RESPONSE_SECONDS_PER_WORD,
                    DEFAULT_RESPONSE_SECONDS_PER_WORD,
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.05, max=3)),
            vol.Required(
                CONF_RESPONSE_DISPLAY_MAX_TIME,
                default=defaults.get(
                    CONF_RESPONSE_DISPLAY_MAX_TIME,
                    DEFAULT_RESPONSE_DISPLAY_MAX_TIME,
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=120)),
            vol.Required(
                CONF_RELATED_VIEW_DISPLAY_TIME,
                default=defaults.get(
                    CONF_RELATED_VIEW_DISPLAY_TIME, DEFAULT_RELATED_VIEW_DISPLAY_TIME
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=120)),
            vol.Required(
                CONF_VIEW_NAVIGATION_DELAY,
                default=defaults.get(
                    CONF_VIEW_NAVIGATION_DELAY, DEFAULT_VIEW_NAVIGATION_DELAY
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
        }
    )


def _validate_view_assist(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate general View Assist response sequencing options."""
    errors: dict[str, str] = {}
    if user_input[CONF_RESPONSE_VIEW_ENABLED] and not validate_view_path(
        user_input[CONF_RESPONSE_VIEW_PATH]
    ):
        errors[CONF_RESPONSE_VIEW_PATH] = "invalid_view_path"
    if (
        user_input[CONF_RESPONSE_DISPLAY_MAX_TIME]
        < user_input[CONF_RESPONSE_DISPLAY_MIN_TIME]
    ):
        errors[CONF_RESPONSE_DISPLAY_MAX_TIME] = "response_max_before_min"
    return errors


def _normalize_view_assist(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize the response view path."""
    normalized = dict(user_input)
    normalized[CONF_RESPONSE_VIEW_PATH] = normalize_view_path(
        normalized[CONF_RESPONSE_VIEW_PATH]
    )
    return normalized


def _view_schema(defaults: dict[str, Any], slug: str) -> vol.Schema:
    """Build a clear three-field form for one View Assist category."""
    definition = VIEW_DEFINITIONS_BY_SLUG[slug]
    return vol.Schema(
        {
            vol.Required(
                definition.enabled_key,
                default=defaults.get(
                    definition.enabled_key, definition.default_enabled
                ),
            ): bool,
            vol.Required(
                definition.path_key,
                default=defaults.get(definition.path_key, definition.default_path),
            ): TextSelector(TextSelectorConfig(multiline=False)),
            vol.Required(
                definition.keywords_key,
                default=defaults.get(
                    definition.keywords_key, definition.default_keywords
                ),
            ): TextSelector(TextSelectorConfig(multiline=True)),
        }
    )


def _validate_routing(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    forbidden_agent_ids: set[str] | None = None,
) -> dict[str, str]:
    """Validate agents and the main keyword filter."""
    errors: dict[str, str] = {}
    forbidden_agent_ids = forbidden_agent_ids or set()

    selected_agents = {
        user_input[CONF_DOMOTICS_AGENT],
        user_input[CONF_GENERAL_AGENT],
        user_input[CONF_OPENCLAW_AGENT],
    }
    if len(selected_agents) != 3:
        errors["base"] = "agents_must_differ"

    for field in (CONF_DOMOTICS_AGENT, CONF_GENERAL_AGENT, CONF_OPENCLAW_AGENT):
        agent_id = user_input[field]
        if agent_id in forbidden_agent_ids:
            errors[field] = "recursive_agent"
        elif async_get_agent(hass, agent_id) is None:
            errors[field] = "agent_not_found"

    if not parse_keywords(user_input[CONF_KEYWORDS]):
        errors[CONF_KEYWORDS] = "keywords_required"

    return errors


def _validate_openclaw(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate OpenClaw options."""
    errors: dict[str, str] = {}
    if not user_input[CONF_OPENCLAW_ACK_MESSAGE].strip():
        errors[CONF_OPENCLAW_ACK_MESSAGE] = "ack_message_required"
    if not user_input[CONF_OPENCLAW_BACKGROUND_INSTRUCTION].strip():
        errors[CONF_OPENCLAW_BACKGROUND_INSTRUCTION] = (
            "background_instruction_required"
        )
    path = user_input[CONF_OPENCLAW_VIEW_PATH_V2]
    if user_input[CONF_OPENCLAW_VIEW_ENABLED] and not validate_view_path(path):
        errors[CONF_OPENCLAW_VIEW_PATH_V2] = "invalid_view_path"
    return errors


def _validate_view(user_input: dict[str, Any], slug: str) -> dict[str, str]:
    """Validate one visual category."""
    definition = VIEW_DEFINITIONS_BY_SLUG[slug]
    errors: dict[str, str] = {}
    if user_input[definition.enabled_key]:
        if not validate_view_path(user_input[definition.path_key]):
            errors[definition.path_key] = "invalid_view_path"
        if not parse_keywords(user_input[definition.keywords_key]):
            errors[definition.keywords_key] = "view_keywords_required"
    return errors


def _normalize_routing(user_input: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(user_input)
    normalized[CONF_KEYWORDS] = canonicalize_keywords(normalized[CONF_KEYWORDS])
    return normalized


def _normalize_openclaw(user_input: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(user_input)
    normalized[CONF_OPENCLAW_ACK_MESSAGE] = normalized[
        CONF_OPENCLAW_ACK_MESSAGE
    ].strip()
    normalized[CONF_OPENCLAW_BACKGROUND_INSTRUCTION] = normalized[
        CONF_OPENCLAW_BACKGROUND_INSTRUCTION
    ].strip()
    normalized[CONF_OPENCLAW_VIEW_PATH_V2] = normalize_view_path(
        normalized[CONF_OPENCLAW_VIEW_PATH_V2]
    )
    return normalized


def _normalize_view(user_input: dict[str, Any], slug: str) -> dict[str, Any]:
    definition = VIEW_DEFINITIONS_BY_SLUG[slug]
    normalized = dict(user_input)
    normalized[definition.path_key] = normalize_view_path(
        normalized[definition.path_key]
    )
    normalized[definition.keywords_key] = canonicalize_keywords(
        normalized[definition.keywords_key]
    )
    return normalized


class AssistRouterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Assist Router config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._pending: dict[str, Any] = _base_defaults()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "AssistRouterOptionsFlow":
        """Return the options flow."""
        return AssistRouterOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose destination agents and the main keyword filter."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        agent_options = _agent_options(self.hass)
        errors: dict[str, str] = {}
        if len(agent_options) < 3:
            errors["base"] = "not_enough_agents"

        if user_input is not None:
            errors = _validate_routing(self.hass, user_input)
            if not errors:
                self._pending.update(_normalize_routing(user_input))
                return await self.async_step_general()

        return self.async_show_form(
            step_id="user",
            data_schema=_routing_schema(user_input or self._pending, agent_options),
            errors=errors,
        )

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the fast general agent and its routing policy."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_general(user_input)
            if not errors:
                self._pending.update(_normalize_general(user_input))
                return await self.async_step_openclaw()

        return self.async_show_form(
            step_id="general",
            data_schema=_general_schema(user_input or self._pending),
            errors=errors,
        )

    async def async_step_openclaw(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the immediate OpenClaw handoff."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_openclaw(user_input)
            if not errors:
                self._pending.update(_normalize_openclaw(user_input))
                return await self.async_step_view_assist()

        return self.async_show_form(
            step_id="openclaw",
            data_schema=_openclaw_schema(user_input or self._pending),
            errors=errors,
        )

    async def async_step_view_assist(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure general View Assist behavior; categories use safe defaults."""
        options = _view_assist_entity_options(self.hass)
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_view_assist(user_input)
            if not errors:
                self._pending.update(_normalize_view_assist(user_input))
                return self.async_create_entry(
                    title="Assist Router",
                    data=canonicalize_view_settings(self._pending),
                )

        return self.async_show_form(
            step_id="view_assist",
            data_schema=_view_assist_schema(user_input or self._pending, options),
            errors=errors,
        )


class AssistRouterOptionsFlow(OptionsFlow):
    """Edit logical sections through menus with explicit back navigation."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    def _merged_settings(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Return normalized settings after applying a partial edit."""
        settings = _effective_settings(self._entry)
        settings.update(changes)
        settings.pop(CONF_VIEW_RULES, None)
        settings.pop(CONF_OPENCLAW_VIEW_PATH, None)
        settings.pop(CONF_VIEW_REVERT_TIMEOUT, None)
        return canonicalize_view_settings(settings)

    async def _save_and_return(self, changes: dict[str, Any]) -> ConfigFlowResult:
        """Persist changes immediately and return to the main options menu."""
        settings = self._merged_settings(changes)
        self.hass.config_entries.async_update_entry(
            self._entry,
            options=settings,
        )
        return await self.async_step_init()

    def _show_section_menu(
        self,
        step_id: str,
        edit_step_id: str,
    ) -> ConfigFlowResult:
        """Show an Edit/Back menu for one settings section."""
        return self.async_show_menu(
            step_id=step_id,
            menu_options=[edit_step_id, "init"],
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the main options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "routing",
                "general",
                "conversation",
                "openclaw",
                "view_assist",
                *[f"view_{definition.slug}" for definition in VIEW_DEFINITIONS],
            ],
        )

    async def async_step_routing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self._show_section_menu("routing", "edit_routing")

    async def async_step_edit_routing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        forbidden = _own_agent_ids(self.hass, self._entry)
        agents = _agent_options(self.hass, forbidden)
        errors: dict[str, str] = {}
        if len(agents) < 3:
            errors["base"] = "not_enough_agents"
        if user_input is not None:
            errors = _validate_routing(self.hass, user_input, forbidden)
            if not errors:
                return await self._save_and_return(_normalize_routing(user_input))
        return self.async_show_form(
            step_id="edit_routing",
            data_schema=_routing_schema(
                user_input or _effective_settings(self._entry), agents
            ),
            errors=errors,
        )

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self._show_section_menu("general", "edit_general")

    async def async_step_edit_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_general(user_input)
            if not errors:
                return await self._save_and_return(_normalize_general(user_input))
        return self.async_show_form(
            step_id="edit_general",
            data_schema=_general_schema(
                user_input or _effective_settings(self._entry)
            ),
            errors=errors,
        )

    async def async_step_conversation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self._show_section_menu("conversation", "edit_conversation")

    async def async_step_edit_conversation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_conversation(user_input)
            if not errors:
                return await self._save_and_return(
                    _normalize_conversation(user_input)
                )
        return self.async_show_form(
            step_id="edit_conversation",
            data_schema=_conversation_schema(
                user_input or _effective_settings(self._entry)
            ),
            errors=errors,
        )

    async def async_step_openclaw(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self._show_section_menu("openclaw", "edit_openclaw")

    async def async_step_edit_openclaw(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_openclaw(user_input)
            if not errors:
                return await self._save_and_return(_normalize_openclaw(user_input))
        return self.async_show_form(
            step_id="edit_openclaw",
            data_schema=_openclaw_schema(
                user_input or _effective_settings(self._entry)
            ),
            errors=errors,
        )

    async def async_step_view_assist(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self._show_section_menu("view_assist", "edit_view_assist")

    async def async_step_edit_view_assist(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_view_assist(user_input)
            if not errors:
                return await self._save_and_return(
                    _normalize_view_assist(user_input)
                )
        return self.async_show_form(
            step_id="edit_view_assist",
            data_schema=_view_assist_schema(
                user_input or _effective_settings(self._entry),
                _view_assist_entity_options(self.hass),
            ),
            errors=errors,
        )


def _make_view_menu_step(slug: str):
    """Create one Edit/Back menu per visual category."""

    async def async_step_view_menu(
        self: AssistRouterOptionsFlow,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        return self._show_section_menu(
            f"view_{slug}",
            f"edit_view_{slug}",
        )

    return async_step_view_menu


def _make_view_edit_step(slug: str):
    """Create one editable form per visual category."""

    async def async_step_view_edit(
        self: AssistRouterOptionsFlow,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_view(user_input, slug)
            if not errors:
                return await self._save_and_return(
                    _normalize_view(user_input, slug)
                )
        return self.async_show_form(
            step_id=f"edit_view_{slug}",
            data_schema=_view_schema(
                user_input or _effective_settings(self._entry), slug
            ),
            errors=errors,
        )

    return async_step_view_edit


for _definition in VIEW_DEFINITIONS:
    setattr(
        AssistRouterOptionsFlow,
        f"async_step_view_{_definition.slug}",
        _make_view_menu_step(_definition.slug),
    )
    setattr(
        AssistRouterOptionsFlow,
        f"async_step_edit_view_{_definition.slug}",
        _make_view_edit_step(_definition.slug),
    )
