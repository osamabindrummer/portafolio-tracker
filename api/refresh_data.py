from __future__ import annotations

from backend.http import ApiHandler, read_refresh_options, send_error_json, send_json
from backend.portfolio_refresh import refresh_latest_dataset


class handler(ApiHandler):
    allowed_methods = ("POST", "OPTIONS")

    def do_POST(self) -> None:  # noqa: N802
        try:
            _, _, force = read_refresh_options(self)
        except PermissionError as error:
            send_error_json(self, 401, str(error))
            return
        except ValueError as error:
            send_error_json(self, 400, str(error))
            return

        try:
            result = refresh_latest_dataset(force=force)
        except Exception as error:  # pragma: no cover - depende de APIs externas
            send_error_json(self, 500, f"No se pudo actualizar latest.json: {error}")
            return

        status_code = 200 if result.status == "updated" else 202
        send_json(self, status_code, result.to_dict())
