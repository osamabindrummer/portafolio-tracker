"""Payloads semilla para cuando todavía no existe persistencia remota."""

from __future__ import annotations

INDICATORS_SEED = {
    "items": [
        {
            "key": "uf",
            "label": "UF",
            "series_id": "F073.UFF.PRE.Z.D",
            "value": 39841.72,
            "unit": "CLP",
            "decimals": 2,
            "observed_at": "2026-04-07",
        },
        {
            "key": "utm",
            "label": "UTM",
            "series_id": "F073.UTR.PRE.Z.M",
            "value": 69889.0,
            "unit": "CLP",
            "decimals": 1,
            "observed_at": "2026-04-01",
        },
        {
            "key": "dollar_observed",
            "label": "Dólar observado",
            "series_id": "F073.TCO.PRE.Z.D",
            "value": 914.47,
            "unit": "CLP",
            "decimals": 2,
            "observed_at": "2026-04-07",
        },
        {
            "key": "ipc_annual",
            "label": "IPC anual",
            "series_id": "F074.IPC.IND.Z.EP09.C.M",
            "value": 2.4,
            "unit": "PERCENT",
            "decimals": 1,
            "observed_at": "2026-02-01",
        },
    ],
    "fetched_at": "2026-04-07T12:00:00Z",
    "source": "seed",
    "source_url": "https://mindicador.cl/api",
}
