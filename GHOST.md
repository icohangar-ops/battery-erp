# Ghost Integration — Battery ERP

This document describes how [Ghost](https://ghost.build) — the Postgres database built for AI agents — can provide transactional persistence for pricing engine data, supplier scoring, and inventory snapshots alongside your Fabric Lakehouse analytics.

---

## Overview

Ghost provides unlimited Postgres databases you can create, fork, and discard freely. For Battery ERP:

- **Transactional state** — pricing queries, BOM cost snapshots, supplier scores
- **Fork for scenario planning** — test BOM cost impact of different material price assumptions
- **MCP tools** — the pricing engine and analytics modules query live data
- **Complement to Delta Lake** — Ghost handles OLTP, Delta handles OLAP

**Key Ghost commands:**
```bash
brew install timescale/tap/ghost       # Install
ghost init                               # Configure
ghost create battery-erp-prod            # Main ERP database
ghost fork battery-erp-prod battery-erp-nmc811-scenario  # Fork
ghost sql battery-erp-prod "SELECT * FROM material_prices"  # Query
```

---

## Integration Points

### 1. Transactional Backend for Pricing Engine

Replace the in-memory `DEFAULT_MATERIAL_PRICES` and direct API calls with Ghost-backed persistence:

```bash
ghost create battery-erp-prod
ghost sql battery-erp-prod < src/ghost_schema.sql
```

```sql
-- src/ghost_schema.sql
CREATE TABLE material_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    material TEXT NOT NULL,
    price_per_tonne NUMERIC,
    currency TEXT DEFAULT 'USD',
    source TEXT,                     -- 'alpha_vantage', 'manual', 'airbyte'
    fetched_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE bom_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cell_chemistry TEXT NOT NULL,    -- 'NMC811', 'LFP', 'NCA'
    snapshot_date DATE NOT NULL,
    bom_cost NUMERIC,
    components JSONB,                -- breakdown of material costs
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE supplier_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_name TEXT NOT NULL,
    score_date DATE NOT NULL,
    cost_score NUMERIC,
    quality_score NUMERIC,
    delivery_score NUMERIC,
    esg_score NUMERIC,
    composite_score NUMERIC,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 2. Fork for BOM Scenario Analysis

```bash
# Live pricing
ghost sql battery-erp-prod "SELECT * FROM material_prices WHERE material IN ('Nickel', 'Cobalt', 'Lithium')"

# Fork to test price shock scenario
ghost fork battery-erp-prod battery-erp-ni-price-spike

# Update the fork with shock prices
ghost sql battery-erp-ni-price-spike "
  UPDATE material_prices SET price_per_tonne = price_per_tonne * 1.5
  WHERE material = 'Nickel';
"

# Run BOM cost calculator against both
python -m battery_erp.pricing --ghost-db battery-erp-prod
python -m battery_erp.pricing --ghost-db battery-erp-ni-price-spike

# Compare BOM costs
ghost sql battery-erp-prod "SELECT cell_chemistry, bom_cost FROM bom_snapshots ORDER BY snapshot_date DESC LIMIT 1"
ghost sql battery-erp-ni-price-spike "SELECT cell_chemistry, bom_cost FROM bom_snapshots ORDER BY snapshot_date DESC LIMIT 1"

# Clean up
ghost delete battery-erp-ni-price-spike
```

### 3. MCP Integration

Install Ghost MCP:
```bash
ghost mcp install claude-code
```

**Example agent prompts:**
> Connect to the Ghost database `battery-erp-prod`. What's the current BOM cost for NMC811? How has it changed in the last 30 days?

> Fork the battery ERP database and run a scenario where Lithium prices double. What's the impact on LFP cell costs?

### 4. Complement to Fabric / Delta Tables

The existing Fabric Delta tables (`material_prices`, `price_history`, `suppliers`, etc.) are great for analytics. Ghost handles the operational side:

| Layer | Ghost (OLTP) | Fabric Delta (OLAP) |
|-------|-------------|-------------------|
| **Data** | Current material prices, BOM snapshots, supplier scores | Historical price trends, cost analytics |
| **Access** | Real-time queries, MCP tools, pricing engine | Athena dashboards, Power BI |
| **Lifecycle** | Session/transactional — fork, test, delete | Long-term — append-only, partitioned |
| **Example** | `SELECT current_price FROM material_prices WHERE material = 'Nickel'` | `SELECT AVG(price) FROM price_history WHERE material = 'Nickel' AND date > '2025-01-01'` |

---

## Getting Started

1. **Install Ghost:**
   ```bash
   brew install timescale/tap/ghost
   ghost init
   ```
2. **Create a development database:**
   ```bash
   ghost create battery-erp-dev
   ```
3. **Run schema:**
   ```bash
   ghost sql battery-erp-dev < src/ghost_schema.sql
   ```
4. **Install the MCP server:**
   ```bash
   ghost mcp install claude-code
   ```
5. **Add to `.env.example`:**
   ```
   GHOST_API_KEY=***   GHOST_DEFAULT_DB=battery-erp-dev
   ```

---

## Resources
- [Ghost Documentation](https://ghost.build/docs)
- [Ghost MCP Tools](https://ghost.build/docs/#mcp-integration)
- [Ghost Tutorial](https://ghost.build/tutorials/learn-the-basics)
