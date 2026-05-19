# Cell 1 — Install dependencies
# ============================================================
# Battery ERP — Cost Analytics & Dashboard Pipeline
# Runs in Microsoft Fabric with the Lakehouse created by fabric_setup_lakehouse.py
#
# Pipeline: Read Delta tables → Calculate BOM costs → Chemistry comparison →
#           Inventory health → Supplier scoring → Cost scenarios → Dashboard
# ============================================================

# %%
# Cell 2 — Configuration
# ============================================================
import os

# AlphaVantage (optional — for live commodity prices)
ALPHAVANTAGE_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "")
# FRED (optional — for macro context)
FRED_KEY = os.getenv("FRED_API_KEY", "")

print(f"AlphaVantage: {'configured' if ALPHAVANTAGE_KEY else 'not set (using Lakehouse prices)'}")
print(f"FRED: {'configured' if FRED_KEY else 'not set'}")

# %%
# Cell 3 — Install dependencies
# ============================================================
print("Installing dependencies...")
%pip install openai requests -q
print("Done.")

# %%
# Cell 4 — Business Rules Engine (inline)
# ============================================================
import json
import urllib.request
import urllib.parse
from datetime import datetime, date, timedelta

# --- BOM Cost Rollup ---
def rollup_bom_cost(bom_items):
    """Calculate total BOM cost from Delta table rows."""
    details = []
    material_breakdown = {}
    total_waste = 0.0
    for item in bom_items:
        qty = float(item["quantity_per_unit"])
        cost = float(item["unit_cost_usd"])
        waste_pct = float(item["waste_factor_pct"])
        effective_qty = qty * (1 + waste_pct / 100)
        line_cost = effective_qty * cost
        mat = item["material_name"]
        material_breakdown[mat] = material_breakdown.get(mat, 0) + line_cost
        total_waste += (qty * waste_pct / 100) * cost
        details.append({**item, "line_cost_usd": line_cost})
    total = sum(d["line_cost_usd"] for d in details)
    return {
        "total_cost_usd": round(total, 4),
        "line_items": len(details),
        "material_breakdown": {k: round(v, 4) for k, v in sorted(material_breakdown.items())},
        "waste_cost_usd": round(total_waste, 4),
    }


# --- Cell BOM Generator ---
CATHODE_LOADING = {
    "NMC-111": {"nickel": 0.21, "manganese": 0.21, "cobalt": 0.21, "lithium_carbonate": 0.45},
    "NMC-811": {"nickel": 0.63, "manganese": 0.09, "cobalt": 0.09, "lithium_carbonate": 0.50},
    "NMC-622": {"nickel": 0.42, "manganese": 0.14, "cobalt": 0.14, "lithium_carbonate": 0.47},
    "NCA":     {"nickel": 0.80, "cobalt": 0.05, "aluminum": 0.05, "lithium_carbonate": 0.52},
    "LFP":     {"lithium_carbonate": 0.30, "iron_phosphate": 0.65},
    "LMO":     {"lithium_carbonate": 0.28, "manganese": 0.55},
}

COMMON_PER_KWH = {
    "graphite_anode": 0.50, "electrolyte": 0.25, "copper_foil": 0.18,
    "aluminum_foil": 0.12, "separator": 0.04, "binder_pvdf": 0.02, "conductive_additive": 0.01,
}

def build_cell_bom(chemistry, cell_capacity_ah, material_prices):
    """Build BOM for a cell chemistry from material prices dict."""
    cell_kwh = (cell_capacity_ah * 3.7) / 1000
    spec = CATHODE_LOADING.get(chemistry, CATHODE_LOADING["NMC-111"])
    bom = []
    for mat, kg_per_kwh in spec.items():
        qty = kg_per_kwh * cell_kwh
        bom.append({"material_name": mat, "quantity_per_unit": round(qty, 4),
                     "unit_cost_usd": material_prices.get(mat, 0.0), "waste_factor_pct": 3.0})
    for mat, kg_per_kwh in COMMON_PER_KWH.items():
        qty = kg_per_kwh * cell_kwh
        bom.append({"material_name": mat, "quantity_per_unit": round(qty, 4),
                     "unit_cost_usd": material_prices.get(mat, 0.0), "waste_factor_pct": 2.0})
    return bom


