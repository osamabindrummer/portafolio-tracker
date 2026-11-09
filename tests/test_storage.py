"""Comprueba compatibilidad del SDK y recuperación sin acceso al Blob real."""

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend import storage


class StorageTests(unittest.TestCase):
    def test_installed_sdk_matches_storage_adapter(self):
        for function in (
            storage.put_blob,
            storage.get_blob,
            storage.query_blobs,
            storage.delete_blob,
        ):
            self.assertTrue(callable(function))

    def test_explicit_blob_mode_reports_missing_token(self):
        with patch.dict(
            os.environ, {"PORTFOLIO_STORAGE": "blob", "BLOB_READ_WRITE_TOKEN": ""}
        ):
            with self.assertRaisesRegex(RuntimeError, "BLOB_READ_WRITE_TOKEN"):
                storage.should_use_blob_storage()

    def test_reader_recovers_previous_valid_snapshot(self):
        now = datetime.now(UTC)
        blobs = [
            SimpleNamespace(
                uploaded_at=now - timedelta(seconds=i),
                pathname=f"snapshot-{i}",
                url=f"https://example.org/{i}",
            )
            for i in range(2)
        ]
        payload = json.loads(storage.INDICATORS_DATASET.local_path.read_text())
        with (
            patch.object(storage, "query_blobs", return_value=iter(blobs)),
            patch.object(
                storage,
                "get_blob",
                side_effect=[
                    ValueError("JSON inválido"),
                    SimpleNamespace(body=json.dumps(payload).encode()),
                ],
            ),
            self.assertLogs("backend.storage", level="ERROR"),
        ):
            actual, meta = storage._read_from_blob(storage.INDICATORS_DATASET)
        self.assertEqual(actual, payload)
        self.assertEqual(meta.pathname, "snapshot-1")
        self.assertTrue(meta.warning)

    def test_reader_uses_local_seed_during_blob_outage(self):
        with (
            patch.object(storage, "should_use_blob_storage", return_value=True),
            patch.object(
                storage, "_read_from_blob", side_effect=RuntimeError("Sin conexión")
            ),
            self.assertLogs("backend.storage", level="ERROR"),
        ):
            payload, meta = storage.read_dataset(storage.LATEST_DATASET)
        self.assertEqual(meta.source, "local-fallback")
        self.assertTrue(payload["platforms"])

    def test_atomic_write_does_not_truncate_previous_file_on_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text('{"previous":true}')
            with self.assertRaises(ValueError):
                storage.write_local_json(path, {"value": float("nan")})
            self.assertEqual(json.loads(path.read_text()), {"previous": True})
            self.assertEqual(len(list(path.parent.iterdir())), 1)

    def test_retention_runs_after_successful_write(self):
        now = datetime.now(UTC)
        blobs = [
            SimpleNamespace(
                uploaded_at=now - timedelta(seconds=i),
                pathname=f"old-{i}",
                url=f"url-{i}",
            )
            for i in range(8)
        ]
        result = SimpleNamespace(pathname="new", url="new-url")
        with (
            patch.object(storage, "put_blob", return_value=result) as put,
            patch.object(storage, "query_blobs", return_value=iter(blobs)),
            patch.object(storage, "delete_blob") as delete,
        ):
            storage._write_to_blob(storage.INDICATORS_DATASET, {"items": []})
        self.assertFalse(put.call_args.kwargs["add_random_suffix"])
        self.assertEqual(delete.call_args.args[0], [f"url-{i}" for i in range(4, 8)])


if __name__ == "__main__":
    unittest.main()
