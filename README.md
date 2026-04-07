# Portafolio Tracker

Sitio estático con HTML, CSS y JS para visualizar y comparar inversiones de Racional y Fintual. El hosting principal es **Vercel** y los datasets públicos se sirven desde funciones y almacenamiento persistente.

## Estado actual de la arquitectura

- `index.html` y `assets/`: frontend estático servido por Vercel.
- `api/data/latest`: entrega el dataset principal usado por la app.
- `api/indicators`: entrega el snapshot del banner económico.
- `api/refresh-data`: regenera `latest.json` en backend.
- `api/refresh-indicators`: vuelve a consultar fuentes públicas en backend.
- `api/refresh-all`: refresca ambos flujos con una sola llamada.
- `api/cron/refresh`: endpoint pensado para Vercel Cron.
- `Vercel Blob`: persistencia de los JSON generados en producción.
- `data/latest.json` y `public/indicators/latest.json`: quedan como semillas locales y fallback inicial.

## Por qué esta combinación

### `Vercel Functions`

Se usan porque permiten ejecutar backend sin montar un servidor propio. Es la opción más simple para un sitio que ya era estático.

### `Vercel Blob`

Se usa porque el filesystem de Vercel Functions es efímero y de solo lectura fuera de `/tmp`, así que no sirve para guardar datos que deban sobrevivir entre ejecuciones. Blob encaja mejor que KV o Postgres porque aquí estamos guardando archivos JSON completos, no datos relacionales ni claves sueltas.

### `Vercel Cron`

Queda preparado para automatizar refresh sin depender de GitHub Actions. En Hobby, Vercel limita los cron jobs a una frecuencia máxima de una vez por día, así que una pauta tipo lunes/miércoles/viernes sí es viable, pero una horaria no.

## Flujo de datos en producción

1. El frontend carga `/api/data/latest` y `/api/indicators`.
2. Esos endpoints leen desde Vercel Blob.
3. Si Blob todavía no tiene datos, se usa el JSON versionado dentro del repo como fallback.
4. Al hacer clic en `Actualizar datos`, la web llama `/api/refresh-all`.
5. Por defecto, ese refresh general también intenta refrescar el banner económico.
6. Al hacer clic en el banner económico, la web llama `/api/refresh-indicators`.
7. El backend consulta fuentes públicas y guarda un snapshot normalizado.

## Seguridad y límites reales

- El endpoint público de refresh no expone secretos, pero al ser público no puede distinguir entre tu clic y el de otro visitante.
- Para reducir abuso, el backend aplica un enfriamiento configurable con `REFRESH_COOLDOWN_SECONDS`.
- Si en el futuro quieres que sólo tú puedas refrescar manualmente, habrá que añadir autenticación real.

## Estructura relevante del repo

- `assets/js/app.js`: coordina carga, refresh global y refresh del banner.
- `assets/js/state.js`: consume `/api/data/latest` y `/api/refresh-all`.
- `assets/js/indicators-banner.js`: consume `/api/indicators` y `/api/refresh-indicators`.
- `backend/storage.py`: decide si usa archivos locales o Vercel Blob.
- `backend/portfolio_refresh.py`: lógica de refresh, fallback entre fuentes públicas y enfriamiento.
- `api/`: funciones serverless de Vercel.
- `vercel.json`: rewrites, funciones y cron.
- `.env.example`: plantilla de variables.

## Variables de entorno

### Requeridas en Vercel

- `BLOB_READ_WRITE_TOKEN`
- `CRON_SECRET`

### Recomendadas

- `REFRESH_COOLDOWN_SECONDS`
- `REFRESH_ALL_INCLUDES_INDICATORS=true`
- `CRON_REFRESH_INDICATORS=true`

Notas:
- `refresh-all` refresca indicadores por defecto, salvo que definas `REFRESH_ALL_INCLUDES_INDICATORS=false`
- el cron refresca indicadores por defecto, salvo que definas `CRON_REFRESH_INDICATORS=false`

### Opcionales para desarrollo local

- `PORTFOLIO_STORAGE=local`

### Indicadores usados en el banner

- UF: `F073.UFF.PRE.Z.D`
- UTM: `F073.UTR.PRE.Z.M`
- Dólar observado: `F073.TCO.PRE.Z.D`
- IPC anual: `F074.IPC.IND.Z.EP09.C.M`

### Flujo de fuentes públicas

1. El backend intenta primero `https://mindicador.cl/api`.
2. Si falla, intenta `https://findic.cl/api`.
3. Calcula `IPC anual` a partir de los últimos 12 IPC mensuales de la fuente activa.
4. Normaliza el resultado a un JSON estable para el frontend.

## Desarrollo local

### Prechecks

