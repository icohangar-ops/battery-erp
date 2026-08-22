# Inventory integration: SMS text-line ↔ REST ↔ shared service ↔ MCP

This document describes the scaffold under `battery_erp.services`,
`battery_erp.api`, and `battery_erp.mcp`.

## Architecture

```
SMS provider (e.g. ClickSend)
   ↓
Text-line API (your app — inbound webhook)
   ↓
REST adapter  (python3 -m battery_erp.api)     MCP host (Cursor / Claude)
   ↓                                              ↓
              InventoryService  (shared)
                         ↓
              InMemoryInventoryStore  (demo; swap for Fabric later)
                         ↓
              Human bin confirmation
                         ↓
              SMS reply (your app)
```

**Do not** call MCP from a public browser. The text-line backend should call
REST (or the Python service layer) server-side. MCP is for AI agents and
operator assistants asking questions like “How many of part X are available?”

Run **REST and MCP in separate terminals**. MCP uses stdio and will look idle
until a host attaches.

## Shared service layer

| Module | Role |
|---|---|
| `battery_erp.services.inventory.InventoryService` | Lookups, bin-check tasks, authenticated confirmations |
| `battery_erp.services.store.InMemoryInventoryStore` | Thread-safe demo store + JSONL audit |
| `battery_erp.services.fixtures` | Seed SKUs + SMS-friendly aliases |

Exposed fields (first cut): `sku`, `quantity_on_hand`, `quantity_reserved`,
`quantity_available`, `reorder_point`, `reorder_qty`, `status`, warehouse, unit, cost.

## Environment

| Variable | Purpose |
|---|---|
| `BATTERY_ERP_CONFIRM_TOKEN` | Required for `record_bin_confirmation` / `POST .../bin-confirm` |
| `BATTERY_ERP_AUDIT_LOG` | Optional path to append-only JSONL audit file |
| `BATTERY_ERP_API_HOST` | API bind host (default `127.0.0.1`) |
| `BATTERY_ERP_API_PORT` | API bind port (default `8088`) |

## REST adapter (text-line)

```bash
cd /path/to/battery-erp
python3 -m pip install -e '.[api]'
export BATTERY_ERP_CONFIRM_TOKEN=dev-secret
export BATTERY_ERP_AUDIT_LOG=/tmp/battery-erp-audit.jsonl
PYTHONPATH=src python3 -m battery_erp.api
# or: python3 -m uvicorn battery_erp.api.app:app --host 127.0.0.1 --port 8088
```

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/inventory` | All seeded SKUs |
| GET | `/inventory/lookup/{part}` | Compact availability |
| GET | `/inventory/status/{part}` | Status + reorder suggestion |
| GET | `/inventory/record/{sku}` | Full record |
| POST | `/inventory/bin-check/{part}` | Create human verification task |
| POST | `/inventory/bin-confirm/{part}` | Header `X-Battery-Erp-Token` required |

### Example SMS → REST flow

1. Inbound webhook receives: `CHECK LI-CARB-001`
2. App normalizes part number and `GET /inventory/lookup/LI-CARB-001`
3. App creates bin check: `POST /inventory/bin-check/LI-CARB-001`
4. Warehouse operator confirms physical count
5. App posts confirmation with token header
6. App sends SMS reply with updated available qty

```bash
curl -s http://127.0.0.1:8088/inventory/lookup/lithium | jq .
curl -s -X POST http://127.0.0.1:8088/inventory/bin-check/lithium \
  -H 'Content-Type: application/json' -d '{"notes":"sms"}' | jq .
curl -s -X POST http://127.0.0.1:8088/inventory/bin-confirm/LI-CARB-001 \
  -H 'Content-Type: application/json' \
  -H 'X-Battery-Erp-Token: dev-secret' \
  -d '{"actual_quantity":12000,"request_id":"<id>","actor":"wh-a"}' | jq .
```

## MCP server (agents / operators)

Requires `mcp` SDK **2.x** (`MCPServer`; `FastMCP` was removed from the package).

```bash
# Separate terminal from the REST API
cd /path/to/battery-erp
python3 -m pip install -e '.[mcp]'
export BATTERY_ERP_CONFIRM_TOKEN=dev-secret
PYTHONPATH=src python3 -m battery_erp.mcp
```

Tools:

- `lookup_inventory(part_number)`
- `get_inventory_status(part_number)`
- `get_inventory_record(sku)`
- `list_inventory()`
- `create_bin_check_request(part_number, notes?)`
- `record_bin_confirmation(part_number, actual_quantity, auth_token, ...)`

### Cursor / Claude Desktop

```json
{
  "mcpServers": {
    "battery-erp": {
      "command": "python3",
      "args": ["-m", "battery_erp.mcp"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/battery-erp/src",
        "BATTERY_ERP_CONFIRM_TOKEN": "replace-me",
        "BATTERY_ERP_AUDIT_LOG": "/tmp/battery-erp-audit.jsonl"
      }
    }
  }
}
```

## Why both REST and MCP?

- **REST** — deterministic SMS / text-line production path
- **MCP** — conversational inventory Q&A for agents and ops
- **One service layer** — both call `InventoryService`; swap the store later for Fabric/Ghost without rewriting tools or routes

## Next steps (not in this scaffold)

- Persist inventory via Fabric Delta `inventory` table instead of in-memory seed
- Wire text-line webhook project (ClickSend / Twilio) to these REST routes
- Add role-based auth beyond a shared confirm token
- Rate-limit public SMS entry points in the text-line app (not here)