# --- Supplier Scoring ---
def score_supplier(row):
    quality = float(row["quality_rating"])
    otd = float(row["on_time_delivery_pct"])
    lead = int(row["lead_time_days"])
    lead_score = 100 if lead <= 14 else (80 if lead <= 30 else (60 if lead <= 60 else 40))
    certs = len(str(row.get("certifications", "")).split(",")) if row.get("certifications") else 0
    cert_bonus = min(certs * 3, 10)
    composite = quality * 0.35 + otd * 0.35 + lead_score * 0.20 + cert_bonus
    grade = "A" if composite >= 80 else ("B" if composite >= 65 else ("C" if composite >= 50 else "D"))
    return {**row, "composite_score": round(composite, 1), "grade": grade}


print("Business rules engine loaded.")

# %%
# Cell 5 — Read all Delta tables
# ============================================================
materials_df = spark.table("raw_materials").toPandas()
chemistry_df = spark.table("cell_chemistries").toPandas()
cells_df = spark.table("battery_cells").toPandas()
packs_df = spark.table("battery_packs").toPandas()
bom_df = spark.table("bill_of_materials").toPandas()
suppliers_df = spark.table("suppliers").toPandas()
inventory_df = spark.table("inventory").toPandas()
po_df = spark.table("purchase_orders").toPandas()
price_df = spark.table("price_history").toPandas()
mfg_df = spark.table("manufacturing_batches").toPandas()
scenarios_df = spark.table("cost_scenarios").toPandas()

print(f"Tables loaded: materials={len(materials_df)}, chemistries={len(chemistry_df)}, "
      f"cells={len(cells_df)}, packs={len(packs_df)}, bom={len(bom_df)}, "
      f"suppliers={len(suppliers_df)}, inventory={len(inventory_df)}, "
      f"POs={len(po_df)}, prices={len(price_df)}, batches={len(mfg_df)}, "
      f"scenarios={len(scenarios_df)}")

# %%
# Cell 6 — Build material price table from Lakehouse
# ============================================================
# Get latest prices from raw_materials table
material_prices = {}
for _, row in materials_df.iterrows():
    name = row["name"]
    # Map to BOM material names
    name_map = {
        "Lithium Carbonate": "lithium_carbonate",
        "Nickel (Class 1)": "nickel",
        "Cobalt": "cobalt",
        "Manganese (Electrolytic)": "manganese",
        "Graphite (Spherical)": "graphite_anode",
        "Electrolyte (LiPF6)": "electrolyte",
        "Copper Foil": "copper_foil",
        "Aluminum Foil": "aluminum_foil",
        "Separator (Ceramic-Coated)": "separator",
    }
    mapped = name_map.get(name)
    if mapped:
        material_prices[mapped] = float(row["unit_price_usd"])

# Add pack-level defaults
material_prices.setdefault("binder_pvdf", 25.00)
material_prices.setdefault("conductive_additive", 8.00)
material_prices.setdefault("pack_casing_aluminum", 3.50)
material_prices.setdefault("bms_module", 15.00)
material_prices.setdefault("thermal_coolant", 5.00)
material_prices.setdefault("wiring_harness", 6.00)
material_prices.setdefault("insulation", 4.00)
material_prices.setdefault("pack_structural_adhesive", 8.00)

print(f"Material price table: {len(material_prices)} materials")
for k, v in sorted(material_prices.items()):
    print(f"  {k}: ${v:.2f}/kg")

# %%
# Cell 7 — Chemistry Cost Comparison Dashboard
# ============================================================
print(f"\n{'='*70}")
print("CHEMISTRY COST COMPARISON DASHBOARD")
print(f"{'='*70}\n")

