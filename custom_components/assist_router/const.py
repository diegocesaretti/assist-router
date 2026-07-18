"""Constants for the Assist Router integration."""

DOMAIN = "assist_router"

CONF_DOMOTICS_AGENT = "domotics_agent"
CONF_GENERAL_AGENT = "general_agent"
CONF_OPENCLAW_AGENT = "openclaw_agent"
CONF_KEYWORDS = "keywords"
CONF_OPENCLAW_ACK_MESSAGE = "openclaw_ack_message"
CONF_OPENCLAW_BACKGROUND_INSTRUCTION = "openclaw_background_instruction"
CONF_GENERAL_ROUTER_INSTRUCTION = "general_router_instruction"
CONF_FORCE_OPENCLAW_PHRASES = "force_openclaw_phrases"

CONF_STREMIO_ENABLED = "stremio_enabled"
CONF_STREMIO_ENTRY_ID = "stremio_entry_id"
CONF_STREMIO_DEFAULT_PLAYER = "stremio_default_player"
CONF_STREMIO_TV_ALIASES = "stremio_tv_aliases"
CONF_STREMIO_RESULT_LIMIT = "stremio_result_limit"
CONF_STREMIO_VIEW_ENABLED = "stremio_view_enabled"
CONF_STREMIO_VIEW_PATH = "stremio_view_path"
CONF_STREMIO_PLAY_ACK = "stremio_play_ack"
CONF_STREMIO_PENDING_TIMEOUT = "stremio_pending_timeout"

CONF_END_PHRASES = "end_phrases"
CONF_END_RESPONSE = "end_response"
CONF_END_VIEW_HOME = "end_view_home"
CONF_FOLLOW_UP_ENABLED = "follow_up_enabled"

CONF_VIEW_ASSIST_ENABLED = "view_assist_enabled"
CONF_VIEW_ASSIST_ENTITY = "view_assist_entity"
CONF_VIEW_REVERT_TIMEOUT = "view_revert_timeout"
CONF_VIEW_NAVIGATION_DELAY = "view_navigation_delay"
CONF_RESPONSE_VIEW_ENABLED = "view_response_enabled"
CONF_RESPONSE_VIEW_PATH = "view_response_path"
CONF_RESPONSE_DISPLAY_TIME = "view_response_display_time"  # Legacy fixed-duration key.
CONF_RESPONSE_DISPLAY_MIN_TIME = "view_response_min_time"
CONF_RESPONSE_SECONDS_PER_WORD = "view_response_seconds_per_word"
CONF_RESPONSE_DISPLAY_MAX_TIME = "view_response_max_time"
CONF_RELATED_VIEW_DISPLAY_TIME = "view_related_display_time"

# Legacy keys retained only so existing 0.1.x installations can be migrated.
CONF_VIEW_RULES = "view_rules"
CONF_OPENCLAW_VIEW_PATH = "openclaw_view_path"

CONF_OPENCLAW_VIEW_ENABLED = "view_openclaw_enabled"
CONF_OPENCLAW_VIEW_PATH_V2 = "view_openclaw_path"

VIEW_ASSIST_AUTO_ENTITY = "__auto__"

DEFAULT_KEYWORDS = """luz
luces
lampara
lamparas
aire
aires
calor
ventilador
humedad
calefaccion
temperatura
termostato
persiana
persianas
cortina
cortinas
porton
puerta
ventana
riego
bomba
enchufe
televisor
tele
alarma
camara
extractor
prender
encender
apagar
abrir
cerrar
subir
bajar
pone
pieza
dormitorio
cocina
patio
living
tiempo
clima
recordatorio"""


LEGACY_DEFAULT_KEYWORDS_0_1_3 = """luz
luces
lampara
lamparas
aire
calefaccion
temperatura
termostato
persiana
persianas
cortina
cortinas
porton
puerta
ventana
riego
bomba
enchufe
televisor
tele
alarma
camara
ventilador
extractor
prender
encender
apagar
abrir
cerrar
subir
bajar"""

