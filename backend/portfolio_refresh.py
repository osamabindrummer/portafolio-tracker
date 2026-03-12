"""Servicios para refrescar datasets del portafolio."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.storage import GOALS_DATASET, LATEST_DATASET, StorageMeta, read_dataset, write_dataset
from scripts.fetch_data import generate_offline_payload, generate_online_payload
from scripts.validate_json import ValidationError, validate_payload


FINTUAL_API_URL = "https://fintual.cl/api/goals"
DEFAULT_COOLDOWN_SECONDS = 600


@dataclass(frozen=True)
class RefreshResult:
    dataset: str
    status: str
    message: str
    timestamp: str | None = None
    storage: str | None = None
    pathname: str | None = None
    url: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def refresh_latest_dataset(*, force: bool = False, mode: str = "online") -> RefreshResult:
    existing_payload = _safe_read_payload(LATEST_DATASET)
    if not force and _is_recent(existing_payload, LATEST_DATASET.timestamp_field):
        return _build_skipped_result(LATEST_DATASET.key, existing_payload, "El dataset principal ya fue actualizado hace poco.")

    if mode == "offline":
        payload = generate_offline_payload()
    else:
        payload = generate_online_payload()

    try:
        validate_payload(payload)
    except ValidationError as error:
        raise RuntimeError(f"El JSON generado para latest.json no pasó validación: {error}") from error

    storage = write_dataset(LATEST_DATASET, payload)
    return _build_updated_result(LATEST_DATASET.key, payload, storage, "Datos principales actualizados correctamente.")


def refresh_fintual_goals(*, force: bool = False) -> RefreshResult:
    existing_payload = _safe_read_payload(GOALS_DATASET)
    if not force and _is_recent(existing_payload, GOALS_DATASET.timestamp_field):
        return _build_skipped_result(GOALS_DATASET.key, existing_payload, "Las metas de Fintual ya fueron actualizadas hace poco.")

    payload = fetch_fintual_goals_payload()
    storage = write_dataset(GOALS_DATASET, payload)
    return _build_updated_result(GOALS_DATASET.key, payload, storage, "Metas de Fintual actualizadas correctamente.")


def fetch_latest_payload() -> tuple[Dict[str, Any], StorageMeta]:
    return read_dataset(LATEST_DATASET)


def fetch_goals_payload() -> tuple[Dict[str, Any], StorageMeta]:
    return read_dataset(GOALS_DATASET)


def fetch_fintual_goals_payload() -> Dict[str, Any]:
    email = _read_required_env("FINTUAL_USER_EMAIL", aliases=("FINTUAL_USER", "FINTUAL_USERNAME"))
    token = _read_required_env("FINTUAL_USER_TOKEN")
    request = Request(
        FINTUAL_API_URL,
        headers={
            "Accept": "application/json",
            "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "X-User-Email": email,
            "X-User-Token": token,
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=30) as response:
            raw_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 401:
            raise RuntimeError(
                "La API de Fintual respondió HTTP 401. Revisa en Vercel que el email o usuario "
                "esté cargado en FINTUAL_USER_EMAIL o FINTUAL_USER, y que FINTUAL_USER_TOKEN siga vigente."
            ) from error
        raise RuntimeError(f"La API de Fintual respondió HTTP {error.code}.") from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError("No se pudo conectar con la API de Fintual.") from error
    except json.JSONDecodeError as error:
        raise RuntimeError("La respuesta de Fintual no es JSON válido.") from error

    if not isinstance(raw_payload, dict) or not isinstance(raw_payload.get("data"), list):
        raise RuntimeError("La respuesta de Fintual no tiene el formato esperado.")

    return {
        **raw_payload,
        "fetched_at": _iso_now(),
        "source_url": FINTUAL_API_URL,
    }


def _safe_read_payload(dataset) -> Dict[str, Any] | None:
    try:
        payload, _ = read_dataset(dataset)
        return payload
    except (FileNotFoundError, RuntimeError, json.JSONDecodeError):
        return None


def _is_recent(payload: Dict[str, Any] | None, timestamp_field: str) -> bool:
    if not payload:
        return False

    raw_timestamp = payload.get(timestamp_field)
    if not isinstance(raw_timestamp, str) or not raw_timestamp.strip():
        return False

    try:
        parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False

    delta = datetime.now(UTC) - parsed.astimezone(UTC)
    return delta.total_seconds() < _read_cooldown_seconds()


def _read_cooldown_seconds() -> int:
    raw_value = os.getenv("REFRESH_COOLDOWN_SECONDS", str(DEFAULT_COOLDOWN_SECONDS)).strip()
    try:
        value = int(raw_value)
    except ValueError:
        return DEFAULT_COOLDOWN_SECONDS
    return max(0, value)


def _read_required_env(name: str, aliases: tuple[str, ...] = ()) -> str:
    candidate_names = (name, *aliases)
    for candidate in candidate_names:
        value = os.getenv(candidate, "").strip()
        if value:
            return value

    aliases_text = ", ".join(aliases)
    if aliases_text:
        raise RuntimeError(f"Falta la variable de entorno requerida: {name}. También se aceptan: {aliases_text}.")
    raise RuntimeError(f"Falta la variable de entorno requerida: {name}.")


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_skipped_result(dataset: str, payload: Dict[str, Any] | None, message: str) -> RefreshResult:
    timestamp = None
    if dataset == "latest" and payload:
        timestamp = payload.get("generated_at")
    if dataset == "goals" and payload:
        timestamp = payload.get("fetched_at")
    return RefreshResult(
        dataset=dataset,
        status="skipped",
        message=message,
        timestamp=timestamp if isinstance(timestamp, str) else None,
        storage="local-or-existing",
    )


def _build_updated_result(
    dataset: str,
    payload: Dict[str, Any],
    storage: StorageMeta,
    message: str,
) -> RefreshResult:
    timestamp_field = "generated_at" if dataset == "latest" else "fetched_at"
    timestamp = payload.get(timestamp_field)
    return RefreshResult(
        dataset=dataset,
        status="updated",
        message=message,
        timestamp=timestamp if isinstance(timestamp, str) else None,
        storage=storage.source,
        pathname=storage.pathname,
        url=storage.url,
    )
