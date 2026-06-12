# Airbyte Agents Integration — Battery ERP

This document describes how [Airbyte Agents](https://docs.airbyte.com/ai-agents) can replace the hardcoded price data and direct API calls in your battery-recycling ERP with managed connectors and scheduled syncs.

---

## Overview

Battery ERP currently uses hardcoded `DEFAULT_MATERIAL_PRICES` with live commodity price fallback via AlphaVantage and FRED. Airbyte Agents provides managed connectors with incremental syncs, schema normalization, and reliable scheduling.

**Integration options:**
- **[MCP](https://docs.airbyte.com/ai-agents/interfaces/mcp)** — Remote MCP server. Best for ad-hoc queries.
- **[SDK](https://docs.airbyte.com/ai-agents/interfaces/sdk)** — Python library for ERP pipeline integration.
- **[CLI/API](https://docs.airbyte.com/ai-agents/interfaces/sdk)** — Shell/HTTP for automation.

---

## Integration Points

### 1. Replace Commodity Price Data

| Current Source | File | Data | Airbyte Alternative |
|---------------|------|------|-------------------|
| `DEFAULT_MATERIAL_PRICES` (hardcoded) | `src/battery_erp/pricing/__init__.py` | 20+ battery material prices | Airbyte AlphaVantage / Twelve Data source |
| `AlphaVantage COMMODITY_DAILY` | `src/battery_erp/pricing/__init__.py` | Ni, Co, Al, Cu spot prices | Airbyte AlphaVantage source |
| `FRED DGS10, PPIACO` | `src/battery_erp/pricing/__init__.py` | Macro context (10Y Treasury, PPI) | Airbyte FRED source |

### 2. Populate Delta Lake Tables via Airbyte

The existing 11 Delta tables (defined in `notebooks/fabric_setup_lakehouse.py`) can be populated by Airbyte instead of manual notebook runs:

```python
# Example: Sync commodity prices into the price_history Delta table
from airbyte_agent_sdk import connect

async def sync_material_prices():
    """Populate price_history Delta table via Airbyte."""
    av = connect("alpha-vantage")
    try:
        # Fetch Ni, Co, Al, Cu, Li prices
        result = await av.execute("commodities", "list", params={
            "function": "MONTHLY",
            "symbols": "NICKEL,COBALT,ALUMINUM,COPPER,LITHIUM",
        })
        # Write to Delta table (via Spark or Airbyte destination)
        for item in result.data:
            print(f"{item['date']}: {item['symbol']} = {item['value']}")
    finally:
        await av.close()
```

### 3. Supplier and Inventory Sync

Airbyte can sync supplier master data and purchase orders from external systems into the existing Delta table schemas:

| Data | Source | Fabric Delta Table | Sync |
|------|--------|-------------------|------|
| Supplier profiles | ERP / Google Sheets | suppliers | Weekly batch |
| Purchase orders | Procurement system | purchase_orders | Daily |
| Material costs | Commodity APIs | price_history | Daily/hourly |
| Inventory levels | WMS / IoT platform | inventory | Real-time streaming |

### 4. MCP for ERP Queries

Add the Airbyte MCP server:

```json
{
  "mcpServers": {
    "airbyte": {
      "url": "https://mcp.airbyte.ai/mcp"
    }
  }
}
```

> "Connect to my battery material pricing data via Airbyte MCP. Show me the current Ni and Co spot prices, the 90-day trailing average, and the impact on BOM cost for NMC811 cells."

---

## Getting Started

1. **Sign up** at [app.airbyte.ai](https://app.airbyte.ai).
2. **Install the SDK**:
   ```bash
   uv add airbyte-agent-sdk
   ```
3. **Add to `.env.example`**:
   ```
   AIRBYTE_CLIENT_ID=your_client_id
   AIRBYTE_CLIENT_SECRET=***   ```
4. **Create Airbyte syncs** for material pricing, supplier data, and inventory, feeding directly into the Fabric Lakehouse Delta tables.

---

## Connector Catalog

| Category | Connectors | Battery ERP Use |
|----------|-----------|----------------|
| **Commodity Prices** | AlphaVantage, Twelve Data, FRED | Ni, Co, Al, Cu, Li pricing |
| **ERP** | QuickBooks, Xero, NetSuite | General ledger, POs, AP/AR |
| **Supplier Data** | Google Sheets, Airtable, databases | Supplier master data |
| **Data Warehouse** | Microsoft Fabric (Delta Lake), Snowflake, S3 | Storage and analytics |

Full catalog: [docs.airbyte.com/ai-agents/connectors](https://docs.airbyte.com/ai-agents/connectors)
