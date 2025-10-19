# Plan del proyecto: Portafolio Tracker

## 0. Contexto y objetivo
- Diseñar un sitio personal en GitHub Pages que funcione como tracker de mis inversiones.
- Mostrar evolución histórica y comparada de ETFs/acciones agrupadas por plataforma (Racional vs Fintual).
- Permitir actualización manual en la UI (botón) y mostrar el mapa de calor de Finviz (https://finviz.com/map.ashx).
- Mantener una experiencia ligera, clara y personalizada, priorizando exactitud de datos y claridad visual.

## 1. Decisiones confirmadas
- **Datos frescos**: GitHub Actions generará `data/latest.json` ejecutando un script Python (`yfinance` u otra fuente). El workflow corre a demanda o programado, guarda el archivo y lo commitea; el frontend solo lee ese JSON.
- **Stack UI**: Sitio estático puro con HTML + JavaScript nativo (ESM) + Chart.js (vía CDN) + CSS ligero (flex/utility propia). No se utilizarán bundlers ni frameworks.
- **Modelo de datos**: Un único JSON con toda la información necesaria para la UI según el formato descrito en `formato_json.md`. El frontend no interactúa directamente con proveedores de datos.

## 2. Fundamentos del repositorio
1. Definir estructura básica:
   - `index.html` (layout principal).
   - `assets/css/styles.css` (estilos compartidos).
   - `assets/js/app.js` (entry point) + módulos auxiliares (`charts.js`, `state.js`, `ui.js`).
   - `data/latest.json` (archivo generado por el workflow).
   - `scripts/fetch_data.py` y utilidades asociadas.
   - `.github/workflows/update-data.yml` para automatizar la actualización.
2. Configurar herramientas opcionales:
   - Prettier o ESLint para estilos de código (via `npm` o configuración manual).
   - `requirements.txt` para dependencias Python utilizadas en el script de datos.
3. Documentar en `README.md`:
   - Objetivo del proyecto.
   - Cómo ejecutar el script localmente.
   - Cómo forzar la actualización del workflow y desplegar en GitHub Pages.

## 3. Obtención y actualización de datos
### 3.1 Inventario de tickers y pesos
- Racional: `CFIETFGE (20%)`, `IYWCL (35%)`, `EEMCL (20%)`, `CFMITNIPSA (15%)`, `CFIETFCC (5%)`, `CFMDIVO (5%)`.
- Fintual (Risky Norris): `ESGV (28.94%)`, `FTEC (17.87%)`, `QQQM (17.16%)`, `SOXX (10.69%)`, `VGK (10.04%)`, `IAUM (7.32%)`, `KOMP (4.43%)`, `EPP (1.87%)`.

### 3.2 Flujo de generación `data/latest.json`
1. Implementar `scripts/fetch_data.py`:
   - Mapear tickers locales a los símbolos compatibles con `yfinance` o la API elegida.
   - Descargar precios ajustados de los últimos 5 años.
   - Calcular retornos 1Y y 5Y, variación diaria y series normalizadas (base 100) por ETF.
   - Construir el JSON siguiendo `formato_json.md` y escribirlo en `data/latest.json`.
   - Generar imagen estática del mapa Finviz (p. ej. con Playwright/Selenium + screenshot) y guardarla en `assets/img/finviz-map.png`.
   - Registrar timestamp de generación.
2. Validar manejo de errores:
   - Retries ante fallos de red.
   - Logs descriptivos para monitorear el workflow.
   - Caída graciosa si algún ticker no posee datos (ej. marcarlo con bandera `missing_data`).
3. Configurar workflow `update-data.yml`:
   - Disparador manual (`workflow_dispatch`) + cron opcional (ej. diario).
   - Pasos: configurar Python, instalar dependencias, ejecutar script, validar JSON, commitear y push.
   - Usar `actions/checkout` con permisos de escritura y `actions/setup-python`.
4. (Opcional) Añadir script local `make update-data` para permitir la ejecución manual y commit desde laptop antes de deploy.

## 4. Arquitectura frontend
1. Estructura HTML:
   - Header con branding personal, selector de plataforma y botón “Actualizar datos”.
   - Sección de métricas rápidas (cards con pesos, retorno 1Y/5Y).
   - Panel principal con gráficos: línea 5Y, histogramas (1Y y 5Y) y tabla.
   - Sección final con embed del mapa Finviz y notas informativas.
2. JavaScript modular:
   - `state.js`: carga inicial del JSON, almacenamiento en memoria, control de plataforma activa.
   - `charts.js`: encapsular la configuración de Chart.js para línea e histogramas.
   - `ui.js`: render de cards, tabla, timestamp y manejo de eventos.
   - `app.js`: inicialización general, binding de eventos y refresco cuando se presiona “Actualizar”.
3. Consumo de datos:
   - `fetch('/data/latest.json', { cache: 'no-store' })` para evitar caché.
   - Al cambiar de plataforma, filtrar holdings desde `state`.
   - Reutilizar estructuras del JSON (sin transformaciones pesadas en runtime).
4. Manejo del botón “Actualizar datos”:
   - Re-descargar `latest.json` y refrescar UI; mostrar spinner y timestamp actualizado.
   - Comunicar en tooltip que la última actualización depende del workflow (no instantáneo).

## 5. Diseño de UI/UX
1. Identidad visual:
   - Colores base sobrios con acentos diferenciados (Racional vs Fintual).
   - Tipografía legible (ej. Inter / system).
2. Distribución:
   - Layout responsive con CSS Grid/Flex.
   - Navbar fija opcional para acceso rápido al selector de plataformas.
3. Interacciones:
   - Tooltips en gráficos (Chart.js los provee).
   - Animaciones suaves (transparencia/scale) evitando saturar la experiencia.
   - Indicadores claros cuando no hay datos disponibles.
   - Mostrar fecha de la imagen del mapa Finviz y enlace a la versión interactiva.
4. Accesibilidad:
   - Contraste adecuado, orden lógico en el DOM, focus states visibles.

## 6. Integraciones y gráficos
1. Línea de tiempo (Chart.js `line`):
   - Dataset por ETF (normalizado a 100, 5 años).
   - Mostrar leyenda filtrable, tooltips con valor real y normalizado.
2. Histogramas (Chart.js `bar`):
   - Dos paneles: retorno 1Y y retorno 5Y.
   - Ordenar de mayor a menor, colorear según plataforma.
3. Tabla detallada:
   - Columnas: Ticker, Nombre, % Portafolio, Retorno 1Y, Retorno 5Y, Variación diaria.
   - Posibilidad de ordenar por columna (JS nativo).
4. Mapa tipo Finviz:
   - Workflow descarga imagen estática (PNG) del mapa usando navegador headless o API alternativa y la guarda como `assets/img/finviz-map.png`.
   - Frontend muestra la imagen con `<img>` y un enlace “Abrir en Finviz” para interacción completa.
   - Incluir texto auxiliar indicando fecha de actualización y limitaciones (imagen sin interacción).

## 7. Lógica de actualización y estados
1. Estados principales:
   - `loading`: mientras se carga `latest.json`.
   - `ready`: datos disponibles, renderizar componentes.
   - `error`: mostrar mensaje y opciones (reintentar o revisar workflow).
2. Timestamp:
   - Leer `generated_at` del JSON y mostrarlo en formato local.
   - Guardar en `localStorage` la última versión cargada para detectar cambios futuros.
3. Mensajería del botón:
   - Tooltip/nota que la actualización depende del último run del workflow.
   - Enlace al workflow en GitHub para lanzar actualización manual si se desea.

## 8. QA y validación
1. Validar script Python:
   - Tests unitarios ligeros para cálculos (usando `pytest`).
   - Validación del esquema JSON (usando `jsonschema` o script custom).
2. QA del frontend:
   - Pruebas manuales en navegadores principales (Chrome, Firefox, Safari móvil).
   - Verificar que Chart.js renderiza correctamente con datos reales y mocks vacíos.
3. Accesibilidad y performance:
   - Lighthouse en modo móvil/escritorio para revisar métricas básicas.
   - Revisión de peso del bundle (solo dependencias CDN necesarias).

## 9. Deploy en GitHub Pages
1. Configurar Pages desde `main` (carpeta `/` o `/docs` según preferencia).
2. Añadir workflow de deploy (`deploy.yml`) que:
   - Valide que `data/latest.json` exista.
   - Ejecute pruebas/lint opcionales.
   - Publique automáticamente en Pages (`actions/upload-pages-artifact` + `actions/deploy-pages`) o use `peaceiris/actions-gh-pages`.
3. Verificar URL final y actualizar README con instrucciones de acceso.

## 10. Mantenimiento y roadmap futuro
- Ajustar cron del workflow según la frecuencia deseada.
- Añadir métricas adicionales (drawdown, volatilidad, aportes) cuando haya datos.
- Expandir a vista histórica por plataforma (comparar retorno total).
- Incluir exportación CSV del portafolio o integración con Google Sheets.
- Considerar autenticación básica si más adelante se incluyen datos sensibles.

## 11. Checklist de arranque
- [x] Crear estructura base del repo (HTML, CSS, JS, carpetas `data/` y `scripts/`).
- [x] Implementar `scripts/fetch_data.py` y generar un `data/latest.json` inicial.
- [x] Escribir `formato_json.md` con el esquema de datos y ejemplos (este archivo).
- [x] Configurar workflow `update-data.yml` y probar un run manual.
- [x] Montar el layout HTML con los contenedores de secciones.
- [x] Integrar Chart.js y renderizar gráficos con datos dummy.
- [x] Implementar carga real desde `data/latest.json` y selector de plataformas.
- [x] Añadir el mapa de Finviz y mensaje alternativo si falla.
- [x] Realizar pruebas básicas (QA/Lighthouse) y pulir estilos responsivos.
- [x] Configurar deploy automático a GitHub Pages y documentar el proceso.

## 12. Notas para GitHub Pages (a futuro)
- Verificar el tipo de sitio que publicará GitHub Pages. Si es un Project Page (`/repo-name`), ajustar rutas relativas en `index.html` y en `assets/js/state.js` (prefijo opcional con `const basePath = window.location.pathname.replace(/index\.html$/, '')`).
- Asegurarse de que `data/latest.json` exista y se incluya en los commits; el workflow `update-data.yml` debe ejecutarse antes del deploy para que Pages sirva datos recientes.
- Confirmar que los assets servidos por CDN (p. ej. Chart.js) estén permitidos; si se requiere modo offline, empaquetar Chart.js en `assets/vendor/`.
- Validar en Pages que la petición `fetch('data/latest.json')` no se vea afectada por caché (usar `cache: 'no-store'` como ya está o añadir query param con versión).
