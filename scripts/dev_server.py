"""Sirve la aplicación y sus handlers reales en 127.0.0.1:3001."""

from __future__ import annotations

import importlib
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ROUTES = {
    "/api/data/latest": "api.data.latest",
    "/api/indicators": "api.indicators",
    "/api/refresh-data": "api.refresh_data",
    "/api/refresh-indicators": "api.refresh_indicators",
    "/api/refresh-all": "api.refresh_all",
    "/api/cron/refresh": "api.cron.refresh",
}


class LocalHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("X-Portfolio-App", "portafolio-tracker-local")
        super().end_headers()

    def _route(self, method):
        path = urlsplit(self.path).path
        if path not in ROUTES:
            return False
        handler = importlib.import_module(ROUTES[path]).handler
        action = getattr(handler, f"do_{method}", None)
        if not action:
            self.send_error(405, "Método no permitido")
        elif method == "OPTIONS":
            from backend.http import send_options

            send_options(self, handler.allowed_methods)
        else:
            action(self)
        return True

    def do_GET(self):
        if self._route("GET"):
            return
        path = unquote(urlsplit(self.path).path)
        target = (ROOT / path.lstrip("/")).resolve()
        # El servidor local no expone secretos, código Python ni archivos internos.
        if path in ("/", "/index.html", "/datos.html") or (
            target.is_relative_to(ROOT / "assets") and target.is_file()
        ):
            super().do_GET()
        else:
            self.send_error(404)

    def do_HEAD(self):
        path = unquote(urlsplit(self.path).path)
        target = (ROOT / path.lstrip("/")).resolve()
        if path in ("/", "/index.html", "/datos.html") or (
            target.is_relative_to(ROOT / "assets") and target.is_file()
        ):
            super().do_HEAD()
        else:
            self.send_error(404)

    def do_POST(self):
        if not self._route("POST"):
            self.send_error(404)

    def do_OPTIONS(self):
        if not self._route("OPTIONS"):
            self.send_error(404)


def main():
    os.environ["PORTFOLIO_STORAGE"] = "local"
    os.environ.pop("VERCEL", None)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 3001), LocalHandler)
    except OSError as error:
        raise SystemExit(
            "No se pudo abrir 127.0.0.1:3001. Comprueba que el puerto esté libre."
        ) from error
    print("Portafolio Tracker local: http://127.0.0.1:3001", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
