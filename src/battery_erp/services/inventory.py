"""Inventory service — single source of truth for MCP tools and REST routes."""

from __future__ import annotations

import os
from typing import Any, Optional

from battery_erp.core.rules import check_reorder_suggestions, update_inventory_status

from .store import InMemoryInventoryStore


class InventoryAuthError(PermissionError):
    """Raised when a mutating confirmation lacks a valid token."""


class InventoryNotFoundError(KeyError):
    """Raised when a part/SKU cannot be resolved."""


class InventoryService:
    """Safe inventory lookups + authenticated bin confirmation with audit."""

    def __init__(
        self,
        store: Optional[InMemoryInventoryStore] = None,
        confirm_token: Optional[str] = None,
    ) -> None:
        self.store = store or InMemoryInventoryStore(
            audit_path=os.environ.get("BATTERY_ERP_AUDIT_LOG"),
        )
        self._confirm_token = confirm_token if confirm_token is not None else os.environ.get(
            "BATTERY_ERP_CONFIRM_TOKEN", ""
        )

    def _require_record(self, part_or_sku: str):
        sku = self.store.normalize_part(part_or_sku)
        rec = self.store.get(sku)
        if rec is None:
            raise InventoryNotFoundError(f"No inventory for part/sku: {part_or_sku}")
        return rec

    def _record_dict(self, rec) -> dict[str, Any]:
        rec.calculate_available()
        return {
            "sku": rec.sku,
            "material_name": rec.material_name,
            "warehouse": rec.warehouse,
            "quantity_on_hand": rec.quantity_on_hand,
            "quantity_reserved": rec.quantity_reserved,
            "quantity_available": rec.quantity_available,
            "unit": rec.unit.value if hasattr(rec.unit, "value") else str(rec.unit),
            "reorder_point": rec.reorder_point,
            "reorder_qty": rec.reorder_qty,
            "unit_cost_usd": rec.unit_cost_usd,
            "total_value_usd": round(rec.total_value_usd, 2),
            "status": rec.status.value if hasattr(rec.status, "value") else str(rec.status),
            "last_replenished": rec.last_replenished.isoformat() if rec.last_replenished else None,
        }

    # --- read tools ---

    def lookup_inventory(self, part_number: str) -> dict[str, Any]:
        """Resolve part number and return a compact availability summary."""
        rec = self._require_record(part_number)
        status_rows = update_inventory_status([rec])
        row = status_rows[0]
        return {
            "part_number": part_number,
            "sku": row["sku"],
            "material": row["material"],
            "status": row["status"],
            "available": row["available"],
            "on_hand": row["on_hand"],
            "reserved": row["reserved"],
            "action": row["action"],
            "warehouse": rec.warehouse,
            "unit": rec.unit.value if hasattr(rec.unit, "value") else str(rec.unit),
        }

    def get_inventory_status(self, part_number: str) -> dict[str, Any]:
        """Status + reorder suggestion if applicable."""
        summary = self.lookup_inventory(part_number)
        rec = self._require_record(part_number)
        suggestions = check_reorder_suggestions([rec])
        summary["reorder"] = suggestions[0] if suggestions else None
        return summary

    def get_inventory_record(self, sku: str) -> dict[str, Any]:
        """Full inventory record for a SKU / part."""
        rec = self._require_record(sku)
        return self._record_dict(rec)

    def list_inventory(self) -> list[dict[str, Any]]:
        return update_inventory_status(self.store.list_all())

    # --- write / workflow tools ---

    def create_bin_check_request(
        self,
        part_number: str,
        notes: str = "",
        actor: str = "system",
    ) -> dict[str, Any]:
        """Create a human verification task for a physical bin count."""
        rec = self._require_record(part_number)
        req = self.store.create_bin_check(
            sku=rec.sku,
            part_number=part_number,
            notes=notes,
        )
        self.store.append_audit(
            action="bin_check_created",
            actor=actor,
            sku=rec.sku,
            detail={"request_id": req.request_id, "part_number": part_number, "notes": notes},
        )
        return req.to_dict()

    def record_bin_confirmation(
        self,
        part_number: str,
        actual_quantity: float,
        *,
        auth_token: str = "",
        actor: str = "operator",
        request_id: Optional[str] = None,
        notes: str = "",
    ) -> dict[str, Any]:
        """Apply a human-confirmed on-hand quantity. Requires BATTERY_ERP_CONFIRM_TOKEN."""
        expected = self._confirm_token
        if not expected:
            raise InventoryAuthError(
                "Mutating confirmations disabled: set BATTERY_ERP_CONFIRM_TOKEN"
            )
        if not auth_token or auth_token != expected:
            raise InventoryAuthError("Invalid or missing auth_token for bin confirmation")
        if actual_quantity < 0:
            raise ValueError("actual_quantity must be >= 0")

        rec = self._require_record(part_number)
        previous = rec.quantity_on_hand
        rec.quantity_on_hand = float(actual_quantity)
        rec.calculate_available()
        self.store.upsert(rec)

        if request_id:
            try:
                self.store.mark_bin_check_confirmed(request_id)
            except KeyError:
                pass

        audit = self.store.append_audit(
            action="bin_confirmation",
            actor=actor,
            sku=rec.sku,
            detail={
                "part_number": part_number,
                "previous_on_hand": previous,
                "actual_quantity": actual_quantity,
                "request_id": request_id,
                "notes": notes,
            },
        )
        return {
            "ok": True,
            "sku": rec.sku,
            "previous_on_hand": previous,
            "quantity_on_hand": rec.quantity_on_hand,
            "quantity_available": rec.quantity_available,
            "status": rec.status.value,
            "audit_event_id": audit.event_id,
        }
