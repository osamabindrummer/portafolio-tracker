"""Comprueba y recupera el histórico diario del ETF Global Equities en Yahoo."""

from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo


class PriceHistory(list):
    """Conserva junto a los precios la explicación de una recuperación."""

    def __init__(self, points, warnings=()):
        super().__init__(points)
        self.warnings = list(warnings)


def recover_global_equities(ticker, daily):
    # Yahoo puede entregar cierres diarios erróneos aunque sus operaciones por hora
    # y la cotización de portada sean correctas. No estimamos ni multiplicamos precios.
    closes = daily['Close'].dropna()
    nearby = closes.index.to_series().diff().dt.days.le(7)
    jumps = (closes.pct_change().abs() > 0.25) & nearby
    metadata = ticker.get_history_metadata()
    quote = metadata.get('regularMarketPrice')
    quote_time = metadata.get('regularMarketTime')
    if not quote or not quote_time or not math.isfinite(float(quote)) or quote <= 0:
        raise RuntimeError('CFIETFGE.SN: Yahoo no permite comprobar la cotización actual.')
    if isinstance(quote_time, datetime):
        quote_date = quote_time.astimezone(ZoneInfo('America/Santiago')).date()
    else:
        quote_date = datetime.fromtimestamp(quote_time, ZoneInfo('America/Santiago')).date()
    mismatch = not closes.empty and abs(float(closes.iloc[-1]) / quote - 1) > 0.25
    missing_latest = closes.empty or closes.index[-1].date() < quote_date
    if not jumps.any() and not mismatch and not missing_latest:
        return daily, []

    hourly = ticker.history(period='3mo', interval='1h', auto_adjust=False)
    if hourly.empty:
        raise RuntimeError('CFIETFGE.SN: histórico diario inconsistente y sin operaciones por hora para recuperarlo.')
    hourly = hourly.copy()
    hourly.index = hourly.index.tz_convert('America/Santiago')
    valid_hourly = hourly['Close'].dropna()
    recovered = valid_hourly.groupby(valid_hourly.index.date).last()
    if recovered.empty or recovered.index[-1] != quote_date or abs(float(recovered.iloc[-1]) / quote - 1) > 0.02:
        raise RuntimeError('CFIETFGE.SN: las operaciones por hora no corroboran la última cotización de Yahoo.')

    suspect_dates = [idx.date() for idx in closes.index[jumps]]
    repair_start = min(suspect_dates) if suspect_dates else quote_date
    result = daily.copy()
    corrected_dates = []
    for day, close in recovered.items():
        if day < repair_start:
            continue
        index = next((idx for idx in result.index if idx.date() == day), None)
        raw = result.at[index, 'Close'] if index is not None else float('nan')
        if math.isfinite(float(raw)) and raw > 0 and abs(raw / close - 1) <= 0.25:
            continue
        if index is None:
            # El cierre faltante se obtiene de una operación fechada en esa sesión.
            import pandas as pd
            index = pd.Timestamp(day, tz='America/Santiago')
        result.loc[index, 'Close'] = close
        result.loc[index, 'Adj Close'] = close
        corrected_dates.append(day)

    if corrected_dates:
        first = min(corrected_dates)
        # No mezclamos precios sin ajustar con una distribución o un split reciente.
        actions = daily.loc[[idx.date() >= first for idx in daily.index]]
        for column in ('Dividends', 'Stock Splits', 'Capital Gains'):
            if column in actions and actions[column].fillna(0).ne(0).any():
                raise RuntimeError('CFIETFGE.SN: hay eventos corporativos que requieren verificar el ajuste antes de recuperar precios.')
    result = result.sort_index()
    final_closes = result['Close'].dropna()
    nearby = final_closes.index.to_series().diff().dt.days.le(7)
    if ((final_closes.pct_change().abs() > 0.25) & nearby).any():
        raise RuntimeError('CFIETFGE.SN: persisten saltos sin corroborar en el histórico recuperado.')
    warning = (
        f'Yahoo entregó cierres diarios inconsistentes o incompletos; se recuperaron '
        f'{len(corrected_dates)} sesiones con el último precio por hora de la misma fecha '
        f'y se verificó la cotización al {quote_date.isoformat()}.'
    )
    return result, [warning]
