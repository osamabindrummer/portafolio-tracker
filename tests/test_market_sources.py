"""Regresiones de las tres fuentes que bloqueaban el Pack 107 LIR."""

import copy
import json
import unittest
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from scripts.fetch_data import PLATFORM_CONFIG, generate_online_price_history
from scripts.portfolio import pack_payload, refresh_derived, unpack_payload
from scripts.racional_history import fetch_racional_history, parse_racional_history
from scripts.yahoo_history import recover_from_snapshot

FIXTURES = Path(__file__).parent / "fixtures/market_history"


def record(ticker="CFIETFEM"):
    return json.loads((FIXTURES / f"{ticker.lower()}.json").read_text())


def html(data):
    flight = "1:" + json.dumps(["$", "$L21", None, data]) + "\n"
    # El proveedor divide un objeto JSON entre varios scripts. No evaluamos JavaScript.
    cut = len(flight) // 2
    return "".join(
        "<script>self.__next_f.push(" + json.dumps([1, part]) + ")</script>"
        for part in (flight[:cut], flight[cut:])
    )


def quote(symbol="CFIETFEM.SN", value=955.41, day="2026-11-09"):
    return {
        "symbol": symbol,
        "currency": "CLP",
        "exchangeName": "SGO",
        "regularMarketPrice": value,
        "regularMarketTime": datetime.fromisoformat(day + "T19:00:00+00:00"),
    }


def frame(days, values):
    return pd.DataFrame(
        {"Close": values, "Adj Close": values, "Dividends": 0.0, "Stock Splits": 0.0},
        index=pd.DatetimeIndex(days, tz="America/Santiago"),
    )


class RacionalHistoryTests(unittest.TestCase):
    def setUp(self):
        self.holding = next(
            h
            for h in PLATFORM_CONFIG["racional_107_lir"]["holdings"]
            if h.ticker == "CFIETFEM"
        )

    def fetch(self, data, metadata=None, previous=None):
        with patch(
            "scripts.racional_history.urlopen",
            return_value=BytesIO(html(data).encode()),
        ):
            return fetch_racional_history(
                self.holding, quote() if metadata is None else metadata, previous
            )

    def test_reads_real_fragmented_records_and_longest_period(self):
        for ticker, size, last in [
            ("CFIETFEM", 21, 955.41),
            ("CFIETFIPSA", 261, 1280.5),
        ]:
            points = parse_racional_history(html(record(ticker)), ticker, "CLP")
            self.assertEqual(len(points), size)
            self.assertEqual(points[-1], {"date": "2026-11-09", "close": last})

    def test_rejects_wrong_identity_currency_order_and_prices(self):
        changes = [
            lambda p: p.update(ticker="OTHER"),
            lambda p: p.update(moneda="USD"),
            lambda p: p["periods"][0]["prices"].pop(),
            lambda p: p["periods"][0]["prices"].__setitem__(0, float("nan")),
            lambda p: p["periods"][0]["prices"].__setitem__(0, True),
            lambda p: p["periods"][0]["dates"].__setitem__(
                1, p["periods"][0]["dates"][0]
            ),
            lambda p: p["periods"][0]["dates"].__setitem__(
                0, "2026-10-12T10:00:00.000Z"
            ),
        ]
        for change in changes:
            data = record()
            change(data)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                parse_racional_history(html(data), "CFIETFEM", "CLP")

    def test_rejects_conflicting_overlapping_periods(self):
        data = record()
        duplicate = copy.deepcopy(data["periods"][0])
        duplicate["id"] = "MTD"
        duplicate["prices"][-1] *= 1.01
        data["periods"].append(duplicate)
        with self.assertRaisesRegex(RuntimeError, "incompatibles"):
            parse_racional_history(html(data), "CFIETFEM", "CLP")

    def test_requires_same_dated_quote_and_instrument(self):
        for metadata in [
            quote(value=500),
            quote(day="2026-11-06"),
            quote(symbol="OTHER.SN"),
            {**quote(), "currency": "USD"},
        ]:
            with self.subTest(metadata=metadata), self.assertRaises(RuntimeError):
                self.fetch(record(), metadata)

    def test_currency_missing_in_yahoo_is_verified_by_broker(self):
        history = self.fetch(record(), {**quote(), "currency": None})
        self.assertEqual(history[-1]["close"], 955.41)
        self.assertFalse(history.provenance["adjusted"])

    def test_keeps_previous_broker_history_without_mixing_adjusted_prices(self):
        source = self.fetch(record())
        old = [{"date": "2026-10-09", "close": 1070}] + list(source)
        previous = {"series": {"price_history": old}, "price_source": source.provenance}
        updated = self.fetch(record(), previous=previous)
        self.assertEqual(updated, old)
        previous["price_source"] = {"provider": "yfinance", "adjusted": True}
        with self.assertRaisesRegex(RuntimeError, "mezclará"):
            self.fetch(record(), previous=previous)

    def test_unknown_adjustments_never_become_long_term_adjusted_returns(self):
        data = record("CFIETFIPSA")
        history = parse_racional_history(html(data), "CFIETFIPSA", "CLP")
        payload = {
            "generated_at": "2026-11-09T20:00:00Z",
            "source": {"provider": "yfinance+racional"},
            "platforms": [
                {
                    "id": "test",
                    "name": "Test",
                    "holdings": [
                        {
                            "ticker": "CFIETFIPSA",
                            "currency": "CLP",
                            "weight": 1,
                            "series": {"price_history": history},
                            "price_source": {"provider": "racional", "adjusted": False},
                        }
                    ],
                }
            ],
        }
        restored = unpack_payload(pack_payload(refresh_derived(payload)))
        holding = restored["platforms"][0]["holdings"][0]
        self.assertIsNotNone(holding["metrics"]["monthly_change_pct"])
        self.assertIsNone(holding["metrics"]["return_1y"])
        self.assertIsNone(holding["metrics"]["return_5y"])
        self.assertEqual(holding["price_source"]["provider"], "racional")


