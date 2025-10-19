## Portafolio Tracker — Torpedo rápido

### Contexto general
- Repo `osamabindrummer/portafolio-tracker` alojado en GitHub, publicado vía GitHub Pages con un flujo de deploy basado en Actions.
- Scripts Python (`scripts/fetch_data.py`) generan `data/latest.json`; la UI consume solo ese JSON y se ejecuta como sitio estático.
- Eliminado el antiguo heatmap de Finviz (mapa PNG); ahora solo se mantiene el embed de TradingView como referencia de mercado.

### Git y GitHub CLI
- Crear repo local y primer commit:
  ```bash
  cd /Users/dsj-air/Codex/portafolio-tracker
  git init
  git add .
  git commit -m "chore: initial project snapshot"
  ```
- Autenticarse con la CLI:
  ```bash
  gh auth login --hostname github.com --web --scopes repo,workflow
  ```
- Crear y publicar el repo remoto:
  ```bash
  gh repo create osamabindrummer/portafolio-tracker --source=. --public --push
  ```
- Flujo de cambios: `git status` → `git add` → `git commit` → `git push`.

### Workflows clave
- `Update data` (`.github/workflows/update-data.yml`)
  - Corre en cron `0 9 * * 1,3,5` (lunes, miércoles y viernes 09:00 UTC, equivalente a las 06:00 en Chile mientras la diferencia sea -3 h) y manual con `workflow_dispatch`.
  - Pasos: checkout → Python 3.11 → instalar deps → `python scripts/fetch_data.py` → `python -m json.tool data/latest.json` → auto-commit del JSON.
  - Ejecutar manualmente:
    ```bash
    gh workflow run update-data.yml
    gh run watch --exit-status
    ```
  - Ver runs recientes: `gh run list --workflow update-data.yml`.
- `Deploy to GitHub Pages` (`.github/workflows/deploy.yml`)
  - Empaqueta el sitio y usa `actions/deploy-pages`.
  - Para habilitar Pages: Settings → Pages → “Build and deployment: GitHub Actions”, o vía CLI:
    ```bash
    gh api repos/osamabindrummer/portafolio-tracker/pages --method POST -F build_type=workflow
    ```
  - Ejecutar:
    ```bash
    gh workflow run deploy.yml
    gh run watch --exit-status
    gh deployment list --environment=github-pages
    gh api repos/osamabindrummer/portafolio-tracker/pages --jq '.html_url'
    ```

### Operación del sitio
- Botón **Obtener datos** en la página funciona solo cuando corre el servidor local:
  ```bash
  python3 scripts/dev_server.py
  ```
- Para datos “en la nube” usa los workflows; la página se refresca en cualquier dispositivo tras cada commit en `main`.
- Refrescar manualmente desde el navegador (p. ej. en iPhone) para cargar el JSON más reciente; usar `pull-to-refresh` o agregar query `?v=YYYYMMDD`.

### Ajustes recientes importantes
- `fetch_data.py` ya no emite la sección `heatmap`; `assets/js/state.js` actualiza el estado acorde.
- `update-data.yml` solo versiona `data/latest.json` para evitar fallos cuando no existe la imagen.
- Documentación (`plan.md`, `formato_json.md`, `changelog.md`) refleja la nueva arquitectura sin Finviz.

### Preguntas frecuentes
- **¿Cómo cambio la frecuencia del cron?** Edita la línea `cron: "0 9 * * 1,3,5"` en `update-data.yml`, realiza commit y push.
- **¿Qué límites y cobros tiene GitHub Actions?** Cada ejecución consume “minutes”; en planes gratuitos son 2 000 min/mes para repos privados (públicos ilimitados). No hay cobro extra mientras estés dentro del cupo; si te acercas al límite verás avisos en Billing, y solo se restringe al excederlo. El cron actual (3 veces por semana) está muy por debajo de cualquier límite y también respeta los topes de GitHub/yfinance.
- **¿Puedo disparar el workflow desde el sitio?** No directamente; la API de GitHub exige autenticación. Solución sería un backend propio que actúe como proxy.
- **¿Qué pasa si el workflow modifica el JSON?** Haz `git pull` después del run; el auto-commit vive en `main`.

### Flujo rápido para publicar cambios
- Inspeccionar estado: `git status`
- Preparar commit: `git add .github/workflows/update-data.yml`
- Registrar cambio: `git commit -m "chore: run data update three times per week"`
- Subir al remoto: `git push`

Mantén este torpedo como referencia rápida para flujos de despliegue, automatización de datos y limitaciones del botón de obtención. Actualízalo cuando cambie el pipeline o se agreguen nuevos flujos.***
