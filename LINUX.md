# Desarrollo local en Linux

Desde la raíz del repositorio, con Python 3.11.5–3.14:

```sh
python3.11 -m venv .venv-review
.venv-review/bin/python -m pip install -r requirements.lock
./scripts/dev.sh
```

Abrir [Portafolio Tracker local](http://127.0.0.1:3001/). El puerto debe estar libre; el lanzador falla con un mensaje claro si está ocupado. No se requiere Vercel CLI ni credenciales remotas. Para elegir otro intérprete compatible, usar `PORTFOLIO_PYTHON=/ruta/al/python ./scripts/dev.sh`.

El servidor local comparte los handlers de producción y escribe sólo archivos locales. El botón de actualización puede consultar fuentes externas y modifica la semilla únicamente cuando supera los controles de calidad. Detener con `Ctrl+C`.

La validación completa y la interpretación de las métricas están en [README.md](README.md).
