# Portafolio Tracker

Sitio estático con HTML, CSS y JS para visualizar y comparar inversiones de Racional y Fintual. Desde esta migración, el hosting principal pasa a ser **Vercel** y las actualizaciones ya no dependen de GitHub Pages para servir los JSON públicos.

## Estado actual de la arquitectura

- `index.html` y `assets/`: frontend estático servido por Vercel.
- `api/data/latest`: entrega el dataset principal usado por la app.
- `api/fintual/goals`: entrega el snapshot del banner de Fintual.
- `api/refresh-data`: regenera `latest.json` en backend.
- `api/refresh-fintual`: vuelve a consultar Fintual en backend.
- `api/refresh-all`: refresca ambos flujos con una sola llamada.
- `api/cron/refresh`: endpoint pensado para Vercel Cron.
- `Vercel Blob`: persistencia de los JSON generados en producción.
- `data/latest.json` y `public/fintual/goals.json`: quedan como semillas locales y fallback inicial.

## Por qué esta combinación

### `Vercel Functions`

Se usan porque permiten ejecutar backend sin montar un servidor propio. Es la opción más simple para un sitio que ya era estático.

### `Vercel Blob`

Se usa porque el filesystem de Vercel Functions es efímero y de solo lectura fuera de `/tmp`, así que no sirve para guardar datos que deban sobrevivir entre ejecuciones. Blob encaja mejor que KV o Postgres porque aquí estamos guardando archivos JSON completos, no datos relacionales ni claves sueltas.

### `Vercel Cron`

Queda preparado para automatizar refresh sin depender de GitHub Actions. En Hobby, Vercel limita los cron jobs a una frecuencia máxima de una vez por día, así que una pauta tipo lunes/miércoles/viernes sí es viable, pero una horaria no.

## Flujo de datos en producción

1. El frontend carga `/api/data/latest` y `/api/fintual/goals`.
2. Esos endpoints leen desde Vercel Blob.
3. Si Blob todavía no tiene datos, se usa el JSON versionado dentro del repo como fallback.
4. Al hacer clic en `Actualizar datos`, la web llama `/api/refresh-all`.
5. Al hacer clic en el banner de Fintual, la web llama `/api/refresh-fintual`.
6. Las credenciales privadas viven sólo en variables de entorno del backend.

## Seguridad y límites reales

- `FINTUAL_USER_EMAIL` y `FINTUAL_USER_TOKEN` no salen al frontend.
- El endpoint público de refresh no expone secretos, pero al ser público no puede distinguir entre tu clic y el de otro visitante.
- Para reducir abuso, el backend aplica un enfriamiento configurable con `REFRESH_COOLDOWN_SECONDS`.
- Si en el futuro quieres que sólo tú puedas refrescar manualmente, habrá que añadir autenticación real.

## Estructura relevante del repo

- `assets/js/app.js`: coordina carga, refresh global y refresh del banner.
- `assets/js/state.js`: consume `/api/data/latest` y `/api/refresh-all`.
- `assets/js/fintual-banner.js`: consume `/api/fintual/goals` y `/api/refresh-fintual`.
- `backend/storage.py`: decide si usa archivos locales o Vercel Blob.
- `backend/portfolio_refresh.py`: lógica de refresh y enfriamiento.
- `api/`: funciones serverless de Vercel.
- `vercel.json`: rewrites, funciones y cron.
- `.env.example`: plantilla de variables.

## Variables de entorno

### Requeridas en Vercel

- `BLOB_READ_WRITE_TOKEN`
- `FINTUAL_USER_EMAIL`
- `FINTUAL_USER_TOKEN`
- `CRON_SECRET`

### Recomendadas

- `REFRESH_COOLDOWN_SECONDS`

### Opcionales para desarrollo local

- `PORTFOLIO_STORAGE=local`

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
- Si no configuraste Fintual, el refresh combinado puede quedar parcial y eso es esperado.

### Verificación rápida local

```bash
.venv/bin/python -m compileall backend api scripts
node --check assets/js/app.js
node --check assets/js/state.js
node --check assets/js/fintual-banner.js
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
vercel env add FINTUAL_USER_EMAIL production
vercel env add FINTUAL_USER_TOKEN production
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
   - `FINTUAL_USER_EMAIL`
   - `FINTUAL_USER_TOKEN`
   - `CRON_SECRET`
   - `REFRESH_COOLDOWN_SECONDS`
5. Confirmar que el cron de `vercel.json` quede habilitado después del deploy.
6. Revisar en Logs que `/api/refresh-all` y `/api/refresh-fintual` respondan sin error.

## Qué hacer con GitHub Pages

Después de confirmar que Vercel está bien en producción:

1. Ve a GitHub `Settings -> Pages`.
2. Desactiva GitHub Pages o déjalo sin fuente activa.
3. Mantén los workflows manuales sólo como respaldo temporal, si quieres.

## GitHub Actions después de la migración

Los workflows de GitHub ya no redeployan Pages:

- `deploy.yml`: queda manual y sólo valida.
- `update-data.yml`: queda manual para refrescar `data/latest.json` si quieres mantener la semilla del repo.
- `fintual.yml`: queda manual para refrescar `public/fintual/goals.json` si quieres mantener la semilla del repo.

## Endpoints resultantes

- `GET /api/data/latest`
- `GET /api/fintual/goals`
- `POST /api/refresh-data`
- `POST /api/refresh-fintual`
- `POST /api/refresh-all`
- `GET /api/cron/refresh`

## Checklist de verificación final

- El sitio carga desde Vercel.
- `Actualizar datos` devuelve una actualización real o un `skipped` razonable por enfriamiento.
- El banner de Fintual refresca sin exponer credenciales.
- `data/latest` y `fintual/goals` responden desde `/api/...`.
- Blob recibe nuevas versiones de JSON.
- GitHub Pages deja de ser el hosting principal.
