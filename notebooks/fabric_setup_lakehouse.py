# Cell 1 — Install dependencies
# ============================================================
# Battery ERP — Fabric Lakehouse Table Setup
# Creates all Delta tables for the battery value chain ERP.
#
# Tables: raw_materials, cell_chemistries, battery_cells, battery_packs,
#         bill_of_materials, suppliers, inventory, purchase_orders,
#         price_history, manufacturing_batches, cost_scenarios
# ============================================================

# %%
# Cell 2 — raw_materials: Battery raw material catalog
# ============================================================
raw_materials_seed = [
    {"material_id": "LM-CARB", "name": "Lithium Carbonate", "chemical_formula": "Li2CO3",
     "category": "cathode", "unit": "kg", "unit_price_usd": 12.50, "price_as_of": "2025-05-03",
     "price_source": "benchmark_minerals", "min_purity_pct": 99.5, "hs_code": "2836.91",
     "hazards": ["irritant", "environmental"], "notes": "Battery grade, 99.5% min"},
    {"material_id": "NI-C1", "name": "Nickel (Class 1)", "chemical_formula": "Ni",
     "category": "cathode", "unit": "kg", "unit_price_usd": 16.50, "price_as_of": "2025-05-03",
     "price_source": "lme", "min_purity_pct": 99.9, "hs_code": "7504.10",
     "hazards": ["allergen", "carcinogen"], "notes": "LME Class 1, cathode grade"},
    {"material_id": "CO-LME", "name": "Cobalt", "chemical_formula": "Co",
     "category": "cathode", "unit": "kg", "unit_price_usd": 24.00, "price_as_of": "2025-05-03",
     "price_source": "lme", "min_purity_pct": 99.8, "hs_code": "8105.20",
     "hazards": ["toxic", "carcinogen"], "notes": "LME refined cobalt"},
    {"material_id": "MN-ELEC", "name": "Manganese (Electrolytic)", "chemical_formula": "Mn",
     "category": "cathode", "unit": "kg", "unit_price_usd": 2.80, "price_as_of": "2025-05-03",
     "price_source": "fastmarkets", "min_purity_pct": 99.7, "hs_code": "8102.10",
     "hazards": ["oxidizer"], "notes": "Electrolytic manganese metal"},
    {"material_id": "GR-SPH", "name": "Graphite (Spherical)", "chemical_formula": "C",
     "category": "anode", "unit": "kg", "unit_price_usd": 12.00, "price_as_of": "2025-05-03",
     "price_source": "benchmark_minerals", "min_purity_pct": 99.95, "hs_code": "3801.10",
     "hazards": [], "notes": "Spherical natural graphite, battery grade"},
    {"material_id": "EL-LIPF6", "name": "Electrolyte (LiPF6)", "chemical_formula": "LiPF6",
     "category": "electrolyte", "unit": "kg", "unit_price_usd": 8.50, "price_as_of": "2025-05-03",
     "price_source": "internal", "min_purity_pct": 99.9, "hs_code": "2827.60",
     "hazards": ["corrosive", "moisture_sensitive"], "notes": "LiPF6 in EC/DMC solvent"},
    {"material_id": "CU-FOIL", "name": "Copper Foil", "chemical_formula": "Cu",
     "category": "anode_current_collector", "unit": "kg", "unit_price_usd": 9.00, "price_as_of": "2025-05-03",
     "price_source": "lme", "min_purity_pct": 99.9, "hs_code": "7406.20",
     "hazards": [], "notes": "8um electrolytic copper foil"},
    {"material_id": "AL-FOIL", "name": "Aluminum Foil", "chemical_formula": "Al",
     "category": "cathode_current_collector", "unit": "kg", "unit_price_usd": 3.20, "price_as_of": "2025-05-03",
     "price_source": "lme", "min_purity_pct": 99.7, "hs_code": "7606.10",
     "hazards": [], "notes": "15um aluminum foil for cathode"},
    {"material_id": "SEP-CER", "name": "Separator (Ceramic-Coated)", "chemical_formula": "PE/PP",
     "category": "separator", "unit": "kg", "unit_price_usd": 15.00, "price_as_of": "2025-05-03",
     "price_source": "supplier_quote", "min_purity_pct": 100.0, "hs_code": "3920.99",
     "hazards": [], "notes": "20um PE/PP with Al2O3 ceramic coating"},
    {"material_id": "FE-PO4", "name": "Iron Phosphate", "chemical_formula": "FePO4",
     "category": "cathode", "unit": "kg", "unit_price_usd": 1.50, "price_as_of": "2025-05-03",
     "price_source": "internal", "min_purity_pct": 99.0, "hs_code": "2834.29",
     "hazards": [], "notes": "Battery grade iron phosphate for LFP cathode"},
]

