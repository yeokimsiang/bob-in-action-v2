"""
Tests for invoice-preview-v1 FastAPI service.
Run: python -m unittest discover -s tests -v
Requires: fastapi==0.143.1, uvicorn==0.54.0, httpx==0.28.1 (via requirements.txt)
No pytest dependency.
"""
import json
import sys
import os
import unittest

# Ensure app package is importable from bounded-proof/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


class TestHealth(unittest.TestCase):
    def test_health_200(self):
        r = client.get("/internal/health")
        self.assertEqual(r.status_code, 200)

    def test_health_status_up(self):
        r = client.get("/internal/health")
        self.assertEqual(r.json()["status"], "UP")

    def test_health_read_only(self):
        r = client.get("/internal/health")
        self.assertIs(r.json()["readOnly"], True)

    def test_health_write_count_zero(self):
        r = client.get("/internal/health")
        self.assertEqual(r.json()["writeCount"], 0)

    def test_health_exact_fields(self):
        r = client.get("/internal/health")
        self.assertEqual(set(r.json().keys()), {"status", "readOnly", "writeCount"})


class TestInvoiceResponseFields(unittest.TestCase):
    """Exact response shape from contract."""

    def _post(self, payload):
        return client.post(
            "/api/invoice-preview",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_top_level_fields(self):
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json().keys()),
                         {"customerId", "customerName", "tier", "subtotal", "gst", "total", "lines"})

    def test_line_fields(self):
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        line = r.json()["lines"][0]
        self.assertEqual(set(line.keys()),
                         {"lineNo", "productCode", "qty", "unitPrice", "lineNet"})


