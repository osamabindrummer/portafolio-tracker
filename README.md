# Portafolio Tracker

https://osamabindrummer.github.io/portafolio-tracker/

Sitio estático con HTML, CSS y JS para visualizar y comparar mis inversiones en Racional y Fintual a partir de información de [Yahoo Finance](https://finance.yahoo.com/). El frontend consume el archivo `data/latest.json` generado por un script de Python y publicado mediante GitHub Actions los días lunes, miércoles y viernes a las 6 am.

## Qué ofrece

- Comparación simultánea de portafolios Racional y Fintual (métricas ponderadas, retornos y variaciones).
- Tablas con holdings detallados, pesos y enlaces a Yahoo Finance.
- Gráficos interactivos impulsados por Chart.js.
- Widget embebido de TradingView para desempeño de principales acciones individuales.

## Estructura del repositorio

- `index.html`: Shell del sitio y punto de entrada.
- `assets/css/styles.css`: Estilos y tokens responsivos.
- `assets/js/`: Lógica de UI, estado y gráficos (`app`, `state`, `ui`, `charts`).
- `data/latest.json`: Dataset que alimenta la aplicación.
- `scripts/fetch_data.py`: Generador del JSON (script Python).
- `.github/workflows/`: Automatizaciones de generación de datos y despliegue en GitHub Pages.
- `changelog.md`: Bitácora de cambios relevantes.

## Requisitos

- Python 3.9 o superior.
- `pip` (incluido con Python) para instalar `requirements.txt` (`yfinance`, etc.).

## Puesta en marcha local

Para trabajar localmente en VS Code:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/fetch_data.py          # usa cotizaciones reales (requiere internet)
# python3 scripts/fetch_data.py --offline   # alternativa determinista sin red (datos inventados)
python3 -m http.server 8000
```

Luego se visita `http://localhost:8000/index.html`. El sitio es 100 % estático, pero necesita un servidor local para cargar assets y JSON sin problemas de rutas/CORS.

En este proyecto no se usa `npm install` ni `npm run dev` porque no hay bundlers ni toolchain de Node: todo se resuelve con Python + servidor estático.

## Automatización (GitHub Actions)

- `update-data.yml`: Ejecuta `scripts/fetch_data.py`, valida el JSON y commitea el resultado (cron diario + disparo manual).
- `deploy.yml`: Publica `index.html` y assets en GitHub Pages cada vez que se hace push a `main` o se lanza el workflow manualmente.

Activa GitHub Pages en **Settings → Pages** usando la opción “GitHub Actions” para que el despliegue quede operativo.
