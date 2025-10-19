#!/usr/bin/env python3
"""
Servidor de desarrollo para el Portafolio Tracker.

Expone un endpoint POST `/api/fetch-data` que ejecuta `scripts/fetch_data.py`
y sirve los archivos estáticos del proyecto. Pensado para uso local.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
FETCH_SCRIPT = BASE_DIR / "scripts" / "fetch_data.py"
LATEST_JSON = BASE_DIR / "data" / "latest.json"


class PortfolioRequestHandler(SimpleHTTPRequestHandler):
    """Manejador de peticiones que agrega el endpoint /api/fetch-data."""

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/api/fetch-data"):
            self._handle_fetch_data()
        else:
            self.send_error(404, "Ruta no encontrada")

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/fetch-data"):
            self._handle_fetch_data()
        else:
            super().do_GET()

    def do_OPTIONS(self):  # noqa: N802
        if self.path.startswith("/api/fetch-data"):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
        else:
            self.send_response(200)
            self.end_headers()

    def _handle_fetch_data(self) -> None:
        mode = self._parse_mode()
        cmd = [sys.executable, str(FETCH_SCRIPT)]
        if mode == "offline":
            cmd.append("--offline")

        try:
            completed = subprocess.run(
                cmd,
                cwd=str(BASE_DIR),
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            self._send_json(
                500,
                {
                    "message": "No se pudo ejecutar fetch_data.py.",
                    "stderr": error.stderr,
                },
            )
            return

        generated_at = None
        if LATEST_JSON.exists():
            try:
                payload = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
                generated_at = payload.get("generated_at")
            except json.JSONDecodeError:
                generated_at = None

        response = {
            "message": 'Datos generados correctamente. Presiona "Actualizar página".',
            "generated_at": generated_at,
            "stdout": completed.stdout.strip() if completed.stdout else "",
        }
        self._send_json(200, response)

    def _parse_mode(self) -> str:
        if "?" not in self.path:
            return "online"
        query = self.path.split("?", 1)[1]
        params = dict(item.split("=", 1) for item in query.split("&") if "=" in item)
        return params.get("mode", "online")

    def _send_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        """Reduce el ruido en consola."""
        sys.stderr.write("%s - - %s\n" % (self.log_date_time_string(), format % args))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Servidor local para Portafolio Tracker")
    parser.add_argument("--host", default="127.0.0.1", help="Host a usar (por defecto 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Puerto HTTP (por defecto 8000)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    handler_cls = partial(PortfolioRequestHandler, directory=str(BASE_DIR))
    server = ThreadingHTTPServer((args.host, args.port), handler_cls)
    print(f"Servidor disponible en http://{args.host}:{args.port}")
    print("POST /api/fetch-data (agregar ?mode=offline para datos deterministas)\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