CAPACITY_AH = 50.0
cell_kwh = (CAPACITY_AH * 3.7) / 1000

print(f"Cell reference: {CAPACITY_AH}Ah @ 3.7V = {cell_kwh:.4f} kWh\n")
print(f"{'Chemistry':<12} {'BOM $':>8} {'$/kWh':>8} {'Cath %':>7} {'Anode %':>8} {'Other %':>8}")
print("-" * 55)

chem_results = {}
for chem_name in ["NMC-111", "NMC-811", "NMC-622", "NCA", "LFP", "LMO"]:
    bom = build_cell_bom(chem_name, CAPACITY_AH, material_prices)
    rollup = rollup_bom_cost(bom)

    cathode_mats = {"nickel", "manganese", "cobalt", "lithium_carbonate", "lithium_hydroxide",
                    "iron_phosphate", "aluminum"}
    anode_mats = {"graphite_anode"}

    total = rollup["total_cost_usd"]
    cath_cost = sum(v for k, v in rollup["material_breakdown"].items() if k in cathode_mats)
    anode_cost = sum(v for k, v in rollup["material_breakdown"].items() if k in anode_mats)
    other_cost = total - cath_cost - anode_cost

    cost_per_kwh = total / cell_kwh if cell_kwh > 0 else 0
    cath_pct = (cath_cost / total * 100) if total > 0 else 0
    anode_pct = (anode_cost / total * 100) if total > 0 else 0
    other_pct = (other_cost / total * 100) if total > 0 else 0

    print(f"{chem_name:<12} {total:>8.2f} {cost_per_kwh:>8.1f} {cath_pct:>6.1f}% {anode_pct:>7.1f}% {other_pct:>7.1f}%")

    chem_results[chem_name] = {
        "bom_cost": total, "cost_per_kwh": cost_per_kwh,
        "cathode_pct": cath_pct, "anode_pct": anode_pct, "other_pct": other_pct,
        "breakdown": rollup["material_breakdown"],
    }

# Ranking
ranking = sorted(chem_results.items(), key=lambda x: x[1]["cost_per_kwh"])
print(f"\nCost ranking (cheapest to most expensive):")
for i, (chem, data) in enumerate(ranking):
    print(f"  {i+1}. {chem}: ${data['cost_per_kwh']:.1f}/kWh")

# %%
# Cell 8 — Pack-Level Cost Estimation
# ============================================================
print(f"\n{'='*70}")
print("PACK-LEVEL COST ESTIMATION")
print(f"{'='*70}\n")

for _, pack in packs_df.iterrows():
    pack_sku = pack["sku"]
    cell_sku = pack["cell_sku"]
    total_cells = int(pack["total_cells"])
    pack_kwh = float(pack["nominal_capacity_kwh"])
    pack_weight = float(pack["pack_weight_kg"])

    # Find cell BOM cost
    # Look up chemistry from pack
    chem = pack.get("chemistry", "NMC-811")
    cell_bom = build_cell_bom(chem, CAPACITY_AH, material_prices)
    cell_rollup = rollup_bom_cost(cell_bom)
    cell_cost = cell_rollup["total_cost_usd"]

    # Pack-level components cost
    pack_comp_cost = (
        material_prices.get("pack_casing_aluminum", 3.50) * 2.5 * pack_kwh +
        max(1.0, 0.02 * pack_kwh) * material_prices.get("bms_module", 15.00) +
        material_prices.get("thermal_coolant", 5.00) * 0.8 * pack_kwh +
        material_prices.get("wiring_harness", 6.00) * 0.3 * pack_kwh +
        material_prices.get("insulation", 4.00) * 0.1 * pack_kwh +
        material_prices.get("pack_structural_adhesive", 8.00) * 0.15 * pack_kwh
    )

    cells_cost = cell_cost * total_cells
    total_pack_cost = cells_cost + pack_comp_cost
    cost_per_kwh = total_pack_cost / pack_kwh if pack_kwh > 0 else 0
    density = (pack_kwh * 1000 / pack_weight) if pack_weight > 0 else 0

    print(f"Pack: {pack_sku} ({pack.get('name', '')})")
    print(f"  Chemistry: {chem} | Cells: {total_cells} | Capacity: {pack_kwh} kWh")
    print(f"  Cell BOM cost:   ${cell_cost:.2f}")
    print(f"  Cells cost:      ${cells_cost:.2f} ({total_cells} x ${cell_cost:.2f})")
    print(f"  Pack components: ${pack_comp_cost:.2f}")
    print(f"  Total pack cost: ${total_pack_cost:.2f}")
    print(f"  Pack $/kWh:      ${cost_per_kwh:.1f}")
    print(f"  Pack Wh/kg:      {density:.0f}")
    print()

