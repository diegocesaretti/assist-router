"""Constants for the Assist Router integration."""

DOMAIN = "assist_router"

CONF_DOMOTICS_AGENT = "domotics_agent"
CONF_OPENCLAW_AGENT = "openclaw_agent"
CONF_KEYWORDS = "keywords"
CONF_OPENCLAW_ACK_MESSAGE = "openclaw_ack_message"
CONF_OPENCLAW_BACKGROUND_INSTRUCTION = "openclaw_background_instruction"

CONF_VIEW_ASSIST_ENABLED = "view_assist_enabled"
CONF_VIEW_ASSIST_ENTITY = "view_assist_entity"
CONF_VIEW_REVERT_TIMEOUT = "view_revert_timeout"

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

DEFAULT_OPENCLAW_ACK_MESSAGE = "Dejame trabajar en eso y te aviso por WhatsApp."

DEFAULT_OPENCLAW_BACKGROUND_INSTRUCTION = (
    "Esta solicitud fue delegada en segundo plano desde Home Assistant. "
    "Procesala completamente y, cuando termines, enviá el resultado al usuario "
    "por WhatsApp usando el canal configurado en OpenClaw. No dependas de que "
    "Home Assistant mantenga abierta esta conversación de voz."
)

DEFAULT_VIEW_ASSIST_ENABLED = True
DEFAULT_VIEW_ASSIST_ENTITY = VIEW_ASSIST_AUTO_ENTITY
DEFAULT_VIEW_REVERT_TIMEOUT = 20
DEFAULT_OPENCLAW_VIEW_ENABLED = True
DEFAULT_OPENCLAW_VIEW_PATH = "info"

ROUTE_DOMOTICS = "domotics"
ROUTE_OPENCLAW = "openclaw"
