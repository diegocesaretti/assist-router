# Assist Router 0.1.3 para Home Assistant

Agente frontal para Assist que deriva cada texto del STT a un agente de domótica o a OpenClaw y, cuando corresponde, abre en View Assist la vista relacionada con la respuesta final.

## Flujo

```text
STT
 └─ Assist Router
     ├─ contiene una palabra de domótica
     │   └─ Gemini / agente doméstico
     │       ├─ devuelve la respuesta para TTS
     │       └─ Assist Router analiza esa respuesta y abre la vista relacionada
     └─ no contiene palabras de domótica
         └─ responde inmediatamente y ejecuta OpenClaw en segundo plano
             └─ abre una vista configurable de “procesando”
```

## Novedades de la versión 0.1.3

- Integración opcional con `view_assist.navigate`.
- Detección automática del satélite View Assist que originó la conversación.
- Menú para seleccionar un satélite fijo como respaldo.
- Clasificación de la **respuesta final** del agente doméstico por categorías editables.
- Ruta de View Assist configurable para cada categoría.
- Timeout configurable para volver a la vista anterior.
- Vista configurable mientras OpenClaw trabaja en segundo plano.

## Categorías y vistas

El campo **Categorías de respuesta y vistas** usa una regla por línea:

```text
categoria | /view-assist/ruta | palabra1, palabra2, palabra3
```

Ejemplo:

```text
clima|/view-assist/weather|clima, pronostico, lluvia, soleado, nublado
termostato|/view-assist/thermostat|aire, calefaccion, termostato, temperatura
camara|/view-assist/camera|camara, portero, timbre
alarma|/view-assist/alarm|alarma, temporizador, recordatorio
domotica|/view-assist/intent|luz, persiana, puerta, ventana, encendido, apagado
```

Las reglas se evalúan de arriba hacia abajo. La primera que coincide gana. La comparación:

- usa palabras completas;
- ignora mayúsculas;
- ignora tildes;
- se realiza sobre el texto hablado por Gemini o el agente doméstico, no sobre el STT original.

Si no coincide ninguna categoría, el router entrega la respuesta por TTS y no cambia la vista.

## OpenClaw

Cuando no hay ninguna palabra de domótica:

1. Home Assistant dice inmediatamente la frase configurada.
2. OpenClaw recibe el pedido en segundo plano con la instrucción adicional configurada.
3. El pipeline de voz queda libre.
4. View Assist abre por defecto `/view-assist/info`.
5. OpenClaw debe entregar el resultado por WhatsApp usando su propio canal configurado.

La ruta de OpenClaw puede dejarse vacía para no cambiar la pantalla.

## Selección del satélite

La opción recomendada es:

```text
Automático: usar el satélite que escuchó
```

El router compara el `device_id` de la conversación con el micrófono configurado en cada instancia de View Assist y navega el sensor correspondiente.

Si el dispositivo no entrega un `device_id`, se puede seleccionar un satélite fijo en la configuración. En instalaciones con un único satélite, el router también puede usarlo automáticamente.

## Instalación o actualización

1. Descomprimir el ZIP.
2. Reemplazar `/config/custom_components/assist_router` por la carpeta nueva.
3. Reiniciar Home Assistant completamente.
4. Abrir **Ajustes → Dispositivos y servicios → Assist Router → Configurar**.
5. Revisar:
   - agente de domótica;
   - agente OpenClaw;
   - palabras del filtro;
   - opciones de OpenClaw;
   - activar View Assist;
   - satélite automático o fijo;
   - categorías y rutas;
   - timeout de retorno.

No hace falta borrar la entrada de integración existente.

## Diagnóstico

En **Ajustes → Sistema → Registros** pueden aparecer mensajes como:

```text
View Assist navigation skipped: service view_assist.navigate is not available
View Assist navigation skipped: no satellite matched the conversation device
View Assist navigation failed for path ...
OpenClaw background request failed
```

Un error visual no bloquea ni elimina la respuesta hablada.
