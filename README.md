# Battery ERP — Material, cell, pack, and supply-chain management with real-time
# commodity pricing and Fabric Lakehouse analytics.
#
# Covers the full battery value chain: lithium, cobalt, nickel, manganese, graphite
# through cell chemistries (NMC-811, NCA, LFP, LMO) to battery packs with BOM costing,
# supplier scoring, inventory management, and what-if cost scenarios.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-32%20passing-brightgreen)](tests/)
[![Fabric](https://img.shields.io/badge/Microsoft-Fabric-0078D4)](https://fabric.microsoft.com)

---

## What this is

Battery ERP manages the **complete battery value chain** — from raw material sourcing
through cell manufacturing to pack assembly. Every cost is traceable to a specific
material, supplier, and price point.

| Layer | Role |
|---|---|
| **Data Models** | RawMaterial, CellChemistry, BatteryCell, BatteryPack, BOMItem, Supplier, InventoryRecord, PurchaseOrder, ManufacturingBatch |
| **Business Rules** | BOM cost rollups, inventory status management, supplier scoring (composite A-D grade), manufacturing yield tracking, price trend analysis, what-if cost scenarios |
| **Pricing Engine** | Default material price table (20+ materials), AlphaVantage integration for live commodity prices, FRED macro overlay |
| **Analytics** | Inventory health reports, supply chain reports, manufacturing yield reports, chemistry cost comparison dashboards |
| **Fabric Lakehouse** | 11 Delta tables for persistent storage and SQL analytics |

---

## Quick start

```bash
git clone https://codeberg.org/cubiczan/battery-erp.git
cd battery-erp
pip install pytest

# Run all 32 tests
PYTHONPATH=src pytest tests/ -v

# Use the modules
PYTHONPATH=src python3 -c "
from battery_erp.pricing import calculate_cell_cost_summary, get_material_price_table
prices = get_material_price_table()
for chem in ['NMC-811', 'NMC-622', 'NCA', 'LFP', 'LMO']:
    r = calculate_cell_cost_summary(chem, 50.0, prices)
    print(f'{chem}: \${r[\"cost_per_kwh\"]:.1f}/kWh (BOM: \${r[\"bom_cost_usd\"]:.2f})')
"
```

---

## Architecture

```
                    ┌──────────────────────────────────────┐
                    │  Raw Materials (20+ tracked)          │
                    │  Lithium · Cobalt · Nickel · Mn · Gr  │
                    └──────────────┬───────────────────────┘
                                   │ BOM
                    ┌──────────────▼───────────────────────┐
                    │  Cell Chemistries                     │
                    │  NMC-811 · NMC-622 · NCA · LFP · LMO  │
                    └──────────────┬───────────────────────┘
                                   │ cells + components
                    ┌──────────────▼───────────────────────┐
                    │  Battery Packs                        │
                    │  EV · ESS · Consumer · Industrial     │
                    └──────────────────────────────────────┘

Side modules:
  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
  │ Supplier Scoring │  │ Inventory Mgmt   │  │ Cost Scenarios    │
  │ Composite 0-100  │  │ Reorder logic    │  │ What-if analysis  │
  │ A/B/C/D grades   │  │ Status tracking  │  │ Price shock model │
  └─────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## Core modules

### `battery_erp.core.models`
All domain dataclasses:
- `RawMaterial` — material catalog with pricing, HS codes, hazards
- `CellChemistry` — NMC-111/622/811, NCA, LFP, LMO with energy density and cycle life
- `BatteryCell` — cell specs (capacity, voltage, form factor, weight)
- `BatteryPack` — pack assembly (cells + BMS + thermal)
- `BOMItem` — bill of materials line item with waste factor
- `Supplier` — supplier catalog with quality rating, lead time, certifications
- `InventoryRecord` — warehouse positions with reorder logic
- `PurchaseOrder` — PO lifecycle tracking
- `ManufacturingBatch` — production batch yield tracking
- `PriceHistory` — commodity price time series

### `battery_erp.core.rules`
Deterministic business rules:
- `rollup_bom_cost()` — total BOM cost with material breakdown and waste cost
- `calculate_cell_bom()` — generate representative BOM for any chemistry
- `calculate_pack_bom()` — pack-level BOM (cells + casing + BMS + cooling)
- `update_inventory_status()` — recalculate in_stock/low/out_of_stock
- `check_reorder_suggestions()` — generate PO suggestions
- `calculate_batch_metrics()` — aggregate manufacturing yield
- `analyze_price_history()` — price trend analysis with volatility
- `estimate_cell_cost_impact()` — what-if cost scenario modeling
- `calculate_pack_metrics()` — pack energy density and efficiency

### `battery_erp.supply_chain`
Supply chain management:
- `score_supplier()` — composite score (quality 35%, OTD 35%, lead time 20%, certs 10%)
- `rank_suppliers()` — rank by score, filter by material
- `create_purchase_order()` — PO creation from supplier data
- `analyze_po_pipeline()` — PO pipeline analysis (overdue detection, lead time tracking)
- `suggest_dual_sourcing()` — dual-sourcing strategy recommendation

### `battery_erp.pricing`
Commodity pricing:
- `get_material_price_table()` — default prices for 20+ battery materials
- `calculate_cell_cost_summary()` — quick cost estimate per chemistry
- `update_prices_from_alpha_vantage()` — live commodity price fetch
- `update_prices_from_fred()` — macro economic indicators

### `battery_erp.analytics`
Reporting:
- `generate_inventory_report()` — full inventory health dashboard
- `generate_supply_chain_report()` — supplier + PO pipeline report
- `generate_manufacturing_report()` — yield metrics
- `generate_pricing_report()` — chemistry cost comparison + price trends

---

## Chemistry cost comparison (default prices, 50Ah cell)

| Chemistry | BOM Cost | $/kWh | Cathode % | Key feature |
|---|---|---|---|---|
| **LFP** | Lowest | ~$50-55 | ~35% | No Co/Ni, ultra-safe, 4000+ cycles |
| **LMO** | Low | ~$55-60 | ~40% | Low cost, power tools |
| **NMC-111** | Medium | ~$70-80 | ~50% | Balanced, legacy |
| **NMC-622** | Medium | ~$75-85 | ~48% | Good energy-cost balance |
| **NMC-811** | Higher | ~$80-90 | ~52% | High energy, EV dominant |
| **NCA** | Highest | ~$85-95 | ~55% | Tesla flagship, 270 Wh/kg |

---

## Microsoft Fabric Integration

### Fabric Notebooks

| Notebook | Purpose |
|---|---|
| `fabric_setup_lakehouse.py` | Create all 11 Delta tables with seed data |
| `fabric_cost_dashboard.py` | Full cost analytics dashboard (chemistry comparison, pack costing, inventory, suppliers, price trends, scenarios) |

### Delta Table Schema

| Table | Key Columns |
|---|---|
| `raw_materials` | material_id, name, category, unit_price_usd, price_source, hs_code |
| `cell_chemistries` | chemistry_id, name, cathode_type, energy_density_wh_per_kg, cycle_life |
| `battery_cells` | cell_id, sku, chemistry, form_factor, nominal_capacity_ah, energy_wh, weight_kg |
| `battery_packs` | pack_id, sku, cell_sku, total_cells, nominal_capacity_kwh, pack_weight_kg |
| `bill_of_materials` | bom_id, parent_sku, material_name, quantity_per_unit, unit_cost_usd, waste_factor_pct |
| `suppliers` | supplier_id, name, country, materials_supplied, quality_rating, lead_time_days |
| `inventory` | record_id, sku, material_name, quantity_on_hand, quantity_reserved, reorder_point |
| `purchase_orders` | po_id, po_number, supplier_name, quantity, total_usd, status, expected_delivery |
| `price_history` | material_name, price_usd, as_of, source |
| `manufacturing_batches` | batch_id, product_sku, chemistry, quantity_produced, quantity_pass, yield_pct |
| `cost_scenarios` | scenario_id, scenario_name, material_name, current_price_usd, scenario_price_usd, pct_change |

### Fabric Quick Start

1. Run `fabric_setup_lakehouse.py` to create all 11 Delta tables
2. Run `fabric_cost_dashboard.py` for the full analytics dashboard
3. Dashboard covers: chemistry cost comparison, pack-level costing, inventory health, supplier scorecard, price trends, manufacturing yield, cost scenarios

---

## Tests

```bash
PYTHONPATH=src pytest tests/ -v
# 32 tests passing: models, BOM costing, inventory, supplier scoring,
#                    price analytics, cost scenarios, pack metrics, reports
```

---

## Use cases

- **Cell manufacturers** — BOM cost tracking across chemistries, yield optimization
- **Pack integrators** — pack-level cost estimation, supplier selection
- **Procurement** — supplier scoring, dual-sourcing, PO pipeline management
- **Finance** — commodity price risk, what-if scenarios, inventory valuation
- **C-suite** — dashboard showing $/kWh trends, supply chain resilience, cost reduction opportunities

---

## License

MIT. See [LICENSE](LICENSE).
