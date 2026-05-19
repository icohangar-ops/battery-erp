# Battery ERP — Analytics Module
"""Reporting, KPI dashboards, and Fabric Lakehouse helpers."""

from __future__ import annotations

from datetime import date
from typing import Optional


def generate_inventory_report(records: list) -> dict:
    """Generate a full inventory status report."""
    from ..core.rules import update_inventory_status

    statuses = update_inventory_status(records)
    total_on_hand = sum(r.quantity_on_hand for r in records)
    total_reserved = sum(r.quantity_reserved for r in records)
    total_available = sum(s["available"] for s in statuses)
    total_value = sum(r.quantity_on_hand * r.unit_cost_usd for r in records)

    low_stock = [s for s in statuses if s["status"] == "low"]
    out_of_stock = [s for s in statuses if s["status"] == "out_of_stock"]

    return {
        "report_date": str(date.today()),
        "total_skus": len(records),
        "total_on_hand": round(total_on_hand, 2),
        "total_reserved": round(total_reserved, 2),
        "total_available": round(total_available, 2),
        "total_inventory_value_usd": round(total_value, 2),
        "low_stock_count": len(low_stock),
        "out_of_stock_count": len(out_of_stock),
        "low_stock_items": low_stock,
        "out_of_stock_items": out_of_stock,
        "health_score": _calculate_inventory_health(statuses),
    }


def generate_supply_chain_report(orders: list, suppliers: list) -> dict:
    """Generate supply chain health report."""
    from ..core.models import PurchaseOrder
    from ..supply_chain import analyze_po_pipeline, rank_suppliers

    po_analysis = analyze_po_pipeline(orders)
    supplier_rankings = rank_suppliers(suppliers)

    return {
        "report_date": str(date.today()),
        "purchase_orders": po_analysis,
        "supplier_count": len(suppliers),
        "top_suppliers": supplier_rankings[:5],
        "overdue_orders": po_analysis.get("overdue", []),
        "avg_lead_time_days": po_analysis.get("avg_lead_time_days", 0),
    }


def generate_manufacturing_report(batches: list) -> dict:
    """Generate manufacturing yield report."""
    from ..core.rules import calculate_batch_metrics

    metrics = calculate_batch_metrics(batches)
    return {
        "report_date": str(date.today()),
        **metrics,
    }


def generate_pricing_report(
    price_history: list,
    material_prices: dict,
    chemistries: Optional[list[str]] = None,
    cell_capacity_ah: float = 50.0,
) -> dict:
    """Generate cell cost estimates for multiple chemistries."""
    from ..pricing import calculate_cell_cost_summary
    from ..core.rules import analyze_price_history

    if chemistries is None:
        chemistries = ["NMC-111", "NMC-811", "NMC-622", "NCA", "LFP", "LMO"]

    # Cell cost comparisons
    cell_costs = {}
    for chem in chemistries:
        cell_costs[chem] = calculate_cell_cost_summary(chem, cell_capacity_ah, material_prices)

    # Price trends for key materials
    key_materials = ["lithium_carbonate", "nickel", "cobalt", "graphite_anode", "manganese"]
    price_trends = {}
    for mat in key_materials:
        trend = analyze_price_history(price_history, mat)
        if not trend.get("insufficient_data"):
            price_trends[mat] = trend

    # Cost ranking
    cost_ranking = sorted(
        [(chem, data["cost_per_kwh"]) for chem, data in cell_costs.items()],
        key=lambda x: x[1],
    )

    return {
        "report_date": str(date.today()),
        "cell_capacity_ah": cell_capacity_ah,
        "chemistry_comparison": {k: {
            "cost_per_kwh": v["cost_per_kwh"],
            "cathode_pct": v["cathode_pct"],
            "anode_pct": v["anode_pct"],
        } for k, v in cell_costs.items()},
        "cost_ranking_cheapest_to_most": cost_ranking,
        "price_trends": price_trends,
    }


def _calculate_inventory_health(statuses: list) -> str:
    """Calculate overall inventory health score."""
    if not statuses:
        return "unknown"
    total = len(statuses)
    healthy = sum(1 for s in statuses if s["status"] == "in_stock")
    pct = (healthy / total) * 100
    if pct >= 90:
        return "excellent"
    if pct >= 70:
        return "good"
    if pct >= 50:
        return "fair"
    return "poor"
