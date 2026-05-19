# Battery ERP — Core tests
"""Unit tests for data models, business rules, and supply chain logic."""

import unittest
from datetime import date, timedelta

from battery_erp.core.models import (
    BOMItem,
    BatteryCell,
    BatteryPack,
    BatteryCategory,
    CellFormFactor,
    InventoryRecord,
    ManufacturingBatch,
    MaterialUnit,
    OrderStatus,
    PriceHistory,
    PurchaseOrder,
    RawMaterial,
    SupplyStatus,
    Supplier,
)
from battery_erp.core.rules import (
    analyze_price_history,
    calculate_batch_metrics,
    calculate_cell_bom,
    calculate_pack_bom,
    calculate_pack_metrics,
    check_reorder_suggestions,
    estimate_cell_cost_impact,
    rollup_bom_cost,
    update_inventory_status,
)
from battery_erp.pricing import (
    calculate_cell_cost_summary,
    get_material_price_table,
    update_prices_from_fred,
)
from battery_erp.supply_chain import (
    analyze_po_pipeline,
    create_purchase_order,
    rank_suppliers,
    score_supplier,
    suggest_dual_sourcing,
)
from battery_erp.analytics import (
    generate_inventory_report,
    generate_manufacturing_report,
    generate_pricing_report,
    generate_supply_chain_report,
)


class TestRawMaterial(unittest.TestCase):
    def test_price_per_kg(self):
        mat = RawMaterial(name="Nickel", unit_price_usd=16500, unit=MaterialUnit.TONNE)
        self.assertAlmostEqual(mat.price_per_kg, 16.5)

    def test_price_per_kg_direct(self):
        mat = RawMaterial(name="Cobalt", unit_price_usd=24.0, unit=MaterialUnit.KG)
        self.assertAlmostEqual(mat.price_per_kg, 24.0)


class TestBatteryCell(unittest.TestCase):
    def test_energy_kwh(self):
        cell = BatteryCell(nominal_capacity_ah=50, nominal_voltage_v=3.7, energy_wh=185)
        self.assertAlmostEqual(cell.energy_kwh, 0.185)


class TestBatteryPack(unittest.TestCase):
    def test_energy_density(self):
        pack = BatteryPack(nominal_capacity_kwh=75.0, pack_weight_kg=375.0)
        self.assertAlmostEqual(pack.energy_density_pack_wh_per_kg, 200.0)

    def test_total_cells_computation(self):
        pack = BatteryPack(cells_in_series=96, cells_in_parallel=3)
        self.assertEqual(pack.cells_in_series * pack.cells_in_parallel, 288)