class TestExactFullResponse(unittest.TestCase):
    """Full response body matches contract case exactly."""

    def _post(self, payload):
        return client.post(
            "/api/invoice-preview",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_full_response_qty99(self):
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": 99, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["customerId"], 1)
        self.assertEqual(body["customerName"], "Aster Office Supplies")
        self.assertEqual(body["tier"], "A")
        self.assertEqual(body["subtotal"], "940.50")
        self.assertEqual(body["gst"], "84.65")
        self.assertEqual(body["total"], "1025.15")
        self.assertEqual(len(body["lines"]), 1)
        line = body["lines"][0]
        self.assertEqual(line["lineNo"], 1)
        self.assertEqual(line["productCode"], "PAPER-A4")
        self.assertEqual(line["qty"], 99)
        self.assertEqual(line["unitPrice"], "10.0000")
        self.assertEqual(line["lineNet"], "940.50")


class TestTotals(unittest.TestCase):
    """Contract totals — preserved exactly per invoice-preview-v1.json cases."""

    def _post(self, payload):
        return client.post(
            "/api/invoice-preview",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_qty99_total(self):
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": 99, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["customerName"], "Aster Office Supplies")
        self.assertEqual(body["tier"], "A")
        self.assertEqual(body["subtotal"], "940.50")
        self.assertEqual(body["gst"], "84.65")
        self.assertEqual(body["total"], "1025.15")

    def test_qty100_total(self):
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": 100, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["customerName"], "Aster Office Supplies")
        self.assertEqual(body["tier"], "A")
        self.assertEqual(body["subtotal"], "931.00")
        self.assertEqual(body["gst"], "83.79")
        self.assertEqual(body["total"], "1014.79")

    def test_qty101_total(self):
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": 101, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["customerName"], "Aster Office Supplies")
        self.assertEqual(body["tier"], "A")
        self.assertEqual(body["subtotal"], "940.31")
        self.assertEqual(body["gst"], "84.63")
        self.assertEqual(body["total"], "1024.94")

    def test_rounding_5x3335(self):
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "CABLE-USB", "qty": 5, "unitPrice": "3.3350"}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["customerName"], "Aster Office Supplies")
        self.assertEqual(body["tier"], "A")
        self.assertEqual(body["subtotal"], "15.84")
        self.assertEqual(body["gst"], "1.43")
        self.assertEqual(body["total"], "17.27")

    def test_tier_b(self):
        r = self._post({"customerId": 2,
                        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["customerName"], "Merlion Retail")
        self.assertEqual(body["tier"], "B")
        self.assertEqual(body["subtotal"], "9.70")
        self.assertEqual(body["gst"], "0.87")
        self.assertEqual(body["total"], "10.57")

    def test_tier_c(self):
        r = self._post({"customerId": 3,
                        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["customerName"], "Straits Workshop")
        self.assertEqual(body["tier"], "C")
        self.assertEqual(body["subtotal"], "10.00")
        self.assertEqual(body["gst"], "0.90")
        self.assertEqual(body["total"], "10.90")


class TestCallerTierIgnored(unittest.TestCase):
    """Caller-supplied tier must be silently ignored; server resolves tier from customerId."""

    def _post(self, payload):
        return client.post(
            "/api/invoice-preview",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_no_tier_in_payload_uses_server_tier(self):
        """No-tier legacy payload: customerId 1 resolves to tier A."""
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["tier"], "A")
        self.assertEqual(body["customerName"], "Aster Office Supplies")
        self.assertEqual(body["subtotal"], "9.50")
        self.assertEqual(body["gst"], "0.86")
        self.assertEqual(body["total"], "10.36")

    def test_mismatched_tier_injection_ignored(self):
        """Caller injects tier=C for customerId 1 (tier A); server returns tier A totals."""
        r = self._post({"customerId": 1, "tier": "C",
                        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        # Server resolves to A, not the caller's injected C
        self.assertEqual(body["tier"], "A")
        self.assertEqual(body["customerName"], "Aster Office Supplies")
        self.assertEqual(body["subtotal"], "9.50")
        self.assertEqual(body["gst"], "0.86")
        self.assertEqual(body["total"], "10.36")

    def test_tier_a_in_payload_still_uses_server_tier(self):
        """Caller supplies matching tier A for customerId 1 — server still resolves independently."""
        r = self._post({"customerId": 1, "tier": "A",
                        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["tier"], "A")
        self.assertEqual(body["customerName"], "Aster Office Supplies")


class TestNotFound(unittest.TestCase):
    """Unknown customer or product → HTTP 404."""

    def _post(self, payload):
        return client.post(
            "/api/invoice-preview",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_unknown_customer_is_404(self):
        r = self._post({"customerId": 999,
                        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 404)

    def test_unknown_product_is_404(self):
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "UNKNOWN", "qty": 1, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 404)


class TestValidationErrors(unittest.TestCase):
    """Invalid input → HTTP 400."""

    def _post(self, payload):
        return client.post(
            "/api/invoice-preview",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def _post_raw(self, raw: str):
        return client.post(
            "/api/invoice-preview",
            content=raw,
            headers={"Content-Type": "application/json"},
        )

    def test_missing_customer_id(self):
        r = self._post({"lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 400)

    def test_missing_lines(self):
        r = self._post({"customerId": 1})
        self.assertEqual(r.status_code, 400)

    def test_empty_lines(self):
        r = self._post({"customerId": 1, "lines": []})
        self.assertEqual(r.status_code, 400)

    def test_qty_string_is_400(self):
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": "100", "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 400)

    def test_qty_zero_is_400(self):
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": 0, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 400)

    def test_qty_fractional_float_is_400(self):
        # JSON fractional number for qty
        r = self._post_raw(
            '{"customerId": 1, "lines": [{"productCode": "PAPER-A4", "qty": 1.5, "unitPrice": "10.00"}]}'
        )
        self.assertEqual(r.status_code, 400)

    def test_unit_price_non_positive_is_400(self):
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "0.00"}]})
        self.assertEqual(r.status_code, 400)

    def test_malformed_json_is_400(self):
        r = self._post_raw("{not valid json}")
        self.assertEqual(r.status_code, 400)


class TestWriteRouteRejection(unittest.TestCase):
    """Undeclared routes and write methods are rejected."""

    def test_put_invoice_preview_rejected(self):
        r = client.put("/api/invoice-preview",
                       content=json.dumps({}),
                       headers={"Content-Type": "application/json"})
        self.assertIn(r.status_code, (404, 405))

    def test_delete_invoice_preview_rejected(self):
        r = client.delete("/api/invoice-preview")
        self.assertIn(r.status_code, (404, 405))

    def test_undeclared_route_rejected(self):
        r = client.get("/api/not-a-route")
        self.assertEqual(r.status_code, 404)

    def test_post_health_rejected(self):
        r = client.post("/internal/health",
                        content=json.dumps({}),
                        headers={"Content-Type": "application/json"})
        self.assertIn(r.status_code, (404, 405))


class TestNoWriteCount(unittest.TestCase):
    """Preview must never increment writeCount."""

    def _post(self, payload):
        return client.post(
            "/api/invoice-preview",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_write_count_stays_zero_after_preview(self):
        self._post({"customerId": 1,
                    "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}]})
        r = client.get("/internal/health")
        self.assertEqual(r.json()["writeCount"], 0)

    def test_write_count_stays_zero_after_multiple_previews(self):
        for _ in range(3):
            self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}]})
        r = client.get("/internal/health")
        self.assertEqual(r.json()["writeCount"], 0)


class TestLinePriceFormat(unittest.TestCase):
    """unitPrice echoes four-decimal legacy representation; lineNet is two-decimal ROUND_HALF_UP."""

    def _post(self, payload):
        return client.post(
            "/api/invoice-preview",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_qty99_unitprice_four_decimal_and_linenet(self):
        """qty=99: unitPrice must be 10.0000, lineNet must be 940.50."""
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": 99, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        line = r.json()["lines"][0]
        self.assertEqual(line["unitPrice"], "10.0000")
        self.assertEqual(line["lineNet"], "940.50")

    def test_qty100_unitprice_four_decimal_and_linenet(self):
        """qty=100: unitPrice must be 10.0000, lineNet must be 931.00 (bulk discount applied)."""
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "PAPER-A4", "qty": 100, "unitPrice": "10.00"}]})
        self.assertEqual(r.status_code, 200)
        line = r.json()["lines"][0]
        self.assertEqual(line["unitPrice"], "10.0000")
        self.assertEqual(line["lineNet"], "931.00")

    def test_rounding_3335_unitprice_four_decimal_and_linenet(self):
        """3.3350 rounding case: unitPrice must be 3.3350, lineNet must be 15.84."""
        r = self._post({"customerId": 1,
                        "lines": [{"productCode": "CABLE-USB", "qty": 5, "unitPrice": "3.3350"}]})
        self.assertEqual(r.status_code, 200)
        line = r.json()["lines"][0]
        self.assertEqual(line["unitPrice"], "3.3350")
        self.assertEqual(line["lineNet"], "15.84")


if __name__ == "__main__":
    unittest.main()
