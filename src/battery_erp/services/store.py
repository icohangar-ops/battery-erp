"""In-memory inventory store with append-only audit log.

Replace with Fabric/Ghost adapters later without changing InventoryService.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from battery_erp.core.models import InventoryRecord

from .fixtures import PART_ALIASES, seed_inventory


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class BinCheckRequest:
    request_id: str
    sku: str
    part_number: str
    warehouse: str
    system_quantity_on_hand: float
    status: str = "pending"  # pending | confirmed | cancelled
    created_at: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEvent:
    event_id: str
    action: str
    actor: str
    sku: str
    detail: dict[str, Any] = field(default_factory=dict)
    at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InMemoryInventoryStore:
    """Thread-safe demo store. Not durable across process restarts unless audit_path set."""

    def __init__(
        self,
        records: Optional[list[InventoryRecord]] = None,
        aliases: Optional[dict[str, str]] = None,
        audit_path: Optional[str | Path] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, InventoryRecord] = {}
        self._aliases = {k.lower(): v.upper() for k, v in (aliases or PART_ALIASES).items()}
        self._bin_checks: dict[str, BinCheckRequest] = {}
        self._audit: list[AuditEvent] = []
        self._audit_path = Path(audit_path) if audit_path else None
        for r in records if records is not None else seed_inventory():
            r.calculate_available()
            self._records[r.sku.upper()] = r

    def normalize_part(self, part_number: str) -> str:
        """Resolve part_number / SKU / alias to canonical SKU (uppercased)."""
        raw = (part_number or "").strip()
        if not raw:
            raise ValueError("part_number is required")
        key = raw.lower()
        if key in self._aliases:
            return self._aliases[key]
        # material_name match
        with self._lock:
            for sku, rec in self._records.items():
                if rec.material_name.lower() == key or sku.lower() == key:
                    return sku
                if rec.sku.lower() == key:
                    return sku
        return raw.upper()

    def get(self, sku: str) -> Optional[InventoryRecord]:
        with self._lock:
            return self._records.get(sku.upper())

    def list_all(self) -> list[InventoryRecord]:
        with self._lock:
            return list(self._records.values())

    def upsert(self, record: InventoryRecord) -> InventoryRecord:
        with self._lock:
            record.calculate_available()
            self._records[record.sku.upper()] = record
            return record

    def create_bin_check(
        self,
        sku: str,
        part_number: str,
        notes: str = "",
    ) -> BinCheckRequest:
        with self._lock:
            rec = self._records.get(sku.upper())
            if rec is None:
                raise KeyError(f"unknown sku: {sku}")
            req = BinCheckRequest(
                request_id=str(uuid.uuid4())[:8],
                sku=rec.sku,
                part_number=part_number,
                warehouse=rec.warehouse,
                system_quantity_on_hand=rec.quantity_on_hand,
                created_at=_utcnow().isoformat(),
                notes=notes,
            )
            self._bin_checks[req.request_id] = req
            return req

    def get_bin_check(self, request_id: str) -> Optional[BinCheckRequest]:
        with self._lock:
            return self._bin_checks.get(request_id)

    def mark_bin_check_confirmed(self, request_id: str) -> BinCheckRequest:
        with self._lock:
            req = self._bin_checks.get(request_id)
            if req is None:
                raise KeyError(f"unknown bin check request: {request_id}")
            req.status = "confirmed"
            return req

    def append_audit(
        self,
        action: str,
        actor: str,
        sku: str,
        detail: Optional[dict[str, Any]] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid.uuid4())[:8],
            action=action,
            actor=actor,
            sku=sku,
            detail=detail or {},
            at=_utcnow().isoformat(),
        )
        with self._lock:
            self._audit.append(event)
            if self._audit_path is not None:
                self._audit_path.parent.mkdir(parents=True, exist_ok=True)
                with self._audit_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event.to_dict()) + "\n")
        return event

    def recent_audit(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._audit[-limit:]]