# %%
# Cell 9 — Inventory Health Report
# ============================================================
print(f"{'='*70}")
print("INVENTORY HEALTH REPORT")
print(f"{'='*70}\n")

total_value = 0
low_count = 0
oos_count = 0

for _, inv in inventory_df.iterrows():
    on_hand = float(inv["quantity_on_hand"])
    reserved = float(inv["quantity_reserved"])
    available = on_hand - reserved
    unit_cost = float(inv["unit_cost_usd"])
    value = on_hand * unit_cost
    total_value += value

    status = "IN_STOCK"
    if available <= 0:
        status = "OUT_OF_STOCK"
        oos_count += 1
    elif available <= float(inv["reorder_point"]):
        status = "LOW"
        low_count += 1

    print(f"  {inv['material_name']:<25} | {on_hand:>8.0f} kg | "
          f"Avail: {available:>8.0f} | ${value:>10.0f} | {status}")

print(f"\n  Total SKUs: {len(inventory_df)}")
print(f"  Total inventory value: ${total_value:,.0f}")
print(f"  Low stock: {low_count} | Out of stock: {oos_count}")
print(f"  Health: {'POOR' if (low_count + oos_count) > len(inventory_df) // 2 else 'FAIR' if (low_count + oos_count) > 0 else 'GOOD'}")

# %%
# Cell 10 — Supplier Scorecard
# ============================================================
print(f"\n{'='*70}")
print("SUPPLIER SCORECARD")
print(f"{'='*70}\n")

scored = []
for _, s in suppliers_df.iterrows():
    scored.append(score_supplier(s))

scored.sort(key=lambda x: x["composite_score"], reverse=True)

print(f"{'Supplier':<25} {'Score':>6} {'Grade':>5} {'Quality':>8} {'OTD':>6} {'Lead':>5} {'Region':>6}")
print("-" * 68)
for s in scored:
    print(f"{s['name']:<25} {s['composite_score']:>6.1f} {s['grade']:>5} "
          f"{s['quality_rating']:>7.0f}% {s['on_time_delivery_pct']:>5.0f}% "
          f"{s['lead_time_days']:>4d}d {s['region']:>6}")

# %%
# Cell 11 — Price Trend Analysis
# ============================================================
print(f"\n{'='*70}")
print("PRICE TREND ANALYSIS")
print(f"{'='*70}\n")

tracked_materials = ["Lithium Carbonate", "Nickel (Class 1)", "Cobalt", "Graphite (Spherical)"]

