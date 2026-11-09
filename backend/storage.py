"""Snapshots locales atómicos o versiones limitadas en Vercel Blob."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.seed_payloads import INDICATORS_SEED
from scripts.portfolio import pack_payload, unpack_payload
from scripts.validate_json import validate_indicators, validate_payload

try:
    from vercel.blob.sync import delete_blob, get_blob, put_blob, query_blobs
except ImportError:
    delete_blob = get_blob = put_blob = query_blobs = None

BASE_DIR = Path(__file__).resolve().parents[1]
RETAINED_SNAPSHOTS = 5
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatasetConfig:
    key: str
    local_path: Path
    blob_prefix: str
    timestamp_field: str


@dataclass(frozen=True)
class StorageMeta:
    source: str
    pathname: str | None = None
    url: str | None = None
    warning: str | None = None


LATEST_DATASET = DatasetConfig(
    "latest", BASE_DIR / "data/latest.json", "portfolio/latest", "generated_at"
)
INDICATORS_DATASET = DatasetConfig(
    "indicators",
    BASE_DIR / "public/indicators/latest.json",
    "portfolio/indicators",
    "fetched_at",
)


def _decode(config, raw):
    payload = json.loads(raw)
    if config.key == "latest":
        payload = unpack_payload(payload)
        validate_payload(payload)
        return payload
    validate_indicators(payload)
    return payload


def read_dataset(config):
    warning = None
    try:
        if should_use_blob_storage():
            payload, meta = _read_from_blob(config)
            if payload is not None:
                return payload, meta
            warning = "Blob todavía no contiene snapshots; se usa la semilla local."
    except Exception:
        logger.exception(
            "No se pudo leer Blob para %s; se intentará la semilla local.", config.key
        )
        warning = "No se pudo leer Blob; se usa la semilla local."
    if config.local_path.exists():
        return _decode(
            config, config.local_path.read_text(encoding="utf-8")
        ), StorageMeta(
            source="local-fallback" if warning else "local",
            pathname=str(config.local_path.relative_to(BASE_DIR)),
            warning=warning,
        )
    if config.key == "indicators":
        return INDICATORS_SEED, StorageMeta("embedded-seed", warning=warning)
    raise FileNotFoundError(f"No existe un snapshot válido de {config.key}.")


def write_dataset(config, payload):
    if config.key == "latest":
        validate_payload(payload)
        payload = pack_payload(payload)
    else:
        validate_indicators(payload)
    if should_use_blob_storage():
        return _write_to_blob(config, payload)
    if is_running_on_vercel():
        raise RuntimeError(
            "Vercel requiere Blob; el almacenamiento local sólo se permite fuera de Vercel."
        )
    write_local_json(config.local_path, payload)
    return StorageMeta("local", str(config.local_path.relative_to(BASE_DIR)))


def should_use_blob_storage():
    mode = os.getenv("PORTFOLIO_STORAGE", "").strip().lower()
    if mode not in ("", "local", "blob"):
        raise RuntimeError("PORTFOLIO_STORAGE debe ser local o blob.")
    requested = mode == "blob" or (is_running_on_vercel() and mode != "local")
    if not requested:
        return False
    if put_blob is None:
        raise RuntimeError(
            "SDK de Blob incompatible o ausente. Instala requirements.txt."
        )
    if not os.getenv("BLOB_READ_WRITE_TOKEN", "").strip():
        raise RuntimeError("Falta BLOB_READ_WRITE_TOKEN para utilizar Blob.")
    return True


def is_running_on_vercel():
    return bool(os.getenv("VERCEL"))


def write_local_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Reemplazar el archivo completo evita que una lectura encuentre JSON a medias.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as output:
            temporary = Path(output.name)
            json.dump(
                payload,
                output,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def _read_from_blob(config):
    # query_blobs recorre todas las páginas, también en almacenes anteriores a esta versión.
    blobs = sorted(
        query_blobs(prefix=f"{config.blob_prefix}/"),
        key=lambda b: b.uploaded_at,
        reverse=True,
    )
    for index, blob in enumerate(blobs[:RETAINED_SNAPSHOTS]):
        try:
            payload = _decode(config, get_blob(blob.url, access="public").body)
            return payload, StorageMeta(
                "blob",
                blob.pathname,
                blob.url,
                "Se recuperó una versión anterior de Blob." if index else None,
            )
        except Exception:
            logger.exception("Snapshot ilegible: %s", blob.pathname)
    if blobs:
        raise RuntimeError("No se encontraron snapshots válidos en Blob.")
    return None, StorageMeta("blob")


def _write_to_blob(config, payload):
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    pathname = f"{config.blob_prefix}/{stamp}-{uuid4().hex}.json"
    blob = put_blob(
        pathname,
        json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode(),
        access="public",
        content_type="application/json; charset=utf-8",
        add_random_suffix=False,
    )
    # La limpieza ocurre después de guardar. Su fallo no invalida una escritura exitosa.
    try:
        previous = sorted(
            (
                b
                for b in query_blobs(prefix=f"{config.blob_prefix}/")
                if b.pathname != pathname
            ),
            key=lambda b: b.uploaded_at,
            reverse=True,
        )
        obsolete = [b.url for b in previous[RETAINED_SNAPSHOTS - 1 :]]
        for start in range(0, len(obsolete), 1000):
            delete_blob(obsolete[start : start + 1000])
    except Exception:
        logger.exception("No se pudo limitar la retención de %s.", config.key)
    return StorageMeta("blob", blob.pathname, blob.url)