raw_materials_df = spark.createDataFrame(raw_materials_seed)
raw_materials_df.write.format("delta").mode("overwrite").saveAsTable("raw_materials")
print(f"raw_materials: {spark.table('raw_materials').count()} records")

# %%
# Cell 3 — cell_chemistries: Battery chemistry catalog
# ============================================================
chemistries_seed = [
    {"chemistry_id": "NMC811", "name": "NMC-811",
     "cathode_type": "LiNi0.8Mn0.1Co0.1O2", "anode_type": "Graphite",
     "electrolyte_type": "LiPF6 EC/DMC", "nominal_voltage_v": 3.7,
     "energy_density_wh_per_kg": 260, "energy_density_wh_per_l": 650,
     "cycle_life": 1500, "operating_temp_min_c": -20.0, "operating_temp_max_c": 60.0,
     "notes": "High energy, reduced cobalt. EV dominant."},
    {"chemistry_id": "NMC111", "name": "NMC-111",
     "cathode_type": "LiNiMnCoO2", "anode_type": "Graphite",
     "electrolyte_type": "LiPF6 EC/DMC", "nominal_voltage_v": 3.7,
     "energy_density_wh_per_kg": 200, "energy_density_wh_per_l": 450,
     "cycle_life": 2000, "operating_temp_min_c": -20.0, "operating_temp_max_c": 55.0,
     "notes": "Balanced performance. Legacy EV + ESS."},
    {"chemistry_id": "NCA", "name": "NCA",
     "cathode_type": "LiNiCoAlO2", "anode_type": "Silicon-Graphite",
     "electrolyte_type": "LiPF6 EC/DMC", "nominal_voltage_v": 3.65,
     "energy_density_wh_per_kg": 270, "energy_density_wh_per_l": 680,
     "cycle_life": 500, "operating_temp_min_c": -20.0, "operating_temp_max_c": 55.0,
     "notes": "Tesla flagship. High energy, lower cycle life."},
    {"chemistry_id": "LFP", "name": "LFP",
     "cathode_type": "LiFePO4", "anode_type": "Graphite",
     "electrolyte_type": "LiPF6 EC/DMC", "nominal_voltage_v": 3.2,
     "energy_density_wh_per_kg": 160, "energy_density_wh_per_l": 320,
     "cycle_life": 4000, "operating_temp_min_c": -20.0, "operating_temp_max_c": 60.0,
     "notes": "Ultra-safe, long life, no cobalt/nickel. ESS + standard range EV."},
    {"chemistry_id": "LMO", "name": "LMO",
     "cathode_type": "LiMn2O4", "anode_type": "Graphite",
     "electrolyte_type": "LiPF6 EC/DMC", "nominal_voltage_v": 3.8,
     "energy_density_wh_per_kg": 140, "energy_density_wh_per_l": 280,
     "cycle_life": 1000, "operating_temp_min_c": -20.0, "operating_temp_max_c": 55.0,
     "notes": "Low cost. Power tools, medical, some PHEV."},
    {"chemistry_id": "NMC622", "name": "NMC-622",
     "cathode_type": "LiNi0.6Mn0.2Co0.2O2", "anode_type": "Graphite",
     "electrolyte_type": "LiPF6 EC/DMC", "nominal_voltage_v": 3.7,
     "energy_density_wh_per_kg": 230, "energy_density_wh_per_l": 550,
     "cycle_life": 1800, "operating_temp_min_c": -20.0, "operating_temp_max_c": 60.0,
     "notes": "Good balance of energy, cost, and cycle life."},
]

