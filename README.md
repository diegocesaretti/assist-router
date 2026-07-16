# Assist Router 0.2.3 para Home Assistant

Agente frontal para Assist que deriva el texto del STT a un agente doméstico o a OpenClaw. También integra una secuencia visual con View Assist y permite cerrar explícitamente una conversación de seguimiento.

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
     │       ├─ muestra la respuesta escrita
     │       └─ abre la vista relacionada
     └─ no contiene palabras de domótica
         └─ responde inmediatamente y ejecuta OpenClaw en segundo plano
```

## Novedades de la versión 0.2.3

- La respuesta del agente se muestra escrita en la vista `info` antes de abrir la vista temática.
- Tiempo configurable para la respuesta escrita; valor predeterminado: **3 segundos**.
- Tiempo configurable para la vista relacionada; valor predeterminado: **4 segundos**.
- Ruta configurable para la vista que muestra la respuesta escrita.
- La secuencia limpia el mensaje antes de cambiar a clima, cámaras, domótica u otra vista.
- Si no existe una vista relacionada, vuelve a inicio después de mostrar la respuesta.
- La respuesta de OpenClaw también puede mostrarse escrita antes de abrir su vista de procesamiento.

## Secuencia visual

```text
Respuesta del agente
        ↓
Demora inicial de navegación (0,8 s)
        ↓
Vista info + respuesta escrita (3 s)
        ↓
Vista relacionada, por ejemplo weather o intent (4 s)
        ↓
Retorno de View Assist
```

Para mostrar el texto, el router primero navega a la vista configurada y después llama a `view_assist.set_state` con:

```yaml
entity_id: sensor.view_assist_del_satelite
title: Respuesta
message: La luz del living quedó encendida
message_font_size: 6vw
```

Luego llama a `view_assist.navigate` para abrir la vista relacionada.

## Configuración

Desde:

```text
Ajustes → Dispositivos y servicios → Assist Router → Configurar
```

En **View Assist: ajustes generales** se pueden cambiar:

- Satélite View Assist.
- Mostrar o no la respuesta escrita.
- Vista para mostrar la respuesta; predeterminado: `info`.
- Segundos de respuesta escrita; predeterminado: `3`.
- Segundos de la vista relacionada; predeterminado: `4`.
- Demora inicial de navegación; predeterminado: `0.8`.

Las rutas pueden ser relativas:

```text
info
weather
camera
music
intent
```

El router las combina con la ruta base real del dashboard del satélite. También acepta rutas absolutas como `/view-assist/info`.

## Frases de cierre

Valores predeterminados:

```text
chau
gracias
ok
bueno
hasta luego
```

La coincidencia ignora mayúsculas, tildes y signos, pero exige que toda la frase coincida.

```text
“¡Gracias!”          → cierra
“Hasta luego”        → cierra
“Gracias por apagar” → no cierra
“Bueno, prendé luz”  → no cierra
```

## OpenClaw

Cuando no hay palabras de domótica:

1. Home Assistant reproduce inmediatamente la confirmación configurada.
2. Esa confirmación puede mostrarse escrita durante el tiempo configurado.
3. OpenClaw recibe la solicitud en segundo plano.
4. Se abre la vista de procesamiento configurada.
5. OpenClaw entrega el resultado por WhatsApp según la instrucción configurada.

## Instalación o actualización

1. Descomprimir el ZIP.
2. Reemplazar completamente:

```text
/config/custom_components/assist_router
```

3. Reiniciar Home Assistant.
4. Abrir **Assist Router → Configurar → View Assist: ajustes generales**.
5. Confirmar inicialmente estos valores:

```text
Mostrar la respuesta escrita: activado
Vista para mostrar la respuesta: info
Segundos de respuesta escrita: 3
Segundos de la vista relacionada: 4
Demora inicial: 0.8
```

No hace falta borrar ni volver a crear la entrada de integración.

## Diagnóstico

En **Ajustes → Sistema → Registros**, buscar `assist_router`. La versión registra:

```text
Showing written response on ...
Showing related View Assist view on ...
View Assist response sequence skipped ...
View Assist response sequence failed
```

Un fallo visual no interrumpe la respuesta hablada ni el envío a OpenClaw.


## 0.2.3

- Corrige el bucle de confirmación al derivar a OpenClaw.
- La confirmación inmediata ahora cierra explícitamente la conversación (`conversation_id=None` y `continue_conversation=False`).
- Agrega un filtro anti-eco: si STT vuelve a oír exactamente la confirmación configurada, la descarta en silencio y no llama a ningún agente.
