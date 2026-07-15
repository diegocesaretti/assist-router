"""Constants for the Assist Router integration."""

DOMAIN = "assist_router"

CONF_DOMOTICS_AGENT = "domotics_agent"
CONF_OPENCLAW_AGENT = "openclaw_agent"
CONF_KEYWORDS = "keywords"
CONF_OPENCLAW_ACK_MESSAGE = "openclaw_ack_message"
CONF_OPENCLAW_BACKGROUND_INSTRUCTION = "openclaw_background_instruction"

CONF_VIEW_ASSIST_ENABLED = "view_assist_enabled"
CONF_VIEW_ASSIST_ENTITY = "view_assist_entity"
CONF_VIEW_RULES = "view_rules"
CONF_VIEW_REVERT_TIMEOUT = "view_revert_timeout"
CONF_OPENCLAW_VIEW_PATH = "openclaw_view_path"

VIEW_ASSIST_AUTO_ENTITY = "__auto__"

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

# Format: category | View Assist path | comma-separated complete words.
# Rules are evaluated from top to bottom against the FINAL spoken response.
DEFAULT_VIEW_RULES = """clima|/view-assist/weather|clima, tiempo, pronostico, lluvia, llueve, soleado, despejado, nublado, viento, humedad, tormenta
termostato|/view-assist/thermostat|aire, calefaccion, termostato, climatizacion, grados, temperatura, frio, calor
camara|/view-assist/camera|camara, camaras, portero, timbre, entrada, vigilancia
alarma|/view-assist/alarm|alarma, alarmas, temporizador, temporizadores, recordatorio, recordatorios
musica|/view-assist/music|musica, cancion, canciones, radio, reproduciendo, volumen
lista|/view-assist/list|lista, listas, compras, tareas, pendientes
deportes|/view-assist/sports|partido, partidos, resultado, resultados, futbol, campeonato
domotica|/view-assist/intent|luz, luces, lampara, lamparas, persiana, persianas, cortina, cortinas, puerta, puertas, ventana, ventanas, porton, enchufe, bomba, riego, ventilador, extractor, encendido, encendida, encendidos, encendidas, apagado, apagada, apagados, apagadas, abierto, abierta, cerrada, cerrado"""

DEFAULT_VIEW_ASSIST_ENABLED = True
DEFAULT_VIEW_ASSIST_ENTITY = VIEW_ASSIST_AUTO_ENTITY
DEFAULT_VIEW_REVERT_TIMEOUT = 20
DEFAULT_OPENCLAW_VIEW_PATH = "/view-assist/info"

ROUTE_DOMOTICS = "domotics"
ROUTE_OPENCLAW = "openclaw"
