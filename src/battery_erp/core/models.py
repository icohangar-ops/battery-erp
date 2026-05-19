# Battery ERP — Core Data Models
"""
Domain models for the battery value chain:
- RawMaterial: lithium, cobalt, nickel, manganese, graphite, etc.
- CellChemistry: NMC-111, NMC-811, NCA, LFP, LMO
- BatteryCell: individual cell specs (capacity, voltage, dimensions)
- BatteryPack: pack of cells with BMS, thermal management
- BillOfMaterials (BOM): material-to-cell cost breakdown
- Supplier: upstream material suppliers with pricing and lead times
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional


class MaterialUnit(Enum):
    KG = "kg"
    TONNE = "tonne"
    LITRE = "litre"
    KWH = "kWh"
    EACH = "each"


class CellFormFactor(Enum):
    CYLINDRICAL = "cylindrical"
    POUCH = "pouch"
    PRISMATIC = "prismatic"


class BatteryCategory(Enum):
    EV = "EV"
    ESS = "ESS"  # Energy Storage System
    CONSUMER = "consumer"
    INDUSTRIAL = "industrial"
    MARINE = "marine"
    AEROSPACE = "aerospace"


class SupplyStatus(Enum):
    IN_STOCK = "in_stock"
    LOW = "low"
    OUT_OF_STOCK = "out_of_stock"
    ON_ORDER = "on_order"
    BACKORDERED = "backordered"


class OrderStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


@dataclass
class RawMaterial:
    """A raw material in the battery supply chain."""
    material_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    chemical_formula: str = ""
    category: str = ""  # cathode, anode, electrolyte, separator, binder, other
    unit: MaterialUnit = MaterialUnit.KG
    unit_price_usd: float = 0.0
    price_as_of: Optional[date] = None
    price_source: str = ""  # "trading_economics", "internal", "supplier_quote"
    min_purity_pct: float = 99.0
    hazards: list[str] = field(default_factory=list)
    hs_code: str = ""
    notes: str = ""

    @property
    def price_per_kg(self) -> float:
        if self.unit == MaterialUnit.KG:
            return self.unit_price_usd
        if self.unit == MaterialUnit.TONNE:
            return self.unit_price_usd / 1000.0
        return self.unit_price_usd


@dataclass
class CellChemistry:
    """Battery cell chemistry (NMC-111, NMC-811, LFP, etc.)."""
    chemistry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""  # "NMC-811", "LFP", "NCA", "LMO"
    cathode_type: str = ""
    anode_type: str = ""
    electrolyte_type: str = ""
    nominal_voltage_v: float = 3.7
    energy_density_wh_per_kg: float = 0.0  # gravimetric
    energy_density_wh_per_l: float = 0.0  # volumetric
    cycle_life: int = 1000  # at 80% SOH
    operating_temp_min_c: float = -20.0
    operating_temp_max_c: float = 60.0
    notes: str = ""


@dataclass
class BatteryCell:
    """Individual battery cell specification."""
    cell_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sku: str = ""
    chemistry: str = ""  # references CellChemistry.name
    form_factor: CellFormFactor = CellFormFactor.PRISMATIC
    nominal_capacity_ah: float = 0.0
    nominal_voltage_v: float = 3.7
    energy_wh: float = 0.0  # capacity_ah * voltage_v
    dimensions_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)  # L x W x H
    weight_kg: float = 0.0
    max_charge_rate_c: float = 1.0
    max_discharge_rate_c: float = 2.0
    category: BatteryCategory = BatteryCategory.EV
    lifecycle_stage: str = "active"  # active, eol, recycled
    date_added: Optional[date] = None

    @property
    def energy_kwh(self) -> float:
        return self.energy_wh / 1000.0


@dataclass
class BatteryPack:
    """Battery pack (collection of cells + BMS + thermal)."""
    pack_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sku: str = ""
    name: str = ""
    cell_sku: str = ""  # references BatteryCell.sku
    chemistry: str = ""
    cells_in_series: int = 1
    cells_in_parallel: int = 1
    total_cells: int = 1  # series * parallel
    nominal_capacity_kwh: float = 0.0
    nominal_voltage_v: float = 0.0
    pack_weight_kg: float = 0.0
    bms_manufacturer: str = ""
    cooling_type: str = ""  # liquid, air, immersion
    category: BatteryCategory = BatteryCategory.EV
    date_added: Optional[date] = None

    @property
    def energy_density_pack_wh_per_kg(self) -> float:
        if self.pack_weight_kg <= 0:
            return 0.0
        return (self.nominal_capacity_kwh * 1000) / self.pack_weight_kg


@dataclass
class BOMItem:
    """Single line item in a Bill of Materials."""
    bom_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_sku: str = ""  # cell or pack SKU
    material_name: str = ""
    material_id: str = ""
    quantity_per_unit: float = 1.0  # kg per cell, or cells per pack
    unit: MaterialUnit = MaterialUnit.KG
    unit_cost_usd: float = 0.0
    line_cost_usd: float = 0.0
    waste_factor_pct: float = 0.0
    notes: str = ""

    def calculate_line_cost(self) -> float:
        effective_qty = self.quantity_per_unit * (1 + self.waste_factor_pct / 100)
        self.line_cost_usd = effective_qty * self.unit_cost_usd
        return self.line_cost_usd


@dataclass
class Supplier:
    """Upstream supplier for raw materials or components."""
    supplier_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    country: str = ""
    region: str = ""  # APAC, EMEA, Americas
    materials_supplied: list[str] = field(default_factory=list)
    lead_time_days: int = 30
    moq_tonnes: float = 1.0
    quality_rating: float = 0.0  # 0-100
    on_time_delivery_pct: float = 0.0  # 0-100
    unit_price_usd: float = 0.0
    price_valid_until: Optional[date] = None
    certifications: list[str] = field(default_factory=list)  # ISO, IATF16949, etc.
    status: SupplyStatus = SupplyStatus.IN_STOCK
    contact_email: str = ""
    notes: str = ""


@dataclass
class InventoryRecord:
    """Current inventory position for a material or component."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sku: str = ""
    material_name: str = ""
    warehouse: str = ""
    quantity_on_hand: float = 0.0
    quantity_reserved: float = 0.0
    quantity_available: float = 0.0
    unit: MaterialUnit = MaterialUnit.KG
    reorder_point: float = 0.0
    reorder_qty: float = 0.0
    unit_cost_usd: float = 0.0
    total_value_usd: float = 0.0
    status: SupplyStatus = SupplyStatus.IN_STOCK
    last_replenished: Optional[date] = None

    def calculate_available(self) -> float:
        self.quantity_available = self.quantity_on_hand - self.quantity_reserved
        self.total_value_usd = self.quantity_on_hand * self.unit_cost_usd
        if self.quantity_available <= 0:
            self.status = SupplyStatus.OUT_OF_STOCK
        elif self.quantity_available <= self.reorder_point:
            self.status = SupplyStatus.LOW
        else:
            self.status = SupplyStatus.IN_STOCK
        return self.quantity_available