- Asegúrate de estar en `/Users/dsj-imac/Developer/portafolio-tracker`.
- Si quieres probar integración real con Vercel, necesitas tener `vercel login` listo.
- Si sólo quieres validar lógica local, `PORTFOLIO_STORAGE=local` es suficiente.

### Comandos

1. Crear o reutilizar entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Qué deberías ver:
- El prompt cambia y empieza a mostrar `(.venv)` o equivalente.

2. Instalar dependencias:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Qué deberías ver:
- Instalación de `yfinance`, `pandas`, `numpy` y `vercel`.
- El comando termina sin `ERROR`.

3. Crear variables locales:

```bash
cp .env.example .env.local
```

Qué deberías ver:
- No imprime nada si sale bien.

4. Para validar sólo con archivos locales:

```bash
PORTFOLIO_STORAGE=local vercel dev --listen 127.0.0.1:3000
```

Qué deberías ver:
- Un mensaje tipo `Ready! Available at http://127.0.0.1:3000`.

5. Abrir el sitio:

```bash
open http://127.0.0.1:3000
```

Qué deberías ver:
- La app abre normal.
- El botón intenta llamar a `/api/refresh-all`.
- Si una fuente pública falla, el backend intentará la siguiente.

### Verificación rápida local

```bash
.venv/bin/python -m compileall backend api scripts
node --check assets/js/app.js
node --check assets/js/state.js
node --check assets/js/indicators-banner.js
node --check assets/js/ui.js
```

Qué deberías ver:
- Sin errores de sintaxis.

## Despliegue a Vercel

### Prechecks

- El repo remoto debe seguir siendo `osamabindrummer/portafolio-tracker`.
- Debes tener acceso a Vercel con la cuenta donde quedará el proyecto.
- Conviene hacer el primer deploy desde una rama limpia.

### Secuencia recomendada

1. Confirmar estado git:

```bash
git status
```

Qué deberías ver:
- Archivos modificados por esta migración antes del commit.
- Luego del commit, un working tree limpio.

2. Commit de la migración:

```bash
git add .
git commit -m "feat: migrate portfolio tracker to vercel backend"
```

Qué deberías ver:
- Un commit nuevo con los archivos de `api/`, `backend/`, `vercel.json` y cambios frontend.

3. Subir cambios:

```bash
git push origin main
```

Qué deberías ver:
- `main -> main`.

4. Vincular el proyecto con Vercel:

```bash
vercel link
```

Qué deberías ver:
- Preguntas para elegir scope y proyecto.
- Al final, un mensaje indicando que el directorio quedó vinculado.

5. Crear o asociar Blob desde Vercel Dashboard:

- Entra a Storage.
- Crea un Blob Store.
- Asígnalo al proyecto.

Qué deberías ver:
- Una integración de Blob asociada al proyecto.

6. Cargar variables al proyecto:

```bash
vercel env add BLOB_READ_WRITE_TOKEN production
vercel env add CRON_SECRET production
vercel env add REFRESH_COOLDOWN_SECONDS production
```

Qué deberías ver:
- Cada comando termina confirmando que la variable quedó guardada.

7. Hacer primer deploy productivo:

```bash
vercel --prod
```

Qué deberías ver:
- Build exitoso.
- Una URL final de producción.

8. Descargar variables para desarrollo local, si quieres probar con el mismo entorno:

```bash
vercel env pull .env.local
```

Qué deberías ver:
- Un archivo `.env.local` actualizado.

## Qué configurar en Vercel Dashboard

1. Importar el repo `osamabindrummer/portafolio-tracker`.
2. Verificar que el framework quede como `Other` o detección automática simple.
3. Asociar un Blob Store al proyecto.
4. Crear estas variables de entorno:
   - `BLOB_READ_WRITE_TOKEN`
   - `CRON_SECRET`
   - `REFRESH_COOLDOWN_SECONDS`
5. Confirmar que el cron de `vercel.json` quede habilitado después del deploy.
6. Revisar en Logs que `/api/refresh-all` y `/api/refresh-indicators` respondan sin error.

## GitHub Actions

- `update-data.yml`: queda manual para refrescar `data/latest.json` si quieres mantener la semilla del repo desde GitHub.
- No quedan workflows para Pages ni para el banner antiguo.

## Endpoints resultantes

- `GET /api/data/latest`
- `GET /api/indicators`
- `POST /api/refresh-data`
- `POST /api/refresh-indicators`
- `POST /api/refresh-all`
- `GET /api/cron/refresh`

## Checklist de verificación final

- El sitio carga desde Vercel.
- `Actualizar datos` devuelve una actualización real o un `skipped` razonable por enfriamiento.
- El banner económico refresca sin exponer credenciales.
- `data/latest` e `indicators/latest` responden desde `/api/...`.
- Blob recibe nuevas versiones de JSON.