class TestBOMCost(unittest.TestCase):
    def test_rollup_simple(self):
        bom = [
            BOMItem(material_name="Nickel", quantity_per_unit=0.3, unit_cost_usd=16.5, waste_factor_pct=3),
            BOMItem(material_name="Cobalt", quantity_per_unit=0.05, unit_cost_usd=24.0, waste_factor_pct=3),
        ]
        result = rollup_bom_cost(bom)
        self.assertGreater(result["total_cost_usd"], 0)
        self.assertEqual(result["line_items"], 2)
        self.assertIn("Nickel", result["material_breakdown"])

    def test_rollup_empty(self):
        result = rollup_bom_cost([])
        self.assertEqual(result["total_cost_usd"], 0)
        self.assertEqual(result["line_items"], 0)

    def test_cell_bom_nmc811(self):
        prices = {"nickel": 16.5, "manganese": 2.8, "cobalt": 24.0, "lithium_carbonate": 12.5,
                  "graphite_anode": 12.0, "electrolyte": 8.5, "copper_foil": 9.0,
                  "aluminum_foil": 3.2, "separator": 15.0, "binder_pvdf": 25.0, "conductive_additive": 8.0}
        bom = calculate_cell_bom("NMC-811", 50.0, prices)
        self.assertGreater(len(bom), 8)
        # All line costs should be positive
        for item in bom:
            self.assertGreater(item.line_cost_usd, 0)

    def test_cell_bom_lfp(self):
        prices = {"lithium_carbonate": 12.5, "iron_phosphate": 1.5,
                  "graphite_anode": 12.0, "electrolyte": 8.5, "copper_foil": 9.0,
                  "aluminum_foil": 3.2, "separator": 15.0, "binder_pvdf": 25.0, "conductive_additive": 8.0}
        bom = calculate_cell_bom("LFP", 50.0, prices)
        self.assertGreater(len(bom), 5)
        mat_names = [item.material_name for item in bom]
        self.assertIn("lithium_carbonate", mat_names)
        self.assertIn("iron_phosphate", mat_names)
        # LFP should NOT have cobalt or nickel
        self.assertNotIn("cobalt", mat_names)

    def test_pack_bom(self):
        pack = BatteryPack(sku="PACK-EV75", cell_sku="CELL-NMC811-50",
                          total_cells=108, nominal_capacity_kwh=75.0)
        prices = {"pack_casing_aluminum": 3.5, "bms_module": 15.0, "thermal_coolant": 5.0,
                  "wiring_harness": 6.0, "insulation": 4.0, "pack_structural_adhesive": 8.0}
        bom = calculate_pack_bom(pack, 8.50, prices)
        self.assertGreater(len(bom), 5)
        # First item should be cells
        self.assertIn("cell_", bom[0].material_name)
        self.assertEqual(bom[0].quantity_per_unit, 108)


class TestInventory(unittest.TestCase):
    def test_update_status_healthy(self):
        records = [
            InventoryRecord(sku="MAT-001", material_name="Nickel",
                           quantity_on_hand=1000, quantity_reserved=100,
                           reorder_point=200, unit_cost_usd=16.5),
        ]
        results = update_inventory_status(records)
        self.assertEqual(results[0]["status"], "in_stock")
        self.assertAlmostEqual(results[0]["available"], 900)

    def test_update_status_low(self):
        records = [
            InventoryRecord(sku="MAT-002", material_name="Cobalt",
                           quantity_on_hand=150, quantity_reserved=50,
                           reorder_point=200, unit_cost_usd=24.0),
        ]
        results = update_inventory_status(records)
        self.assertEqual(results[0]["status"], "low")

    def test_update_status_out_of_stock(self):
        records = [
            InventoryRecord(sku="MAT-003", material_name="Lithium Carbonate",
                           quantity_on_hand=50, quantity_reserved=100,
                           reorder_point=200, unit_cost_usd=12.5),
        ]
        results = update_inventory_status(records)
        self.assertEqual(results[0]["status"], "out_of_stock")

    def test_reorder_suggestions(self):
        records = [
            InventoryRecord(sku="MAT-001", quantity_on_hand=1000, quantity_reserved=100,
                           reorder_point=200, reorder_qty=500, unit_cost_usd=16.5),
            InventoryRecord(sku="MAT-002", quantity_on_hand=50, quantity_reserved=50,
                           reorder_point=200, reorder_qty=300, unit_cost_usd=24.0),
        ]
        suggestions = check_reorder_suggestions(records)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["sku"], "MAT-002")


class TestManufacturing(unittest.TestCase):
    def test_batch_metrics(self):
        batches = [
            ManufacturingBatch(quantity_produced=1000, quantity_pass=980),
            ManufacturingBatch(quantity_produced=1000, quantity_pass=950),
            ManufacturingBatch(quantity_produced=500, quantity_pass=490),
        ]
        metrics = calculate_batch_metrics(batches)
        self.assertEqual(metrics["total_produced"], 2500)
        self.assertEqual(metrics["total_pass"], 2420)
        self.assertAlmostEqual(metrics["avg_yield_pct"], 96.8)

    def test_empty_batches(self):
        metrics = calculate_batch_metrics([])
        self.assertEqual(metrics["total_produced"], 0)


