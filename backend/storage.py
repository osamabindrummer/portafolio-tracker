"""Persistencia de JSON en disco local o Vercel Blob."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from backend.seed_payloads import FINTUAL_GOALS_SEED

try:
    from vercel.blob import BlobClient, list_objects
except ImportError:  # pragma: no cover - depende del entorno
    BlobClient = None  # type: ignore[assignment]
    list_objects = None  # type: ignore[assignment]


BASE_DIR = Path(__file__).resolve().parents[1]


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


LATEST_DATASET = DatasetConfig(
    key="latest",
    local_path=BASE_DIR / "data" / "latest.json",
    blob_prefix="portfolio/latest",
    timestamp_field="generated_at",
)

GOALS_DATASET = DatasetConfig(
    key="goals",
    local_path=BASE_DIR / "public" / "fintual" / "goals.json",
    blob_prefix="portfolio/fintual-goals",
    timestamp_field="fetched_at",
)


def read_dataset(config: DatasetConfig) -> Tuple[Dict[str, Any], StorageMeta]:
    if should_use_blob_storage():
        payload, meta = _read_from_blob(config)
        if payload is not None:
            return payload, meta

    if config.local_path.exists():
        payload = _read_from_local_file(config.local_path)
        return payload, StorageMeta(source="local", pathname=_display_path(config.local_path))

    if config.key == GOALS_DATASET.key:
        return FINTUAL_GOALS_SEED, StorageMeta(source="embedded-seed", pathname="backend/seed_payloads.py")

    raise FileNotFoundError(f"No existe {config.local_path}")


def write_dataset(config: DatasetConfig, payload: Dict[str, Any]) -> StorageMeta:
    if should_use_blob_storage():
        return _write_to_blob(config, payload)

    if is_running_on_vercel():
        raise RuntimeError(
            "Falta BLOB_READ_WRITE_TOKEN en Vercel. No es seguro depender del filesystem local porque es de solo lectura."
        )

    _write_to_local_file(config.local_path, payload)
    return StorageMeta(source="local", pathname=_display_path(config.local_path))


def should_use_blob_storage() -> bool:
    mode = os.getenv("PORTFOLIO_STORAGE", "").strip().lower()
    has_blob_sdk = BlobClient is not None and list_objects is not None
    has_token = bool(os.getenv("BLOB_READ_WRITE_TOKEN"))

    if mode == "local":
        return False
    if mode == "blob":
        return has_blob_sdk and has_token

    return is_running_on_vercel() and has_blob_sdk and has_token


def is_running_on_vercel() -> bool:
    return bool(os.getenv("VERCEL"))


def _read_from_local_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_to_local_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(f"{serialized}\n", encoding="utf-8")


def _read_from_blob(config: DatasetConfig) -> Tuple[Dict[str, Any] | None, StorageMeta]:
    if list_objects is None:
        return None, StorageMeta(source="blob")

    page = list_objects(prefix=f"{config.blob_prefix}/", limit=1000)
    blobs = list(page.blobs)
    if not blobs:
        return None, StorageMeta(source="blob")

    latest_blob = max(blobs, key=lambda item: item.uploaded_at)
    try:
        with urlopen(latest_blob.url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"No se pudo leer el blob {latest_blob.pathname}.") from error

    return payload, StorageMeta(source="blob", pathname=latest_blob.pathname, url=latest_blob.url)


def _write_to_blob(config: DatasetConfig, payload: Dict[str, Any]) -> StorageMeta:
    if BlobClient is None:
        raise RuntimeError("El SDK de Vercel Blob no está disponible en este entorno.")

    client = BlobClient()
    serialized = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    version_stamp = _build_version_stamp(payload.get(config.timestamp_field))
    pathname = f"{config.blob_prefix}/{version_stamp}.json"
    blob = client.put(
        pathname,
        serialized,
        access="public",
        content_type="application/json; charset=utf-8",
        add_random_suffix=False,
        overwrite=False,
    )
    return StorageMeta(source="blob", pathname=blob.pathname, url=blob.url)


def _build_version_stamp(value: Any) -> str:
    unique_suffix = datetime.now(UTC).strftime("%f")
    if isinstance(value, str):
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return f"{parsed.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}-{unique_suffix}"
        except ValueError:
            pass
    return datetime.now(UTC).strftime(f"%Y%m%dT%H%M%SZ-{unique_suffix}")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(BASE_DIR))
    except ValueError:
        return str(path)
