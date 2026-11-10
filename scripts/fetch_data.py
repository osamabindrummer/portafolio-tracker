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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

from scripts.yahoo_history import (
    PriceHistory,
    recover_global_equities,
    recover_from_snapshot,
)
from scripts.portfolio import refresh_derived
from scripts.portfolio import compute_returns as compute_returns


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
                weight=0.20,
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
        ],
    },
    "racional_107_lir": {
        "name": "Racional - Pack 107 LIR",
        "color": "#0B57D0",
        "holdings": [
            HoldingConfig(
                ticker="CFINASDAQ",
                weight=0.30,
                fetch_symbol="CFINASDAQ.SN",
                display_name="Nasdaq 100",
                currency="CLP",
            ),
            HoldingConfig(
                ticker="CFISPETF",
                weight=0.30,
                fetch_symbol="CFISPETF.SN",
                display_name="S&P 500",
                currency="CLP",
            ),
            HoldingConfig(
                ticker="CFIETFGE",
                weight=0.25,
                fetch_symbol="CFIETFGE.SN",
                display_name="Global Equities",
                currency="CLP",
            ),
            HoldingConfig(
                ticker="CFIETFIPSA",
                weight=0.10,
                fetch_symbol="CFIETFIPSA.SN",
                display_name="IPSA",
                currency="CLP",
            ),
            HoldingConfig(
                ticker="CFIETFEM",
                weight=0.05,
                fetch_symbol="CFIETFEM.SN",
                display_name="Emerging Markets",
                currency="CLP",
            ),
        ],
    },
    "fintual": {
        "name": "Fintual",
        "color": "#FF6F61",
        "portfolio_as_of": "2026-10-29",
        "portfolio_source_url": "https://fintual.cl/risky-norris",
        "holdings": [
            HoldingConfig(
                ticker="SPYM",
                weight=0.1935,
                fetch_symbol="SPYM",
                display_name="SPDR Portfolio S&P 500 ETF",
                currency="USD",
            ),
            HoldingConfig(
                ticker="FTEC",
                weight=0.1758,
                fetch_symbol="FTEC",
                display_name="Fidelity MSCI Information Technology Index ETF",
                currency="USD",
            ),
            HoldingConfig(
                ticker="QQQM",
                weight=0.1679,
                fetch_symbol="QQQM",
                display_name="Invesco Nasdaq 100 ETF",
                currency="USD",
            ),
            HoldingConfig(
                ticker="SOXQ",
                weight=0.1007,
                fetch_symbol="SOXQ",
                display_name="Invesco PHLX Semiconductor ETF",
                currency="USD",
            ),
            HoldingConfig(
                ticker="AVDV",
                weight=0.0947,
                fetch_symbol="AVDV",
                display_name="Avantis International Small Cap Value ETF",
                currency="USD",
            ),
            HoldingConfig(
                ticker="SPXS",
                weight=0.0843,
                fetch_symbol="SPXS.L",
                display_name="Invesco S&P 500 UCITS ETF Acumulativo",
                currency="USD",
            ),
            HoldingConfig(
                ticker="IAUM",
                weight=0.0636,
                fetch_symbol="IAUM",
                display_name="iShares Gold Trust Micro",
                currency="USD",
            ),
            HoldingConfig(
                ticker="XLE",
                weight=0.0525,
                fetch_symbol="XLE",
                display_name="Energy Select Sector SPDR Fund",
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
    "CFINASDAQ": {"base_price": 1_500, "annual_return": 0.12, "volatility": 0.05},
    "CFISPETF": {"base_price": 1_300, "annual_return": 0.10, "volatility": 0.04},
    "CFIETFGE": {"base_price": 1_900, "annual_return": 0.06, "volatility": 0.03},
    "CFIETFIPSA": {"base_price": 1_000, "annual_return": 0.05, "volatility": 0.025},
    "CFIETFEM": {"base_price": 900, "annual_return": 0.08, "volatility": 0.04},
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
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def generate_sample_price_history(holding: HoldingConfig) -> List[Dict[str, float]]:
    behavior = SAMPLE_BEHAVIOR.get(
        holding.ticker, {"base_price": 100.0, "annual_return": 0.06, "volatility": 0.04}
    )
    total_days = 5 * 365
    start_date = datetime.now(UTC).date() - timedelta(days=total_days - 1)

    daily_growth_factor = (1 + behavior["annual_return"]) ** (1 / 365)
    seasonal_scale = 0.6

    points = []
    for idx in range(total_days):
        current_date = start_date + timedelta(days=idx)
        trend_component = behavior["base_price"] * (daily_growth_factor**idx)
        seasonal_component = 1 + seasonal_scale * behavior["volatility"] * math.sin(
            2 * math.pi * idx / 180
        )
        price = max(trend_component * seasonal_component, 0.01)
        points.append({"date": current_date.isoformat(), "close": round(price, 2)})
    return points


def generate_online_price_history(
    holding: HoldingConfig, *, previous=None
) -> List[Dict[str, float]]:
    try:
        import yfinance as yf
    except ImportError as error:
        raise RuntimeError(
            "Instala requirements.lock antes de consultar cotizaciones."
        ) from error
    ticker = yf.Ticker(holding.fetch_symbol)
    warnings = []
    if holding.fetch_symbol == "CFIETFGE.SN":
        history = ticker.history(
            period="5y", interval="1d", auto_adjust=False, timeout=6
        )
        try:
            history, warnings = recover_global_equities(ticker, history)
        except RuntimeError:
            if not previous:
                raise
            return recover_from_snapshot(ticker, history, previous)
        # Conservamos la misma base ajustada usada por los demás instrumentos.
        history = history.rename(columns={"Close": "Raw Close", "Adj Close": "Close"})
    else:
        history = ticker.history(
            period="5y", interval="1d", auto_adjust=True, timeout=6
        )
    if len(history.dropna(subset=["Close"])) < 2 and holding.ticker in {
        "CFIETFIPSA",
        "CFIETFEM",
    }:
        from scripts.racional_history import fetch_racional_history

        return fetch_racional_history(holding, ticker.get_history_metadata(), previous)
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
    return PriceHistory(price_history, warnings)


def build_payload(
    series_provider: Callable[[HoldingConfig], List[Dict[str, float]]],
    provider_name: str,
    notes: Optional[Dict[str, str]] = None,
    retrieved_at: Optional[str] = None,
) -> Dict:
    generated_at = iso_now()
    retrieved_value = retrieved_at or generated_at
    platforms = []
    for platform_id, config in PLATFORM_CONFIG.items():
        holdings = []
        for holding in config["holdings"]:
            warnings = []
            try:
                history = series_provider(holding)
                warnings = list(getattr(history, "warnings", []))
                if not history:
                    raise RuntimeError("Sin datos disponibles para este ticker.")
            except Exception as error:
                history = []
                warnings = [str(error)]
            holdings.append(
                {
                    "ticker": holding.ticker,
                    "quote_symbol": holding.fetch_symbol,
                    "display_name": holding.display_name,
                    "platform_id": platform_id,
                    "weight": holding.weight,
                    "currency": holding.currency,
                    "series": {
                        "price_history": sorted(history, key=lambda p: p["date"])
                    },
                    **(
                        {"price_source": history.provenance}
                        if getattr(history, "provenance", None)
                        else {}
                    ),
                    "status": {
                        "warnings": warnings,
                        "retained": bool(getattr(history, "retained", False)),
                    },
                }
            )
        platforms.append(
            {
                "id": platform_id,
                **{k: v for k, v in config.items() if k != "holdings"},
                "holdings": holdings,
            }
        )
    payload = {
        "generated_at": generated_at,
        "source": {"provider": provider_name, "retrieved_at": retrieved_value},
        "platforms": platforms,
    }
    if notes:
        payload["source"]["notes"] = notes
    return refresh_derived(payload)


def generate_offline_payload() -> Dict:
    notes = {
        "info": "Datos deterministas generados en modo offline.",
    }
    cached = {}

    def provider(holding):
        if holding.fetch_symbol not in cached:
            cached[holding.fetch_symbol] = generate_sample_price_history(holding)
        return cached[holding.fetch_symbol]

    return build_payload(provider, provider_name="offline_sample", notes=notes)


def generate_online_payload(existing_payload: Optional[Dict] = None) -> Dict:
    notes = {
        cfg.ticker: cfg.fetch_symbol
        for platform in PLATFORM_CONFIG.values()
        for cfg in platform["holdings"]
        if cfg.ticker != cfg.fetch_symbol
    }
    notes = notes or None
    # Una descarga fallida conserva el histórico anterior y explica su procedencia.
    previous = {}
    real_source = (existing_payload or {}).get("source", {}).get("provider") in {
        "yfinance",
        "yfinance+racional",
    }
    for platform in (
        (existing_payload or {}).get("platforms", []) if real_source else []
    ):
        for h in platform["holdings"]:
            previous[h.get("quote_symbol", h["ticker"])] = h
    from concurrent.futures import ThreadPoolExecutor, wait

    unique = {
        h.fetch_symbol: h for p in PLATFORM_CONFIG.values() for h in p["holdings"]
    }
    executor = ThreadPoolExecutor(max_workers=4)
    futures = {
        symbol: executor.submit(
            generate_online_price_history,
            h,
            **(
                {"previous": previous[symbol]}
                if symbol in previous
                and symbol in {"CFIETFGE.SN", "CFIETFIPSA.SN", "CFIETFEM.SN"}
                else {}
            ),
        )
        for symbol, h in unique.items()
    }
    wait(futures.values(), timeout=25)
    executor.shutdown(wait=False, cancel_futures=True)
    cached = {}

    def provider(holding):
        symbol = holding.fetch_symbol
        if symbol not in cached:
            old = previous.get(symbol, {})
            old_history = old.get("series", {}).get("price_history", [])
            try:
                future = futures[symbol]
                if not future.done() or future.cancelled():
                    raise RuntimeError(
                        "Se agotó el tiempo reservado para cotizaciones."
                    )
                history = future.result()
                if len(history) < 2:
                    raise RuntimeError("La fuente no entregó suficiente histórico.")
                if old_history and (
                    history[-1]["date"] < old_history[-1]["date"]
                    or len(history) < len(old_history) * 0.8
                ):
                    raise RuntimeError(
                        "La descarga retrocedió o perdió gran parte del histórico."
                    )
                cached[symbol] = history
            except Exception as error:
                if old_history:
                    retained = PriceHistory(
                        old_history,
                        [
                            *old.get("status", {}).get("warnings", []),
                            f"Se conservó el histórico anterior: {error}",
                        ],
                    )
                    retained.provenance = old.get("price_source")
                    retained.retained = True
                    cached[symbol] = retained
                else:
                    cached[symbol] = error
        result = cached[symbol]
        if isinstance(result, Exception):
            raise result
        return result

    payload = build_payload(provider, provider_name="yfinance", notes=notes)
    if any(
        (h.get("price_source") or {}).get("provider") == "racional"
        for p in payload["platforms"]
        for h in p["holdings"]
    ):
        payload["source"]["provider"] = "yfinance+racional"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generador del archivo data/latest.json"
    )
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

    from scripts.portfolio import pack_payload, unpack_payload
    from scripts.validate_json import validate_payload
    from backend.portfolio_refresh import validate_refresh_quality

    if args.offline:
        if output_path == DEFAULT_OUTPUT.resolve():
            raise SystemExit(
                "Usa --output con otro archivo para no reemplazar la semilla real por datos de ejemplo."
            )
        payload = generate_offline_payload()
    else:
        existing = (
            unpack_payload(json.loads(output_path.read_text()))
            if output_path.exists()
            else None
        )
        payload = generate_online_payload(existing)
        validate_refresh_quality(payload)
    validate_payload(payload)
    from backend.storage import write_local_json

    write_local_json(output_path, pack_payload(payload))
    print(f"Archivo generado en {output_path}")


if __name__ == "__main__":
    main()