@dataclass
class PurchaseOrder:
    """Purchase order for materials or components."""
    po_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    po_number: str = ""
    supplier_id: str = ""
    supplier_name: str = ""
    material_name: str = ""
    quantity: float = 0.0
    unit: MaterialUnit = MaterialUnit.KG
    unit_price_usd: float = 0.0
    total_usd: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    order_date: Optional[date] = None
    expected_delivery: Optional[date] = None
    actual_delivery: Optional[date] = None
    warehouse: str = ""
    notes: str = ""

    def calculate_total(self) -> float:
        self.total_usd = self.quantity * self.unit_price_usd
        return self.total_usd


@dataclass
class PriceHistory:
    """Historical commodity price point."""
    material_name: str = ""
    price_usd: float = 0.0
    unit: MaterialUnit = MaterialUnit.KG
    as_of: Optional[date] = None
    source: str = ""


@dataclass
class ManufacturingBatch:
    """A production batch of cells or packs."""
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    product_sku: str = ""
    product_type: str = ""  # "cell" or "pack"
    chemistry: str = ""
    quantity_produced: int = 0
    quantity_pass: int = 0
    yield_pct: float = 0.0
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    line_name: str = ""
    notes: str = ""

    def calculate_yield(self) -> float:
        if self.quantity_produced > 0:
            self.yield_pct = (self.quantity_pass / self.quantity_produced) * 100
        return self.yield_pct
