from __future__ import annotations

import os

from backend.http import (
    ApiHandler,
    first_param,
    is_truthy,
    read_refresh_options,
    send_error_json,
    send_json,
)
from backend.portfolio_refresh import refresh_indicators_dataset, refresh_latest_dataset


class handler(ApiHandler):
    allowed_methods = ("POST", "OPTIONS")

    def do_POST(self) -> None:  # noqa: N802
        try:
            query, body, force = read_refresh_options(self)
        except PermissionError as error:
            send_error_json(self, 401, str(error))
            return
        except ValueError as error:
            send_error_json(self, 400, str(error))
            return

        include_indicators = _should_refresh_indicators(query, body)

        latest_result = None
        indicators_result = None
        errors = {}

        try:
            latest_result = refresh_latest_dataset(force=force)
        except Exception as error:  # pragma: no cover - depende de APIs externas
            errors["latest"] = str(error)

        if include_indicators:
            try:
                indicators_result = refresh_indicators_dataset(force=force)
            except Exception as error:  # pragma: no cover - depende de APIs externas
                errors["indicators"] = str(error)

        if latest_result is None and indicators_result is None:
            send_error_json(
                self, 500, "Ningún dataset pudo actualizarse correctamente."
            )
            return

        statuses = {
            result.status
            for result in (latest_result, indicators_result)
            if result is not None
        }
        payload = {
            "status": "updated" if "updated" in statuses else "skipped",
            "message": "Actualización completa finalizada."
            if not errors
            else "Actualización parcial finalizada.",
            "results": {
                "latest": latest_result.to_dict() if latest_result else None,
                "indicators": indicators_result.to_dict()
                if indicators_result
                else None,
            },
        }
        if errors:
            payload["errors"] = errors

        status_code = 200 if payload["status"] == "updated" else 202
        send_json(self, status_code, payload)


def _should_refresh_indicators(
    query: dict[str, list[str]], body: dict[str, object]
) -> bool:
    requested = first_param(query, "includeIndicators")
    if requested is None and "includeIndicators" in body:
        requested = str(body.get("includeIndicators"))

    if requested is not None:
        return is_truthy(requested)

    return is_truthy(os.getenv("REFRESH_ALL_INCLUDES_INDICATORS", "true"))
