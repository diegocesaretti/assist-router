# Assist Router 0.4.0 para Home Assistant

Agente frontal para Assist con skills locales, domótica, consultas generales rápidas y OpenClaw en segundo plano. La versión 0.4.0 agrega reproducción natural de películas y series mediante Stremio Stream Bridge.

## Flujo

```text
STT
 └─ Assist Router
     ├─ frase de cierre exacta
     │   └─ termina la conversación
     ├─ frase que fuerza OpenClaw
     │   └─ confirmación inmediata + trabajo en segundo plano
     ├─ comando de película, serie o episodio
     │   └─ Stremio Stream Bridge
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


## Stremio por voz

La skill de Stremio se ejecuta antes del filtro de domótica, evitando que palabras como `poné` y `tele` terminen en el agente doméstico.

Ejemplos:

```text
Poné Matrix en la tele del living.
Poné la película Dune de 2021 en latino.
Poné Breaking Bad temporada dos capítulo tres en la pieza.
Quiero ver The Matrix.
```

Assist Router consume exclusivamente los servicios públicos de `stremio_stream_bridge`; no importa clases internas ni accede a su `runtime_data`.

El contrato esperado es:

```text
stremio_stream_bridge.resolve
stremio_stream_bridge.play
```

`resolve` debe devolver los estados `exact`, `ambiguous`, `not_found`, `series_needs_episode`, `episode_not_found`, `unsupported` o `error`. Cuando el resultado es exacto, el router llama a `play` en segundo plano y cierra la conversación para evitar que el audio de la película reactive el micrófono.

Cuando hay ambigüedad, acepta respuestas como:

```text
La segunda.
La de 2021.
Dune de 1984.
```

Para series conserva el contexto por conversación:

```text
— Poné Breaking Bad.
— ¿Qué temporada y capítulo?
— Temporada dos, capítulo tres.
```

La configuración se encuentra en:

```text
Assist Router → Configurar → Stremio y televisores
```

Ahí se configuran:

- entrada de Stream Bridge o selección automática;
- tele predeterminada opcional;
- aliases como `living, sala = media_player.tv_living`;
- cantidad máxima de alternativas;
- tiempo del diálogo de seguimiento;
- texto de confirmación con `{title}` y `{target}`;
- vista de View Assist, predeterminada `infopic`.

Si `resolve` todavía no está disponible, un pedido explícito de película o serie informa que falta esa función. Un comando multimedia ambiguo, como “Poné Calamaro en la tele”, evita la ruta de domótica y continúa hacia el agente general, dejando lugar a una futura skill de YouTube o Music Assistant.

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
Vista info + respuesta escrita
        ↓
Tiempo calculado por cantidad de palabras
        ↓
Vista relacionada, predeterminado 5 s
        ↓
Retorno de View Assist
```

El tiempo de lectura usa estos valores predeterminados:

- Mínimo: 3 segundos.
- Velocidad: 0,35 segundos por palabra.
- Máximo: 20 segundos.

La fórmula respeta siempre el mínimo y el máximo. Una respuesta de 20 palabras queda visible 7 segundos; una respuesta corta conserva 3 segundos.

Las rutas pueden ser relativas, por ejemplo `info`, `weather`, `camera`, `music` o `intent`, o absolutas como `/view-assist/info`.

## Navegación de configuración

Cada sección de **Configurar** ahora abre un menú intermedio con:

- **Editar configuración** o **Editar vista**.
- **← Volver** al menú principal.

Al guardar un formulario, los cambios se aplican y se vuelve automáticamente al menú principal, para seguir editando otras secciones sin cerrar y abrir la integración.

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
4. Abrir **Assist Router → Configurar → Stremio y televisores**.
5. Seleccionar la entrada de Stream Bridge y configurar los aliases de las teles.
6. Revisar **Tres agentes y filtro de domótica** y **Clasificador del agente general**.

No hace falta borrar ni volver a crear la integración.

## Diagnóstico

En **Ajustes → Sistema → Registros**, buscar `assist_router`. Los registros indican la ruta seleccionada, el agente general usado, las derivaciones autorizadas a OpenClaw y la secuencia de View Assist.


## 0.3.2: seguimiento y regreso seguro

- Las respuestas normales pueden dejar abierta una escucha de seguimiento.
- La vista temática se muestra 5 segundos por defecto.
- El regreso se hace explícitamente a `home`, nunca a la vista anterior.
- Una nueva frase invalida el regreso pendiente de la respuesta previa.
- El valor 0 deja la vista temática abierta sin retorno automático.


## 0.4.0: skill local de Stremio

- Detecta películas, series, temporadas, capítulos, perfil latino y subtítulos.
- Resuelve títulos mediante el servicio público `stremio_stream_bridge.resolve`.
- Reproduce mediante `stremio_stream_bridge.play` sin duplicar la lógica de streams.
- Pregunta ante títulos ambiguos y conserva el contexto del seguimiento.
- Permite aliases de televisores y una tele predeterminada.
- Muestra póster, estado y alternativas mediante atributos de View Assist.
- Cierra la escucha al iniciar reproducción para reducir activaciones por el audio de la TV.
- Si la integración de Stremio aún no expone `resolve`, el resto del router continúa funcionando.