DEFAULT_END_PHRASES = """chau
gracias
ok
bueno
hasta luego"""
DEFAULT_END_RESPONSE = "Hasta luego."
DEFAULT_END_VIEW_HOME = True
DEFAULT_FOLLOW_UP_ENABLED = True

OPENCLAW_ROUTE_MARKER = "[[ASSIST_ROUTER:OPENCLAW]]"

DEFAULT_OPENCLAW_ACK_MESSAGE = "Dejame trabajar en eso y te aviso por WhatsApp."

DEFAULT_GENERAL_ROUTER_INSTRUCTION = (
    "Derivá a OpenClaw solamente cuando el pedido requiera acceder a datos "
    "personales o privados, correo, calendario, archivos, la PC, WhatsApp, "
    "cuentas externas, ejecutar acciones fuera de Home Assistant, crear o "
    "enviar archivos, o realizar una investigación o tarea prolongada. "
    "Respondé vos mismo las preguntas de interés general, recetas, cuentos, "
    "explicaciones, cálculos y consultas que no necesiten herramientas externas. "
    "Ante la duda, respondé como consulta general y no derives a OpenClaw."
)

DEFAULT_FORCE_OPENCLAW_PHRASES = """openclaw
usa openclaw
por whatsapp
mandame por whatsapp
revisa mis correos
mis archivos
en mi pc"""

STREMIO_AUTO_ENTRY = "__auto__"
DEFAULT_STREMIO_ENABLED = True
DEFAULT_STREMIO_ENTRY_ID = STREMIO_AUTO_ENTRY
DEFAULT_STREMIO_DEFAULT_PLAYER = ""
DEFAULT_STREMIO_TV_ALIASES = ""
DEFAULT_STREMIO_RESULT_LIMIT = 5
DEFAULT_STREMIO_VIEW_ENABLED = True
DEFAULT_STREMIO_VIEW_PATH = "infopic"
DEFAULT_STREMIO_PLAY_ACK = "Preparando {title} en {target}."
DEFAULT_STREMIO_PENDING_TIMEOUT = 120

DEFAULT_OPENCLAW_BACKGROUND_INSTRUCTION = (
    "Esta solicitud fue delegada en segundo plano desde Home Assistant. "
    "Procesala completamente y, cuando termines, enviá el resultado al usuario "
    "por WhatsApp usando el canal configurado en OpenClaw. No dependas de que "
    "Home Assistant mantenga abierta esta conversación de voz."
)

DEFAULT_VIEW_ASSIST_ENABLED = True
DEFAULT_VIEW_ASSIST_ENTITY = VIEW_ASSIST_AUTO_ENTITY
DEFAULT_VIEW_REVERT_TIMEOUT = 20  # Legacy option retained for compatibility.
DEFAULT_VIEW_NAVIGATION_DELAY = 0.8
DEFAULT_RESPONSE_VIEW_ENABLED = True
DEFAULT_RESPONSE_VIEW_PATH = "info"
DEFAULT_RESPONSE_DISPLAY_TIME = 3.0  # Legacy fallback for upgrades.
DEFAULT_RESPONSE_DISPLAY_MIN_TIME = 3.0
DEFAULT_RESPONSE_SECONDS_PER_WORD = 0.35
DEFAULT_RESPONSE_DISPLAY_MAX_TIME = 20.0
LEGACY_DEFAULT_RELATED_VIEW_DISPLAY_TIME = 4
DEFAULT_RELATED_VIEW_DISPLAY_TIME = 5
DEFAULT_OPENCLAW_VIEW_ENABLED = True
DEFAULT_OPENCLAW_VIEW_PATH = "info"

ROUTE_STREMIO = "stremio"
ROUTE_DOMOTICS = "domotics"
ROUTE_GENERAL = "general"
ROUTE_OPENCLAW = "openclaw"
