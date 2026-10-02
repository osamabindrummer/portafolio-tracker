"""Regresiones del histórico falso de CFIETFGE y sus dos packs."""

import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pandas as pd

from scripts.fetch_data import compute_returns, generate_online_payload
from scripts.yahoo_history import recover_global_equities


def frame(dates, prices):
    index = pd.DatetimeIndex(dates, tz='America/Santiago')
    return pd.DataFrame({'Close': prices, 'Adj Close': prices, 'Dividends': 0, 'Stock Splits': 0}, index=index)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.daily = frame(['2021-10-04', '2025-10-01', '2026-09-01', '2026-09-10',
                            '2026-09-14', '2026-09-30', '2026-10-01'],
                           [1784.9, 2931.994141, 3315.7329, 3313.2463, 1730.6, 1730.6, float('nan')])
        self.ticker = Mock()
        self.ticker.get_history_metadata.return_value = {
            'regularMarketPrice': 3464,
            'regularMarketTime': int(datetime(2026, 10, 1, 17, tzinfo=ZoneInfo('America/Santiago')).timestamp()),
        }
        self.ticker.history.return_value = frame(
            ['2026-09-14 15:00', '2026-09-30 15:00', '2026-09-30 16:00', '2026-10-01 16:00'],
            [3382.1, 3420, 3435.3999, 3464])

    def test_recovers_actual_sessions_and_returns(self):
        result, warnings = recover_global_equities(self.ticker, self.daily)
        self.assertEqual(result.loc['2026-09-30', 'Close'], 3435.3999)
        metrics = compute_returns([{'date': idx.date().isoformat(), 'close': row['Adj Close']}
                                   for idx, row in result.iterrows()])
        self.assertEqual(metrics['return_1y'], 0.1814)
        self.assertEqual(metrics['return_5y'], 0.9407)
        self.assertEqual(metrics['monthly_change_pct'], 0.0447)
        self.assertTrue(warnings)

    def test_accepts_metadata_date_already_converted_by_yfinance(self):
        self.ticker.get_history_metadata.return_value['regularMarketTime'] = pd.Timestamp(
            '2026-10-01 17:00', tz='America/Santiago')
        result, warnings = recover_global_equities(self.ticker, self.daily)
        self.assertEqual(result.iloc[-1]['Close'], 3464)
        self.assertTrue(warnings)

    def test_rejects_unverified_recovery(self):
        self.ticker.history.return_value = frame(['2026-10-01 16:00'], [1730.6])
        with self.assertRaisesRegex(RuntimeError, 'no corroboran'):
            recover_global_equities(self.ticker, self.daily)

    def test_does_not_guess_corporate_adjustments(self):
        self.daily.loc['2026-09-14', 'Dividends'] = 100
        with self.assertRaisesRegex(RuntimeError, 'eventos corporativos'):
            recover_global_equities(self.ticker, self.daily)

    def test_healthy_history_does_not_request_hourly_prices(self):
        daily = frame(['2026-09-30', '2026-10-01'], [3435.4, 3464])
        result, warnings = recover_global_equities(self.ticker, daily)
        self.assertTrue(result.equals(daily))
        self.assertEqual(warnings, [])
        self.ticker.history.assert_not_called()

    def test_packs_share_one_fetch_and_recalculate_weights(self):
        history = [{'date': '2021-10-01', 'close': 100}, {'date': '2025-10-01', 'close': 150},
                   {'date': '2026-09-01', 'close': 180}, {'date': '2026-10-01', 'close': 200}]
        with patch('scripts.fetch_data.generate_online_price_history', return_value=history) as fetch:
            payload = generate_online_payload()
        symbols = [call.args[0].fetch_symbol for call in fetch.call_args_list]
        self.assertEqual(symbols.count('CFIETFGE.SN'), 1)
        for platform in payload['platforms']:
            for metric, summary in [('return_1y', 'avg_return_1y'), ('return_5y', 'avg_return_5y'),
                                    ('monthly_change_pct', 'avg_monthly_change')]:
                expected = sum(h['weight'] * h['metrics'][metric] for h in platform['holdings'])
                expected /= sum(h['weight'] for h in platform['holdings'])
                self.assertEqual(platform['summary'][summary], round(expected, 4))


if __name__ == '__main__':
    unittest.main()
