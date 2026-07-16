# Assist Router 0.2.1 para Home Assistant

Agente frontal para Assist que deriva el texto del STT a un agente doméstico o a OpenClaw. También puede abrir vistas de View Assist relacionadas con la respuesta y cerrar explícitamente una conversación de seguimiento.

## Flujo

```text
STT
 └─ Assist Router
     ├─ frase de cierre exacta
     │   ├─ termina la conversación
     │   └─ opcionalmente vuelve a la vista inicial
     ├─ contiene una palabra de domótica
     │   └─ Gemini / agente doméstico
     │       ├─ devuelve la respuesta para TTS
     │       └─ abre la vista relacionada
     └─ no contiene palabras de domótica
         └─ responde inmediatamente y ejecuta OpenClaw en segundo plano
```

## Novedades de la versión 0.2.1

- Frases configurables para cerrar una conversación: `chau`, `gracias`, `ok`, `bueno` y `hasta luego`.
- La frase de cierre se compara contra el mensaje completo; `bueno, prendé la luz` no cierra la conversación.
- Respuesta de cierre configurable, que también puede dejarse vacía.
- Opción para volver a la pantalla inicial de View Assist al cerrar.
- La navegación usa primero el resolvedor oficial de la integración View Assist.
- Nueva demora configurable antes de navegar, para impedir que el propio ciclo del pipeline pise la vista elegida.
- Registros más claros con entidad, ruta y motivo de cualquier fallo de navegación.

## Configuración

Desde:

```text
Ajustes → Dispositivos y servicios → Assist Router → Configurar
```

se muestran secciones separadas:

- **Agentes y filtro principal**: agentes Gemini/OpenClaw y palabras de domótica.
- **Cierre de conversación**: frases, respuesta y retorno a inicio.
- **OpenClaw**: confirmación inmediata, instrucción añadida y vista de procesamiento.
- **View Assist: ajustes generales**: satélite, retorno y demora de navegación.
- Una pantalla separada para cada categoría visual.

## Frases de cierre

Valores predeterminados:

```text
chau
gracias
ok
bueno
hasta luego
```

La coincidencia ignora mayúsculas, tildes y signos, pero exige que toda la frase coincida. Por ejemplo:

```text
“¡Gracias!”          → cierra
“Hasta luego”        → cierra
“Gracias por apagar” → no cierra
“Bueno, prendé luz”  → no cierra
```

Al cerrar, el resultado vuelve con `continue_conversation = false` y sin conservar el identificador de la conversación.

## Navegación de View Assist

El router llama a:

```text
view_assist.navigate
```

con:

```yaml
device: sensor.view_assist_del_satelite
path: /view-assist/weather
revert_timeout: 20
```

La versión 0.2.1 primero intenta identificar el satélite mediante la función interna de View Assist `get_entity_id_from_conversation_device_id`. Si no está disponible, usa el dispositivo, la entidad del satélite y los atributos `mic_device_id`, `voice_device_id` y `mic_device`.

### Demora antes de navegar

El valor predeterminado es:

```text
0,8 segundos
```

La espera ocurre después de recibir la respuesta del agente y antes de ejecutar `view_assist.navigate`. Esto evita una condición de carrera en la que View Assist actualiza su pantalla al terminar el procesamiento y pisa una navegación demasiado temprana.

Si una vista todavía no abre, elegí temporalmente un satélite fijo en vez de **Automático** y revisá los registros.

## Rutas relativas

Las rutas pueden escribirse como nombres simples:

```text
weather
camera
music
intent
```

El router las combina con la ruta base del dashboard del satélite. También se aceptan rutas absolutas como:

```text
/view-assist/weather
```

## OpenClaw

Cuando no hay palabras de domótica:

1. Home Assistant reproduce inmediatamente la confirmación configurada.
2. OpenClaw recibe la solicitud en segundo plano.
3. El pipeline de voz queda libre.
4. Opcionalmente se abre una vista de procesamiento.
5. OpenClaw entrega el resultado por WhatsApp según la instrucción configurada.

## Instalación o actualización

1. Descomprimir el ZIP.
2. Reemplazar completamente:

```text
/config/custom_components/assist_router
```

3. Reiniciar Home Assistant.
4. Abrir la configuración de Assist Router.
5. En **View Assist: ajustes generales**, confirmar el satélite y dejar inicialmente la demora en `0.8`.

No hace falta borrar ni volver a crear la entrada de integración.

## Diagnóstico

En **Ajustes → Sistema → Registros**, buscá `assist_router`. Los mensajes importantes incluyen:

```text
Navigated View Assist entity ... to ...
Configured View Assist entity ... is unavailable
Could not select a View Assist satellite automatically ...
View Assist navigation skipped: service view_assist.navigate is not available
View Assist navigation failed for configured path ...
```

Un fallo visual no interrumpe la respuesta hablada ni el envío a OpenClaw.
