# Seguimiento del problema de actualización de datos

## Contexto y objetivo
La aplicación web expone un botón **"Actualizar datos"** que debe leer el archivo `data/latest.json` generado por el workflow nocturno de GitHub Actions. El archivo se actualiza con regularidad en el repositorio, pero la interfaz no refleja esos cambios de forma confiable.

## Síntomas observados
- En el inspector del navegador aparecen respuestas **HTTP 404** cuando se intenta consultar `https://raw.githubusercontent.com/osamabindrummer/portafolio-tracker/work/data/latest.json`.
- El mismo inspector muestra intentos de lectura sobre `https://osamabindrummer.com/portafolio-tracker/data/latest.json` que ocasionalmente fallan, por lo que el botón termina reutilizando la última respuesta exitosa.
- En pantalla se muestran dos mensajes consecutivos bajo el botón ("Última actualización …" y "Datos del …"), generando ruido visual y confundiendo sobre cuál es la hora vigente.

## Diagnóstico
1. **Branch codificado en metadata**: el documento `index.html` publica `<meta name="data-source:branch" content="work">`. Si el workflow ahora publica en `main`, cualquier intento de consultar `work` produce 404.
2. **Sin recordatorio del último endpoint válido**: incluso cuando el navegador descubre el endpoint correcto (por ejemplo usando el path relativo servido por GitHub Pages), la aplicación no persiste esa información; al siguiente refresco vuelve a probar con el branch inválido.
3. **Mensajería redundante**: al renderizar el estado "ready" se muestra un texto adicional "Datos del …" que duplica la fecha recién mostrada en "Última actualización".

## Opciones consideradas
1. **Modificar manualmente la metadata del branch** cada vez que cambie el workflow.
   - *Contras*: solución frágil, requiere intervención manual.
2. **Preferir siempre el archivo servido por GitHub Pages** (`DATA_URL`).
   - *Pro*: evita depender del branch.
   - *Contra*: GitHub Pages puede demorar en propagar el build; además, cuando se sirva desde otro entorno (por ejemplo un preview local) seguiríamos arriesgando datos obsoletos.
3. **Descubrir dinámicamente el branch correcto y recordar el último endpoint operativo**.
   - *Pro*: permite adaptarse a futuros cambios del workflow sin intervención manual.
   - *Contra*: requiere lógica extra y manejar límites de la API pública de GitHub.

## Plan de trabajo
1. **Construir una estrategia resiliente de endpoints**:
   - Leer repo/branch desde las etiquetas `<meta>` cuando existan.
   - Recordar en `localStorage` el último endpoint que funcionó.
   - Consultar la API pública de GitHub (`/repos/:owner/:repo`) para obtener `default_branch` y agregarlo a la lista de candidatos.
   - Incluir ramas de fallback (`main`, `master`) y la versión alojada en el mismo sitio (`DATA_URL`).
   - Consumir los endpoints en ese orden hasta encontrar un `200`, registrando cuál funcionó para futuros refrescos.
2. **Normalizar la mensajería del botón**:
   - Mantener el indicador "Última actualización".
   - Simplificar el estado "éxito" del botón a un texto neutro (por ejemplo "Datos cargados correctamente") para evitar duplicidad.
3. **Actualizar la documentación de seguimiento** (este archivo) con la decisión tomada y los cambios concretos aplicados.
4. **Probar la carga/actualización manualmente** en ambiente local para asegurar que el flujo utilice el nuevo orden de endpoints.

## Resultados esperados
- El botón "Actualizar datos" utiliza siempre la versión más reciente disponible en `data/latest.json`, sin depender de ajustes manuales cuando cambie la rama de publicación.
- Los mensajes bajo el botón quedan claros y sin duplicidad.
- Este documento queda como referencia para futuras sesiones si el problema reaparece.

## Implementación en esta sesión
- Se añadió una capa de descubrimiento de endpoints que:
  - Prioriza el último endpoint exitoso almacenado en `localStorage`.
  - Consulta la API pública de GitHub para obtener la `default_branch` y la guarda como pista futura.
  - Conserva ramas de respaldo (`main`, `master`) y el archivo servido por el propio sitio.
  - Registra el endpoint válido y la rama detectada en `localStorage` tras cada carga correcta.
- Se simplificó el estado visual del botón eliminando el texto redundante "Datos del …" y dejando un mensaje genérico de éxito.
- Se documentó el análisis y la solución para referencia futura en este mismo archivo.

## Verificación rápida
- Recarga inicial: confirma que se consulta el nuevo orden de endpoints y se almacena el primero que responde 200.
- Refresco manual: verifica que al presionar "Actualizar datos" se reutiliza el endpoint válido sin depender de la metadata desactualizada.
