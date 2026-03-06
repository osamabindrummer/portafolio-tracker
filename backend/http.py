"""Helpers HTTP mínimos para las funciones de Vercel."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict, Iterable
from urllib.parse import parse_qs, urlparse


class ApiHandler(BaseHTTPRequestHandler):
    """Base pequeña para reducir repetición en las funciones."""

    allowed_methods: Iterable[str] = ("GET", "OPTIONS")

    def do_OPTIONS(self) -> None:  # noqa: N802
        send_options(self, self.allowed_methods)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        """Silencia logs verbosos para dejar sólo fallas reales."""
        return


def send_options(handler: BaseHTTPRequestHandler, allowed_methods: Iterable[str]) -> None:
    handler.send_response(204)
    _send_common_headers(handler, allowed_methods=allowed_methods)
    handler.end_headers()


def send_json(
    handler: BaseHTTPRequestHandler,
    status_code: int,
    payload: Any,
    *,
    extra_headers: Dict[str, str] | None = None,
) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
    _send_common_headers(handler, content_length=len(body))
    if extra_headers:
        for key, value in extra_headers.items():
            handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(body)


def send_error_json(handler: BaseHTTPRequestHandler, status_code: int, message: str) -> None:
    send_json(handler, status_code, {"message": message})


def read_json_body(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0") or "0")
    if content_length <= 0:
        return {}

    raw_body = handler.rfile.read(content_length)
    if not raw_body:
        return {}

    try:
        decoded = raw_body.decode("utf-8")
        if not decoded.strip():
            return {}
        parsed = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("El cuerpo JSON es inválido.") from error

    if not isinstance(parsed, dict):
        raise ValueError("El cuerpo JSON debe ser un objeto.")

    return parsed


def get_query_params(handler: BaseHTTPRequestHandler) -> Dict[str, list[str]]:
    parsed = urlparse(handler.path)
    return parse_qs(parsed.query, keep_blank_values=False)


def first_param(query: Dict[str, list[str]], name: str) -> str | None:
    values = query.get(name) or []
    if not values:
        return None
    value = values[0].strip()
    return value or None


def is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def _send_common_headers(
    handler: BaseHTTPRequestHandler,
    *,
    content_length: int | None = None,
    allowed_methods: Iterable[str] = ("GET", "POST", "OPTIONS"),
) -> None:
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, max-age=0")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", ", ".join(allowed_methods))
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    if content_length is not None:
        handler.send_header("Content-Length", str(content_length))