class TestPriceAnalytics(unittest.TestCase):
    def test_price_history_analysis(self):
        history = [
            PriceHistory(material_name="nickel", price_usd=16.0, as_of=date(2025, 1, 1)),
            PriceHistory(material_name="nickel", price_usd=17.0, as_of=date(2025, 2, 1)),
            PriceHistory(material_name="nickel", price_usd=18.0, as_of=date(2025, 3, 1)),
            PriceHistory(material_name="nickel", price_usd=16.5, as_of=date(2025, 4, 1)),
        ]
        result = analyze_price_history(history, "nickel")
        self.assertEqual(result["data_points"], 4)
        self.assertAlmostEqual(result["latest_price"], 16.5)
        self.assertIn(result["trend"], ["up", "flat"])

    def test_insufficient_data(self):
        history = [PriceHistory(material_name="cobalt", price_usd=24.0, as_of=date(2025, 1, 1))]
        result = analyze_price_history(history, "cobalt")
        self.assertTrue(result["insufficient_data"])


class TestCostImpact(unittest.TestCase):
    def test_lithium_price_shock(self):
        current = {"lithium_carbonate": 12.5, "nickel": 16.5, "graphite_anode": 12.0}
        scenario = {"lithium_carbonate": 25.0, "nickel": 16.5, "graphite_anode": 12.0}

        bom = [
            BOMItem(material_name="lithium_carbonate", quantity_per_unit=0.1, unit_cost_usd=12.5),
            BOMItem(material_name="nickel", quantity_per_unit=0.3, unit_cost_usd=16.5),
        ]
        result = estimate_cell_cost_impact(current, scenario, bom)
        self.assertGreater(result["delta_usd"], 0)
        self.assertEqual(len(result["affected_materials"]), 1)
        self.assertEqual(result["affected_materials"][0]["material"], "lithium_carbonate")


class TestPackMetrics(unittest.TestCase):
    def test_pack_efficiency(self):
        cell = BatteryCell(nominal_capacity_ah=50, nominal_voltage_v=3.7,
                          energy_wh=185, weight_kg=0.8)
        pack = BatteryPack(total_cells=108, nominal_capacity_kwh=75.0, pack_weight_kg=380.0)
        metrics = calculate_pack_metrics(cell, pack)
        self.assertGreater(metrics["cell_energy_density_wh_per_kg"], 200)
        self.assertGreater(metrics["density_ratio_pct"], 0)


class TestSupplierScoring(unittest.TestCase):
    def test_supplier_score_a(self):
        s = Supplier(name="TopCo", quality_rating=90, on_time_delivery_pct=95,
                    lead_time_days=14, certifications=["ISO9001", "IATF16949"])
        score = score_supplier(s)
        self.assertGreater(score["composite_score"], 80)
        self.assertEqual(score["grade"], "A")

    def test_supplier_ranking(self):
        suppliers = [
            Supplier(name="TopCo", quality_rating=90, on_time_delivery_pct=95,
                    lead_time_days=14, materials_supplied=["nickel", "cobalt"]),
            Supplier(name="MidCo", quality_rating=70, on_time_delivery_pct=75,
                    lead_time_days=45, materials_supplied=["nickel", "cobalt"]),
        ]
        ranked = rank_suppliers(suppliers, "nickel")
        self.assertEqual(ranked[0]["name"], "TopCo")

    def test_create_po(self):
        supplier = Supplier(name="NickelMart", unit_price_usd=16.5, lead_time_days=21)
        po = create_purchase_order(supplier, "Nickel", 1000, MaterialUnit.KG)
        self.assertEqual(po.quantity, 1000)
        self.assertAlmostEqual(po.total_usd, 16500)
        self.assertEqual(po.status, OrderStatus.PENDING)

    def test_po_pipeline(self):
        orders = [
            PurchaseOrder(total_usd=50000, status=OrderStatus.DELIVERED,
                        order_date=date(2025, 1, 1), expected_delivery=date(2025, 2, 1),
                        actual_delivery=date(2025, 2, 1)),
            PurchaseOrder(total_usd=30000, status=OrderStatus.PENDING,
                        order_date=date(2025, 4, 1), expected_delivery=date(2025, 4, 25)),
        ]
        result = analyze_po_pipeline(orders)
        self.assertEqual(result["total_orders"], 2)
        self.assertAlmostEqual(result["total_value_usd"], 80000)

    def test_dual_sourcing(self):
        primary = Supplier(name="PrimaryCo", materials_supplied=["nickel"], lead_time_days=30)
        suppliers = [
            primary,
            Supplier(name="SecondaryCo", materials_supplied=["nickel"],
                    quality_rating=80, on_time_delivery_pct=85, lead_time_days=35),
        ]
        result = suggest_dual_sourcing(primary, suppliers, "nickel")
        self.assertEqual(result["recommendation"], "dual_source")
        self.assertEqual(result["secondary_supplier"], "SecondaryCo")


