"""Verifica la integración de la cartera nueva con un Blob anterior."""

import copy
import json
import unittest
from unittest.mock import patch

from backend.portfolio_refresh import fetch_latest_payload
from backend.storage import LATEST_DATASET, StorageMeta
from scripts.fetch_data import PLATFORM_CONFIG
from scripts.update_fintual import matches_config


class FintualReconciliationTests(unittest.TestCase):
    def test_old_blob_uses_new_holdings_without_losing_racional_recovery(self):
        seed = json.loads(LATEST_DATASET.local_path.read_text())
        old = copy.deepcopy(seed)
        fintual = next(p for p in old['platforms'] if p['id'] == 'fintual')
        fintual.pop('portfolio_as_of', None)
        fintual['holdings'] = [h for h in fintual['holdings'] if h['ticker'] == 'ESGV']
        original_racional = [p for p in old['platforms'] if p['id'] != 'fintual']
        with patch('backend.portfolio_refresh.read_dataset', return_value=(old, StorageMeta('blob'))):
            updated, meta = fetch_latest_payload()
        self.assertEqual(meta.source, 'blob')
        self.assertTrue(matches_config(updated))
        self.assertEqual([p for p in updated['platforms'] if p['id'] != 'fintual'], original_racional)
        self.assertEqual(updated['source'], old['source'])
        self.assertEqual(updated['generated_at'], old['generated_at'])
        expected = [h.ticker for h in PLATFORM_CONFIG['fintual']['holdings']]
        charts = [updated['charts']['timeseries_5y']['datasets'],
                  *updated['charts']['histograms'].values()]
        for entries in charts:
            self.assertEqual([h.get('ticker', h.get('id')) for h in entries
                              if h['platform_id'] == 'fintual'], expected)
        for platform in original_racional:
            holding = next(h for h in platform['holdings'] if 'CFIETFGE' in h['ticker'])
            self.assertEqual(holding['metrics']['return_1y'], 0.1814)
            self.assertEqual(holding['metrics']['return_5y'], 0.9407)


if __name__ == '__main__':
    unittest.main()
