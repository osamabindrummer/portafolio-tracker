"""Comprueba y recupera el histórico diario del ETF Global Equities en Yahoo."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


class PriceHistory(list):
    """Conserva junto a los precios la explicación de una recuperación."""

    def __init__(self, points, warnings=(), provenance=None):
        super().__init__(points)
        self.warnings = list(warnings)
        self.provenance = provenance


def recover_global_equities(ticker, daily):
    # Yahoo puede entregar cierres diarios erróneos aunque sus operaciones por hora
    # y la cotización de portada sean correctas. No estimamos ni multiplicamos precios.
    closes = daily["Close"].dropna()
    nearby = closes.index.to_series().diff().dt.days.le(7)
    jumps = (closes.pct_change().abs() > 0.25) & nearby
    metadata = ticker.get_history_metadata()
    quote = metadata.get("regularMarketPrice")
    quote_time = metadata.get("regularMarketTime")
    if not quote or not quote_time or not math.isfinite(float(quote)) or quote <= 0:
        raise RuntimeError(
            "CFIETFGE.SN: Yahoo no permite comprobar la cotización actual."
        )
    if isinstance(quote_time, datetime):
        quote_date = quote_time.astimezone(ZoneInfo("America/Santiago")).date()
    else:
        quote_date = datetime.fromtimestamp(
            quote_time, ZoneInfo("America/Santiago")
        ).date()
    mismatch = not closes.empty and abs(float(closes.iloc[-1]) / quote - 1) > 0.25
    missing_latest = closes.empty or closes.index[-1].date() < quote_date
    if not jumps.any() and not mismatch and not missing_latest:
        return daily, []

    hourly = ticker.history(period="3mo", interval="1h", auto_adjust=False, timeout=6)
    if hourly.empty:
        raise RuntimeError(
            "CFIETFGE.SN: histórico diario inconsistente y sin operaciones por hora para recuperarlo."
        )
    hourly = hourly.copy()
    hourly.index = hourly.index.tz_convert("America/Santiago")
    valid_hourly = hourly["Close"].dropna()
    recovered = valid_hourly.groupby(valid_hourly.index.date).last()
    if (
        recovered.empty
        or recovered.index[-1] != quote_date
        or abs(float(recovered.iloc[-1]) / quote - 1) > 0.02
    ):
        raise RuntimeError(
            "CFIETFGE.SN: las operaciones por hora no corroboran la última cotización de Yahoo."
        )

    suspect_dates = [idx.date() for idx in closes.index[jumps]]
    repair_start = min(suspect_dates) if suspect_dates else quote_date
    result = daily.copy()
    corrected_dates = []
    for day, close in recovered.items():
        if day < repair_start:
            continue
        index = next((idx for idx in result.index if idx.date() == day), None)
        raw = result.at[index, "Close"] if index is not None else float("nan")
        if math.isfinite(float(raw)) and raw > 0 and abs(raw / close - 1) <= 0.25:
            continue
        if index is None:
            # El cierre faltante se obtiene de una operación fechada en esa sesión.
            import pandas as pd

            index = pd.Timestamp(day, tz="America/Santiago")
        result.loc[index, "Close"] = close
        result.loc[index, "Adj Close"] = close
        corrected_dates.append(day)

    if corrected_dates:
        first = min(corrected_dates)
        # No mezclamos precios sin ajustar con una distribución o un split reciente.
        actions = daily.loc[[idx.date() >= first for idx in daily.index]]
        for column in ("Dividends", "Stock Splits", "Capital Gains"):
            if column in actions and actions[column].fillna(0).ne(0).any():
                raise RuntimeError(
                    "CFIETFGE.SN: hay eventos corporativos que requieren verificar el ajuste antes de recuperar precios."
                )
    result = result.sort_index()
    final_closes = result["Close"].dropna()
    nearby = final_closes.index.to_series().diff().dt.days.le(7)
    if ((final_closes.pct_change().abs() > 0.25) & nearby).any():
        raise RuntimeError(
            "CFIETFGE.SN: persisten saltos sin corroborar en el histórico recuperado."
        )
    warning = (
        f"Yahoo entregó cierres diarios inconsistentes o incompletos; se recuperaron "
        f"{len(corrected_dates)} sesiones con el último precio por hora de la misma fecha "
        f"y se verificó la cotización al {quote_date.isoformat()}."
    )
    return result, [warning]


def quote_reference(metadata, symbol, *, currency="CLP", allow_missing_currency=False):
    if metadata.get("symbol") != symbol or metadata.get("exchangeName") != "SGO":
        raise RuntimeError(
            f"{symbol}: Yahoo no permite verificar la identidad del instrumento."
        )
    observed_currency = metadata.get("currency")
    if observed_currency != currency and not (
        allow_missing_currency and observed_currency is None
    ):
        raise RuntimeError(f"{symbol}: moneda de cotización incompatible.")
    value, timestamp = (
        metadata.get("regularMarketPrice"),
        metadata.get("regularMarketTime"),
    )
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
        or not timestamp
    ):
        raise RuntimeError(f"{symbol}: cotización de referencia inválida.")
    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            raise RuntimeError("La cotización necesita zona horaria.")
        day = timestamp.astimezone(ZoneInfo("America/Santiago")).date()
    else:
        day = datetime.fromtimestamp(timestamp, ZoneInfo("America/Santiago")).date()
    if day > datetime.now(ZoneInfo("America/Santiago")).date():
        raise RuntimeError("La cotización de referencia está fechada en el futuro.")
    return day, float(value)


def validate_price_points(points, *, min_points=2):
    if len(points) < min_points:
        raise RuntimeError("No hay suficientes observaciones diarias verificables.")
    previous = None
    today = datetime.now(UTC).date()
    for point in points:
        day = date.fromisoformat(point["date"])
        value = point["close"]
        if (
            day > today
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise RuntimeError("Hay fechas o precios inválidos en la serie.")
        if previous:
            last_day, last_value = previous
            if day <= last_day:
                raise RuntimeError("Las fechas deben ser únicas y estar ordenadas.")
            if (day - last_day).days <= 7 and abs(value / last_value - 1) > 0.25:
                raise RuntimeError("Persisten saltos sin corroborar en la serie.")
        previous = day, value


def recover_from_snapshot(ticker, daily, previous):
    """Conserva el prefijo archivado y agrega únicamente sesiones verificadas por hora."""
    archived = previous["series"]["price_history"]
    validate_price_points(archived)
    source = previous.get("price_source") or {}
    if source and (
        source.get("provider") != "yfinance" or source.get("adjusted") is not True
    ):
        raise RuntimeError(
            "No se mezclará un archivo sin ajustar con cierres ajustados."
        )
    quote_day, quote = quote_reference(ticker.get_history_metadata(), "CFIETFGE.SN")
    last_archived = date.fromisoformat(archived[-1]["date"])
    if quote_day < last_archived:
        raise RuntimeError("La cotización retrocedió respecto del archivo conservado.")
    # La sesión más reciente puede seguir cambiando durante el mismo día.
    prefix = archived[:-1] if quote_day == last_archived else archived
    anchor = date.fromisoformat(prefix[-1]["date"])
    if not {"Dividends", "Stock Splits"} <= set(daily.columns):
        raise RuntimeError("Yahoo no permite comprobar eventos corporativos recientes.")
    actions = daily.loc[[idx.date() > anchor for idx in daily.index]]
    for column in ("Dividends", "Stock Splits", "Capital Gains"):
        if column in actions and (
            actions[column].isna().any() or actions[column].ne(0).any()
        ):
            raise RuntimeError(
                "Hay eventos corporativos o ajustes sin verificar después del archivo conservado."
            )
    hourly = ticker.history(period="3mo", interval="1h", auto_adjust=False, timeout=6)
    if hourly.empty or hourly.index.tz is None:
        raise RuntimeError(
            "No hay operaciones por hora fechadas para verificar la continuidad."
        )
    hourly = hourly.copy()
    hourly.index = hourly.index.tz_convert("America/Santiago")
    valid = hourly["Close"].dropna()
    closes = valid.groupby(valid.index.date).last()
    if (
        closes.empty
        or closes.index[-1] != quote_day
        or abs(float(closes.iloc[-1]) / quote - 1) > 0.02
    ):
        raise RuntimeError(
            "Las operaciones por hora no corroboran la última cotización fechada."
        )
    anchors = [p for p in prefix if date.fromisoformat(p["date"]) in closes.index][-5:]
    if (
        len(anchors) < 3
        or anchors[-1]["date"] != anchor.isoformat()
        or any(
            abs(p["close"] / float(closes.loc[date.fromisoformat(p["date"])]) - 1)
            > 0.02
            for p in anchors
        )
    ):
        raise RuntimeError(
            "El archivo anterior y las operaciones por hora no corroboran la misma base de precios."
        )
    tail = [
        {"date": day.isoformat(), "close": round(float(value), 4)}
        for day, value in closes.items()
        if day > anchor
    ]
    if not tail or (date.fromisoformat(tail[0]["date"]) - anchor).days > 7:
        raise RuntimeError(
            "No se puede unir el archivo anterior sin dejar un tramo reciente sin verificar."
        )
    action_days = {index.date() for index in actions.index}
    if {date.fromisoformat(point["date"]) for point in tail} != action_days:
        raise RuntimeError(
            "Las sesiones recuperadas y la información diaria de eventos corporativos no coinciden."
        )
    history = prefix + tail
    validate_price_points(history)
    return PriceHistory(
        history,
        [
            *(
                w
                for w in previous.get("status", {}).get("warnings", [])
                if not w.startswith("Yahoo alteró retrospectivamente")
            ),
            f"Yahoo alteró retrospectivamente el histórico diario. Se conservó el archivo ajustado hasta {anchor.isoformat()} y se añadieron {len(tail)} sesiones observadas por hora, con continuidad contrastada y cotización verificada al {quote_day.isoformat()}.",
        ],
        provenance={
            "provider": "yfinance",
            "source_url": "https://finance.yahoo.com/quote/CFIETFGE.SN/history/",
            "adjusted": True,
            "archive_through": anchor.isoformat(),
            "corroborated_at": quote_day.isoformat(),
        },
    )
