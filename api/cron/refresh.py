from __future__ import annotations

import os

from backend.http import ApiHandler, send_error_json, send_json
from backend.portfolio_refresh import refresh_fintual_goals, refresh_latest_dataset


class handler(ApiHandler):
    allowed_methods = ("GET", "OPTIONS")

    def do_GET(self) -> None:  # noqa: N802
        expected_secret = os.getenv("CRON_SECRET", "").strip()
        authorization = self.headers.get("Authorization", "").strip()

        if expected_secret and authorization != f"Bearer {expected_secret}":
            send_error_json(self, 401, "No autorizado para ejecutar el cron.")
            return

        try:
            latest_result = refresh_latest_dataset(force=False, mode="online")
            goals_result = refresh_fintual_goals(force=False)
        except Exception as error:  # pragma: no cover - depende de APIs externas
            send_error_json(self, 500, f"El cron no pudo refrescar los datos: {error}")
            return

        send_json(
            self,
            200,
            {
                "status": "ok",
                "results": {
                    "latest": latest_result.to_dict(),
                    "goals": goals_result.to_dict(),
                },
            },
        )
