"""Servicios para refrescar datasets del portafolio."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from math import isfinite, prod
from time import monotonic
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.storage import (
    INDICATORS_DATASET,
    LATEST_DATASET,
    StorageMeta,
    read_dataset,
    write_dataset,
)
from scripts.fetch_data import generate_online_payload
from scripts.portfolio import unpack_payload
from scripts.validate_json import ValidationError, validate_payload
from scripts.update_fintual import matches_config, rebuild_payload


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


def refresh_latest_dataset(
    *, force: bool = False, mode: str = "online"
) -> RefreshResult:
    if mode != "online":
        raise ValueError(
            "Los servicios de actualización sólo guardan cotizaciones reales."
        )
    existing_payload = _safe_read_payload(LATEST_DATASET)
    if not force and _is_recent(existing_payload, LATEST_DATASET.timestamp_field):
        return _build_skipped_result(
            LATEST_DATASET.key,
            existing_payload,
            "El dataset principal ya fue actualizado hace poco.",
        )

    payload = generate_online_payload(existing_payload)

    try:
        validate_payload(payload)
    except ValidationError as error:
        raise RuntimeError(
            f"El JSON generado para latest.json no pasó validación: {error}"
        ) from error

    validate_refresh_quality(payload)

    storage = write_dataset(LATEST_DATASET, payload)
    return _build_updated_result(
        LATEST_DATASET.key,
        payload,
        storage,
        "Datos principales actualizados correctamente.",
    )


def validate_refresh_quality(payload: dict) -> None:
    for platform in payload["platforms"]:
        total = sum(h["weight"] for h in platform["holdings"])
        fresh = sum(
            h["weight"]
            for h in platform["holdings"]
            if not any(
                h["status"].get(key) for key in ("missing_data", "stale", "retained")
            )
        )
        if not total or fresh / total < 0.8:
            raise RuntimeError(
                f"{platform['name']}: menos del 80 % del peso configurado tiene históricos recientes descargados. Se conserva el snapshot anterior."
            )


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
    payload, meta = read_dataset(LATEST_DATASET)
    if not matches_config(payload):
        # Un Blob anterior puede conservar otra cartera tras publicar el código.
        seed = unpack_payload(
            json.loads(LATEST_DATASET.local_path.read_text(encoding="utf-8"))
        )
        payload = rebuild_payload(payload, fallback=seed)
    return payload, meta


def fetch_indicators_payload() -> tuple[Dict[str, Any], StorageMeta]:
    return read_dataset(INDICATORS_DATASET)


def fetch_public_indicators_payload() -> Dict[str, Any]:
    sources = (("mindicador", MINDICADOR_API_URL), ("findic", FINDIC_API_URL))
    deadline = monotonic() + 15
    errors: list[str] = []

    for name, url in sources:
        try:
            items = _fetch_from_source(url, deadline)
            _validate_indicator_freshness(items)
            return {
                "items": items,
                "fetched_at": _iso_now(),
                "source": name,
                "source_url": url,
            }
        except RuntimeError as error:
            errors.append(str(error))

    details = " | ".join(errors) if errors else "sin detalle"
    raise RuntimeError(
        f"No se pudo obtener indicadores desde ninguna fuente pública. {details}"
    )


def _validate_indicator_freshness(items: list[dict]) -> None:
    today = datetime.now(UTC).date()
    max_age = {"uf": 7, "utm": 45, "dollar_observed": 7, "ipc_annual": 62}
    for item in items:
        age = (today - date.fromisoformat(item["observed_at"])).days
        if not -1 <= age <= max_age[item["key"]]:
            raise RuntimeError(
                f"{item['label']}: la observación al {item['observed_at']} está fuera del plazo admisible."
            )


def _fetch_from_source(url: str, deadline: float) -> list[Dict[str, Any]]:
    summary = _request_json(url, deadline)

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

    ipc_history = _request_json(f"{url}/ipc", deadline)
    ipc_annual_value, ipc_observed_at = _compute_annual_ipc_from_series(
        _read_series(ipc_history)
    )
    ipc = _build_indicator_item(
        key="ipc_annual",
        value=ipc_annual_value,
        observed_at=ipc_observed_at,
    )

    return [uf, utm, dollar, ipc]


def _request_json(url: str, deadline: float) -> Dict[str, Any]:
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

    remaining = deadline - monotonic()
    if remaining <= 0:
        raise RuntimeError("Se agotó el tiempo reservado para indicadores.")
    try:
        with urlopen(request, timeout=min(4, remaining)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = _read_http_error_details(error)
        raise RuntimeError(
            f"La fuente pública {url} respondió HTTP {error.code}: {details}."
        ) from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(
            f"No se pudo conectar con la fuente pública {url}."
        ) from error
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"La fuente pública {url} devolvió JSON inválido."
        ) from error

    if not isinstance(payload, dict):
        raise RuntimeError(
            f"La fuente pública {url} no devolvió un objeto JSON válido."
        )

    return payload


def _build_indicator_item(
    *, key: str, value: float, observed_at: str
) -> Dict[str, Any]:
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
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
    ):
        raise RuntimeError(
            f"La respuesta del indicador '{code}' no contiene un valor numérico."
        )

    return float(value)


def _read_top_level_date(payload: Dict[str, Any], code: str) -> str:
    node = payload.get(code)
    if not isinstance(node, dict):
        raise RuntimeError(
            f"La respuesta no contiene fecha para el indicador '{code}'."
        )

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
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
        ):
            continue
        normalized_date = _normalize_public_date(raw_date)
        monthly_points.append((normalized_date, float(value)))

    if len(monthly_points) < 12:
        raise RuntimeError(
            "No hay suficientes observaciones mensuales para calcular IPC anual."
        )

    monthly_points.sort(key=lambda item: item[0], reverse=True)
    latest_twelve = monthly_points[:12]
    months = [date_value[:7] for date_value, _ in latest_twelve]
    month_numbers = [int(m[:4]) * 12 + int(m[5:]) for m in months]
    if any(a - b != 1 for a, b in zip(month_numbers, month_numbers[1:])):
        raise RuntimeError("El IPC necesita doce meses consecutivos y sin duplicados.")
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


def _safe_read_payload(dataset) -> Dict[str, Any] | None:
    try:
        payload, _ = read_dataset(dataset)
        return payload
    except (OSError, RuntimeError, ValueError):
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
    return 0 <= delta.total_seconds() < _read_cooldown_seconds()


def _read_cooldown_seconds() -> int:
    raw_value = os.getenv(
        "REFRESH_COOLDOWN_SECONDS", str(DEFAULT_COOLDOWN_SECONDS)
    ).strip()
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


def _build_skipped_result(
    dataset: str, payload: Dict[str, Any] | None, message: str
) -> RefreshResult:
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
