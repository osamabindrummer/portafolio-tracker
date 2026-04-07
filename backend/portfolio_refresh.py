"""Servicios para refrescar datasets del portafolio."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from math import prod
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.storage import INDICATORS_DATASET, LATEST_DATASET, StorageMeta, read_dataset, write_dataset
from scripts.fetch_data import generate_offline_payload, generate_online_payload
from scripts.validate_json import ValidationError, validate_payload


DEFAULT_COOLDOWN_SECONDS = 600
MINDICADOR_API_URL = "https://mindicador.cl/api"
FINDIC_API_URL = "https://findic.cl/api"

INDICATOR_METADATA = {
    "uf": {
        "label": "UF",
        "unit": "CLP",
        "decimals": 2,
    },
    "utm": {
        "label": "UTM",
        "unit": "CLP",
        "decimals": 1,
    },
    "dollar_observed": {
        "label": "Dólar observado",
        "unit": "CLP",
        "decimals": 2,
    },
    "ipc_annual": {
        "label": "IPC anual",
        "unit": "PERCENT",
        "decimals": 1,
    },
}


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


def refresh_indicators_dataset(*, force: bool = False) -> RefreshResult:
    existing_payload = _safe_read_payload(INDICATORS_DATASET)
    if not force and _is_recent(existing_payload, INDICATORS_DATASET.timestamp_field):
        return _build_skipped_result(
            INDICATORS_DATASET.key,
            existing_payload,
            "Los indicadores públicos ya fueron actualizados hace poco.",
        )

    payload = fetch_public_indicators_payload()
    storage = write_dataset(INDICATORS_DATASET, payload)
    return _build_updated_result(
        INDICATORS_DATASET.key,
        payload,
        storage,
        "Indicadores públicos actualizados correctamente.",
    )


def fetch_latest_payload() -> tuple[Dict[str, Any], StorageMeta]:
    return read_dataset(LATEST_DATASET)


def fetch_indicators_payload() -> tuple[Dict[str, Any], StorageMeta]:
    return read_dataset(INDICATORS_DATASET)


def fetch_public_indicators_payload() -> Dict[str, Any]:
    sources = (
        _fetch_from_mindicador,
        _fetch_from_findic,
    )
    errors: list[str] = []

    for fetcher in sources:
        try:
            items = fetcher()
            return {
                "items": items,
                "fetched_at": _iso_now(),
                "source": fetcher.__name__.removeprefix("_fetch_from_"),
                "source_url": _source_url_for(fetcher.__name__),
            }
        except RuntimeError as error:
            errors.append(str(error))

    details = " | ".join(errors) if errors else "sin detalle"
    raise RuntimeError(f"No se pudo obtener indicadores desde ninguna fuente pública. {details}")


def _fetch_from_mindicador() -> list[Dict[str, Any]]:
    summary = _request_json(MINDICADOR_API_URL)

    uf = _build_indicator_item(
        key="uf",
        value=_read_top_level_value(summary, "uf"),
        observed_at=_read_top_level_date(summary, "uf"),
    )
    utm = _build_indicator_item(
        key="utm",
        value=_read_top_level_value(summary, "utm"),
        observed_at=_read_top_level_date(summary, "utm"),
    )
    dollar = _build_indicator_item(
        key="dollar_observed",
        value=_read_top_level_value(summary, "dolar"),
        observed_at=_read_top_level_date(summary, "dolar"),
    )

    ipc_history = _request_json(f"{MINDICADOR_API_URL}/ipc")
    ipc_annual_value, ipc_observed_at = _compute_annual_ipc_from_series(_read_series(ipc_history))
    ipc = _build_indicator_item(
        key="ipc_annual",
        value=ipc_annual_value,
        observed_at=ipc_observed_at,
    )

    return [uf, utm, dollar, ipc]


def _fetch_from_findic() -> list[Dict[str, Any]]:
    summary = _request_json(FINDIC_API_URL)

    uf = _build_indicator_item(
        key="uf",
        value=_read_top_level_value(summary, "uf"),
        observed_at=_read_top_level_date(summary, "uf"),
    )
    utm = _build_indicator_item(
        key="utm",
        value=_read_top_level_value(summary, "utm"),
        observed_at=_read_top_level_date(summary, "utm"),
    )
    dollar = _build_indicator_item(
        key="dollar_observed",
        value=_read_top_level_value(summary, "dolar"),
        observed_at=_read_top_level_date(summary, "dolar"),
    )

    ipc_history = _request_json(f"{FINDIC_API_URL}/ipc")
    ipc_annual_value, ipc_observed_at = _compute_annual_ipc_from_series(_read_series(ipc_history))
    ipc = _build_indicator_item(
        key="ipc_annual",
        value=ipc_annual_value,
        observed_at=ipc_observed_at,
    )

    return [uf, utm, dollar, ipc]


def _request_json(url: str) -> Dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "portafolio-tracker/1.0",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = _read_http_error_details(error)
        raise RuntimeError(f"La fuente pública {url} respondió HTTP {error.code}: {details}.") from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"No se pudo conectar con la fuente pública {url}.") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"La fuente pública {url} devolvió JSON inválido.") from error

    if not isinstance(payload, dict):
        raise RuntimeError(f"La fuente pública {url} no devolvió un objeto JSON válido.")

    return payload


def _build_indicator_item(*, key: str, value: float, observed_at: str) -> Dict[str, Any]:
    metadata = INDICATOR_METADATA[key]
    return {
        "key": key,
        "label": metadata["label"],
        "value": value,
        "unit": metadata["unit"],
        "decimals": metadata["decimals"],
        "observed_at": observed_at,
    }


def _read_top_level_value(payload: Dict[str, Any], code: str) -> float:
    node = payload.get(code)
    if not isinstance(node, dict):
        raise RuntimeError(f"La respuesta no contiene el indicador '{code}'.")

    value = node.get("valor")
    if not isinstance(value, (int, float)):
        raise RuntimeError(f"La respuesta del indicador '{code}' no contiene un valor numérico.")

    return float(value)


def _read_top_level_date(payload: Dict[str, Any], code: str) -> str:
    node = payload.get(code)
    if not isinstance(node, dict):
        raise RuntimeError(f"La respuesta no contiene fecha para el indicador '{code}'.")

    raw_date = node.get("fecha")
    return _normalize_public_date(raw_date)


def _read_series(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    series = payload.get("serie")
    if not isinstance(series, list) or not series:
        raise RuntimeError("La respuesta histórica no contiene serie.")
    filtered = [item for item in series if isinstance(item, dict)]
    if not filtered:
        raise RuntimeError("La serie histórica no contiene observaciones válidas.")
    return filtered


def _compute_annual_ipc_from_series(series: list[Dict[str, Any]]) -> tuple[float, str]:
    monthly_points = []
    for item in series:
        value = item.get("valor")
        raw_date = item.get("fecha")
        if not isinstance(value, (int, float)):
            continue
        normalized_date = _normalize_public_date(raw_date)
        monthly_points.append((normalized_date, float(value)))

    if len(monthly_points) < 12:
        raise RuntimeError("No hay suficientes observaciones mensuales para calcular IPC anual.")

    monthly_points.sort(key=lambda item: item[0], reverse=True)
    latest_twelve = monthly_points[:12]
    annual_factor = prod((1 + (value / 100)) for _, value in latest_twelve)
    annual_value = (annual_factor - 1) * 100
    observed_at = latest_twelve[0][0]
    return round(annual_value, 1), observed_at


def _normalize_public_date(raw_value: Any) -> str:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise RuntimeError("La fuente pública no entregó una fecha válida.")

    normalized = raw_value.strip()
    if "T" in normalized:
        normalized = normalized.split("T", 1)[0]

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise RuntimeError(f"No se pudo interpretar la fecha '{raw_value}'.") from error

    return parsed.date().isoformat()


def _source_url_for(fetcher_name: str) -> str:
    if fetcher_name == "_fetch_from_mindicador":
        return MINDICADOR_API_URL
    if fetcher_name == "_fetch_from_findic":
        return FINDIC_API_URL
    return ""


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


def _read_http_error_details(error: HTTPError) -> str:
    try:
        body = error.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return "sin cuerpo"

    if not body:
        return "sin cuerpo"

    compact = " ".join(body.split())
    return compact[:240]


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_skipped_result(dataset: str, payload: Dict[str, Any] | None, message: str) -> RefreshResult:
    timestamp = None
    if dataset == LATEST_DATASET.key and payload:
        timestamp = payload.get("generated_at")
    if dataset == INDICATORS_DATASET.key and payload:
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
    timestamp_field = "generated_at" if dataset == LATEST_DATASET.key else "fetched_at"
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
