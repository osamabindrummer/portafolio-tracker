"""Modelo del portafolio: históricos únicos, métricas y respuesta pública."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

METRIC_SUMMARIES = {
    "daily_change_pct": "avg_daily_change",
    "monthly_change_pct": "avg_monthly_change",
    "return_1y": "avg_return_1y",
    "return_5y": "avg_return_5y",
}
MAX_QUOTE_AGE_DAYS = 7


def compute_normalized_series(
    price_history: Sequence[Dict[str, float]],
) -> List[Dict[str, float]]:
    if not price_history:
        return []
    base_price = price_history[0]["close"] or 1.0
    normalized = []
    for point in price_history:
        value = 100 * (point["close"] / base_price) if base_price else 0.0
        normalized.append(
            {
                "date": point["date"],
                "value": round(value, 2),
            }
        )
    return normalized


def parse_price_history(
    price_history: Sequence[Dict[str, float]],
) -> List[Tuple[date, float]]:
    parsed: List[Tuple[date, float]] = []
    for point in price_history:
        if "date" not in point or "close" not in point:
            continue
        try:
            parsed_date = datetime.fromisoformat(str(point["date"])).date()
        except ValueError:
            parsed_date = datetime.fromisoformat(str(point["date"])[:10]).date()
        try:
            price_value = float(point["close"])
        except (TypeError, ValueError):
            continue
        parsed.append((parsed_date, price_value))
    parsed.sort(key=lambda item: item[0])
    return parsed


def level_on_or_before(
    history: Sequence[Tuple[date, float]], target: date
) -> Optional[float]:
    for history_date, price in reversed(history):
        if history_date <= target:
            return price if (target - history_date).days <= 7 else None
    # El inicio de la consulta de cinco años puede caer en fin de semana.
    if history and 0 <= (history[0][0] - target).days <= 7:
        return history[0][1]
    return None


def compute_percentage_change(latest: float, base: Optional[float]) -> Optional[float]:
    if base is None or base == 0:
        return None
    return (latest / base) - 1.0


def compute_returns(
    price_history: List[Dict[str, float]],
) -> Dict[str, Optional[float]]:
    parsed_history = parse_price_history(price_history)
    if len(parsed_history) < 2:
        return {
            "return_1y": None,
            "return_5y": None,
            "monthly_change_pct": None,
            "daily_change_pct": None,
        }

    latest_date, latest_price = parsed_history[-1]
    _, previous_price = parsed_history[-2]

    one_month_threshold = latest_date - timedelta(days=30)

    def years_ago(years):
        try:
            return latest_date.replace(year=latest_date.year - years)
        except ValueError:
            return latest_date.replace(year=latest_date.year - years, day=28)

    one_year_threshold = years_ago(1)
    five_year_threshold = years_ago(5)

    base_1m = level_on_or_before(parsed_history, one_month_threshold)
    base_1y = level_on_or_before(parsed_history, one_year_threshold)
    base_5y = level_on_or_before(parsed_history, five_year_threshold)

    daily_change_pct = (
        compute_percentage_change(latest_price, previous_price)
        if (latest_date - parsed_history[-2][0]).days <= 7
        else None
    )
    monthly_change_pct = compute_percentage_change(latest_price, base_1m)
    return_1y = compute_percentage_change(latest_price, base_1y)
    return_5y = compute_percentage_change(latest_price, base_5y)

    def rounded(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return round(value, 4)

    return {
        "return_1y": rounded(return_1y),
        "return_5y": rounded(return_5y),
        "monthly_change_pct": rounded(monthly_change_pct),
        "daily_change_pct": rounded(daily_change_pct),
    }


def refresh_derived(payload: dict) -> dict:
    # Las métricas y los gráficos siempre nacen de los mismos precios.
    result = deepcopy(payload)
    today = datetime.now(UTC).date()
    datasets = []
    labels = set()
    histograms = {"monthly_change": [], "return_1y": [], "return_5y": []}
    for platform in result["platforms"]:
        starts, ends = [], []
        summary = {
            "configured_weight": round(
                sum(h["weight"] for h in platform["holdings"]), 4
            )
        }
        coverage = {}
        currencies = {h["currency"] for h in platform["holdings"]}
        platform["currency"] = (
            next(iter(currencies)) if len(currencies) == 1 else "MIXED"
        )
        for holding in platform["holdings"]:
            history = holding.get("series", {}).get("price_history", [])
            holding["metrics"] = compute_returns(history)
            holding["latest_price"] = history[-1]["close"] if history else None
            holding["observed_at"] = history[-1]["date"] if history else None
            status = holding.setdefault("status", {})
            status["missing_data"] = len(history) < 2
            status["stale"] = (
                not history
                or (today - date.fromisoformat(history[-1]["date"])).days
                > MAX_QUOTE_AGE_DAYS
            )
            status.setdefault("warnings", [])
            normalized = compute_normalized_series(history)
            holding["series"] = {"price_history": history}
            if history:
                starts.append(history[0]["date"])
                ends.append(history[-1]["date"])
                data_map = {p["date"]: p["value"] for p in normalized}
                labels.update(data_map)
                datasets.append(
                    {
                        "id": holding["ticker"],
                        "label": f"{holding['ticker']} · {platform['name']}",
                        "platform_id": platform["id"],
                        "weight": holding["weight"],
                        "data_map": data_map,
                    }
                )
            for metric, histogram in (
                ("monthly_change_pct", "monthly_change"),
                ("return_1y", "return_1y"),
                ("return_5y", "return_5y"),
            ):
                value = holding["metrics"][metric]
                if value is not None:
                    histograms[histogram].append(
                        {
                            "ticker": holding["ticker"],
                            "label": holding["ticker"],
                            "platform_id": platform["id"],
                            "weight": holding["weight"],
                            "value": value,
                        }
                    )
        for metric, summary_key in METRIC_SUMMARIES.items():
            usable = [
                h for h in platform["holdings"] if h["metrics"][metric] is not None
            ]
            weight = sum(h["weight"] for h in usable)
            coverage[metric] = round(weight, 4)
            summary[summary_key] = (
                round(
                    sum(h["weight"] * h["metrics"][metric] for h in usable) / weight, 4
                )
                if weight
                else None
            )
        summary["coverage"] = coverage
        summary["total_weight"] = round(
            sum(
                h["weight"]
                for h in platform["holdings"]
                if not h["status"]["missing_data"]
            ),
            4,
        )
        summary["fresh_weight"] = round(
            sum(
                h["weight"]
                for h in platform["holdings"]
                if not h["status"]["missing_data"]
                and not h["status"]["stale"]
                and not h["status"].get("retained")
            ),
            4,
        )
        if ends:
            summary["timestamp_range"] = {"start": min(starts), "end": max(ends)}
            summary["quote_range"] = {"start": min(ends), "end": max(ends)}
        platform["summary"] = summary
    sorted_labels = sorted(labels)
    for dataset in datasets:
        dataset["data"] = [dataset["data_map"].get(day) for day in sorted_labels]
        del dataset["data_map"]
    result["currency"] = "MIXED"
    result["charts"] = {
        "timeseries_5y": {"labels": sorted_labels, "datasets": datasets},
        "histograms": histograms,
    }
    return result


def pack_payload(payload: dict) -> dict:
    """Guarda cada histórico una vez; las métricas se reconstruyen al leer."""
    if payload.get("schema_version") == 2:
        return payload
    result = {
        k: deepcopy(v) for k, v in payload.items() if k not in ("charts", "platforms")
    }
    result.update(schema_version=2, histories={}, platforms=[])
    for platform in payload["platforms"]:
        packed = {
            k: deepcopy(v)
            for k, v in platform.items()
            if k not in ("summary", "holdings")
        }
        packed["holdings"] = []
        for holding in platform["holdings"]:
            symbol = holding.get("quote_symbol", holding["ticker"])
            history = holding.get("series", {}).get("price_history", [])
            if symbol in result["histories"] and result["histories"][symbol] != history:
                raise ValueError(
                    f"Históricos incompatibles para el símbolo compartido {symbol}."
                )
            result["histories"][symbol] = history
            packed["holdings"].append(
                {
                    k: deepcopy(v)
                    for k, v in holding.items()
                    if k not in ("metrics", "series", "latest_price", "observed_at")
                }
            )
        result["platforms"].append(packed)
    return result


def unpack_payload(payload: dict) -> dict:
    result = deepcopy(payload)
    if result.pop("schema_version", None) == 2:
        histories = result.pop("histories")
        for platform in result["platforms"]:
            for holding in platform["holdings"]:
                symbol = holding.get("quote_symbol", holding["ticker"])
                holding["series"] = {"price_history": histories[symbol]}
    return refresh_derived(result)


def public_payload(payload: dict) -> dict:
    # El navegador sólo necesita las métricas y la serie lista para graficar.
    result = deepcopy(payload)
    for platform in result["platforms"]:
        for holding in platform["holdings"]:
            holding.pop("series", None)
    return result
