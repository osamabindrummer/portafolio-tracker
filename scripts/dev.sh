#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

portfolio_python="${PORTFOLIO_PYTHON:-$PWD/.venv-review/bin/python}"
if ! "$portfolio_python" -c 'import sys; sys.exit(not ((3, 11) <= sys.version_info[:2] < (3, 15)))' 2>/dev/null; then
  echo "Se necesita Python 3.11–3.14. Crea un entorno compatible o indica PORTFOLIO_PYTHON." >&2
  exit 1
fi
if ! "$portfolio_python" -c 'import yfinance; import vercel.blob.sync' 2>/dev/null; then
  echo "Faltan dependencias compatibles. Instala requirements.lock en el entorno elegido." >&2
  exit 1
fi
if ! "$portfolio_python" -c 'import socket; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("127.0.0.1", 3001)); s.close()' 2>/dev/null; then
  echo "El puerto 127.0.0.1:3001 está ocupado. Libéralo antes de iniciar Portafolio Tracker." >&2
  exit 1
fi
export PATH="$(dirname "$portfolio_python"):$PATH"
export PORTFOLIO_STORAGE=local
exec "$portfolio_python" -m scripts.dev_server
