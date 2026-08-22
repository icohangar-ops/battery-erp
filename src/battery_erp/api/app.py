"""Thin REST adapter sharing InventoryService with the MCP server.

Intended for SMS / text-line backends (Twilio webhook → this API → SMS reply).
Do not expose mutating routes publicly without auth.

Run:
  PYTHONPATH=src BATTERY_ERP_CONFIRM_TOKEN=dev-secret \\
    uvicorn battery_erp.api.app:app --host 127.0.0.1 --port 8088

Or:
  PYTHONPATH=src python -m battery_erp.api
"""

from __future__ import annotations

import os
from typing import Any, Optional

from battery_erp.services.inventory import (
    InventoryAuthError,
    InventoryNotFoundError,
    InventoryService,
)

try:
    from fastapi import Body, FastAPI, Header, HTTPException
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Install API extras: pip install 'fastapi>=0.115' 'uvicorn>=0.30'  (or pip install -e '.[api]')"
    ) from exc


class BinConfirmBody(BaseModel):
    actual_quantity: float = Field(..., ge=0)
    request_id: Optional[str] = None
    notes: str = ""
    actor: str = "api-operator"


class BinCheckBody(BaseModel):
    notes: str = ""
    actor: str = "api"


def build_app(service: Optional[InventoryService] = None) -> FastAPI:
    svc = service or InventoryService()
    app = FastAPI(
        title="Battery ERP Inventory API",
        version="0.1.0",
        description=(
            "Server-side adapter for text-line / SMS workflows. "
            "Same InventoryService as the MCP tools."
        ),
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "battery-erp-inventory"}

    @app.get("/inventory")
    def list_inventory() -> list[dict[str, Any]]:
        return svc.list_inventory()

    @app.get("/inventory/lookup/{part_number}")
    def lookup(part_number: str) -> dict[str, Any]:
        try:
            return svc.lookup_inventory(part_number)
        except InventoryNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.get("/inventory/status/{part_number}")
    def status(part_number: str) -> dict[str, Any]:
        try:
            return svc.get_inventory_status(part_number)
        except InventoryNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.get("/inventory/record/{sku}")
    def record(sku: str) -> dict[str, Any]:
        try:
            return svc.get_inventory_record(sku)
        except InventoryNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.post("/inventory/bin-check/{part_number}")
    def bin_check(
        part_number: str,
        payload: BinCheckBody = Body(default_factory=BinCheckBody),
    ) -> dict[str, Any]:
        try:
            return svc.create_bin_check_request(
                part_number, notes=payload.notes, actor=payload.actor
            )
        except InventoryNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.post("/inventory/bin-confirm/{part_number}")
    def bin_confirm(
        part_number: str,
        payload: BinConfirmBody,
        x_battery_erp_token: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        token = x_battery_erp_token or ""
        try:
            return svc.record_bin_confirmation(
                part_number,
                payload.actual_quantity,
                auth_token=token,
                actor=payload.actor,
                request_id=payload.request_id,
                notes=payload.notes,
            )
        except InventoryNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except InventoryAuthError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    return app


app = build_app()


def main() -> None:
    import uvicorn

    host = os.environ.get("BATTERY_ERP_API_HOST", "127.0.0.1")
    port = int(os.environ.get("BATTERY_ERP_API_PORT", "8088"))
    uvicorn.run("battery_erp.api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