chemistries_df = spark.createDataFrame(chemistries_seed)
chemistries_df.write.format("delta").mode("overwrite").saveAsTable("cell_chemistries")
print(f"cell_chemistries: {spark.table('cell_chemistries').count()} records")

# %%
# Cell 4 — battery_cells: Cell catalog
# ============================================================
cells_seed = [
    {"cell_id": "CELL-NMC811-50", "sku": "CELL-NMC811-50", "chemistry": "NMC-811",
     "form_factor": "prismatic", "nominal_capacity_ah": 50.0, "nominal_voltage_v": 3.7,
     "energy_wh": 185.0, "dimensions_mm": "148x92x14", "weight_kg": 0.92,
     "max_charge_rate_c": 2.0, "max_discharge_rate_c": 3.0,
     "category": "EV", "lifecycle_stage": "active", "date_added": "2025-01-15"},
    {"cell_id": "CELL-LFP-280", "sku": "CELL-LFP-280", "chemistry": "LFP",
     "form_factor": "prismatic", "nominal_capacity_ah": 280.0, "nominal_voltage_v": 3.2,
     "energy_wh": 896.0, "dimensions_mm": "207x132x36", "weight_kg": 5.45,
     "max_charge_rate_c": 1.0, "max_discharge_rate_c": 2.0,
     "category": "ESS", "lifecycle_stage": "active", "date_added": "2025-01-15"},
    {"cell_id": "CELL-NCA-21700", "sku": "CELL-NCA-21700", "chemistry": "NCA",
     "form_factor": "cylindrical", "nominal_capacity_ah": 5.0, "nominal_voltage_v": 3.65,
     "energy_wh": 18.25, "dimensions_mm": "21x70", "weight_kg": 0.068,
     "max_charge_rate_c": 2.0, "max_discharge_rate_c": 3.0,
     "category": "EV", "lifecycle_stage": "active", "date_added": "2025-02-01"},
]

cells_df = spark.createDataFrame(cells_seed)
cells_df.write.format("delta").mode("overwrite").saveAsTable("battery_cells")
print(f"battery_cells: {spark.table('battery_cells').count()} records")

# %%
# Cell 5 — battery_packs: Pack catalog
# ============================================================
packs_seed = [
    {"pack_id": "PACK-EV75", "sku": "PACK-EV75", "name": "75 kWh EV Pack (NMC-811)",
     "cell_sku": "CELL-NMC811-50", "chemistry": "NMC-811",
     "cells_in_series": 108, "cells_in_parallel": 1, "total_cells": 108,
     "nominal_capacity_kwh": 75.0, "nominal_voltage_v": 399.6,
     "pack_weight_kg": 375.0, "bms_manufacturer": "NXP",
     "cooling_type": "liquid", "category": "EV", "date_added": "2025-03-01"},
    {"pack_id": "PACK-ESS100", "sku": "PACK-ESS100", "name": "100 kWh ESS Pack (LFP)",
     "cell_sku": "CELL-LFP-280", "chemistry": "LFP",
     "cells_in_series": 128, "cells_in_parallel": 1, "total_cells": 128,
     "nominal_capacity_kwh": 100.0, "nominal_voltage_v": 409.6,
     "pack_weight_kg": 650.0, "bms_manufacturer": "Pace",
     "cooling_type": "air", "category": "ESS", "date_added": "2025-03-15"},
]

packs_df = spark.createDataFrame(packs_seed)
packs_df.write.format("delta").mode("overwrite").saveAsTable("battery_packs")
print(f"battery_packs: {spark.table('battery_packs').count()} records")

