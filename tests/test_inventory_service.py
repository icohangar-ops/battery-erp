# Battery ERP — Inventory service / REST / MCP scaffold tests
"""Tests for the shared InventoryService used by MCP tools and the REST adapter."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from battery_erp.services.inventory import (
    InventoryAuthError,
    InventoryNotFoundError,
    InventoryService,
)
from battery_erp.services.store import InMemoryInventoryStore


class TestInventoryServiceLookup(unittest.TestCase):
    def setUp(self) -> None:
        self.svc = InventoryService(store=InMemoryInventoryStore(), confirm_token="secret")

    def test_lookup_by_sku(self):
        row = self.svc.lookup_inventory("LI-CARB-001")
        self.assertEqual(row["sku"], "LI-CARB-001")
        self.assertIn("available", row)
        self.assertEqual(row["available"], 10500.0)

    def test_lookup_by_alias(self):
        row = self.svc.lookup_inventory("lithium")
        self.assertEqual(row["sku"], "LI-CARB-001")

    def test_lookup_missing(self):
        with self.assertRaises(InventoryNotFoundError):
            self.svc.lookup_inventory("NO-SUCH-PART")

    def test_get_inventory_status_includes_reorder_when_low(self):
        # NI-SULF-001 is out of stock → reorder suggestion
        status = self.svc.get_inventory_status("nickel")
        self.assertEqual(status["sku"], "NI-SULF-001")
        self.assertIsNotNone(status["reorder"])

    def test_get_inventory_record_fields(self):
        rec = self.svc.get_inventory_record("CELL-NMC811-50AH")
        for key in (
            "sku",
            "quantity_on_hand",
            "quantity_reserved",
            "quantity_available",
            "reorder_point",
            "status",
        ):
            self.assertIn(key, rec)

    def test_list_inventory(self):
        rows = self.svc.list_inventory()
        self.assertGreaterEqual(len(rows), 6)
        skus = {r["sku"] for r in rows}
        self.assertIn("GRAPH-001", skus)


class TestBinCheckWorkflow(unittest.TestCase):
    def setUp(self) -> None:
        self.svc = InventoryService(store=InMemoryInventoryStore(), confirm_token="secret")

    def test_create_bin_check_request(self):
        req = self.svc.create_bin_check_request("cobalt", notes="SMS verify")
        self.assertEqual(req["sku"], "CO-SULF-001")
        self.assertEqual(req["status"], "pending")
        self.assertIn("request_id", req)

    def test_record_bin_confirmation_requires_token(self):
        with self.assertRaises(InventoryAuthError):
            self.svc.record_bin_confirmation("graphite", 4100.0, auth_token="wrong")

    def test_record_bin_confirmation_updates_qty(self):
        req = self.svc.create_bin_check_request("GRAPH-001")
        result = self.svc.record_bin_confirmation(
            "GRAPH-001",
            4100.0,
            auth_token="secret",
            request_id=req["request_id"],
            actor="tester",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["quantity_on_hand"], 4100.0)
        rec = self.svc.get_inventory_record("GRAPH-001")
        self.assertEqual(rec["quantity_on_hand"], 4100.0)

    def test_confirm_disabled_without_env_token(self):
        svc = InventoryService(store=InMemoryInventoryStore(), confirm_token="")
        with self.assertRaises(InventoryAuthError):
            svc.record_bin_confirmation("LI-CARB-001", 1.0, auth_token="")

    def test_audit_file_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            store = InMemoryInventoryStore(audit_path=path)
            svc = InventoryService(store=store, confirm_token="secret")
            svc.record_bin_confirmation("LI-CARB-001", 12000.0, auth_token="secret")
            self.assertTrue(path.exists())
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 1)
            self.assertIn("bin_confirmation", lines[-1])


class TestRestAdapter(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi.testclient import TestClient
            from battery_erp.api.app import build_app
        except ImportError:
            self.skipTest("fastapi not installed")
        self.svc = InventoryService(store=InMemoryInventoryStore(), confirm_token="secret")
        self.client = TestClient(build_app(self.svc))

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_lookup(self):
        r = self.client.get("/inventory/lookup/lithium")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["sku"], "LI-CARB-001")

    def test_lookup_404(self):
        r = self.client.get("/inventory/lookup/ZZZ-NONE")
        self.assertEqual(r.status_code, 404)

    def test_bin_confirm_unauthorized(self):
        r = self.client.post(
            "/inventory/bin-confirm/LI-CARB-001",
            json={"actual_quantity": 100.0},
        )
        self.assertEqual(r.status_code, 401)

    def test_bin_confirm_ok(self):
        r = self.client.post(
            "/inventory/bin-confirm/LI-CARB-001",
            json={"actual_quantity": 13000.0, "actor": "sms-operator"},
            headers={"X-Battery-Erp-Token": "secret"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])


class TestMcpScaffoldImport(unittest.TestCase):
    def test_create_mcp_when_mcp_installed(self):
        try:
            from battery_erp.mcp.server import create_mcp
        except SystemExit:
            self.skipTest("mcp package not installed")
        svc = InventoryService(store=InMemoryInventoryStore(), confirm_token="secret")
        try:
            server = create_mcp(svc)
        except SystemExit:
            self.skipTest("mcp package not installed")
        self.assertIsNotNone(server)
        self.assertTrue(hasattr(server, "run"))


if __name__ == "__main__":
    unittest.main()
