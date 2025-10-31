#!/usr/bin/env python3
"""Validador liviano para el archivo data/latest.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

Number = (int, float)


class ValidationError(Exception):
    """Error que agrupa una o más fallas de validación."""

    def __init__(self, errors: Iterable[str]):
        message = "\n".join(errors)
        super().__init__(message)
        self.errors = list(errors)


def _is_number(value: Any, *, allow_none: bool = False) -> bool:
    if value is None and allow_none:
        return True
    return isinstance(value, Number)


def _require(condition: bool, message: str, errors: List[str]) -> None:
    if not condition:
        errors.append(message)


def validate_holding(holding: Dict[str, Any], *, platform_id: str, errors: List[str]) -> None:
    prefix = f"Holding {holding.get('ticker', '<sin ticker>')} ({platform_id})"

    _require(isinstance(holding.get("ticker"), str) and holding["ticker"].strip(), f"{prefix}: ticker inválido", errors)
    _require(
        isinstance(holding.get("display_name"), str) and holding["display_name"].strip(),
        f"{prefix}: display_name inválido",
        errors,
    )
    _require(_is_number(holding.get("weight")), f"{prefix}: weight debe ser numérico", errors)
    _require(isinstance(holding.get("currency"), str), f"{prefix}: currency debe ser string", errors)

    metrics = holding.get("metrics", {})
    _require(isinstance(metrics, dict), f"{prefix}: metrics debe ser objeto", errors)
    for key in ("return_1y", "return_5y", "monthly_change_pct", "daily_change_pct"):
        _require(
            _is_number(metrics.get(key), allow_none=True),
            f"{prefix}: metrics.{key} debe ser número o null",
            errors,
        )

    series = holding.get("series", {})
    _require(isinstance(series, dict), f"{prefix}: series debe ser objeto", errors)

    price_history = series.get("price_history", [])
    _require(isinstance(price_history, list), f"{prefix}: series.price_history debe ser lista", errors)
    for point in price_history:
        _require(isinstance(point, dict), f"{prefix}: price_history debe contener objetos", errors)
        _require(isinstance(point.get("date"), str), f"{prefix}: price_history.date debe ser string", errors)
        _require(
            _is_number(point.get("close")),
            f"{prefix}: price_history.close debe ser numérico",
            errors,
        )

    normalized = series.get("normalized_5y", [])
    _require(isinstance(normalized, list), f"{prefix}: series.normalized_5y debe ser lista", errors)
    for point in normalized:
        _require(isinstance(point, dict), f"{prefix}: normalized_5y debe contener objetos", errors)
        _require(isinstance(point.get("date"), str), f"{prefix}: normalized_5y.date debe ser string", errors)
        _require(
            _is_number(point.get("value")),
            f"{prefix}: normalized_5y.value debe ser numérico",
            errors,
        )


def validate_platform(platform: Dict[str, Any], errors: List[str]) -> None:
    platform_id = platform.get("id", "")
    prefix = f"Plataforma {platform_id or '<sin id>'}"

    _require(isinstance(platform_id, str) and platform_id.strip(), f"{prefix}: id inválido", errors)
    _require(isinstance(platform.get("name"), str), f"{prefix}: name debe ser string", errors)
    _require(isinstance(platform.get("color"), str), f"{prefix}: color debe ser string", errors)

    holdings = platform.get("holdings", [])
    _require(isinstance(holdings, list), f"{prefix}: holdings debe ser lista", errors)
    for holding in holdings:
        if isinstance(holding, dict):
            validate_holding(holding, platform_id=platform_id, errors=errors)
        else:
            errors.append(f"{prefix}: holdings debe contener objetos")

    summary = platform.get("summary")
    if summary is not None:
        _require(isinstance(summary, dict), f"{prefix}: summary debe ser objeto", errors)
        if isinstance(summary, dict):
            for key in ("total_weight", "avg_return_1y", "avg_return_5y", "avg_monthly_change"):
                if key in summary:
                    _require(
                        _is_number(summary.get(key)),
                        f"{prefix}: summary.{key} debe ser numérico",
                        errors,
                    )
            if "timestamp_range" in summary:
                range_value = summary["timestamp_range"]
                _require(isinstance(range_value, dict), f"{prefix}: summary.timestamp_range debe ser objeto", errors)
                if isinstance(range_value, dict):
                    _require(
                        isinstance(range_value.get("start"), str),
                        f"{prefix}: summary.timestamp_range.start debe ser string",
                        errors,
                    )
                    _require(
                        isinstance(range_value.get("end"), str),
                        f"{prefix}: summary.timestamp_range.end debe ser string",
                        errors,
                    )


def validate_charts(charts: Dict[str, Any], errors: List[str]) -> None:
    _require(isinstance(charts, dict), "charts debe ser un objeto", errors)
    if not isinstance(charts, dict):
        return

    timeseries = charts.get("timeseries_5y", {})
    _require(isinstance(timeseries, dict), "charts.timeseries_5y debe ser objeto", errors)
    if isinstance(timeseries, dict):
        labels = timeseries.get("labels", [])
        _require(isinstance(labels, list), "charts.timeseries_5y.labels debe ser lista", errors)
        for label in labels:
            _require(isinstance(label, str), "charts.timeseries_5y.labels debe contener strings", errors)

        datasets = timeseries.get("datasets", [])
        _require(isinstance(datasets, list), "charts.timeseries_5y.datasets debe ser lista", errors)
        for dataset in datasets:
            _require(isinstance(dataset, dict), "charts.timeseries_5y.datasets debe contener objetos", errors)
            if not isinstance(dataset, dict):
                continue
            prefix = f"Dataset {dataset.get('id', '<sin id>')}"
            for key in ("id", "label", "platform_id", "borderColor", "backgroundColor"):
                _require(isinstance(dataset.get(key), str), f"{prefix}: {key} debe ser string", errors)
            data = dataset.get("data", [])
            _require(isinstance(data, list), f"{prefix}: data debe ser lista", errors)
            for value in data:
                _require(
                    _is_number(value, allow_none=True),
                    f"{prefix}: data debe contener números o null",
                    errors,
                )

    histograms = charts.get("histograms", {})
    _require(isinstance(histograms, dict), "charts.histograms debe ser objeto", errors)
    if isinstance(histograms, dict):
        for histogram_key in ("monthly_change", "return_1y", "return_5y"):
            if histogram_key not in histograms:
                continue
            histogram_values = histograms[histogram_key]
            _require(isinstance(histogram_values, list), f"charts.histograms.{histogram_key} debe ser lista", errors)
            for entry in histogram_values:
                _require(isinstance(entry, dict), f"charts.histograms.{histogram_key} debe contener objetos", errors)
                if not isinstance(entry, dict):
                    continue
                prefix = f"Histogram {histogram_key} · {entry.get('ticker', '<sin ticker>')}"
                _require(isinstance(entry.get("ticker"), str), f"{prefix}: ticker debe ser string", errors)
                _require(isinstance(entry.get("platform_id"), str), f"{prefix}: platform_id debe ser string", errors)
                _require(isinstance(entry.get("label"), str), f"{prefix}: label debe ser string", errors)
                _require(_is_number(entry.get("weight")), f"{prefix}: weight debe ser numérico", errors)
                _require(
                    _is_number(entry.get("value")),
                    f"{prefix}: value debe ser numérico",
                    errors,
                )


def validate_payload(payload: Dict[str, Any]) -> None:
    errors: List[str] = []

    for key in ("generated_at", "currency", "source", "platforms", "charts"):
        _require(key in payload, f"Falta la clave obligatoria: {key}", errors)

    _require(isinstance(payload.get("generated_at"), str), "generated_at debe ser string", errors)
    _require(isinstance(payload.get("currency"), str), "currency debe ser string", errors)

    source = payload.get("source", {})
    _require(isinstance(source, dict), "source debe ser objeto", errors)
    if isinstance(source, dict):
        _require(isinstance(source.get("provider"), str), "source.provider debe ser string", errors)
        if "retrieved_at" in source:
            _require(isinstance(source.get("retrieved_at"), str), "source.retrieved_at debe ser string", errors)
        if "notes" in source:
            _require(isinstance(source.get("notes"), dict), "source.notes debe ser objeto", errors)

    platforms = payload.get("platforms", [])
    _require(isinstance(platforms, list), "platforms debe ser lista", errors)
    for platform in platforms:
        if isinstance(platform, dict):
            validate_platform(platform, errors)
        else:
            errors.append("platforms debe contener objetos")

    charts = payload.get("charts", {})
    validate_charts(charts, errors)

    if errors:
        raise ValidationError(errors)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida la estructura del JSON del portafolio")
    parser.add_argument("json_path", type=Path, help="Ruta al archivo JSON a validar")
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    json_path: Path = args.json_path

    if not json_path.exists():
        raise SystemExit(f"No existe el archivo {json_path}")

    with json_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    try:
        validate_payload(payload)
    except ValidationError as error:
        raise SystemExit(f"Estructura inválida:\n{error}") from error

    print(f"{json_path} pasa la validación de estructura ✅")


if __name__ == "__main__":
    main()
