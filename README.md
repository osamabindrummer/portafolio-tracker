# Portafolio Tracker

Aplicación estática con HTML, CSS y JavaScript para comparar componentes de carteras de Racional y Fintual. Las funciones Python de Vercel consultan cotizaciones e indicadores; Vercel Blob conserva snapshots. No requiere un framework de frontend ni una base de datos.

## Arquitectura

- `index.html` y `assets/`: vista principal con métricas, tablas y gráficos.
- `datos.html`: página de datos y metodología, enlazada desde el extremo derecho del pie de página; reúne resultados de actualización, cobertura, fechas y advertencias. El último intento se conserva durante la sesión del navegador.
- `scripts/fetch_data.py`: configuración de carteras y descarga de históricos.
- `scripts/portfolio.py`: métricas, gráficos, formato compacto y respuesta pública.
- `scripts/validate_json.py`: validación de estructura y coherencia.
- `backend/portfolio_refresh.py`: calidad, enfriamiento e indicadores.
- `backend/storage.py`: archivos locales atómicos, Blob y recuperación.
- `api/`: handlers compartidos por Vercel y el servidor local.
- `data/latest.json`: semilla real compacta; un histórico por símbolo.
- `public/indicators/latest.json`: semilla de indicadores.

Los archivos compactos usan `schema_version: 2`. El lector también admite snapshots anteriores. Las métricas y los gráficos se reconstruyen desde los precios; la respuesta pública omite históricos internos. No se convierten monedas ni se normalizan los pesos configurados al 100 %.

## Interpretación de las métricas

Los retornos son cambios acumulados de cierres ajustados en la moneda de cotización. Se muestran promedios ponderados sobre los componentes con datos para cada período, con su peso cubierto disponible en Datos y metodología. No equivalen a la rentabilidad histórica efectiva de un fondo: no incorporan comisiones, cambios de cartera ni conversión cambiaria.

- Un mes significa los últimos 30 días; uno y cinco años usan aniversarios de calendario.
- Se admite una diferencia máxima de siete días alrededor del inicio por cierres de mercado y límites de consulta. Una observación anterior al objetivo tampoco puede estar alejada más de siete días.
- Sin cobertura del período, se muestra `--`; nunca se sustituye por el retorno desde el inicio.
- La página Datos y metodología muestra por instrumento la fecha de cotización y una advertencia si supera siete días.
- La fecha de generación del snapshot, la de composición y las fechas de precios son distintas. La compactación conserva las fechas históricas originales.
- Los primeros ocho holdings de Risky Norris pueden sumar menos del 100 % del patrimonio. El resto no se estima.

CFIETFGE.SN mantiene la verificación específica del histórico de Yahoo con cotización fechada y operaciones por hora. No se interpolan precios ni se inventan ajustes; los eventos corporativos no verificables impiden la recuperación. Las advertencias se conservan y se consultan en Datos y metodología.

## Actualizaciones y seguridad

- Los endpoints HTTP sólo admiten `mode=online`; los ejemplos offline se generan exclusivamente mediante CLI en un archivo separado.
- El botón público respeta `REFRESH_COOLDOWN_SECONDS` (600 segundos por defecto).
- `force=true` requiere `Authorization: Bearer <CRON_SECRET>`; el secreto nunca forma parte del frontend.
- El cron siempre exige ese secreto, incluso cuando la variable falta: sin configuración responde 401.
- Las actualizaciones públicas siguen siendo públicas. El enfriamiento es una comprobación sobre el snapshot, no un límite distribuido ni autenticación de visitantes; para restringirlas por completo se necesita autenticación o un límite en la plataforma.
- No se anuncia éxito ni se guarda si menos del 80 % del peso configurado de **cada** plataforma tiene históricos recientes descargados. La antigüedad máxima es de siete días.
- Descargas vacías, que retroceden de fecha o pierden más del 20 % del histórico conservan los precios anteriores con advertencia. Esos datos conservados no cuentan como descarga reciente para el umbral de calidad.
- Un fallo de actualización conserva las tablas visibles. Los errores parciales identifican el dataset afectado en Datos y metodología, sin añadir avisos extensos a la vista principal.
- Las cotizaciones tienen un presupuesto de espera de 25 segundos con cuatro consultas simultáneas; los indicadores comparten 15 segundos entre sus dos fuentes. Las operaciones de almacenamiento añaden su propio tiempo. Vercel mantiene un máximo de 60 segundos por función. Una observación de indicadores no puede exceder siete días para UF/dólar, 45 para UTM o 62 para IPC; una respuesta antigua provoca el intento con la siguiente fuente.

Blob conserva las últimas cinco versiones por dataset. La lectura pagina el listado y, si falla el snapshot más reciente, intenta versiones anteriores. Si Blob no está disponible utiliza la semilla local y expone una advertencia. La limpieza sólo se intenta después de guardar una versión nueva; un fallo de limpieza no invalida la escritura. Las escrituras locales usan reemplazo atómico.

