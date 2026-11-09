"""Regresiones de seguridad, cobertura y conservación de precios reales."""

import copy
import json
import os
import unittest
from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from backend.http import read_refresh_options
from backend.portfolio_refresh import (
    refresh_latest_dataset,
    _compute_annual_ipc_from_series,
    _validate_indicator_freshness,
)
from backend.storage import StorageMeta
from scripts.fetch_data import build_payload, compute_returns, generate_online_payload
from scripts.portfolio import pack_payload, public_payload, unpack_payload
from scripts.validate_json import ValidationError, validate_payload


def recent_history():
    end = datetime.now(UTC).date()
    return [
        {"date": (end - timedelta(days=days)).isoformat(), "close": 100 + index}
        for index, days in enumerate([1826, 365, 30, 1, 0])
    ]


class RefreshSafetyTests(unittest.TestCase):
    def test_public_api_rejects_offline_and_unauthorized_force(self):
        for path, body, error in [
            ("?mode=offline", {}, ValueError),
            ("", {"mode": "offline"}, ValueError),
            ("?force=true", {}, PermissionError),
            ("", {"force": True}, PermissionError),
        ]:
            raw = json.dumps(body).encode()
            request = SimpleNamespace(
                path="/api/refresh-data" + path,
                headers={"Content-Length": str(len(raw))},
                rfile=BytesIO(raw),
            )
            with patch.dict(os.environ, {"CRON_SECRET": ""}), self.assertRaises(error):
                read_refresh_options(request)

    def test_force_requires_matching_server_secret(self):
        request = SimpleNamespace(
            path="/?force=true",
            headers={"Authorization": "Bearer test-secret"},
            rfile=BytesIO(),
        )
        with patch.dict(os.environ, {"CRON_SECRET": "test-secret"}):
            self.assertTrue(read_refresh_options(request)[2])

    def test_short_history_does_not_claim_long_period_returns(self):
        metrics = compute_returns(recent_history()[-2:])
        self.assertIsNone(metrics["return_1y"])
        self.assertIsNone(metrics["return_5y"])
        self.assertIsNone(metrics["monthly_change_pct"])
        self.assertIsNotNone(metrics["daily_change_pct"])

    def test_return_tolerance_does_not_use_a_quote_months_before_target(self):
        metrics = compute_returns(
            [{"date": "2024-01-01", "close": 100}, {"date": "2026-11-01", "close": 120}]
        )
        self.assertIsNone(metrics["return_1y"])
        self.assertIsNone(metrics["daily_change_pct"])

    def test_invalid_or_empty_refresh_never_writes(self):
        for provider in [
            lambda h: [],
            lambda h: [
                {"date": "2001-01-01", "close": 100},
                {"date": "2001-01-02", "close": 101},
            ],
        ]:
            payload = build_payload(provider, "yfinance")
            with (
                patch(
                    "backend.portfolio_refresh._safe_read_payload", return_value=None
                ),
                patch(
                    "backend.portfolio_refresh.generate_online_payload",
                    return_value=payload,
                ),
                patch("backend.portfolio_refresh.write_dataset") as write,
            ):
                with self.assertRaisesRegex(RuntimeError, "80 %"):
                    refresh_latest_dataset()
                write.assert_not_called()

    def test_all_failed_fetches_preserve_previous_histories_without_claiming_success(
        self,
    ):
        previous = build_payload(lambda h: recent_history(), "yfinance")
        with patch(
            "scripts.fetch_data.generate_online_price_history",
            side_effect=RuntimeError("Fuente caída"),
        ):
            result = generate_online_payload(previous)
        for old, new in zip(previous["platforms"], result["platforms"]):
            for old_h, new_h in zip(old["holdings"], new["holdings"]):
                self.assertEqual(old_h["series"], new_h["series"])
                self.assertTrue(new_h["status"]["retained"])
        with (
            patch("backend.portfolio_refresh._safe_read_payload", return_value=None),
            patch(
                "backend.portfolio_refresh.generate_online_payload", return_value=result
            ),
            patch("backend.portfolio_refresh.write_dataset") as write,
        ):
            with self.assertRaisesRegex(RuntimeError, "80 %"):
                refresh_latest_dataset()
            write.assert_not_called()

    def test_partial_download_keeps_previous_prices_and_records_warning(self):
        previous = build_payload(lambda h: recent_history(), "yfinance")

        def fetch(h):
            if h.fetch_symbol == "CFIETFCC.SN":
                raise RuntimeError("Fuente caída")
            return recent_history()

        with patch(
            "scripts.fetch_data.generate_online_price_history", side_effect=fetch
        ):
            result = generate_online_payload(previous)
        with (
            patch("backend.portfolio_refresh._safe_read_payload", return_value=None),
            patch(
                "backend.portfolio_refresh.generate_online_payload", return_value=result
            ),
            patch(
                "backend.portfolio_refresh.write_dataset",
                return_value=StorageMeta("local"),
            ) as write,
        ):
            self.assertEqual(refresh_latest_dataset().status, "updated")
            self.assertTrue(
                write.call_args.args[1]["platforms"][0]["holdings"][-1]["status"][
                    "retained"
                ]
            )

    def test_compact_round_trip_preserves_prices_and_warnings(self):
        payload = build_payload(lambda h: recent_history(), "yfinance")
        payload["platforms"][0]["holdings"][0]["status"]["warnings"] = [
            "Histórico recuperado"
        ]
        packed = pack_payload(payload)
        self.assertEqual(len(packed["histories"]), 17)
        restored = unpack_payload(packed)
        self.assertEqual(payload, restored)
        self.assertNotIn(
            "series", public_payload(restored)["platforms"][0]["holdings"][0]
        )

    def test_validator_rejects_bad_numbers_and_dates_without_crashing(self):
        payload = build_payload(lambda h: recent_history(), "yfinance")
        for field, value in [
            ("weight", -1),
            ("weight", True),
            ("weight", float("nan")),
        ]:
            invalid = copy.deepcopy(payload)
            invalid["platforms"][0]["holdings"][0][field] = value
            with self.assertRaises(ValidationError):
                validate_payload(invalid)
        for history in [
            [None],
            [{"date": "no-es-fecha", "close": 100}],
            [{"date": "2026-01-01", "close": float("inf")}],
        ]:
            invalid = copy.deepcopy(payload)
            invalid["platforms"][0]["holdings"][0]["series"]["price_history"] = history
            with self.assertRaises(ValidationError):
                validate_payload(invalid)
        invalid = copy.deepcopy(payload)
        invalid["charts"]["timeseries_5y"]["datasets"][0]["data"].pop()
        with self.assertRaises(ValidationError):
            validate_payload(invalid)

    def test_recent_fetch_cannot_hide_stale_ipc(self):
        items = [
            {"key": "ipc_annual", "label": "IPC anual", "observed_at": "2025-12-01"}
        ]
        with self.assertRaisesRegex(RuntimeError, "fuera del plazo"):
            _validate_indicator_freshness(items)

    def test_offline_examples_share_one_history_per_symbol(self):
        from scripts.fetch_data import generate_offline_payload

        payload = pack_payload(generate_offline_payload())
        self.assertEqual(len(payload["histories"]), 17)
        validate_payload(payload)

    def test_ipc_requires_consecutive_unique_months(self):
        series = [
            {"fecha": f"2026-{month:02d}-01", "valor": 0.2} for month in range(1, 13)
        ]
        self.assertEqual(_compute_annual_ipc_from_series(series)[0], 2.4)
        series[-1]["fecha"] = series[-2]["fecha"]
        with self.assertRaisesRegex(RuntimeError, "consecutivos"):
            _compute_annual_ipc_from_series(series)


if __name__ == "__main__":
    unittest.main()
