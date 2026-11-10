"""Lee cierres publicados por Racional y los contrasta con la cotización de Yahoo."""

from __future__ import annotations

import json
import math
from datetime import date
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from scripts.yahoo_history import PriceHistory, quote_reference, validate_price_points

SUPPORTED_TICKERS = {"CFIETFIPSA", "CFIETFEM"}


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.current = []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.scripts.append("".join(self.current))
            self.current = None


def _records(value):
    if isinstance(value, dict):
        if {"ticker", "moneda", "periods"} <= value.keys():
            yield value
        for item in value.values():
            yield from _records(item)
    elif isinstance(value, list):
        for item in value:
            yield from _records(item)


def parse_racional_history(html: str, ticker: str, currency: str) -> list[dict]:
    parser = _Scripts()
    parser.feed(html)
    parts = []
    decoder = json.JSONDecoder()
    prefix = "self.__next_f.push("
    for script in parser.scripts:
        offset = 0
        while (start := script.find(prefix, offset)) >= 0:
            try:
                value, end = decoder.raw_decode(script, start + len(prefix))
            except ValueError as error:
                raise RuntimeError(
                    "Racional: los datos de la página no son JSON válido."
                ) from error
            offset = end
            if (
                isinstance(value, list)
                and len(value) == 2
                and value[0] == 1
                and isinstance(value[1], str)
            ):
                parts.append(value[1])
    candidates = []
    for line in "".join(parts).splitlines():
        _, _, value = line.partition(":")
        if value.startswith(("[", "{")):
            try:
                candidates.extend(_records(json.loads(value)))
            except ValueError:
                continue
    matches = [record for record in candidates if record["ticker"] == ticker]
    if len(matches) != 1 or matches[0]["moneda"] != currency:
        raise RuntimeError(
            f"Racional: no se pudo verificar identidad y moneda de {ticker}."
        )
    periods = matches[0]["periods"]
    if not isinstance(periods, list):
        raise RuntimeError("Racional: períodos inválidos.")
    histories = []
    for period in periods:
        if not isinstance(period, dict) or period.get("id") not in {
            "MTD",
            "1M",
            "YTD",
            "1A",
        }:
            continue
        prices, dates = period.get("prices"), period.get("dates")
        if (
            not isinstance(prices, list)
            or not isinstance(dates, list)
            or len(prices) != len(dates)
        ):
            raise RuntimeError("Racional: las fechas y los precios no coinciden.")
        points = []
        for stamp, price in zip(dates, prices):
            # En estas series la medianoche UTC identifica la sesión, no una operación intradía.
            if not isinstance(stamp, str) or stamp[10:] != "T00:00:00.000Z":
                raise RuntimeError("Racional: fecha diaria inválida.")
            try:
                day = date.fromisoformat(stamp[:10])
            except ValueError as error:
                raise RuntimeError("Racional: fecha inválida.") from error
            if (
                isinstance(price, bool)
                or not isinstance(price, (int, float))
                or not math.isfinite(price)
                or price <= 0
            ):
                raise RuntimeError("Racional: precio inválido.")
            points.append({"date": day.isoformat(), "close": float(price)})
        if not points:
            continue
        validate_price_points(points, min_points=1)
        histories.append(points)
    if not histories:
        raise RuntimeError(
            f"Racional: no hay una serie diaria verificable para {ticker}."
        )
    history = max(histories, key=len)
    validate_price_points(history)
    # Los períodos superpuestos deben describir los mismos cierres.
    known = {p["date"]: p["close"] for p in history}
    for series in histories:
        if any(
            p["date"] not in known or abs(p["close"] / known[p["date"]] - 1) > 0.0001
            for p in series
        ):
            raise RuntimeError("Racional: los períodos entregan cierres incompatibles.")
    return history


def fetch_racional_history(holding, metadata: dict, previous=None) -> PriceHistory:
    if holding.ticker not in SUPPORTED_TICKERS:
        raise RuntimeError(
            "El instrumento no tiene un respaldo verificado en Racional."
        )
    url = f"https://racional.cl/assets/{holding.ticker.lower()}"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; PortafolioTracker/0.2)",
            "Accept": "text/html",
        },
    )
    with urlopen(request, timeout=6) as response:
        html = response.read(2_000_001)
    if len(html) > 2_000_000:
        raise RuntimeError("Racional: la respuesta supera el tamaño permitido.")
    history = parse_racional_history(
        html.decode("utf-8"), holding.ticker, holding.currency
    )
    quote_day, quote = quote_reference(
        metadata,
        holding.fetch_symbol,
        currency=holding.currency,
        allow_missing_currency=True,
    )
    if (
        history[-1]["date"] != quote_day.isoformat()
        or abs(history[-1]["close"] / quote - 1) > 0.02
    ):
        raise RuntimeError(
            f"{holding.ticker}: Racional y Yahoo no corroboran el último cierre fechado."
        )
    if previous:
        source = previous.get("price_source") or {}
        old = previous.get("series", {}).get("price_history", [])
        if (
            old
            and source.get("provider") == "racional"
            and source.get("adjusted") is False
        ):
            new_by_date = {p["date"]: p["close"] for p in history}
            anchors = [
                p
                for p in old
                if p["date"] in new_by_date and p["date"] < history[-1]["date"]
            ][-5:]
            if len(anchors) < 3 or any(
                abs(p["close"] / new_by_date[p["date"]] - 1) > 0.02 for p in anchors
            ):
                raise RuntimeError(
                    "Racional: el histórico nuevo no permite verificar continuidad con el anterior."
                )
            history = [p for p in old if p["date"] < history[0]["date"]] + history
            validate_price_points(history)
        elif len(old) > 1:
            raise RuntimeError(
                "No se mezclará el histórico ajustado anterior con cierres sin ajuste verificado."
            )
    return PriceHistory(
        history,
        [
            "Yahoo no ofrece histórico suficiente; se usan cierres publicados por Racional y se contrasta el último con Yahoo en la misma fecha.",
            "Serie de precios sin ajuste de distribuciones verificado: sólo se calculan variaciones diaria y mensual; no se atribuyen retornos ajustados a uno o cinco años.",
        ],
        provenance={
            "provider": "racional",
            "source_url": url,
            "adjusted": False,
            "corroborated_at": quote_day.isoformat(),
        },
    )
