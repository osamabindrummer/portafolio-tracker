from __future__ import annotations

from backend.http import ApiHandler, first_param, get_query_params, is_truthy, read_json_body, send_error_json, send_json
from backend.portfolio_refresh import refresh_fintual_goals, refresh_latest_dataset


class handler(ApiHandler):
    allowed_methods = ("POST", "OPTIONS")

    def do_POST(self) -> None:  # noqa: N802
        query = get_query_params(self)
        try:
            body = read_json_body(self)
        except ValueError as error:
            send_error_json(self, 400, str(error))
            return

        mode = first_param(query, "mode") or str(body.get("mode", "online")).strip().lower() or "online"
        force = is_truthy(first_param(query, "force")) or is_truthy(body.get("force"))

        latest_result = None
        goals_result = None
        errors = {}

        try:
            latest_result = refresh_latest_dataset(force=force, mode=mode)
        except Exception as error:  # pragma: no cover - depende de APIs externas
            errors["latest"] = str(error)

        try:
            goals_result = refresh_fintual_goals(force=force)
        except Exception as error:  # pragma: no cover - depende de APIs externas
            errors["goals"] = str(error)

        if latest_result is None and goals_result is None:
            send_error_json(self, 500, "Ningún dataset pudo actualizarse correctamente.")
            return

        statuses = {result.status for result in (latest_result, goals_result) if result is not None}
        payload = {
            "status": "updated" if "updated" in statuses else "skipped",
            "message": "Actualización completa finalizada." if not errors else "Actualización parcial finalizada.",
            "results": {
                "latest": latest_result.to_dict() if latest_result else None,
                "goals": goals_result.to_dict() if goals_result else None,
            },
        }
        if errors:
            payload["errors"] = errors

        status_code = 200 if payload["status"] == "updated" else 202
        send_json(self, status_code, payload)
