"""Battery ERP MCP server — inventory tools for agents/operators.

Compatible with the official ``mcp`` Python SDK 2.x (``MCPServer``).

Run (leave REST running in another terminal):
  PYTHONPATH=src BATTERY_ERP_CONFIRM_TOKEN=dev-secret \\
    python3 -m battery_erp.mcp

Cursor / Claude Desktop config example:
  {
    "mcpServers": {
      "battery-erp": {
        "command": "python3",
        "args": ["-m", "battery_erp.mcp"],
        "env": {
          "PYTHONPATH": "/path/to/battery-erp/src",
          "BATTERY_ERP_CONFIRM_TOKEN": "replace-me",
          "BATTERY_ERP_AUDIT_LOG": "/tmp/battery-erp-audit.jsonl"
        }
      }
    }
  }

Do not call this MCP from a public browser. Text-line apps should hit the
REST adapter (`python3 -m battery_erp.api`) server-side.
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
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # pragma: no cover — older mcp 1.x
    try:
        from mcp.server.fastmcp import FastMCP as _Server
    except ImportError as exc:
        raise SystemExit(
            "Install MCP extras: python3 -m pip install 'mcp>=2.0'  "
            "(or: python3 -m pip install -e '.[mcp]')"
        ) from exc


def build_service() -> InventoryService:
    return InventoryService()


def create_mcp(service: Optional[InventoryService] = None) -> Any:
    """Build an MCP server bound to an InventoryService instance."""
    svc = service or build_service()
    mcp = _Server(
        name="battery-erp",
        instructions=(
            "Battery ERP inventory tools for Li-ion materials, cells, and packs. "
            "Use lookup/status/record for availability questions. "
            "create_bin_check_request starts a human verification task. "
            "record_bin_confirmation requires auth_token and writes an audit event."
        ),
    )

    @mcp.tool()
    def lookup_inventory(part_number: str) -> dict:
        """Look up available quantity and stock status for a part number or SKU."""
        try:
            return svc.lookup_inventory(part_number)
        except InventoryNotFoundError as e:
            return {"error": "not_found", "message": str(e)}

    @mcp.tool()
    def get_inventory_status(part_number: str) -> dict:
        """Get inventory status plus reorder suggestion when below reorder point."""
        try:
            return svc.get_inventory_status(part_number)
        except InventoryNotFoundError as e:
            return {"error": "not_found", "message": str(e)}

    @mcp.tool()
    def get_inventory_record(sku: str) -> dict:
        """Return the full inventory record for a SKU (on-hand, reserved, reorder, cost)."""
        try:
            return svc.get_inventory_record(sku)
        except InventoryNotFoundError as e:
            return {"error": "not_found", "message": str(e)}

    @mcp.tool()
    def list_inventory() -> list:
        """List status for all seeded inventory SKUs (demo store)."""
        return svc.list_inventory()

    @mcp.tool()
    def create_bin_check_request(part_number: str, notes: str = "") -> dict:
        """Create a human bin-count verification task for SMS / warehouse workflows."""
        try:
            return svc.create_bin_check_request(part_number, notes=notes, actor="mcp")
        except InventoryNotFoundError as e:
            return {"error": "not_found", "message": str(e)}

    @mcp.tool()
    def record_bin_confirmation(
        part_number: str,
        actual_quantity: float,
        auth_token: str,
        request_id: str = "",
        notes: str = "",
        actor: str = "mcp-operator",
    ) -> dict:
        """Record a human-confirmed on-hand quantity. Requires auth_token matching BATTERY_ERP_CONFIRM_TOKEN."""
        try:
            return svc.record_bin_confirmation(
                part_number,
                actual_quantity,
                auth_token=auth_token,
                actor=actor,
                request_id=request_id or None,
                notes=notes,
            )
        except InventoryNotFoundError as e:
            return {"error": "not_found", "message": str(e)}
        except InventoryAuthError as e:
            return {"error": "unauthorized", "message": str(e)}
        except ValueError as e:
            return {"error": "invalid", "message": str(e)}

    return mcp


def main() -> None:
    if not os.environ.get("BATTERY_ERP_CONFIRM_TOKEN"):
        # Read tools still work; mutating confirmation will refuse until set.
        pass
    mcp = create_mcp()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
