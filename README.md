# Assist Router 0.1.1

Agente de conversación para Home Assistant que deriva cada texto recibido por Assist:

- Si contiene alguna palabra clave de domótica, lo envía al agente configurado como **Domótica**.
- Si no contiene ninguna, lo envía al agente configurado como **OpenClaw**.

## Instalación

1. Copiar la carpeta `custom_components/assist_router` dentro de `/config/custom_components/`.
2. Reiniciar Home Assistant por completo.
3. Ir a **Ajustes → Dispositivos y servicios → Añadir integración**.
4. Buscar **Assist Router**.
5. Elegir ambos agentes y editar la lista de palabras.
6. En el pipeline principal de Assist, seleccionar el agente **Assist Router: Router**.

## Cambio de la versión 0.1.1

Se reemplazó el selector moderno de agentes por menús desplegables clásicos. Esto corrige el formulario vacío que algunas versiones del frontend de Home Assistant mostraban con solamente el botón **Enviar**.

Las coincidencias se hacen por palabra completa, sin distinguir mayúsculas ni tildes.
