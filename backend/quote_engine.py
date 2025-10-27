"""
Core Quote Engine Algorithm
Implements the roofing quote calculation logic based on roofer profiles and roof data
"""

from typing import Dict, Tuple, List
import math
from models.roofer_profile import RooferProfile, QuoteResult


def get_region_multiplier(zip_code: str) -> float:
    """
    Calculate regional cost multiplier based on ZIP code
    Simple placeholder implementation - can be enhanced with external API
    """
    high_cost_zips = ["100", "90", "94", "11"]
    low_cost_zips = ["83", "59", "35", "73"]
    
    zip_prefix = str(zip_code)[:2]
    
    if zip_prefix in high_cost_zips:
        return 1.25
    elif zip_prefix in low_cost_zips:
        return 0.85
    else:
        return 1.0


def calculate_crew_size(roof_area: float, pitch: float, height_ft: float, 
                       base_crew_size: int, crew_scaling_rule: str) -> int:
    """
    Calculate dynamic crew size based on project complexity
    """
    crew_size = base_crew_size
    
    # Size-based scaling
    if roof_area > 3000:
        crew_size += 1
    if roof_area > 5000:
        crew_size += 1
    
    # Complexity-based scaling (if enabled)
    if crew_scaling_rule == "size_and_complexity":
        if pitch > 30 or height_ft > 25:
            crew_size += 1
    
    return crew_size


def get_slope_factor(pitch: float, slope_adjustments: Dict[str, float]) -> float:
    """
    Get slope difficulty factor based on roof pitch
    """
    if pitch <= 15:
        return slope_adjustments["flat_low"]
    elif pitch <= 30:
        return slope_adjustments["moderate"]
    elif pitch <= 45:
        return slope_adjustments["steep"]
    else:
        return slope_adjustments["very_steep"]


def calculate_material_cost(roof_area: float, material: str, material_costs: Dict[str, float]) -> float:
    """
    Calculate base material cost for roof installation
    """
    material = material.lower()
    cost_per_sqft = material_costs.get(material, 5.0)  # Default fallback
    return roof_area * cost_per_sqft


def calculate_labor_cost(roof_area: float, pitch: float, height_ft: float,
                        labor_rate: float, daily_productivity: int, base_crew_size: int,
                        crew_scaling_rule: str, slope_adjustments: Dict[str, float]) -> Tuple[float, int]:
    """
    Calculate labor cost including crew scaling and slope adjustments
    Returns (labor_cost, crew_size_used)
    """
    # Calculate crew size
    crew_size = calculate_crew_size(roof_area, pitch, height_ft, base_crew_size, crew_scaling_rule)
    
    # Calculate hours needed
    hours = (roof_area / daily_productivity) * 8  # 8 hours per day
    
    # Base labor cost
    labor_cost = hours * labor_rate * crew_size
    
    # Apply slope difficulty adjustment
    slope_factor = get_slope_factor(pitch, slope_adjustments)
    labor_cost *= (1 + slope_factor)
    
    return labor_cost, crew_size


def calculate_repair_cost(row: Dict, replacement_costs: Dict[str, float]) -> float:
    """
    Calculate repair costs for damaged materials
    """
    repair_cost = 0.0
    
    repair_fields = [
        "shingle repair area (sqm)",
        "tile repair area (sqm)", 
        "metal repair area (sqm)"
    ]
    
    for field in repair_fields:
        if field in row and row[field] > 0:
            # Extract material type from field name
            material_type = field.split()[0]
            rate = replacement_costs.get(material_type, 50.0)  # Default fallback
            repair_cost += row[field] * rate
    
    return repair_cost


def estimate_roof_area(row: Dict) -> float:
    """
    Estimate roof area from available data
    Uses repair areas and tile count as indicators
    """
    # Try to get explicit area first
    if "roof_area" in row:
        return float(row["roof_area"])
    
    # Estimate from repair areas
    repair_areas = [
        "shingle repair area (sqm)",
        "tile repair area (sqm)",
        "metal repair area (sqm)"
    ]
    
    total_repair_area = sum(row.get(field, 0) for field in repair_areas if field in row)
    
    # If we have repair areas, estimate total area (assume 10-20% needs repair)
    if total_repair_area > 0:
        estimated_area = total_repair_area * 8  # Assume 12.5% needs repair
        return estimated_area * 10.764  # Convert sqm to sqft
    
    # Fallback: estimate from tile count
    if "tile count" in row and row["tile count"] > 0:
        tile_count = row["tile count"]
        # Assume average tile is 1 sqft
        return float(tile_count)
    
    # Default fallback
    return 2500.0


def calculate_quote(row: Dict, roofer: RooferProfile) -> QuoteResult:
    """
    Main quote calculation function
    Implements the core algorithm from the technical specification
    """
    # Extract key data with fallbacks
    roof_area = estimate_roof_area(row)
    pitch = float(row.get("pitch", 15))
    height_ft = float(row.get("height (ft)", 15))
    material = row.get("roof_material", "asphalt").lower()
    condition = float(row.get("roof condition summary score", 80))
    address = row.get("address", "Unknown Address")
    
    # 1. Base material cost
    material_cost = calculate_material_cost(roof_area, material, roofer.material_costs.to_dict())
    
    # 2. Labor cost with crew scaling and slope adjustment
    labor_cost, crew_size_used = calculate_labor_cost(
        roof_area, pitch, height_ft,
        roofer.labor_rate, roofer.daily_productivity, roofer.base_crew_size,
        roofer.crew_scaling_rule.value, roofer.slope_cost_adjustment.to_dict()
    )
    
    # 3. Repair costs
    repair_cost = calculate_repair_cost(row, roofer.replacement_costs.to_dict())
    
    # 4. Regional multiplier
    regional_multiplier = get_region_multiplier(roofer.primary_zip_code)
    
    # 5. Combine totals
    subtotal = (material_cost + labor_cost + repair_cost) * regional_multiplier
    overhead = subtotal * roofer.overhead_percent
    profit = (subtotal + overhead) * roofer.profit_margin
    total = subtotal + overhead + profit
    
    # 6. Generate quote range
    min_quote = total * 0.9
    max_quote = total * 1.15
    
    # Format quote range
    quote_range = f"${min_quote:,.0f} - ${max_quote:,.0f}"
    
    return QuoteResult(
        address=address,
        roof_material=material,
        pitch=pitch,
        estimated_quote_range=quote_range,
        min_quote=round(min_quote, 2),
        max_quote=round(max_quote, 2),
        region_multiplier=regional_multiplier,
        crew_size_used=crew_size_used,
        roof_area=roof_area,
        material_cost=round(material_cost, 2),
        labor_cost=round(labor_cost, 2),
        repair_cost=round(repair_cost, 2),
        subtotal=round(subtotal, 2),
        overhead=round(overhead, 2),
        profit=round(profit, 2),
        total=round(total, 2)
    )


def process_csv_quotes(csv_data: List[Dict], roofer: RooferProfile) -> List[QuoteResult]:
    """
    Process entire CSV dataset and generate quotes for all properties
    """
    quotes = []
    
    for row in csv_data:
        try:
            quote = calculate_quote(row, roofer)
            quotes.append(quote)
        except Exception as e:
            print(f"Error processing row: {e}")
            continue
    
    return quotes
