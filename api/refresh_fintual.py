from __future__ import annotations

from backend.http import ApiHandler, first_param, get_query_params, is_truthy, read_json_body, send_error_json, send_json
from backend.portfolio_refresh import refresh_fintual_goals


class handler(ApiHandler):
    allowed_methods = ("POST", "OPTIONS")

    def do_POST(self) -> None:  # noqa: N802
        query = get_query_params(self)
        try:
            body = read_json_body(self)
        except ValueError as error:
            send_error_json(self, 400, str(error))
            return

        force = is_truthy(first_param(query, "force")) or is_truthy(body.get("force"))

        try:
            result = refresh_fintual_goals(force=force)
        except Exception as error:  # pragma: no cover - depende de APIs externas
            send_error_json(self, 500, f"No se pudo actualizar goals.json: {error}")
            return

        status_code = 200 if result.status == "updated" else 202
        send_json(self, status_code, result.to_dict())