# %%
# Cell 6 — bill_of_materials: BOM line items
# ============================================================
bom_seed = [
    {"bom_id": "BOM-NMC811-CATH", "parent_sku": "CELL-NMC811-50", "material_name": "Nickel (Class 1)",
     "material_id": "NI-C1", "quantity_per_unit": 0.063, "unit": "kg",
     "unit_cost_usd": 16.50, "line_cost_usd": 1.07, "waste_factor_pct": 3.0},
    {"bom_id": "BOM-NMC811-CO", "parent_sku": "CELL-NMC811-50", "material_name": "Cobalt",
     "material_id": "CO-LME", "quantity_per_unit": 0.009, "unit": "kg",
     "unit_cost_usd": 24.00, "line_cost_usd": 0.22, "waste_factor_pct": 3.0},
    {"bom_id": "BOM-NMC811-MN", "parent_sku": "CELL-NMC811-50", "material_name": "Manganese (Electrolytic)",
     "material_id": "MN-ELEC", "quantity_per_unit": 0.009, "unit": "kg",
     "unit_cost_usd": 2.80, "line_cost_usd": 0.03, "waste_factor_pct": 3.0},
    {"bom_id": "BOM-NMC811-LI", "parent_sku": "CELL-NMC811-50", "material_name": "Lithium Carbonate",
     "material_id": "LM-CARB", "quantity_per_unit": 0.050, "unit": "kg",
     "unit_cost_usd": 12.50, "line_cost_usd": 0.64, "waste_factor_pct": 3.0},
    {"bom_id": "BOM-NMC811-GR", "parent_sku": "CELL-NMC811-50", "material_name": "Graphite (Spherical)",
     "material_id": "GR-SPH", "quantity_per_unit": 0.050, "unit": "kg",
     "unit_cost_usd": 12.00, "line_cost_usd": 0.61, "waste_factor_pct": 2.0},
    {"bom_id": "BOM-NMC811-EL", "parent_sku": "CELL-NMC811-50", "material_name": "Electrolyte (LiPF6)",
     "material_id": "EL-LIPF6", "quantity_per_unit": 0.025, "unit": "kg",
     "unit_cost_usd": 8.50, "line_cost_usd": 0.22, "waste_factor_pct": 2.0},
]

bom_df = spark.createDataFrame(bom_seed)
bom_df.write.format("delta").mode("overwrite").saveAsTable("bill_of_materials")
print(f"bill_of_materials: {spark.table('bill_of_materials').count()} records")

# %%
# Cell 7 — suppliers: Upstream supplier catalog
# ============================================================
suppliers_seed = [
    {"supplier_id": "SUP-GANFENG", "name": "Ganfeng Lithium", "country": "China", "region": "APAC",
     "materials_supplied": "Lithium Carbonate,Lithium Hydroxide", "lead_time_days": 21,
     "moq_tonnes": 5.0, "quality_rating": 88, "on_time_delivery_pct": 92,
     "unit_price_usd": 12.50, "price_valid_until": "2025-12-31",
     "certifications": "ISO9001,ISO14001,IATF16949", "status": "in_stock",
     "notes": "Top 3 global lithium producer. Vertical integration."},
    {"supplier_id": "SUP-SUMITOMO", "name": "Sumitomo Metal Mining", "country": "Japan", "region": "APAC",
     "materials_supplied": "Nickel (Class 1),Cobalt", "lead_time_days": 30,
     "moq_tonnes": 2.0, "quality_rating": 95, "on_time_delivery_pct": 98,
     "unit_price_usd": 17.00, "price_valid_until": "2025-12-31",
     "certifications": "ISO9001,ISO14001,IATF16949,IRMA", "status": "in_stock",
     "notes": "Premium nickel. NMC-811 qualified. Responsible sourcing."},
    {"supplier_id": "SUP-GRAFTECH", "name": "Graphex Group", "country": "China", "region": "APAC",
     "materials_supplied": "Graphite (Spherical)", "lead_time_days": 28,
     "moq_tonnes": 3.0, "quality_rating": 82, "on_time_delivery_pct": 85,
     "unit_price_usd": 11.50, "price_valid_until": "2025-12-31",
     "certifications": "ISO9001,ISO14001", "status": "in_stock",
     "notes": "Spherical graphite specialist. Competitive pricing."},
    {"supplier_id": "SUP-ASPIRE", "name": "Aspire Mining", "country": "Australia", "region": "APAC",
     "materials_supplied": "Manganese (Electrolytic)", "lead_time_days": 35,
     "moq_tonnes": 10.0, "quality_rating": 78, "on_time_delivery_pct": 80,
     "unit_price_usd": 2.60, "price_valid_until": "2025-12-31",
     "certifications": "ISO9001", "status": "on_order",
     "notes": "E&P company developing manganese deposits."},
]

