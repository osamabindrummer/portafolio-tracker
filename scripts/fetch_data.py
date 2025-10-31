#!/usr/bin/env python3
"""
Genera el archivo data/latest.json con la información del portafolio.
Permite producir datos deterministas (--offline) o consultar yfinance para obtener
históricos reales de los ETFs configurados.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

try:
    import yfinance as yf  # type: ignore
except ImportError:  # pragma: no cover
    yf = None  # type: ignore


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BASE_DIR / "data" / "latest.json"


@dataclass(frozen=True)
class HoldingConfig:
    ticker: str
    weight: float
    fetch_symbol: str
    display_name: str
    currency: str


PLATFORM_CONFIG: Dict[str, Dict] = {
    "racional": {
        "name": "Racional",
        "color": "#0B57D0",
        "holdings": [
            HoldingConfig(
                ticker="CFIETFGE.SN",
                weight=0.20,
                fetch_symbol="CFIETFGE.SN",
                display_name="Singular Global Equities",
                currency="CLP",
            ),
            HoldingConfig(
                ticker="IYWCL.SN",
                weight=0.35,
                fetch_symbol="IYWCL.SN",
                display_name="iShares U.S. Technology",
                currency="CLP",
            ),
            HoldingConfig(
                ticker="EEMCL.SN",
                weight=0.20,
                fetch_symbol="EEMCL.SN",
                display_name="iShares MSCI Emerging Markets",
                currency="CLP",
            ),
            HoldingConfig(
                ticker="CFMITNIPSA.SN",
                weight=0.15,
                fetch_symbol="CFMITNIPSA.SN",
                display_name="IT NOW S&P IPSA",
                currency="CLP",
            ),
            HoldingConfig(
                ticker="CFIETFCC.SN",
                weight=0.05,
                fetch_symbol="CFIETFCC.SN",
                display_name="Singular Chile Corporativo",
                currency="CLP",
            ),
            HoldingConfig(
                ticker="CFMDIVO.SN",
                weight=0.05,
                fetch_symbol="CFMDIVO.SN",
                display_name="It Now S&P/CLX Chile Dividend Index",
                currency="CLP",
            ),
        ],
    },
    "fintual": {
        "name": "Fintual",
        "color": "#FF6F61",
        "holdings": [
            HoldingConfig(
                ticker="ESGV",
                weight=0.294345,
                fetch_symbol="ESGV",
                display_name="Vanguard ESG U.S. Stock ETF",
                currency="USD",
            ),
            HoldingConfig(
                ticker="FTEC",
                weight=0.181753,
                fetch_symbol="FTEC",
                display_name="Fidelity MSCI Information Tech ETF",
                currency="USD",
            ),
            HoldingConfig(
                ticker="QQQM",
                weight=0.174532,
                fetch_symbol="QQQM",
                display_name="Invesco NASDAQ 100 ETF",
                currency="USD",
            ),
            HoldingConfig(
                ticker="SOXX",
                weight=0.108727,
                fetch_symbol="SOXX",
                display_name="iShares Semiconductor ETF",
                currency="USD",
            ),
            HoldingConfig(
                ticker="VGK",
                weight=0.102116,
                fetch_symbol="VGK",
                display_name="Vanguard FTSE Europe ETF",
                currency="USD",
            ),
            HoldingConfig(
                ticker="IAUM",
                weight=0.074451,
                fetch_symbol="IAUM",
                display_name="iShares Gold Trust Micro",
                currency="USD",
            ),
            HoldingConfig(
                ticker="KOMP",
                weight=0.045057,
                fetch_symbol="KOMP",
                display_name="SPDR Kensho New Economies ETF",
                currency="USD",
            ),
            HoldingConfig(
                ticker="EPP",
                weight=0.019019,
                fetch_symbol="EPP",
                display_name="iShares MSCI Pacific ex-Japan ETF",
                currency="USD",
            ),
        ],
    },
}


SAMPLE_BEHAVIOR: Dict[str, Dict[str, float]] = {
    "CFIETFGE.SN": {"base_price": 19_000, "annual_return": 0.06, "volatility": 0.03},
    "IYWCL.SN": {"base_price": 42_000, "annual_return": 0.12, "volatility": 0.05},
    "EEMCL.SN": {"base_price": 32_000, "annual_return": 0.08, "volatility": 0.04},
    "CFMITNIPSA.SN": {"base_price": 21_000, "annual_return": 0.05, "volatility": 0.025},
    "CFIETFCC.SN": {"base_price": 18_500, "annual_return": 0.045, "volatility": 0.02},
    "CFMDIVO.SN": {"base_price": 17_200, "annual_return": 0.04, "volatility": 0.02},
    "ESGV": {"base_price": 83.0, "annual_return": 0.11, "volatility": 0.045},
    "FTEC": {"base_price": 130.0, "annual_return": 0.15, "volatility": 0.06},
    "QQQM": {"base_price": 140.0, "annual_return": 0.16, "volatility": 0.08},
    "SOXX": {"base_price": 460.0, "annual_return": 0.18, "volatility": 0.09},
    "VGK": {"base_price": 61.0, "annual_return": 0.07, "volatility": 0.035},
    "IAUM": {"base_price": 19.0, "annual_return": 0.05, "volatility": 0.02},
    "KOMP": {"base_price": 45.0, "annual_return": 0.09, "volatility": 0.055},
    "EPP": {"base_price": 49.0, "annual_return": 0.065, "volatility": 0.03},
}


def iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Color inválido: {hex_color}")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def compute_normalized_series(price_history: Sequence[Dict[str, float]]) -> List[Dict[str, float]]:
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


def parse_price_history(price_history: Sequence[Dict[str, float]]) -> List[Tuple[date, float]]:
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


def level_on_or_before(history: Sequence[Tuple[date, float]], target: date, fallback_to_first: bool = False) -> Optional[float]:
    for history_date, price in reversed(history):
        if history_date <= target:
            return price
    if fallback_to_first and history:
        return history[0][1]
    return None


def compute_percentage_change(latest: float, base: Optional[float]) -> Optional[float]:
    if base is None or base == 0:
        return None
    return (latest / base) - 1.0


def compute_returns(price_history: List[Dict[str, float]]) -> Dict[str, Optional[float]]:
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
    one_year_threshold = latest_date - timedelta(days=365)
    five_year_threshold = latest_date - timedelta(days=365 * 5)

    base_1m = level_on_or_before(parsed_history, one_month_threshold, fallback_to_first=True)
    base_1y = level_on_or_before(parsed_history, one_year_threshold, fallback_to_first=True)
    base_5y = level_on_or_before(parsed_history, five_year_threshold, fallback_to_first=True)

    daily_change_pct = compute_percentage_change(latest_price, previous_price)
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


def generate_sample_price_history(holding: HoldingConfig) -> List[Dict[str, float]]:
    behavior = SAMPLE_BEHAVIOR[holding.ticker]
    total_days = 5 * 365
    start_date = datetime.utcnow().date() - timedelta(days=total_days - 1)

    daily_growth_factor = (1 + behavior["annual_return"]) ** (1 / 365)
    seasonal_scale = 0.6

    points = []
    for idx in range(total_days):
        current_date = start_date + timedelta(days=idx)
        trend_component = behavior["base_price"] * (daily_growth_factor**idx)
        seasonal_component = 1 + seasonal_scale * behavior["volatility"] * math.sin(2 * math.pi * idx / 180)
        price = max(trend_component * seasonal_component, 0.01)
        points.append({"date": current_date.isoformat(), "close": round(price, 2)})
    return points


def generate_online_price_history(holding: HoldingConfig) -> List[Dict[str, float]]:
    if yf is None:
        raise RuntimeError(
            "yfinance no está instalado. Ejecuta `pip install -r requirements.txt` antes de usar el modo en línea."
        )
    ticker = yf.Ticker(holding.fetch_symbol)
    history = ticker.history(period="5y", interval="1d", auto_adjust=True)
    if history.empty:
        return []
    history = history[["Close"]].dropna()
    price_history: List[Dict[str, float]] = []
    for index, row in history.iterrows():
        if hasattr(index, "to_pydatetime"):
            as_dt = index.to_pydatetime()
        else:
            as_dt = index
        if hasattr(as_dt, "date"):
            date_str = as_dt.date().isoformat()
        else:
            date_str = str(as_dt)[:10]
        price_history.append(
            {
                "date": date_str,
                "close": round(float(row["Close"]), 4),
            }
        )
    return price_history


def build_payload(
    series_provider: Callable[[HoldingConfig], List[Dict[str, float]]],
    provider_name: str,
    notes: Optional[Dict[str, str]] = None,
    retrieved_at: Optional[str] = None,
) -> Dict:
    generated_at = iso_now()
    retrieved_value = retrieved_at or generated_at
    platforms_output = []
    histogram_monthly = []
    histogram_1y = []
    histogram_5y = []
    labels_set = set()
    datasets_temp = []

    for platform_id, platform_data in PLATFORM_CONFIG.items():
        holdings_output = []
        weights_with_data = 0.0
        weighted_monthly_change = 0.0
        weighted_return_1y = 0.0
        weighted_return_5y = 0.0
        monthly_weight = 0.0
        return_1y_weight = 0.0
        return_5y_weight = 0.0
        platform_start_dates = []
        platform_end_dates = []

        for holding in platform_data["holdings"]:
            try:
                price_history = series_provider(holding)
            except Exception as error:  # pragma: no cover - avisamos en payload
                holdings_output.append(
                    {
                        "ticker": holding.ticker,
                        "display_name": holding.display_name,
                        "platform_id": platform_id,
                        "weight": holding.weight,
                        "currency": holding.currency,
                        "latest_price": None,
                        "metrics": {},
                        "series": {"price_history": [], "normalized_5y": []},
                        "status": {"missing_data": True, "warnings": [str(error)]},
                    }
                )
                continue

            if not price_history:
                holdings_output.append(
                    {
                        "ticker": holding.ticker,
                        "display_name": holding.display_name,
                        "platform_id": platform_id,
                        "weight": holding.weight,
                        "currency": holding.currency,
                        "latest_price": None,
                        "metrics": {},
                        "series": {"price_history": [], "normalized_5y": []},
                        "status": {"missing_data": True, "warnings": ["Sin datos disponibles para este ticker."]},
                    }
                )
                continue

            # Aseguramos orden cronológico
            price_history = sorted(price_history, key=lambda item: item["date"])
            normalized = compute_normalized_series(price_history)
            metrics = compute_returns(price_history)
            latest_price = price_history[-1]["close"]
            platform_start_dates.append(price_history[0]["date"])
            platform_end_dates.append(price_history[-1]["date"])

            dataset_map = {point["date"]: point["value"] for point in normalized}
            labels_set.update(dataset_map.keys())
            datasets_temp.append(
                {
                    "id": holding.ticker,
                    "label": f"{holding.ticker} · {platform_data['name']}",
                    "platform_id": platform_id,
                    "borderColor": platform_data["color"],
                    "backgroundColor": hex_to_rgba(platform_data["color"], 0.15),
                    "weight": holding.weight,
                    "data_map": dataset_map,
                }
            )

            holdings_output.append(
                {
                    "ticker": holding.ticker,
                    "display_name": holding.display_name,
                    "platform_id": platform_id,
                    "weight": holding.weight,
                    "currency": holding.currency,
                    "latest_price": latest_price,
                    "metrics": metrics,
                    "series": {
                        "price_history": price_history,
                        "normalized_5y": normalized,
                    },
                }
            )

            histogram_entry = {
                "ticker": holding.ticker,
                "platform_id": platform_id,
                "label": holding.ticker,
                "weight": holding.weight,
            }
            if metrics["monthly_change_pct"] is not None:
                histogram_monthly.append({**histogram_entry, "value": metrics["monthly_change_pct"]})
                weighted_monthly_change += holding.weight * metrics["monthly_change_pct"]
                monthly_weight += holding.weight
            if metrics["return_1y"] is not None:
                histogram_1y.append({**histogram_entry, "value": metrics["return_1y"]})
                weighted_return_1y += holding.weight * metrics["return_1y"]
                return_1y_weight += holding.weight
            if metrics["return_5y"] is not None:
                histogram_5y.append({**histogram_entry, "value": metrics["return_5y"]})
                weighted_return_5y += holding.weight * metrics["return_5y"]
                return_5y_weight += holding.weight

            weights_with_data += holding.weight

        summary: Dict[str, Optional[float]] = {}
        if weights_with_data:
            summary["total_weight"] = round(weights_with_data, 4)
        if monthly_weight:
            summary["avg_monthly_change"] = round(weighted_monthly_change / monthly_weight, 4)
        if return_1y_weight:
            summary["avg_return_1y"] = round(weighted_return_1y / return_1y_weight, 4)
        if return_5y_weight:
            summary["avg_return_5y"] = round(weighted_return_5y / return_5y_weight, 4)
        if platform_start_dates and platform_end_dates:
            summary["timestamp_range"] = {
                "start": min(platform_start_dates),
                "end": max(platform_end_dates),
            }

        platforms_output.append(
            {
                "id": platform_id,
                "name": platform_data["name"],
                "color": platform_data["color"],
                "summary": summary,
                "holdings": holdings_output,
            }
        )

    labels = sorted(labels_set)
    datasets = []
    for dataset in datasets_temp:
        data = []
        for label in labels:
            value = dataset["data_map"].get(label)
            data.append(round(value, 2) if value is not None else None)
        datasets.append(
            {
                "id": dataset["id"],
                "label": dataset["label"],
                "platform_id": dataset["platform_id"],
                "borderColor": dataset["borderColor"],
                "backgroundColor": dataset["backgroundColor"],
                "data": data,
                "weight": dataset["weight"],
            }
        )

    payload = {
        "generated_at": generated_at,
        "currency": "USD",
        "source": {
            "provider": provider_name,
            "retrieved_at": retrieved_value,
        },
        "platforms": platforms_output,
        "charts": {
            "timeseries_5y": {
                "labels": labels,
                "datasets": datasets,
            },
            "histograms": {
                "monthly_change": histogram_monthly,
                "return_1y": histogram_1y,
                "return_5y": histogram_5y,
            },
        },
    }
    if notes:
        payload["source"]["notes"] = notes
    return payload


def generate_offline_payload() -> Dict:
    notes = {
        "info": "Datos deterministas generados en modo offline.",
    }
    return build_payload(generate_sample_price_history, provider_name="offline_sample", notes=notes)


def generate_online_payload() -> Dict:
    notes = {
        cfg.ticker: cfg.fetch_symbol
        for platform in PLATFORM_CONFIG.values()
        for cfg in platform["holdings"]
        if cfg.ticker != cfg.fetch_symbol
    }
    notes = notes or None
    return build_payload(generate_online_price_history, provider_name="yfinance", notes=notes)


def write_json(payload: Dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generador del archivo data/latest.json")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Ruta de salida para el JSON (por defecto data/latest.json).",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Genera datos deterministas de ejemplo sin consultar APIs externas.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = Path(args.output).resolve()

    if args.offline:
        payload = generate_offline_payload()
    else:
        payload = generate_online_payload()

    write_json(payload, output_path)
    print(f"Archivo generado en {output_path}")


if __name__ == "__main__":
    main()
