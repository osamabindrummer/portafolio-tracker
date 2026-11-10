#!/usr/bin/env python3
"""Valida estructura y coherencia de precios antes de guardar un portafolio."""

from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime
from pathlib import Path


class ValidationError(ValueError):
    """Agrupa los errores para que puedan corregirse en una sola revisión."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_indicators(payload: dict) -> None:
    errors = []
    expected = {"uf", "utm", "dollar_observed", "ipc_annual"}
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValidationError(["Los indicadores deben contener una lista items."])
    keys = []
    for item in payload["items"]:
        if not isinstance(item, dict):
            errors.append("Cada indicador debe ser un objeto.")
            continue
        key = item.get("key")
        if not isinstance(key, str):
            errors.append("Identificador de indicador inválido.")
            continue
        if key not in expected or key in keys:
            errors.append("Indicador desconocido o duplicado.")
        keys.append(key)
        if not _is_number(item.get("value")) or (
            key != "ipc_annual" and item["value"] <= 0
        ):
            errors.append("Valor de indicador inválido.")
        if not isinstance(item.get("label"), str) or item.get("unit") not in (
            "CLP",
            "PERCENT",
        ):
            errors.append("Nombre o unidad de indicador inválidos.")
        decimals = item.get("decimals")
        if type(decimals) is not int or not 0 <= decimals <= 6:
            errors.append("Precisión del indicador inválida.")
        try:
            date.fromisoformat(item.get("observed_at", ""))
        except (ValueError, TypeError):
            errors.append("Fecha de observación inválida.")
    if set(keys) != expected:
        errors.append("Faltan indicadores obligatorios.")
    try:
        timestamp = datetime.fromisoformat(
            payload.get("fetched_at", "").replace("Z", "+00:00")
        )
        if timestamp.tzinfo is None:
            errors.append("La fecha de consulta necesita zona horaria.")
    except (ValueError, TypeError, AttributeError):
        errors.append("Fecha de consulta inválida.")
    if errors:
        raise ValidationError(errors)


def validate_payload(payload: dict) -> None:
    if isinstance(payload, dict) and payload.get("schema_version") == 2:
        from scripts.portfolio import unpack_payload

        try:
            payload = unpack_payload(payload)
        except (KeyError, TypeError, ValueError) as error:
            raise ValidationError(
                [f"Históricos compactos inválidos: {error}"]
            ) from error
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    def valid_date(value):
        try:
            return (
                isinstance(value, str)
                and date.fromisoformat(value).isoformat() == value
            )
        except ValueError:
            return False

    if not isinstance(payload, dict):
        raise ValidationError(["El portafolio debe ser un objeto."])
    for field in ("generated_at",):
        try:
            stamp = datetime.fromisoformat(
                payload.get(field, "").replace("Z", "+00:00")
            )
            require(stamp.tzinfo is not None, f"{field} necesita zona horaria.")
        except (ValueError, AttributeError, TypeError):
            errors.append(f"{field} debe ser una fecha válida.")
    require(isinstance(payload.get("currency"), str), "currency debe ser texto.")
    source = payload.get("source")
    require(
        isinstance(source, dict) and isinstance(source.get("provider"), str),
        "source.provider es obligatorio.",
    )
    platforms = payload.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        raise ValidationError(errors + ["platforms debe ser una lista no vacía."])
    platform_ids = set()
    for platform in platforms:
        if not isinstance(platform, dict):
            errors.append("Cada plataforma debe ser un objeto.")
            continue
        pid = platform.get("id")
        require(
            isinstance(pid, str) and bool(pid) and pid not in platform_ids,
            "Identificador de plataforma inválido o duplicado.",
        )
        if not isinstance(pid, str):
            continue
        platform_ids.add(pid)
        for field in ("name", "color"):
            require(isinstance(platform.get(field), str), f"{pid}: falta {field}.")
        holdings = platform.get("holdings")
        if not isinstance(holdings, list) or not holdings:
            errors.append(f"{pid}: holdings debe ser una lista no vacía.")
            continue
        tickers = set()
        total_weight = 0
        for holding in holdings:
            if not isinstance(holding, dict):
                errors.append(f"{pid}: cada holding debe ser un objeto.")
                continue
            ticker = holding.get("ticker")
            require(
                isinstance(ticker, str) and bool(ticker) and ticker not in tickers,
                f"{pid}: ticker inválido o duplicado.",
            )
            if isinstance(ticker, str):
                tickers.add(ticker)
            for field in ("display_name", "currency"):
                require(
                    isinstance(holding.get(field), str), f"{ticker}: falta {field}."
                )
            weight = holding.get("weight")
            require(
                _is_number(weight) and 0 < weight <= 1,
                f"{ticker}: peso fuera de rango.",
            )
            if _is_number(weight):
                total_weight += weight
            metrics = holding.get("metrics")
            if not isinstance(metrics, dict):
                errors.append(f"{ticker}: metrics debe ser objeto.")
            else:
                for key in (
                    "return_1y",
                    "return_5y",
                    "monthly_change_pct",
                    "daily_change_pct",
                ):
                    require(
                        metrics.get(key) is None or _is_number(metrics[key]),
                        f"{ticker}: {key} no es finito.",
                    )
            price_source = holding.get("price_source")
            if price_source is not None:
                if not isinstance(price_source, dict):
                    errors.append(f"{ticker}: price_source debe ser un objeto.")
                else:
                    require(
                        price_source.get("provider") in ("yfinance", "racional"),
                        f"{ticker}: fuente de precios desconocida.",
                    )
                    require(
                        type(price_source.get("adjusted")) is bool,
                        f"{ticker}: adjusted debe ser booleano.",
                    )
                    require(
                        isinstance(price_source.get("source_url"), str)
                        and price_source["source_url"].startswith("https://"),
                        f"{ticker}: falta la URL de la fuente.",
                    )
                    require(
                        valid_date(price_source.get("corroborated_at")),
                        f"{ticker}: falta la fecha de corroboración.",
                    )
                    if price_source.get("provider") == "racional":
                        require(
                            price_source.get("adjusted") is False,
                            f"{ticker}: no se ha verificado el ajuste de distribuciones de Racional.",
                        )
                    if price_source.get("adjusted") is False and isinstance(
                        metrics, dict
                    ):
                        require(
                            metrics.get("return_1y") is None
                            and metrics.get("return_5y") is None,
                            f"{ticker}: no se pueden atribuir retornos ajustados a esta fuente.",
                        )
            series = holding.get("series")
            history = series.get("price_history") if isinstance(series, dict) else None
            if not isinstance(history, list):
                errors.append(f"{ticker}: price_history debe ser una lista.")
                continue
            previous = None
            for point in history:
                if not isinstance(point, dict):
                    errors.append(f"{ticker}: observación inválida.")
                    continue
                day, close = point.get("date"), point.get("close")
                require(valid_date(day), f"{ticker}: fecha inválida.")
                if valid_date(day):
                    require(
                        previous is None or day > previous,
                        f"{ticker}: fechas duplicadas o desordenadas.",
                    )
                    previous = day
                require(
                    _is_number(close) and close > 0,
                    f"{ticker}: precio no positivo o no finito.",
                )
        require(total_weight <= 1.001, f"{pid}: los pesos superan el 100 %.")
    charts = payload.get("charts")
    if not isinstance(charts, dict):
        errors.append("charts debe ser un objeto.")
    else:
        timeseries = charts.get("timeseries_5y", {})
        labels = timeseries.get("labels") if isinstance(timeseries, dict) else None
        datasets = timeseries.get("datasets") if isinstance(timeseries, dict) else None
        if not isinstance(labels, list) or not isinstance(datasets, list):
            errors.append("La serie de gráficos debe contener labels y datasets.")
        else:
            require(
                all(valid_date(day) for day in labels)
                and labels == sorted(set(labels)),
                "Fechas del gráfico inválidas.",
            )
            for dataset in datasets:
                if not isinstance(dataset, dict) or not isinstance(
                    dataset.get("data"), list
                ):
                    errors.append("Dataset del gráfico inválido.")
                    continue
                require(
                    dataset.get("platform_id") in platform_ids,
                    "Plataforma desconocida en gráfico.",
                )
                require(
                    len(dataset["data"]) == len(labels),
                    "Las fechas y los valores del gráfico no coinciden.",
                )
                require(
                    all(v is None or _is_number(v) for v in dataset["data"]),
                    "Valores del gráfico no finitos.",
                )
    if errors:
        raise ValidationError(errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", type=Path)
    args = parser.parse_args()
    validate_payload(json.loads(args.json_path.read_text(encoding="utf-8")))
    print(f"{args.json_path} pasa la validación de estructura y coherencia.")


if __name__ == "__main__":
    main()