## Desarrollo local

Prechecks: trabajar desde la raíz del repositorio, disponer de Python **3.11.5–3.14** y dejar libre `127.0.0.1:3001`. El entorno anterior de este equipo usa Python 3.9; se conserva intacto. El entorno para revisión es `.venv-review`.

1. Crear el entorno e instalar las versiones verificadas:

```sh
python3.11 -m venv .venv-review
.venv-review/bin/python -m pip install -r requirements.lock
```

2. Iniciar la aplicación:

```sh
./scripts/dev.sh
```

El lanzador usa `.venv-review` por defecto. Para otro entorno compatible, indicar `PORTFOLIO_PYTHON=/ruta/al/python`. Verifica versión, dependencias y puerto antes de arrancar. No cambia automáticamente de dirección ni abre el navegador. Debe aparecer `Portafolio Tracker local: http://127.0.0.1:3001`.

3. Abrir [la revisión local](http://127.0.0.1:3001/). El servidor incluye `X-Portfolio-App: portafolio-tracker-local` en sus respuestas como señal de identidad. Detener con `Ctrl+C`.

El servidor usa exclusivamente almacenamiento local y los handlers reales de `api/`. No carga credenciales remotas ni necesita Vercel CLI; sirve sólo la interfaz y sus assets. Esto evita el fallo `DEV_BUILDER_RESULT_HAS_MAXDURATION` observado con Vercel CLI 63.1.2 y el builder Python al usar `vercel dev`. El despliegue continúa usando Vercel Functions.

## Validación

Desde la raíz:

```sh
.venv-review/bin/python -m unittest discover -s tests -v
.venv-review/bin/python -m scripts.validate_json data/latest.json
.venv-review/bin/python -m compileall -q backend api scripts
node --test tests/*.test.mjs
for file in assets/js/*.js; do node --check "$file"; done
```

Las pruebas simulan caídas externas y almacenamiento remoto; no escriben en el Blob real. En `.github/workflows/check.yml` se ejecutan en cada push y pull request. `update-data.yml` sigue siendo exclusivamente manual y ejecuta los scripts como módulos.

Para generar ejemplos sin tocar la semilla:

```sh
.venv-review/bin/python -m scripts.fetch_data --offline --output /tmp/portfolio-example.json
```

Para actualizar cotizaciones locales reales, usar `python -m scripts.fetch_data` con el intérprete del entorno. Esta operación sí modifica `data/latest.json` cuando supera los controles. No es necesaria para revisar la interfaz.

Se usan yfinance, pandas y el paquete específico `vercel-blob`; no se instala el conjunto de servicios de Vercel. Todas las versiones de ejecución, incluidas las transitivas, se fijan en `requirements.lock`. Tanto `requirements.txt` como `pyproject.toml` toman ese archivo para reproducir la misma instalación en desarrollo, validación y Vercel. Una actualización de dependencias debe volver a generar el lock y pasar las pruebas, incluida la compatibilidad con Blob.

## Configuración de producción

Copiar los nombres de `.env.example` al configurar Vercel; no versionar valores secretos.

- `BLOB_READ_WRITE_TOKEN`: requerido para almacenamiento remoto.
- `CRON_SECRET`: requerido para cron y solicitudes forzadas.
- `REFRESH_COOLDOWN_SECONDS=600`.
- `REFRESH_ALL_INCLUDES_INDICATORS=true`.
- `CRON_REFRESH_INDICATORS=true`.

Vercel usa Python 3.12, fijado en `.python-version`. No configurar `PORTFOLIO_STORAGE=local` en producción. El adaptador informa por separado la ausencia de token y la incompatibilidad del SDK. El cron de `vercel.json` ejecuta lunes, miércoles y viernes a las 09:00 UTC.

Endpoints: `GET /api/data/latest`, `GET /api/indicators`, `POST /api/refresh-data`, `POST /api/refresh-indicators`, `POST /api/refresh-all`, `GET /api/cron/refresh`.

La publicación requiere autorización explícita. Antes de desplegar, revisar el diff y las pruebas. Después de publicar, verificar lectura/escritura real de Blob, protección del cron y respuesta pública. La validación local con almacenamiento simulado no demuestra esa integración remota.

## Actualización manual de Risky Norris

La skill versionada en [.agents/skills/actualizar-risky-norris/SKILL.md](.agents/skills/actualizar-risky-norris/SKILL.md) se usa sólo cuando el usuario solicita actualizar esa composición. El helper `python -m scripts.update_fintual` admite la semilla compacta y conserva históricos, fuentes y fechas. Esta revisión no cambia la cartera configurada ni su fecha oficial.

[Guía de Linux](LINUX.md).
