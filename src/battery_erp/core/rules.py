# Battery ERP — Business Rules Engine
"""
Pricing, BOM cost rollups, inventory logic, and yield calculations.
All deterministic — no AI dependency.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from .models import (
    BOMItem,
    BatteryCell,
    BatteryPack,
    CellChemistry,
    CellFormFactor,
    InventoryRecord,
    ManufacturingBatch,
    MaterialUnit,
    OrderStatus,
    PriceHistory,
    PurchaseOrder,
    RawMaterial,
    SupplyStatus,
)


# ---------------------------------------------------------------------------
# Bill of Materials — cost rollup
# ---------------------------------------------------------------------------

def rollup_bom_cost(bom_items: list[BOMItem]) -> dict:
    """Calculate total BOM cost and material breakdown.

    Returns:
        {
            "total_cost_usd": float,
            "line_items": int,
            "material_breakdown": {material_name: cost},
            "waste_cost_usd": float,
            "details": [BOMItem with line_cost populated],
        }
    """
    details = []
    material_breakdown: dict[str, float] = {}
    total_waste = 0.0

    for item in bom_items:
        effective_qty = item.quantity_per_unit * (1 + item.waste_factor_pct / 100)
        base_cost = item.quantity_per_unit * item.unit_cost_usd
        waste_cost = (item.quantity_per_unit * item.waste_factor_pct / 100) * item.unit_cost_usd
        line_cost = effective_qty * item.unit_cost_usd

        item.line_cost_usd = line_cost
        total_waste += waste_cost

        material_breakdown[item.material_name] = (
            material_breakdown.get(item.material_name, 0.0) + line_cost
        )
        details.append(item)

    total = sum(d.line_cost_usd for d in details)

    return {
        "total_cost_usd": round(total, 4),
        "line_items": len(details),
        "material_breakdown": {k: round(v, 4) for k, v in sorted(material_breakdown.items())},
        "waste_cost_usd": round(total_waste, 4),
        "details": details,
    }


def calculate_cell_bom(
    chemistry: str,
    cell_capacity_ah: float,
    material_prices: dict[str, float],
) -> list[BOMItem]:
    """Generate a representative BOM for a cell chemistry.

    Args:
        chemistry: e.g. "NMC-811", "LFP", "NCA"
        cell_capacity_ah: cell capacity in Ah
        material_prices: {material_name: price_per_kg}

    Returns:
        List of BOMItem with costs populated.
    """
    # Typical cathode active material content per kWh (kg)
    cathode_loading = {
        "NMC-111": {"nickel": 0.21, "manganese": 0.21, "cobalt": 0.21, "lithium_carbonate": 0.45},
        "NMC-811": {"nickel": 0.63, "manganese": 0.09, "cobalt": 0.09, "lithium_carbonate": 0.50},
        "NMC-622": {"nickel": 0.42, "manganese": 0.14, "cobalt": 0.14, "lithium_carbonate": 0.47},
        "NCA":     {"nickel": 0.80, "cobalt": 0.05, "aluminum": 0.05, "lithium_carbonate": 0.52},
        "LFP":     {"lithium_carbonate": 0.30, "iron_phosphate": 0.65},
        "LMO":     {"lithium_carbonate": 0.28, "manganese": 0.55},
    }

    # Common non-cathode materials per kWh (kg)
    common_per_kwh = {
        "graphite_anode": 0.50,
        "electrolyte": 0.25,
        "copper_foil": 0.18,
        "aluminum_foil": 0.12,
        "separator": 0.04,
        "binder_pvdf": 0.02,
        "conductive_additive": 0.01,
    }

    cell_energy_kwh = (cell_capacity_ah * 3.7) / 1000  # assume 3.7V nominal

    spec = cathode_loading.get(chemistry, cathode_loading["NMC-111"])
    bom_items = []

    # Cathode materials
    for mat, kg_per_kwh in spec.items():
        qty = kg_per_kwh * cell_energy_kwh
        price = material_prices.get(mat, 0.0)
        bom_items.append(BOMItem(
            parent_sku="CELL",
            material_name=mat,
            quantity_per_unit=round(qty, 4),
            unit=MaterialUnit.KG,
            unit_cost_usd=price,
            waste_factor_pct=3.0,  # typical cathode manufacturing waste
        ))

    # Common materials
    for mat, kg_per_kwh in common_per_kwh.items():
        qty = kg_per_kwh * cell_energy_kwh
        price = material_prices.get(mat, 0.0)
        bom_items.append(BOMItem(
            parent_sku="CELL",
            material_name=mat,
            quantity_per_unit=round(qty, 4),
            unit=MaterialUnit.KG,
            unit_cost_usd=price,
            waste_factor_pct=2.0,
        ))

    # Calculate line costs
    for item in bom_items:
        item.calculate_line_cost()

    return bom_items


def calculate_pack_bom(
    pack: BatteryPack,
    cell_cost_usd: float,
    material_prices: dict[str, float],
) -> list[BOMItem]:
    """Generate pack-level BOM (cells + pack-level components).

    Args:
        pack: BatteryPack instance
        cell_cost_usd: cost of a single cell
        material_prices: {material_name: price_per_kg}
    """
    bom_items = []

    # Cells
    bom_items.append(BOMItem(
        parent_sku=pack.sku,
        material_name=f"cell_{pack.cell_sku}",
        quantity_per_unit=float(pack.total_cells),
        unit=MaterialUnit.EACH,
        unit_cost_usd=cell_cost_usd,
        waste_factor_pct=0.5,  # cell rejection
    ))

    # Pack-level components (per kWh)
    pack_kwh = pack.nominal_capacity_kwh
    pack_components = {
        "pack_casing_aluminum": 2.5,   # kg per kWh
        "bms_module": 0.02,             # units per kWh (one BMS per ~50kWh pack)
        "thermal_coolant": 0.8,         # kg per kWh
        "wiring_harness": 0.3,          # kg per kWh
        "insulation": 0.1,              # kg per kWh
        "pack_structural_adhesive": 0.15,  # kg per kWh
    }

    for mat, qty_per_kwh in pack_components.items():
        qty = qty_per_kwh * pack_kwh
        if mat == "bms_module":
            qty = max(1.0, qty)
            unit = MaterialUnit.EACH
            price = material_prices.get(mat, 15.0)  # typical BMS cost
        else:
            unit = MaterialUnit.KG
            price = material_prices.get(mat, 0.0)

        bom_items.append(BOMItem(
            parent_sku=pack.sku,
            material_name=mat,
            quantity_per_unit=round(qty, 4),
            unit=unit,
            unit_cost_usd=price,
            waste_factor_pct=1.0,
        ))

    for item in bom_items:
        item.calculate_line_cost()

    return bom_items


# ---------------------------------------------------------------------------
# Inventory logic
# ---------------------------------------------------------------------------

def update_inventory_status(records: list[InventoryRecord]) -> list[dict]:
    """Recalculate all inventory statuses and return summary.

    Returns list of {"sku": ..., "status": ..., "available": ..., "action": ...}
    """
    results = []
    for r in records:
        avail = r.calculate_available()
        action = "none"
        if r.status == SupplyStatus.OUT_OF_STOCK:
            action = "urgent_reorder"
        elif r.status == SupplyStatus.LOW:
            action = "reorder"
        results.append({
            "sku": r.sku,
            "material": r.material_name,
            "status": r.status.value,
            "on_hand": r.quantity_on_hand,
            "reserved": r.quantity_reserved,
            "available": round(avail, 2),
            "action": action,
        })
    return results


def check_reorder_suggestions(records: list[InventoryRecord]) -> list[dict]:
    """Generate purchase order suggestions for low-stock items."""
    suggestions = []
    for r in records:
        avail = r.calculate_available()
        if avail <= r.reorder_point:
            suggestions.append({
                "sku": r.sku,
                "material": r.material_name,
                "current_available": round(avail, 2),
                "reorder_point": r.reorder_point,
                "suggested_qty": r.reorder_qty,
                "estimated_cost_usd": round(r.reorder_qty * r.unit_cost_usd, 2),
                "urgency": "critical" if avail <= 0 else "standard",
            })
    return sorted(suggestions, key=lambda x: x["urgency"] == "critical", reverse=True)


# ---------------------------------------------------------------------------
# Manufacturing yield
# ---------------------------------------------------------------------------

def calculate_batch_metrics(batches: list[ManufacturingBatch]) -> dict:
    """Aggregate manufacturing batch metrics."""
    if not batches:
        return {"total_produced": 0, "total_pass": 0, "avg_yield_pct": 0, "best_batch": None, "worst_batch": None}

    total_produced = sum(b.quantity_produced for b in batches)
    total_pass = sum(b.quantity_pass for b in batches)
    avg_yield = (total_pass / total_produced * 100) if total_produced > 0 else 0

    best = max(batches, key=lambda b: b.calculate_yield())
    worst = min(batches, key=lambda b: b.calculate_yield())

    return {
        "total_produced": total_produced,
        "total_pass": total_pass,
        "total_reject": total_produced - total_pass,
        "avg_yield_pct": round(avg_yield, 2),
        "best_batch_id": best.batch_id,
        "best_yield_pct": round(best.yield_pct, 2),
        "worst_batch_id": worst.batch_id,
        "worst_yield_pct": round(worst.yield_pct, 2),
    }


# ---------------------------------------------------------------------------
# Price analytics
# ---------------------------------------------------------------------------

def analyze_price_history(history: list[PriceHistory], material: str) -> dict:
    """Analyze price trends for a material.

    Args:
        history: list of PriceHistory (can include multiple materials)
        material: filter to this material name
    """
    filtered = [h for h in history if h.material_name == material]
    if len(filtered) < 2:
        return {"material": material, "data_points": len(filtered), "insufficient_data": True}

    prices = sorted(filtered, key=lambda h: h.as_of)
    latest = prices[-1]
    oldest = prices[0]

    price_points = [p.price_usd for p in prices]
    avg_price = sum(price_points) / len(price_points)
    max_price = max(price_points)
    min_price = min(price_points)

    pct_change = ((latest.price_usd - oldest.price_usd) / oldest.price_usd * 100) if oldest.price_usd > 0 else 0

    # Volatility: standard deviation as % of mean
    if avg_price > 0:
        variance = sum((p - avg_price) ** 2 for p in price_points) / len(price_points)
        std_dev = variance ** 0.5
        volatility_pct = (std_dev / avg_price) * 100
    else:
        volatility_pct = 0.0

    return {
        "material": material,
        "data_points": len(prices),
        "latest_price": latest.price_usd,
        "latest_date": str(latest.as_of),
        "oldest_price": oldest.price_usd,
        "oldest_date": str(oldest.as_of),
        "avg_price": round(avg_price, 4),
        "max_price": max_price,
        "min_price": min_price,
        "pct_change": round(pct_change, 2),
        "volatility_pct": round(volatility_pct, 2),
        "trend": "up" if pct_change > 5 else ("down" if pct_change < -5 else "flat"),
    }


def estimate_cell_cost_impact(
    current_prices: dict[str, float],
    scenario_prices: dict[str, float],
    bom_items: list[BOMItem],
) -> dict:
    """Estimate cell cost change under a price scenario.

    Args:
        current_prices: {material_name: current_price}
        scenario_prices: {material_name: scenario_price}
        bom_items: list of BOMItem

    Returns:
        {"current_cost": ..., "scenario_cost": ..., "delta_usd": ..., "delta_pct": ..., "affected_materials": [...]}
    """
    current_total = 0.0
    scenario_total = 0.0
    affected = []

    for item in bom_items:
        mat = item.material_name
        cur_price = current_prices.get(mat, item.unit_cost_usd)
        scen_price = scenario_prices.get(mat, cur_price)

        effective_qty = item.quantity_per_unit * (1 + item.waste_factor_pct / 100)
        cur_line = effective_qty * cur_price
        scen_line = effective_qty * scen_price

        current_total += cur_line
        scenario_total += scen_line

        if cur_price != scen_price:
            affected.append({
                "material": mat,
                "current_price": cur_price,
                "scenario_price": scen_price,
                "delta_per_kg": round(scen_price - cur_price, 4),
                "impact_usd": round(scen_line - cur_line, 4),
            })

    delta = scenario_total - current_total
    delta_pct = (delta / current_total * 100) if current_total > 0 else 0

    return {
        "current_cost_usd": round(current_total, 4),
        "scenario_cost_usd": round(scenario_total, 4),
        "delta_usd": round(delta, 4),
        "delta_pct": round(delta_pct, 2),
        "affected_materials": sorted(affected, key=lambda x: abs(x["impact_usd"]), reverse=True),
    }


# ---------------------------------------------------------------------------
# Pack energy density and efficiency
# ---------------------------------------------------------------------------

def calculate_pack_metrics(
    cell: BatteryCell,
    pack: BatteryPack,
) -> dict:
    """Calculate pack-level performance metrics from cell specs."""
    cell_energy_wh = cell.energy_wh
    total_cell_energy_wh = cell_energy_wh * pack.total_cells

    # Theoretical pack energy
    theoretical_pack_kwh = total_cell_energy_wh / 1000

    # Pack overhead (BMS, cooling, casing typically 15-25%)
    overhead_pct = 0.20
    effective_pack_kwh = theoretical_pack_kwh * (1 - overhead_pct)

    # Energy density
    cell_grav_wh_kg = (cell.energy_wh / cell.weight_kg) if cell.weight_kg > 0 else 0
    pack_grav_wh_kg = (effective_pack_kwh * 1000 / pack.pack_weight_kg) if pack.pack_weight_kg > 0 else 0

    # Pack-to-cell ratio
    density_ratio = (pack_grav_wh_kg / cell_grav_wh_kg) if cell_grav_wh_kg > 0 else 0

    return {
        "cell_energy_wh": cell_energy_wh,
        "total_cells": pack.total_cells,
        "theoretical_pack_kwh": round(theoretical_pack_kwh, 2),
        "overhead_pct": overhead_pct * 100,
        "effective_pack_kwh": round(effective_pack_kwh, 2),
        "cell_energy_density_wh_per_kg": round(cell_grav_wh_kg, 1),
        "pack_energy_density_wh_per_kg": round(pack_grav_wh_kg, 1),
        "density_ratio_pct": round(density_ratio * 100, 1),
        "pack_to_cell_cost_ratio": "N/A",  # requires cell and pack cost
    }