class TestPricingEngine(unittest.TestCase):
    def test_default_prices(self):
        prices = get_material_price_table()
        self.assertIn("lithium_carbonate", prices)
        self.assertIn("nickel", prices)
        self.assertGreater(prices["cobalt"], prices["manganese"])

    def test_cell_cost_nmc811_vs_lfp(self):
        prices = get_material_price_table()
        nmc = calculate_cell_cost_summary("NMC-811", 50.0, prices)
        lfp = calculate_cell_cost_summary("LFP", 50.0, prices)
        # LFP should be cheaper (no cobalt, no nickel)
        self.assertLess(lfp["cost_per_kwh"], nmc["cost_per_kwh"])
        # LFP cathode % should be lower (iron phosphate is cheap)
        self.assertLess(lfp["cathode_pct"], nmc["cathode_pct"])

    def test_cell_cost_all_chemistries(self):
        prices = get_material_price_table()
        for chem in ["NMC-111", "NMC-811", "NMC-622", "NCA", "LFP", "LMO"]:
            result = calculate_cell_cost_summary(chem, 50.0, prices)
            self.assertGreater(result["bom_cost_usd"], 0)
            self.assertGreater(result["cost_per_kwh"], 0)


class TestAnalytics(unittest.TestCase):
    def test_inventory_report(self):
        records = [
            InventoryRecord(sku="MAT-001", material_name="Nickel",
                           quantity_on_hand=1000, quantity_reserved=100,
                           reorder_point=200, unit_cost_usd=16.5),
            InventoryRecord(sku="MAT-002", material_name="Cobalt",
                           quantity_on_hand=250, quantity_reserved=100,
                           reorder_point=200, unit_cost_usd=24.0),
            InventoryRecord(sku="MAT-003", material_name="Lithium",
                           quantity_on_hand=50, quantity_reserved=100,
                           reorder_point=200, unit_cost_usd=12.5),
        ]
        report = generate_inventory_report(records)
        self.assertEqual(report["total_skus"], 3)
        self.assertEqual(report["low_stock_count"], 1)
        self.assertEqual(report["out_of_stock_count"], 1)

    def test_manufacturing_report(self):
        batches = [
            ManufacturingBatch(quantity_produced=1000, quantity_pass=980),
        ]
        report = generate_manufacturing_report(batches)
        self.assertEqual(report["total_produced"], 1000)
        self.assertAlmostEqual(report["avg_yield_pct"], 98.0)

    def test_pricing_report(self):
        prices = get_material_price_table()
        report = generate_pricing_report([], prices, cell_capacity_ah=50.0)
        self.assertIn("chemistry_comparison", report)
        self.assertIn("cost_ranking_cheapest_to_most", report)
        self.assertGreater(len(report["cost_ranking_cheapest_to_most"]), 3)

    def test_supply_chain_report(self):
        suppliers = [
            Supplier(name="TopCo", quality_rating=90, on_time_delivery_pct=95, lead_time_days=14),
        ]
        report = generate_supply_chain_report([], suppliers)
        self.assertEqual(report["supplier_count"], 1)


if __name__ == "__main__":
    unittest.main()
