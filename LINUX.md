# Uso en Linux (Arch, Manjaro u otras distribuciones)

Abre una terminal en la carpeta raíz de este repositorio clonado. Para revisar archivos y editar código, no necesitas ejecutar el servidor: usa tu editor y Git normalmente. Los comandos siguientes sirven para abrir la aplicación local. Detén un servidor con `Ctrl+C`. Los archivos `.command` son accesos rápidos de macOS; en Linux usa estos comandos.

## Vista local

Este proyecto usa funciones de Vercel para sus rutas `/api/`. Instala Python, las dependencias del proyecto y Vercel CLI; configura el CLI si te lo solicita. Desde la raíz:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env.local
PORTFOLIO_STORAGE=local vercel dev --listen 127.0.0.1:3001
```

Abre `http://127.0.0.1:3001/`. El modo `local` usa los archivos semilla del repositorio; las actualizaciones pueden consultar fuentes externas. `.env.local` y `.venv/` se crean en cada equipo. Véase [README.md](README.md).