class ArchivedGlobalHistoryTests(unittest.TestCase):
    def setUp(self):
        days = ["2026-09-25", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01"]
        values = [3454.8, 3430, 3428.1001, 3435.3999, 3464]
        self.previous = {
            "series": {
                "price_history": [{"date": d, "close": v} for d, v in zip(days, values)]
            },
            "status": {"warnings": ["Recuperación anterior verificada"]},
        }
        self.daily = frame(
            [
                "2026-07-14",
                "2026-07-15",
                *days,
                "2026-10-02",
                "2026-11-06",
                "2026-11-09",
            ],
            [1730.6, 3230.3, *values, 3441, 3313.2, 3359.9],
        )
        self.hourly = frame(
            [d + " 16:00" for d in [*days, "2026-10-02", "2026-11-06", "2026-11-09"]],
            [*values, 3441, 3313.2, 3359.9],
        )
        self.ticker = Mock()
        self.ticker.get_history_metadata.return_value = quote("CFIETFGE.SN", 3359.9)
        self.ticker.history.return_value = self.hourly

    def test_preserves_archive_and_appends_only_corroborated_sessions(self):
        result = recover_from_snapshot(self.ticker, self.daily, self.previous)
        self.assertEqual(result[:5], self.previous["series"]["price_history"])
        self.assertEqual(result[-1], {"date": "2026-11-09", "close": 3359.9})
        self.assertEqual(result.provenance["archive_through"], "2026-10-01")
        self.assertTrue(result.provenance["adjusted"])
        self.assertIn("Recuperación anterior verificada", result.warnings)

    def test_can_refresh_same_session_without_duplicate_dates(self):
        first = recover_from_snapshot(self.ticker, self.daily, self.previous)
        previous = {
            "series": {"price_history": first},
            "status": {"warnings": first.warnings},
            "price_source": first.provenance,
        }
        updated = recover_from_snapshot(self.ticker, self.daily, previous)
        self.assertEqual(updated, first)
        self.assertEqual(len({p["date"] for p in updated}), len(updated))
        self.assertEqual(
            sum(
                w.startswith("Yahoo alteró retrospectivamente")
                for w in updated.warnings
            ),
            1,
        )

    def test_rejects_events_missing_anchors_and_unverified_quote(self):
        for change in [
            "dividend",
            "split",
            "missing_anchor",
            "wrong_basis",
            "wrong_quote",
            "wrong_currency",
            "missing_actions",
            "missing_session",
            "unadjusted_archive",
        ]:
            with self.subTest(case=change):
                self.setUp()
                if change == "dividend":
                    self.daily.loc["2026-10-02", "Dividends"] = 10
                if change == "split":
                    self.daily.loc["2026-10-02", "Stock Splits"] = 2
                if change == "missing_anchor":
                    self.ticker.history.return_value = self.hourly.iloc[-3:]
                if change == "wrong_basis":
                    self.previous["series"]["price_history"][2]["close"] *= 1.1
                if change == "wrong_quote":
                    self.ticker.get_history_metadata.return_value[
                        "regularMarketPrice"
                    ] = 1700
                if change == "wrong_currency":
                    self.ticker.get_history_metadata.return_value["currency"] = "USD"
                if change == "missing_actions":
                    self.daily = self.daily.drop(columns=["Dividends"])
                if change == "missing_session":
                    self.ticker.history.return_value = self.hourly.drop(
                        self.hourly.index[-2]
                    )
                if change == "unadjusted_archive":
                    self.previous["price_source"] = {
                        "provider": "racional",
                        "adjusted": False,
                    }
                with self.assertRaises(RuntimeError):
                    recover_from_snapshot(self.ticker, self.daily, self.previous)

    def test_existing_generator_uses_archive_only_after_strict_recovery_fails(self):
        holding = next(
            h
            for h in PLATFORM_CONFIG["racional"]["holdings"]
            if h.fetch_symbol == "CFIETFGE.SN"
        )
        self.ticker.history.side_effect = [self.daily, self.hourly, self.hourly]
        with patch("yfinance.Ticker", return_value=self.ticker):
            history = generate_online_price_history(holding, previous=self.previous)
        self.assertEqual(history[-1]["close"], 3359.9)
        self.assertEqual(history[:5], self.previous["series"]["price_history"])


if __name__ == "__main__":
    unittest.main()
