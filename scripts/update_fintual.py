#!/usr/bin/env python3
"""Aplica la cartera configurada conservando históricos y las otras plataformas."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.fetch_data import (
    DEFAULT_OUTPUT, PLATFORM_CONFIG, build_payload, generate_online_price_history, write_json,
)
from scripts.validate_json import validate_payload


def matches_config(payload: dict) -> bool:
    platform = next((p for p in payload.get("platforms", []) if p["id"] == "fintual"), {})
    config = PLATFORM_CONFIG["fintual"]
    return platform.get("portfolio_as_of") == config["portfolio_as_of"] and [
        (h["ticker"], h.get("quote_symbol"), h["weight"], h["display_name"])
        for h in platform.get("holdings", [])
    ] == [(h.ticker, h.fetch_symbol, h.weight, h.display_name) for h in config["holdings"]]


def rebuild_payload(payload: dict, *, fallback: dict | None = None, fetch_missing: bool = False) -> dict:
    # La clave incluye plataforma y símbolo para no confundir productos homónimos.
    cached = {}
    for source in (fallback or {}, payload):
        for platform in source.get("platforms", []):
            for holding in platform["holdings"]:
                history = holding.get("series", {}).get("price_history", [])
                if history:
                    cached[(platform["id"], holding.get("quote_symbol", holding["ticker"]))] = history

    platform_by_ticker = {id(h): pid for pid, p in PLATFORM_CONFIG.items() for h in p["holdings"]}

    def provider(holding):
        key = (platform_by_ticker[id(holding)], holding.fetch_symbol)
        if key in cached:
            return cached[key]
        if fetch_missing:
            history = generate_online_price_history(holding)
            if history:
                return history
        raise RuntimeError(f"Sin histórico real para {holding.fetch_symbol}; no se generarán datos de ejemplo.")

    updated = build_payload(provider, payload["source"]["provider"],
                            notes=payload["source"].get("notes"),
                            retrieved_at=payload["source"].get("retrieved_at"))
    # Cambiar la composición no equivale a refrescar las cotizaciones existentes.
    updated["generated_at"] = payload["generated_at"]
    updated["source"] = payload["source"]
    original = {p["id"]: p for p in payload["platforms"]}
    updated["platforms"] = [p if p["id"] == "fintual" else original[p["id"]] for p in updated["platforms"]]
    validate_payload(updated)
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text())
    updated = rebuild_payload(payload, fetch_missing=True)
    fintual = next(p for p in updated["platforms"] if p["id"] == "fintual")
    missing = [h["ticker"] for h in fintual["holdings"] if not h.get("series", {}).get("price_history")]
    if missing:
        raise SystemExit(f"No se guardó la actualización: faltan históricos reales para {', '.join(missing)}")
    write_json(updated, args.output)
    print(f"Cartera al {fintual['portfolio_as_of']}: {len(fintual['holdings'])} holdings guardados.")


if __name__ == "__main__":
    main()