suppliers_df = spark.createDataFrame(suppliers_seed)
suppliers_df.write.format("delta").mode("overwrite").saveAsTable("suppliers")
print(f"suppliers: {spark.table('suppliers').count()} records")

# %%
# Cell 8 — inventory: Current warehouse positions
# ============================================================
inventory_seed = [
    {"record_id": "INV-001", "sku": "MAT-LM-CARB", "material_name": "Lithium Carbonate",
     "warehouse": "WH-MAIN", "quantity_on_hand": 2500, "quantity_reserved": 500,
     "unit": "kg", "reorder_point": 1000, "reorder_qty": 2000,
     "unit_cost_usd": 12.50, "total_value_usd": 31250.0, "status": "in_stock",
     "last_replenished": "2025-04-20"},
    {"record_id": "INV-002", "sku": "MAT-NI-C1", "material_name": "Nickel (Class 1)",
     "warehouse": "WH-MAIN", "quantity_on_hand": 800, "quantity_reserved": 300,
     "unit": "kg", "reorder_point": 500, "reorder_qty": 1500,
     "unit_cost_usd": 16.50, "total_value_usd": 13200.0, "status": "in_stock",
     "last_replenished": "2025-04-25"},
    {"record_id": "INV-003", "sku": "MAT-CO-LME", "material_name": "Cobalt",
     "warehouse": "WH-MAIN", "quantity_on_hand": 150, "quantity_reserved": 100,
     "unit": "kg", "reorder_point": 200, "reorder_qty": 500,
     "unit_cost_usd": 24.00, "total_value_usd": 3600.0, "status": "low",
     "last_replenished": "2025-04-10"},
    {"record_id": "INV-004", "sku": "MAT-GR-SPH", "material_name": "Graphite (Spherical)",
     "warehouse": "WH-MAIN", "quantity_on_hand": 2000, "quantity_reserved": 400,
     "unit": "kg", "reorder_point": 800, "reorder_qty": 3000,
     "unit_cost_usd": 12.00, "total_value_usd": 24000.0, "status": "in_stock",
     "last_replenished": "2025-04-18"},
]

inventory_df = spark.createDataFrame(inventory_seed)
inventory_df.write.format("delta").mode("overwrite").saveAsTable("inventory")
print(f"inventory: {spark.table('inventory').count()} records")

