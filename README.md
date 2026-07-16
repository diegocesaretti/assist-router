# Assist Router 0.2.0 para Home Assistant

Agente frontal para Assist que deriva el texto del STT a un agente de domótica o a OpenClaw. La rama doméstica puede abrir en View Assist una vista relacionada con la respuesta.

## Qué cambia en 0.2.0

- La configuración ya no usa el campo confuso `categoria|ruta|palabras`.
- **Cada vista tiene su propia pantalla** con:
  - activar o desactivar;
  - ruta;
  - palabras asociadas.
- Las rutas pueden ser relativas, por ejemplo `weather`, `camera` o `intent`.
- El router obtiene el dashboard base del satélite View Assist y arma la ruta completa automáticamente.
- La respuesta del agente tiene prioridad para seleccionar la vista.
- Si la respuesta es demasiado corta, por ejemplo “Listo”, se usa el texto original del STT como respaldo.
- Se reforzó la detección del satélite mediante `device_id`, `satellite_id`, `mic_device_id`, `voice_device_id` y la entidad del micrófono.
- La llamada a `view_assist.navigate` se realiza dentro de una tarea independiente y espera la confirmación del servicio para registrar errores reales.
- Las configuraciones de la versión 0.1.x se convierten automáticamente al nuevo modelo al abrir las opciones.

## Flujo

```text
STT
 └─ Assist Router
     ├─ contiene una palabra del filtro principal
     │   └─ agente de domótica / Gemini
     │       ├─ devuelve la respuesta para TTS
     │       ├─ clasifica la respuesta
     │       ├─ usa el STT como respaldo si la respuesta no aporta contexto
     │       └─ abre la vista relacionada en el mismo satélite
     └─ no contiene palabras del filtro
         └─ responde inmediatamente
             ├─ abre la vista de procesamiento, si está activada
             └─ ejecuta OpenClaw en segundo plano
```

## Lista predeterminada del filtro principal

```text
luz
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
recordatorio
```

La comparación usa palabras completas, ignora mayúsculas y elimina tildes antes de comparar.

## Menú de configuración

Abrí:

```text
Ajustes → Dispositivos y servicios → Assist Router → Configurar
```

La pantalla principal muestra secciones independientes:

- **Agentes y filtro principal**
- **OpenClaw**
- **View Assist: ajustes generales**
- **Clima y tiempo**
- **Aire y calefacción**
- **Cámaras**
- **Alarmas y recordatorios**
- **Música y multimedia**
- **Listas y tareas**
- **Deportes**
- **Domótica general**

Cada vista tiene tres campos simples:

```text
Abrir esta vista: sí/no
Ruta: weather
Palabras: una por línea
```

## Rutas relativas

Es recomendable escribir solo el nombre de la vista:

```text
weather
camera
music
intent
```

Si el sensor View Assist informa que su dashboard es `/view-assist`, el router convierte `weather` en:

```text
/view-assist/weather
```

Si otro satélite usa `/panel-cocina`, la misma configuración se convierte en:

```text
/panel-cocina/weather
```

También se acepta una ruta absoluta, por ejemplo:

```text
/view-assist/weather
```

Las rutas absolutas se usan sin modificación.

## Vistas activadas por defecto

Se activan solo las vistas más comunes:

- Clima y tiempo: `weather`
- Cámaras: `camera`
- Música y multimedia: `music`
- Domótica general: `intent`
- OpenClaw: `info`

Las vistas opcionales quedan desactivadas hasta confirmar que existen en el dashboard:

- Aire y calefacción: `thermostat`
- Alarmas y recordatorios: `alarm`
- Listas y tareas: `list`
- Deportes: `sports`

Esto evita navegar a páginas inexistentes.

## Cómo se selecciona una vista

El router suma coincidencias por categoría:

1. Las palabras presentes en la **respuesta final** tienen mayor peso.
2. Las palabras del **pedido original** sirven de respaldo.
3. Gana la categoría con mayor cantidad de coincidencias.
4. Las categorías desactivadas se ignoran.

Ejemplo:

```text
Pedido: “Prendé la luz del living”
Respuesta: “Listo”
```

Aunque la respuesta no contenga “luz”, el router usa el pedido como respaldo y abre la vista `intent`.

## OpenClaw

Cuando no hay palabras del filtro principal:

1. Home Assistant responde inmediatamente.
2. El pedido se envía a OpenClaw en segundo plano.
3. Se añade la instrucción configurada para entregar el resultado por WhatsApp.
4. Puede abrirse una vista relativa como `info`.

## Actualización desde 0.1.3

1. Descomprimí el ZIP.
2. Reemplazá completamente:

```text
/config/custom_components/assist_router
```

por la carpeta nueva incluida en el paquete.

3. Reiniciá Home Assistant completamente.
4. Entrá a **Assist Router → Configurar**.
5. Revisá primero **View Assist: ajustes generales**.
6. Entrá en cada vista que realmente tengas instalada y verificá su nombre de ruta.

No hace falta borrar la entrada de integración ni volver a elegir los agentes.

## Diagnóstico

Buscá `assist_router` en:

```text
Ajustes → Sistema → Registros
```

Los mensajes de depuración incluyen:

- categoría elegida;
- palabras coincidentes en la respuesta;
- palabras coincidentes en el STT;
- entidad View Assist seleccionada;
- ruta configurada;
- ruta final resuelta.

Un error de navegación visual no interrumpe la respuesta por voz.
