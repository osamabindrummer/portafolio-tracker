# Portafolio Tracker

Sitio estático para visualizar y comparar mis inversiones en Racional y Fintual. El frontend consume el archivo `data/latest.json` generado por un script de Python y publicado mediante GitHub Actions.

## Estructura principal

- `index.html`: Prototipo de la UI (selector de plataforma, métricas comparadas, gráficos y widget TradingView).
- `assets/css/styles.css`: Estilos responsivos y tokens de diseño.
- `assets/js/`: Código JavaScript modular (`app`, `state`, `ui`, `charts`).
- `data/latest.json`: Fuente de datos que alimenta la UI.
- `scripts/fetch_data.py`: Genera `data/latest.json` (modo en línea y modo offline determinista).
- `.github/workflows/update-data.yml`: Actualiza `data/latest.json` y commitea los cambios.
- `.github/workflows/deploy.yml`: Publica el sitio en GitHub Pages.
- `changelog.md`: Registro de cambios paso a paso durante la implementación del plan.

## Requisitos locales

- Python 3.9 o superior.
- `pip` para instalar dependencias (`requirements.txt`).

## Generar datos localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/fetch_data.py --offline   # usa datos deterministas para probar la UI
# python scripts/fetch_data.py           # (requiere yfinance y conexión a internet)
```

El script almacenará la última ejecución en `data/latest.json`; la UI consume directamente los datos sin dependencias externas.

## Workflows de GitHub Actions

### `update-data.yml`
- Disparadores: `workflow_dispatch` (manual) y cron diario (09:00 CL local).
- Pasos: checkout, instalar dependencias, ejecutar `scripts/fetch_data.py`, validar el JSON y commitear el resultado.

### `deploy.yml`
- Disparadores: `workflow_dispatch` y `push` a `main`.
- Pasos: checkout, validar que `data/latest.json` exista, preparar artefacto y desplegar en GitHub Pages con `actions/deploy-pages`.
- Permisos configurados para escritura en Pages (`pages: write`) e ID token (OIDC).

Para activar Pages, ve a **Settings → Pages** y selecciona la opción “GitHub Actions” como fuente. El workflow `deploy.yml` publicará la última versión del sitio.

## Flujo recomendado

1. Ejecutar `scripts/fetch_data.py` localmente (opcional) para validar cambios.
2. Commits y push a `main`.
3. Lanzar `Update data` manualmente si necesitas refrescar `data/latest.json`.
4. El workflow `deploy.yml` se activará con cada push a `main` y publicará el sitio en Pages.

## Próximos pasos

- Conectar más fuentes de datos (o automatizar descargas de nuevos widgets) en `scripts/fetch_data.py`.
- Añadir tests con `pytest` para validar cálculos y esquema del JSON.
- Ejecutar Lighthouse y registrar métricas de performance/accesibilidad.
