# Assist Router para Home Assistant

Integración personalizada que crea un agente de conversación frontal para Assist.

## Funcionamiento

1. Home Assistant realiza wake word y STT.
2. Assist Router normaliza el texto: minúsculas y sin tildes.
3. Busca coincidencias por **palabra completa** con la lista editable.
4. Si hay coincidencia, delega al agente de domótica elegido y espera su respuesta normal para TTS.
5. Si no hay coincidencia:
   - responde inmediatamente por TTS con una frase configurable;
   - envía el pedido a OpenClaw como tarea en segundo plano;
   - agrega una instrucción configurable para que OpenClaw entregue el resultado por WhatsApp;
   - descarta la respuesta tardía de OpenClaw dentro de Home Assistant, para no dejar abierto el pipeline de voz.

El historial de ambos destinos se separa automáticamente mediante IDs de conversación distintos.

## Comportamiento predeterminado de OpenClaw

Respuesta inmediata:

> Dejame trabajar en eso y te aviso por WhatsApp.

Instrucción añadida al pedido:

> Esta solicitud fue delegada en segundo plano desde Home Assistant. Procesala completamente y, cuando termines, enviá el resultado al usuario por WhatsApp usando el canal configurado en OpenClaw. No dependas de que Home Assistant mantenga abierta esta conversación de voz.

Para que la entrega realmente llegue por WhatsApp, la instancia de OpenClaw debe tener disponible y configurado ese canal. Assist Router solamente le agrega la instrucción; no implementa por sí mismo el envío de WhatsApp.

## Instalación manual

1. Descomprimir el ZIP.
2. Copiar la carpeta `custom_components/assist_router` a `/config/custom_components/assist_router`.
3. Reiniciar Home Assistant completamente.
4. Si la integración ya estaba instalada, abrir **Ajustes → Dispositivos y servicios → Assist Router → Configurar** y guardar las nuevas opciones.
5. Si es una instalación nueva, ir a **Ajustes → Dispositivos y servicios → Añadir integración** y buscar **Assist Router**.
6. Elegir:
   - agente de domótica;
   - agente OpenClaw;
   - lista de palabras;
   - respuesta inmediata;
   - instrucción de entrega para OpenClaw.
7. En **Ajustes → Asistentes de voz**, seleccionar `Assist Router: Router` como agente de conversación del pipeline frontal.

## Cambiar la configuración

Abrir **Ajustes → Dispositivos y servicios → Assist Router → Configurar**. Se pueden cambiar los agentes, las palabras y ambos mensajes sin reinstalar la integración.

## Lista inicial

Incluye términos como `luz`, `aire`, `calefaccion`, `temperatura`, `persiana`, `riego`, `prender`, `apagar`, `abrir` y `cerrar`.

## Detalles del filtro

- `lámpara`, `Lampara` y `LAMPARA` coinciden con `lampara`.
- `luz` coincide con `prendé la luz`.
- `luz` no coincide con una parte interna de otra palabra.
- Solo se manejan palabras; no hay frases, reglas combinadas ni clasificación con IA.

## Registro de errores

Si OpenClaw falla después de que Home Assistant ya dio la respuesta inmediata, el error se registra como:

```text
OpenClaw background request failed
```

Ese error puede verse en **Ajustes → Sistema → Registros**.