for mat_name in tracked_materials:
    mat_prices = price_df[price_df["material_name"] == mat_name].sort_values("as_of")
    if len(mat_prices) < 2:
        print(f"  {mat_name}: insufficient data ({len(mat_prices)} points)")
        continue

    oldest = mat_prices.iloc[0]
    latest = mat_prices.iloc[-1]

    old_price = float(oldest["price_usd"])
    new_price = float(latest["price_usd"])
    pct = ((new_price - old_price) / old_price * 100) if old_price > 0 else 0
    trend = "UP" if pct > 5 else ("DOWN" if pct < -5 else "FLAT")

    prices = [float(p["price_usd"]) for _, p in mat_prices.iterrows()]
    avg = sum(prices) / len(prices)
    mx, mn = max(prices), min(prices)

    print(f"  {mat_name}:")
    print(f"    Latest: ${new_price:.2f} (as of {latest['as_of']})")
    print(f"    Change: {pct:+.1f}% ({trend}) | Avg: ${avg:.2f} | Range: ${mn:.2f} - ${mx:.2f}")

# %%
# Cell 12 — Manufacturing Yield Report
# ============================================================
print(f"\n{'='*70}")
print("MANUFACTURING YIELD REPORT")
print(f"{'='*70}\n")

total_produced = 0
total_pass = 0

print(f"{'Batch ID':<20} {'Product':<20} {'Produced':>8} {'Passed':>8} {'Yield':>7}")
print("-" * 70)
for _, b in mfg_df.iterrows():
    prod = int(b["quantity_produced"])
    passed = int(b["quantity_pass"])
    total_produced += prod
    total_pass += passed
    yld = (passed / prod * 100) if prod > 0 else 0
    print(f"{b['batch_id']:<20} {b['product_sku']:<20} {prod:>8} {passed:>8} {yld:>6.1f}%")

avg_yield = (total_pass / total_produced * 100) if total_produced > 0 else 0
print("-" * 70)
print(f"{'TOTAL':<40} {total_produced:>8} {total_pass:>8} {avg_yield:>6.1f}%")

# %%
# Cell 13 — Cost Scenario Impact
# ============================================================
print(f"\n{'='*70}")
print("COST SCENARIO IMPACT")
print(f"{'='*70}\n")

for _, sc in scenarios_df.iterrows():
    pct = float(sc["pct_change"])
    direction = "INCREASE" if pct > 0 else "DECREASE"
    print(f"Scenario: {sc['scenario_name']}")
    print(f"  Material: {sc['material_name']} | {direction}: {abs(pct):.1f}%")
    print(f"  Current: ${float(sc['current_price_usd']):.2f} -> Scenario: ${float(sc['scenario_price_usd']):.2f}")
    print(f"  Impact per cell: ${float(sc['impact_cell_cost_delta_usd']):+.4f}")
    print(f"  Impact per 108-cell pack: ${float(sc['impact_pack_cost_delta_usd']):+.2f}")
    print()

# %%
# Cell 14 — Dashboard Summary
# ============================================================
print(f"\n{'='*70}")
print("BATTERY ERP DASHBOARD SUMMARY")
print(f"{'='*70}")
print(f"  Report generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
print(f"")
print(f"  MATERIALS TRACKED: {len(materials_df)}")
print(f"  CHEMISTRIES: {len(chemistry_df)}")
print(f"  CELL SKUs: {len(cells_df)}")
print(f"  PACK SKUs: {len(packs_df)}")
print(f"  SUPPLIERS: {len(suppliers_df)} (top grade: {scored[0]['grade'] if scored else 'N/A'})")
print(f"")
print(f"  INVENTORY VALUE: ${total_value:,.0f}")
print(f"  INVENTORY HEALTH: {low_count} low, {oos_count} out-of-stock")
print(f"")
print(f"  CHEAPEST CHEMISTRY: {ranking[0][0]} (${ranking[0][1]['cost_per_kwh']:.1f}/kWh)")
print(f"  MOST EXPENSIVE: {ranking[-1][0]} (${ranking[-1][1]['cost_per_kwh']:.1f}/kWh)")
print(f"")
print(f"  MFG AVG YIELD: {avg_yield:.1f}% ({total_pass}/{total_produced} cells)")
print(f"  COST SCENARIOS LOADED: {len(scenarios_df)}")
print(f"")
print(f"{'='*70}")
print(f"All data sourced from Fabric Lakehouse Delta tables.")
