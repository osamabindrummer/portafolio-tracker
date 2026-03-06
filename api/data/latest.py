from __future__ import annotations

from backend.http import ApiHandler, send_error_json, send_json
from backend.portfolio_refresh import fetch_latest_payload


class handler(ApiHandler):
    allowed_methods = ("GET", "OPTIONS")

    def do_GET(self) -> None:  # noqa: N802
        try:
            payload, meta = fetch_latest_payload()
        except Exception as error:  # pragma: no cover - depende del entorno
            send_error_json(self, 500, f"No se pudo cargar el dataset principal: {error}")
            return

        send_json(
            self,
            200,
            payload,
            extra_headers={
                "X-Portfolio-Storage": meta.source,
                "X-Portfolio-Pathname": meta.pathname or "",
            },
        )
