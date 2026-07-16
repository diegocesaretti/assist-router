# Assist Router 0.3.0 para Home Assistant

Agente frontal para Assist con tres destinos: domótica, consultas generales rápidas y OpenClaw en segundo plano. Mantiene la integración con View Assist, el cierre de conversación y la entrega de tareas largas por WhatsApp.

## Flujo

```text
STT
 └─ Assist Router
     ├─ frase de cierre exacta
     │   └─ termina la conversación
     ├─ frase que fuerza OpenClaw
     │   └─ confirmación inmediata + trabajo en segundo plano
     ├─ contiene una palabra de domótica
     │   └─ agente de domótica
     └─ resto
         └─ agente general rápido
             ├─ responde normalmente
             └─ o devuelve una marca interna y autoriza OpenClaw
```

OpenClaw nunca es el destino por descarte. Solo se ejecuta cuando una frase configurada lo fuerza o cuando el agente general determina que el pedido necesita herramientas externas, datos personales o trabajo prolongado.

## Tres agentes configurables

Desde:

```text
Ajustes → Dispositivos y servicios → Assist Router → Configurar
```

En **Tres agentes y filtro de domótica** se eligen:

- Agente de domótica.
- Agente general y clasificador.
- Agente OpenClaw.
- Lista de palabras de domótica.

Para actualizar desde 0.2.3, entrá una vez en esa pantalla y seleccioná el nuevo agente general. Mientras no lo hagas, la integración usa el agente de domótica como respaldo para no dejar de funcionar.

## Clasificador del agente general

El agente general recibe un protocolo interno fijo:

- Si puede contestar directamente, devuelve una respuesta normal.
- Si necesita OpenClaw, devuelve una marca privada que el usuario nunca escucha.
- Ante dudas, debe responder como consulta general.

La pantalla **Clasificador del agente general** permite editar:

- Criterios para derivar a OpenClaw.
- Frases que fuerzan OpenClaw directamente.

Criterios predeterminados: correo, calendario, archivos, PC, WhatsApp, cuentas externas, creación o envío de archivos, acciones fuera de Home Assistant e investigaciones o tareas prolongadas.

Consultas que quedan en el agente general:

```text
¿Cómo hago una salsa blanca?
¿Quién fue San Martín?
Contame un cuento para Cruz.
Explicame la fotosíntesis.
```

Consultas que pueden derivarse a OpenClaw:

```text
Revisame los correos.
Buscá el manual que tengo en la PC.
Prepará un archivo y mandámelo por WhatsApp.
Compará estas opciones y avisame cuando termines.
```

## OpenClaw

Cuando se autoriza una tarea de OpenClaw:

1. Home Assistant responde inmediatamente con la frase configurada.
2. Cierra la conversación de voz para evitar eco y bucles.
3. Muestra la confirmación escrita en View Assist.
4. Envía el pedido a OpenClaw en segundo plano.
5. OpenClaw entrega el resultado por WhatsApp.

La protección anti-eco de la versión 0.2.3 se conserva.

## View Assist

La secuencia visual sigue siendo configurable:

```text
Respuesta del agente
        ↓
Demora inicial, predeterminado 0,8 s
        ↓
Vista info + respuesta escrita, predeterminado 3 s
        ↓
Vista relacionada, predeterminado 4 s
        ↓
Retorno de View Assist
```

Las rutas pueden ser relativas, por ejemplo `info`, `weather`, `camera`, `music` o `intent`, o absolutas como `/view-assist/info`.

## Frases de cierre

Valores predeterminados:

```text
chau
gracias
ok
bueno
hasta luego
```

La coincidencia exige que toda la frase sea de cierre. Por eso “gracias” termina, pero “gracias por apagar la luz” continúa normalmente.

## Instalación o actualización

1. Descomprimir el ZIP.
2. Reemplazar completamente:

```text
/config/custom_components/assist_router
```

3. Reiniciar Home Assistant.
4. Abrir **Assist Router → Configurar → Tres agentes y filtro de domótica**.
5. Seleccionar el agente general rápido.
6. Revisar **Clasificador del agente general**.

No hace falta borrar ni volver a crear la integración.

## Diagnóstico

En **Ajustes → Sistema → Registros**, buscar `assist_router`. Los registros indican la ruta seleccionada, el agente general usado, las derivaciones autorizadas a OpenClaw y la secuencia de View Assist.
