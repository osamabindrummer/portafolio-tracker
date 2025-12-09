# Changelog

## 2025-12-08
- Ajustado el portafolio de Racional tras la absorción de CFMDIVO: `CFMITNIPSA` aumenta a 20 % y se elimina `CFMDIVO` en `scripts/fetch_data.py`, manteniendo la suma de pesos en 1.0 y soportando el modo offline.
- Regenerado `data/latest.json` sin el ticker eliminado y revalidados los histogramas/series para reflejar solo cinco ETFs en la plataforma.
- Actualizada la UI (mapa `RACIONAL_DISPLAY_NAMES`) y la documentación (`plan.md`) para describir la nueva composición del pack ETF.

## 2025-10-19

### Tarea 1
- Rediseñada la cabecera con botones separados “Obtener datos” y “Actualizar página”, mensajes de estado accesibles y comportamiento responsive tanto en desktop como móvil.
- Añadido servidor local `scripts/dev_server.py` y lógica de reintento en la UI para ejecutar manualmente `scripts/fetch_data.py`, evitando errores 501.
- Ampliado `scripts/fetch_data.py` tomando como base `etf_tracker.py`: nuevos helpers para series diarias, cálculo consistente de variaciones (día, 1M, 1Y, 5Y), histogramas filtrados y generación offline con ~6 años de precios.
- Actualizadas métricas rápidas y tablas para mostrar variación mensual, retorno 1Y y 5Y ponderados solo con holdings válidos; se renombró «Racional - Pack ETF» y se mejoró la legibilidad en móviles.
- Integrado el histograma de variación mensual junto a los retornos de 1 y 5 años en Chart.js, manteniendo datos 5Y visibles tras cargar la página.

## 2025-10-18
- Renovado el encabezado: icono 💸 integrado, botón `Actualizar datos` con estilo iOS y fecha de refresco bajo el botón.
- Reestructuradas las métricas rápidas para mostrar simultáneamente Racional y Fintual con logos, tarjetas rectangulares y nuevos gradientes por plataforma.
- Mejorados los gráficos: selector de plataforma dentro de la barra de herramientas, modo por defecto «Retorno 1 año», colores únicos por ticker, leyendas simplificadas y ajustes de escala responsivos.
- Reorganizado «Detalle de holdings»: tablas separadas por plataforma (con enlace externo a la cartera de Fintual), columnas centradas y ticks enlazados a Yahoo Finance; renombrados `display_name` de CFMITNIPSA.SN, CFIETFCC.SN y CFMDIVO.SN.
- Sustituido el antiguo mapa estático por el widget TradingView en «🎯 Mis acciones», ampliando su contenedor.
- Retocado subtítulos de secciones y múltiples detalles visuales (gradientes, espaciados, layout móvil).
- Actualizados `README.md` y `data/latest.json` para reflejar la nueva UI y los nombres de instrumentos.

## 2025-10-16
- 19:51 (-03) Paso 1: Creada la estructura base del proyecto (`index.html`, carpetas `assets/`, `data/`, `scripts/`, archivos JS iniciales y `data/latest.json` placeholder).
- 19:56 (-03) Paso 2: Implementado `scripts/fetch_data.py` con modo offline/online, añadido `requirements.txt` y generado `data/latest.json` inicial usando datos deterministas.
- 19:57 (-03) Paso 3: Ajustado `formato_json.md` para documentar valores `null` en datasets y el origen offline de datos de ejemplo.
- 19:57 (-03) Paso 4: Configurado workflow `.github/workflows/update-data.yml` con ejecución manual/cron, instalación de dependencias y commit automático de `data/latest.json`.
- 20:00 (-03) Paso 5: Montado layout base en `index.html` con secciones, estilos responsivos y placeholders en UI/JS para métricas, tablas, gráficos y bloque de mercado.
- 20:02 (-03) Paso 6: Integrada Chart.js con datasets dummy para línea 5Y y barras 1Y/5Y, removiendo placeholders y configurando estilos básicos.
- 20:10 (-03) Paso 7: Conectada la UI al `data/latest.json` real (state loader, selector de plataformas, métricas, tabla y gráficos dinámicos), habilitando refresh manual y manejo de estados.
- 20:11 (-03) Paso 8: Añadido placeholder para contenido de mercado externo, lógica de fallback en la UI y estilos para mensaje alternativo cuando no haya embed disponible.
- 20:13 (-03) Paso 9: Ejecutada validación rápida de pesos/JSON, normalizados los pesos de Fintual en `scripts/fetch_data.py`, regenerado `data/latest.json` y ajustados estilos responsivos para móviles.
- 20:14 (-03) Paso 10: Añadido workflow de deploy (`deploy.yml`) y documentado flujo en `README.md` (uso de Actions, Pages y generación de datos).
- 20:40 (-03) Paso 11: Simplificada la visualización de gráficos (selector único, canvas compartido) y optimizados estilos para mejorar rendimiento en el prototipo.
- 20:34 (-03) Paso 11: Ajustado el consumo de Chart.js para cargarlo como script global (CDN UMD) y evitar errores 404 en navegadores.
