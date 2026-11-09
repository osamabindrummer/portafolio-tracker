"""Comprueba los handlers HTTP reales sin red ni escrituras remotas."""

import importlib
import json
import os
import unittest
from io import BytesIO
from unittest.mock import patch

from backend.portfolio_refresh import RefreshResult
from backend.storage import LATEST_DATASET, StorageMeta, read_dataset


def request_handler(module, body=None, query="", headers=None):
    instance = module.handler.__new__(module.handler)
    raw = json.dumps(body or {}).encode()
    instance.path = "/api/test" + query
    instance.headers = {"Content-Length": str(len(raw)), **(headers or {})}
    instance.rfile = BytesIO(raw)
    instance.wfile = BytesIO()
    instance.response_headers = {}
    instance.send_response = lambda status: setattr(instance, "status_code", status)
    instance.send_header = lambda key, value: instance.response_headers.update(
        {key: value}
    )
    instance.end_headers = lambda: None
    return instance


class ApiTests(unittest.TestCase):
    def test_get_uses_real_projection_without_exposing_histories(self):
        module = importlib.import_module("api.data.latest")
        with patch.dict(os.environ, {"PORTFOLIO_STORAGE": "local"}):
            payload, _ = read_dataset(LATEST_DATASET)
        request = request_handler(module)
        with patch.object(
            module, "fetch_latest_payload", return_value=(payload, StorageMeta("local"))
        ):
            request.do_GET()
        result = json.loads(request.wfile.getvalue())
        self.assertEqual(request.status_code, 200)
        self.assertNotIn("series", result["platforms"][0]["holdings"][0])
        self.assertIn("charts", result)

    def test_all_public_refresh_routes_reject_offline_and_force(self):
        for name in ("refresh_data", "refresh_indicators", "refresh_all"):
            module = importlib.import_module(f"api.{name}")
            for body, status in [({"mode": "offline"}, 400), ({"force": True}, 401)]:
                with (
                    self.subTest(route=name, body=body),
                    patch.dict(os.environ, {"CRON_SECRET": ""}),
                ):
                    request = request_handler(module, body)
                    request.do_POST()
                    self.assertEqual(request.status_code, status)

    def test_public_refresh_route_passes_online_request(self):
        module = importlib.import_module("api.refresh_data")
        request = request_handler(module)
        with patch.object(
            module,
            "refresh_latest_dataset",
            return_value=RefreshResult("latest", "skipped", "Ya actualizado"),
        ) as refresh:
            request.do_POST()
        self.assertEqual(request.status_code, 202)
        refresh.assert_called_once_with(force=False)

    def test_partial_failure_identifies_dataset(self):
        module = importlib.import_module("api.refresh_all")
        request = request_handler(module, {"includeIndicators": True})
        with (
            patch.object(
                module,
                "refresh_latest_dataset",
                side_effect=RuntimeError("Cotizaciones sin cobertura"),
            ),
            patch.object(
                module,
                "refresh_indicators_dataset",
                return_value=RefreshResult("indicators", "updated", "Actualizado"),
            ),
        ):
            request.do_POST()
        self.assertEqual(request.status_code, 200)
        self.assertEqual(
            json.loads(request.wfile.getvalue())["errors"]["latest"],
            "Cotizaciones sin cobertura",
        )

    def test_cron_is_closed_without_secret_and_rejects_wrong_secret(self):
        module = importlib.import_module("api.cron.refresh")
        for secret in ("", "another-secret"):
            request = request_handler(
                module, headers={"Authorization": "Bearer incorrect"}
            )
            with (
                patch.dict(os.environ, {"CRON_SECRET": secret}),
                patch.object(module, "refresh_latest_dataset") as refresh,
            ):
                request.do_GET()
                self.assertEqual(request.status_code, 401)
                refresh.assert_not_called()

    def test_body_limits_and_malformed_content_length_return_400(self):
        module = importlib.import_module("api.refresh_all")
        for length in ("-1", "5000", "invalid"):
            request = request_handler(module, headers={"Content-Length": length})
            request.do_POST()
            self.assertEqual(request.status_code, 400)


if __name__ == "__main__":
    unittest.main()
