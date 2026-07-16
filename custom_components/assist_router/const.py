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

CONF_END_PHRASES = "end_phrases"
CONF_END_RESPONSE = "end_response"
CONF_END_VIEW_HOME = "end_view_home"

CONF_VIEW_ASSIST_ENABLED = "view_assist_enabled"
CONF_VIEW_ASSIST_ENTITY = "view_assist_entity"
CONF_VIEW_REVERT_TIMEOUT = "view_revert_timeout"
CONF_VIEW_NAVIGATION_DELAY = "view_navigation_delay"
CONF_RESPONSE_VIEW_ENABLED = "view_response_enabled"
CONF_RESPONSE_VIEW_PATH = "view_response_path"
CONF_RESPONSE_DISPLAY_TIME = "view_response_display_time"
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
DEFAULT_RESPONSE_DISPLAY_TIME = 3.0
DEFAULT_RELATED_VIEW_DISPLAY_TIME = 4
DEFAULT_OPENCLAW_VIEW_ENABLED = True
DEFAULT_OPENCLAW_VIEW_PATH = "info"

ROUTE_DOMOTICS = "domotics"
ROUTE_GENERAL = "general"
ROUTE_OPENCLAW = "openclaw"
