# Battery ERP — Pricing Engine
"""
Commodity price tracking and cell/pack cost estimation.
Integrates with Twelve Data, FRED, and AlphaVantage APIs.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
from datetime import datetime, date
from typing import Optional


# Default battery material price table (USD/kg unless noted)
# Sources: Benchmark Mineral Intelligence, Fastmarkets, Trading Economics
DEFAULT_MATERIAL_PRICES = {
    # Cathode materials
    "lithium_carbonate": 12.50,       # $/kg (battery grade, 99.5%)
    "lithium_hydroxide": 13.80,       # $/kg (battery grade)
    "nickel": 16.50,                  # $/kg (Class 1, LME)
    "cobalt": 24.00,                  # $/kg (LME)
    "manganese": 2.80,                # $/kg (electrolytic)
    "iron_phosphate": 1.50,           # $/kg
    "aluminum": 2.40,                 # $/kg (LME)
    # Anode materials
    "graphite_anode": 12.00,          # $/kg (spherical, battery grade)
    "silicon_anode": 45.00,           # $/kg (nano-silicon composite)
    # Electrolyte & other
    "electrolyte": 8.50,              # $/kg (LiPF6-based)
    "copper_foil": 9.00,              # $/kg
    "aluminum_foil": 3.20,            # $/kg
    "separator": 15.00,               # $/kg (PE/PP ceramic-coated)
    "binder_pvdf": 25.00,             # $/kg
    "conductive_additive": 8.00,      # $/kg (carbon black / CNT)
    # Pack-level
    "pack_casing_aluminum": 3.50,     # $/kg
    "bms_module": 15.00,              # $/each
    "thermal_coolant": 5.00,          # $/kg
    "wiring_harness": 6.00,           # $/kg
    "insulation": 4.00,               # $/kg
    "pack_structural_adhesive": 8.00, # $/kg
}


def get_material_price_table() -> dict[str, float]:
    """Return the default material price table."""
    return dict(DEFAULT_MATERIAL_PRICES)


def update_prices_from_alpha_vantage(
    current_prices: dict[str, float],
    api_key: str,
    mappings: Optional[dict[str, str]] = None,
) -> dict[str, dict]:
    """Fetch commodity prices from AlphaVantage and merge into price table.

    Args:
        current_prices: existing price table to merge into
        api_key: AlphaVantage API key
        mappings: {material_name: AV_function} e.g. {"nickel": "NICKEL"}

    Returns:
        {"updated": {mat: new_price}, "unchanged": [...], "errors": [...]}
    """
    if mappings is None:
        mappings = {
            "nickel": "NICKEL",
            "cobalt": "COBALT",
            "aluminum": "ALUMINUM",
            "copper_foil": "COPPER",
        }

    # AlphaVantage commodity functions
    commodity_tickers = {
        "NICKEL": "NICKEL",
        "COBALT": "COBALT",
        "ALUMINUM": "ALUMINUM",
        "COPPER": "COPPER",
    }

    result = {"updated": {}, "unchanged": [], "errors": []}

    for material_name, av_func in mappings.items():
        if av_func not in commodity_tickers:
            result["errors"].append(f"{material_name}: unknown AV function {av_func}")
            continue

        # AlphaVantage uses FX_INTRADAY for metals
        params = {
            "function": "COMMODITY_DAILY",
            "symbol": av_func,
            "interval": "daily",
            "apikey": api_key,
        }
        url = f"https://www.alphavantage.co/query?{urllib.parse.urlencode(params)}"

        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "Note" in data:
                result["errors"].append(f"{material_name}: AV rate limited")
                continue
            if "Error Message" in data:
                result["errors"].append(f"{material_name}: AV error")
                continue

            # Parse latest price from daily data
            time_series = data.get("Time Series (Daily)", {})
            if time_series:
                latest_date = sorted(time_series.keys())[-1]
                latest_data = time_series[latest_date]
                # AlphaVantage commodity prices are in $/ton for some metals
                price_str = latest_data.get("4. close", "0")
                price = float(price_str)

                # Convert $/tonne to $/kg if needed
                if price > 100:
                    price = price / 1000

                current_prices[material_name] = price
                result["updated"][material_name] = round(price, 2)
            else:
                result["unchanged"].append(material_name)
        except Exception as e:
            result["errors"].append(f"{material_name}: {e}")

    return result


def update_prices_from_fred(
    current_prices: dict[str, float],
    api_key: str,
) -> dict[str, dict]:
    """Fetch macro economic indicators from FRED.

    Not direct commodity prices, but useful for context:
    - DGS10 (10Y Treasury) — discount rate for NPV
    - PPIACO (PPI All Commodities) — inflation gauge
    """
    series_map = {
        "DGS10": "10-Year Treasury Yield",
        "PPIACO": "PPI All Commodities",
    }

    result = {"fetched": {}, "errors": []}

    for series_id, label in series_map.items():
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={api_key}"
            f"&file_type=json&sort_order=desc&limit=1"
        )
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            obs = data.get("observations", [])
            if obs:
                value = float(obs[0].get("value", 0))
                result["fetched"][label] = {
                    "value": value,
                    "as_of": obs[0].get("date", ""),
                }
        except Exception as e:
            result["errors"].append(f"FRED {series_id}: {e}")

    return result


def calculate_cell_cost_summary(
    chemistry: str,
    cell_capacity_ah: float,
    material_prices: Optional[dict[str, float]] = None,
) -> dict:
    """Quick cell cost estimate for a given chemistry.

    Returns:
        {
            "chemistry": "NMC-811",
            "cell_capacity_ah": 50.0,
            "cell_energy_kwh": 0.185,
            "bom_cost_usd": 8.23,
            "cost_per_kwh": 44.49,
            "cathode_pct": 45.2,
            "anode_pct": 22.1,
            "other_pct": 32.7,
            "material_breakdown": {...},
        }
    """
    from ..core.rules import calculate_cell_bom, rollup_bom_cost

    prices = material_prices or DEFAULT_MATERIAL_PRICES
    bom = calculate_cell_bom(chemistry, cell_capacity_ah, prices)
    rollup = rollup_bom_cost(bom)

    cell_energy_kwh = (cell_capacity_ah * 3.7) / 1000

    # Category breakdown
    cathode_materials = {"nickel", "manganese", "cobalt", "lithium_carbonate", "lithium_hydroxide",
                        "iron_phosphate", "aluminum", "silicon_anode"}
    anode_materials = {"graphite_anode"}

    cathode_cost = sum(v for k, v in rollup["material_breakdown"].items() if k in cathode_materials)
    anode_cost = sum(v for k, v in rollup["material_breakdown"].items() if k in anode_materials)
    other_cost = rollup["total_cost_usd"] - cathode_cost - anode_cost

    total = rollup["total_cost_usd"]
    return {
        "chemistry": chemistry,
        "cell_capacity_ah": cell_capacity_ah,
        "cell_energy_kwh": round(cell_energy_kwh, 4),
        "bom_cost_usd": round(total, 4),
        "cost_per_kwh": round(total / cell_energy_kwh, 2) if cell_energy_kwh > 0 else 0,
        "cathode_cost_usd": round(cathode_cost, 4),
        "anode_cost_usd": round(anode_cost, 4),
        "other_cost_usd": round(other_cost, 4),
        "cathode_pct": round((cathode_cost / total) * 100, 1) if total > 0 else 0,
        "anode_pct": round((anode_cost / total) * 100, 1) if total > 0 else 0,
        "other_pct": round((other_cost / total) * 100, 1) if total > 0 else 0,
        "material_breakdown": rollup["material_breakdown"],
        "waste_cost_usd": rollup["waste_cost_usd"],
    }