# %%
# Cell 9 — purchase_orders: Active and historical POs
# ============================================================
po_seed = [
    {"po_id": "PO-2025-001", "po_number": "PO-2025-001", "supplier_id": "SUP-GANFENG",
     "supplier_name": "Ganfeng Lithium", "material_name": "Lithium Carbonate",
     "quantity": 5000, "unit": "kg", "unit_price_usd": 12.50, "total_usd": 62500.0,
     "status": "delivered", "order_date": "2025-03-15", "expected_delivery": "2025-04-05",
     "actual_delivery": "2025-04-04", "warehouse": "WH-MAIN"},
    {"po_id": "PO-2025-002", "po_number": "PO-2025-002", "supplier_id": "SUP-SUMITOMO",
     "supplier_name": "Sumitomo Metal Mining", "material_name": "Nickel (Class 1)",
     "quantity": 2000, "unit": "kg", "unit_price_usd": 17.00, "total_usd": 34000.0,
     "status": "shipped", "order_date": "2025-04-10", "expected_delivery": "2025-05-10",
     "actual_delivery": None, "warehouse": "WH-MAIN"},
    {"po_id": "PO-2025-003", "po_number": "PO-2025-003", "supplier_id": "SUP-GANFENG",
     "supplier_name": "Ganfeng Lithium", "material_name": "Cobalt",
     "quantity": 500, "unit": "kg", "unit_price_usd": 24.00, "total_usd": 12000.0,
     "status": "pending", "order_date": "2025-05-01", "expected_delivery": "2025-05-22",
     "actual_delivery": None, "warehouse": "WH-MAIN"},
]

po_df = spark.createDataFrame(po_seed)
po_df.write.format("delta").mode("overwrite").saveAsTable("purchase_orders")
print(f"purchase_orders: {spark.table('purchase_orders').count()} records")

# %%
# Cell 10 — price_history: Historical commodity prices
# ============================================================
price_history_seed = [
    {"material_name": "Lithium Carbonate", "price_usd": 15.00, "unit": "kg", "as_of": "2025-01-01", "source": "benchmark_minerals"},
    {"material_name": "Lithium Carbonate", "price_usd": 13.80, "unit": "kg", "as_of": "2025-02-01", "source": "benchmark_minerals"},
    {"material_name": "Lithium Carbonate", "price_usd": 12.50, "unit": "kg", "as_of": "2025-03-01", "source": "benchmark_minerals"},
    {"material_name": "Lithium Carbonate", "price_usd": 12.50, "unit": "kg", "as_of": "2025-04-01", "source": "benchmark_minerals"},
    {"material_name": "Nickel (Class 1)", "price_usd": 17.20, "unit": "kg", "as_of": "2025-01-01", "source": "lme"},
    {"material_name": "Nickel (Class 1)", "price_usd": 16.80, "unit": "kg", "as_of": "2025-02-01", "source": "lme"},
    {"material_name": "Nickel (Class 1)", "price_usd": 16.50, "unit": "kg", "as_of": "2025-03-01", "source": "lme"},
    {"material_name": "Nickel (Class 1)", "price_usd": 16.50, "unit": "kg", "as_of": "2025-04-01", "source": "lme"},
    {"material_name": "Cobalt", "price_usd": 28.00, "unit": "kg", "as_of": "2025-01-01", "source": "lme"},
    {"material_name": "Cobalt", "price_usd": 26.00, "unit": "kg", "as_of": "2025-02-01", "source": "lme"},
    {"material_name": "Cobalt", "price_usd": 25.00, "unit": "kg", "as_of": "2025-03-01", "source": "lme"},
    {"material_name": "Cobalt", "price_usd": 24.00, "unit": "kg", "as_of": "2025-04-01", "source": "lme"},
    {"material_name": "Graphite (Spherical)", "price_usd": 13.00, "unit": "kg", "as_of": "2025-01-01", "source": "benchmark_minerals"},
    {"material_name": "Graphite (Spherical)", "price_usd": 12.50, "unit": "kg", "as_of": "2025-02-01", "source": "benchmark_minerals"},
    {"material_name": "Graphite (Spherical)", "price_usd": 12.00, "unit": "kg", "as_of": "2025-03-01", "source": "benchmark_minerals"},
    {"material_name": "Graphite (Spherical)", "price_usd": 12.00, "unit": "kg", "as_of": "2025-04-01", "source": "benchmark_minerals"},
]

price_df = spark.createDataFrame(price_history_seed)
price_df.write.format("delta").mode("overwrite").saveAsTable("price_history")
print(f"price_history: {spark.table('price_history').count()} records")

