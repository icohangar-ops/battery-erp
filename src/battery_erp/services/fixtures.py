"""Seed inventory for local / demo use (no Fabric required)."""

from __future__ import annotations

from datetime import date

from battery_erp.core.models import InventoryRecord, MaterialUnit, SupplyStatus


def seed_inventory() -> list[InventoryRecord]:
    """Representative SKUs covering materials + cell/pack components."""
    rows = [
        InventoryRecord(
            sku="LI-CARB-001",
            material_name="lithium_carbonate",
            warehouse="WH-A",
            quantity_on_hand=12500.0,
            quantity_reserved=2000.0,
            unit=MaterialUnit.KG,
            reorder_point=3000.0,
            reorder_qty=5000.0,
            unit_cost_usd=14.5,
            last_replenished=date(2026, 8, 1),
        ),
        InventoryRecord(
            sku="CO-SULF-001",
            material_name="cobalt_sulfate",
            warehouse="WH-A",
            quantity_on_hand=800.0,
            quantity_reserved=600.0,
            unit=MaterialUnit.KG,
            reorder_point=500.0,
            reorder_qty=1000.0,
            unit_cost_usd=28.0,
            last_replenished=date(2026, 7, 20),
        ),
        InventoryRecord(
            sku="NI-SULF-001",
            material_name="nickel_sulfate",
            warehouse="WH-B",
            quantity_on_hand=0.0,
            quantity_reserved=0.0,
            unit=MaterialUnit.KG,
            reorder_point=1000.0,
            reorder_qty=2500.0,
            unit_cost_usd=18.2,
            last_replenished=date(2026, 6, 15),
        ),
        InventoryRecord(
            sku="GRAPH-001",
            material_name="graphite_anode",
            warehouse="WH-B",
            quantity_on_hand=4200.0,
            quantity_reserved=200.0,
            unit=MaterialUnit.KG,
            reorder_point=1500.0,
            reorder_qty=3000.0,
            unit_cost_usd=6.8,
            last_replenished=date(2026, 8, 10),
        ),
        InventoryRecord(
            sku="CELL-NMC811-50AH",
            material_name="nmc811_cell_50ah",
            warehouse="WH-CELL",
            quantity_on_hand=1500.0,
            quantity_reserved=400.0,
            unit=MaterialUnit.EACH,
            reorder_point=800.0,
            reorder_qty=2000.0,
            unit_cost_usd=42.0,
            last_replenished=date(2026, 8, 15),
        ),
        InventoryRecord(
            sku="PACK-ESS-100KWH",
            material_name="ess_pack_100kwh",
            warehouse="WH-PACK",
            quantity_on_hand=12.0,
            quantity_reserved=5.0,
            unit=MaterialUnit.EACH,
            reorder_point=10.0,
            reorder_qty=20.0,
            unit_cost_usd=18500.0,
            last_replenished=date(2026, 8, 5),
        ),
    ]
    for r in rows:
        r.calculate_available()
    return rows


# Optional aliases so SMS / humans can ask by part number or common name.
PART_ALIASES: dict[str, str] = {
    "lithium": "LI-CARB-001",
    "lithium carbonate": "LI-CARB-001",
    "li-carb": "LI-CARB-001",
    "cobalt": "CO-SULF-001",
    "nickel": "NI-SULF-001",
    "graphite": "GRAPH-001",
    "nmc811": "CELL-NMC811-50AH",
    "nmc-811": "CELL-NMC811-50AH",
    "ess pack": "PACK-ESS-100KWH",
    "100kwh": "PACK-ESS-100KWH",
}
