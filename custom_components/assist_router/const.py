"""Constants for the Assist Router integration."""

DOMAIN = "assist_router"

CONF_DOMOTICS_AGENT = "domotics_agent"
CONF_OPENCLAW_AGENT = "openclaw_agent"
CONF_KEYWORDS = "keywords"
CONF_OPENCLAW_ACK_MESSAGE = "openclaw_ack_message"
CONF_OPENCLAW_BACKGROUND_INSTRUCTION = "openclaw_background_instruction"

DEFAULT_KEYWORDS = """luz
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

ROUTE_DOMOTICS = "domotics"
ROUTE_OPENCLAW = "openclaw"