# %%
# Cell 11 — manufacturing_batches: Production batch records
# ============================================================
mfg_seed = [
    {"batch_id": "BATCH-2025-001", "product_sku": "CELL-NMC811-50", "product_type": "cell",
     "chemistry": "NMC-811", "quantity_produced": 10000, "quantity_pass": 9850,
     "yield_pct": 98.5, "start_date": "2025-03-01", "end_date": "2025-03-05",
     "line_name": "LINE-A", "notes": "Standard production run."},
    {"batch_id": "BATCH-2025-002", "product_sku": "CELL-NMC811-50", "product_type": "cell",
     "chemistry": "NMC-811", "quantity_produced": 8000, "quantity_pass": 7760,
     "yield_pct": 97.0, "start_date": "2025-03-15", "end_date": "2025-03-18",
     "line_name": "LINE-A", "notes": "Slightly lower yield — graphite supplier changeover."},
    {"batch_id": "BATCH-2025-003", "product_sku": "CELL-LFP-280", "product_type": "cell",
     "chemistry": "LFP", "quantity_produced": 5000, "quantity_pass": 4950,
     "yield_pct": 99.0, "start_date": "2025-04-01", "end_date": "2025-04-04",
     "line_name": "LINE-B", "notes": "LFP typically higher yield."},
]

mfg_df = spark.createDataFrame(mfg_seed)
mfg_df.write.format("delta").mode("overwrite").saveAsTable("manufacturing_batches")
print(f"manufacturing_batches: {spark.table('manufacturing_batches').count()} records")

# %%
# Cell 12 — cost_scenarios: What-if price scenarios
# ============================================================
scenarios_seed = [
    {"scenario_id": "SCEN-LITHIUM-SHOCK", "scenario_name": "Lithium Price Shock (+100%)",
     "material_name": "Lithium Carbonate", "current_price_usd": 12.50,
     "scenario_price_usd": 25.00, "pct_change": 100.0,
     "impact_cell_cost_delta_usd": 0.64, "impact_pack_cost_delta_usd": 69.12,
     "notes": "Based on 2022 lithium price spike. Stress test for supply disruption.",
     "created_at": "2025-05-03T00:00:00Z"},
    {"scenario_id": "SCEN-COBALT-BAN", "scenario_name": "Cobalt Supply Restriction",
     "material_name": "Cobalt", "current_price_usd": 24.00,
     "scenario_price_usd": 40.00, "pct_change": 66.7,
     "impact_cell_cost_delta_usd": 0.14, "impact_pack_cost_delta_usd": 15.12,
     "notes": "DRC export restrictions or ESG-driven demand shift.",
     "created_at": "2025-05-03T00:00:00Z"},
    {"scenario_id": "SCEN-NICKEL-DOWN", "scenario_name": "Nickel Price Recovery (-15%)",
     "material_name": "Nickel (Class 1)", "current_price_usd": 16.50,
     "scenario_price_usd": 14.03, "pct_change": -15.0,
     "impact_cell_cost_delta_usd": -0.16, "impact_pack_cost_delta_usd": -17.28,
     "notes": "Indonesian supply ramp. Positive for NMC cost structure.",
     "created_at": "2025-05-03T00:00:00Z"},
]

scenarios_df = spark.createDataFrame(scenarios_seed)
scenarios_df.write.format("delta").mode("overwrite").saveAsTable("cost_scenarios")
print(f"cost_scenarios: {spark.table('cost_scenarios').count()} records")

# %%
# Cell 13 — Verify all tables
# ============================================================
tables = [
    "raw_materials", "cell_chemistries", "battery_cells", "battery_packs",
    "bill_of_materials", "suppliers", "inventory", "purchase_orders",
    "price_history", "manufacturing_batches", "cost_scenarios",
]

print("=" * 60)
print("Battery ERP — Lakehouse Delta Tables Created")
print("=" * 60)
for t in tables:
    count = spark.table(t).count()
    print(f"  {t}: {count} records")
print("=" * 60)
print(f"All {len(tables)} Delta tables ready in Fabric Lakehouse!")
