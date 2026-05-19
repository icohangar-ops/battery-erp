# Battery ERP — Supply Chain Module
"""Supply chain tracking: PO management, supplier scoring, lead time analysis."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from ..core.models import (
    MaterialUnit,
    OrderStatus,
    PurchaseOrder,
    Supplier,
    SupplyStatus,
)


def score_supplier(supplier: Supplier) -> dict:
    """Calculate composite supplier score (0-100).

    Weights:
    - Quality rating: 35%
    - On-time delivery: 35%
    - Lead time (lower is better): 20%
    - Price competitiveness: 10% (assumes price is already factored into selection)
    """
    quality_score = min(supplier.quality_rating, 100)
    otd_score = min(supplier.on_time_delivery_pct, 100)

    # Lead time score: <14 days = 100, 14-30 = 80, 30-60 = 60, >60 = 40
    if supplier.lead_time_days <= 14:
        lead_score = 100
    elif supplier.lead_time_days <= 30:
        lead_score = 80
    elif supplier.lead_time_days <= 60:
        lead_score = 60
    else:
        lead_score = 40

    # Certifications bonus
    cert_bonus = min(len(supplier.certifications) * 3, 10)

    composite = (
        quality_score * 0.35 +
        otd_score * 0.35 +
        lead_score * 0.20 +
        cert_bonus
    )

    return {
        "supplier_id": supplier.supplier_id,
        "name": supplier.name,
        "composite_score": round(composite, 1),
        "quality_score": quality_score,
        "otd_score": otd_score,
        "lead_time_score": lead_score,
        "certifications": supplier.certifications,
        "grade": (
            "A" if composite >= 80 else
            "B" if composite >= 65 else
            "C" if composite >= 50 else "D"
        ),
    }


def rank_suppliers(
    suppliers: list[Supplier],
    material: Optional[str] = None,
) -> list[dict]:
    """Rank suppliers by composite score, optionally filtering by material.

    Returns list sorted best-to-worst.
    """
    if material:
        filtered = [s for s in suppliers if material in s.materials_supplied]
    else:
        filtered = suppliers

    scored = [score_supplier(s) for s in filtered]
    return sorted(scored, key=lambda x: x["composite_score"], reverse=True)


def create_purchase_order(
    supplier: Supplier,
    material_name: str,
    quantity: float,
    unit: MaterialUnit,
    warehouse: str = "main",
) -> PurchaseOrder:
    """Create a purchase order from supplier data."""
    po = PurchaseOrder(
        supplier_id=supplier.supplier_id,
        supplier_name=supplier.name,
        material_name=material_name,
        quantity=quantity,
        unit=unit,
        unit_price_usd=supplier.unit_price_usd,
        status=OrderStatus.PENDING,
        order_date=date.today(),
        expected_delivery=date.today() + timedelta(days=supplier.lead_time_days),
        warehouse=warehouse,
    )
    po.calculate_total()
    return po


def analyze_po_pipeline(orders: list[PurchaseOrder]) -> dict:
    """Analyze the purchase order pipeline.

    Returns summary of open, shipped, delivered orders with value breakdown.
    """
    summary = {
        "total_orders": len(orders),
        "total_value_usd": 0.0,
        "by_status": {},
        "overdue": [],
        "avg_lead_time_days": 0,
    }

    lead_times = []
    for o in orders:
        summary["total_value_usd"] += o.total_usd

        status = o.status.value
        if status not in summary["by_status"]:
            summary["by_status"][status] = {"count": 0, "value_usd": 0.0}
        summary["by_status"][status]["count"] += 1
        summary["by_status"][status]["value_usd"] += o.total_usd

        # Check overdue
        if o.status in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
            if o.expected_delivery and date.today() > o.expected_delivery:
                summary["overdue"].append({
                    "po_number": o.po_number,
                    "supplier": o.supplier_name,
                    "material": o.material_name,
                    "expected": str(o.expected_delivery),
                    "days_overdue": (date.today() - o.expected_delivery).days,
                })

        # Lead time tracking
        if o.actual_delivery and o.order_date:
            lead_times.append((o.actual_delivery - o.order_date).days)
        elif o.expected_delivery and o.order_date:
            lead_times.append((o.expected_delivery - o.order_date).days)

    if lead_times:
        summary["avg_lead_time_days"] = round(sum(lead_times) / len(lead_times), 1)

    summary["total_value_usd"] = round(summary["total_value_usd"], 2)
    return summary


def suggest_dual_sourcing(
    current_supplier: Supplier,
    suppliers: list[Supplier],
    material: str,
    split_pct: float = 70.0,
) -> dict:
    """Recommend a dual-sourcing strategy for supply chain resilience.

    Args:
        current_supplier: primary supplier
        suppliers: all available suppliers
        material: material to source
        split_pct: percentage to keep with primary (rest goes to secondary)

    Returns:
        Strategy recommendation with supplier assignments.
    """
    candidates = [s for s in suppliers
                  if s.supplier_id != current_supplier.supplier_id
                  and material in s.materials_supplied]

    if not candidates:
        return {"recommendation": "no_secondary_available", "primary": current_supplier.name}

    ranked = rank_suppliers(candidates, material)
    secondary = ranked[0] if ranked else None

    if secondary is None:
        return {"recommendation": "no_secondary_available", "primary": current_supplier.name}

    return {
        "recommendation": "dual_source",
        "primary_supplier": current_supplier.name,
        "primary_pct": split_pct,
        "secondary_supplier": secondary["name"],
        "secondary_pct": round(100 - split_pct, 1),
        "secondary_score": secondary["composite_score"],
        "risk_reduction": "Single-supplier dependency eliminated for " + material,
    }
