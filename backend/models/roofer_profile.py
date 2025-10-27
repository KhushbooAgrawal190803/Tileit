"""
Roofer Profile Data Models
Defines the schema for roofer business profiles and quote calculations
"""

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum


class CrewScalingRule(Enum):
    SIZE_ONLY = "size_only"
    SIZE_AND_COMPLEXITY = "size_and_complexity"


@dataclass
class SlopeCostAdjustment:
    """Slope-based cost adjustments for different roof pitches"""
    flat_low: float = 0.0      # 0-15 degrees
    moderate: float = 0.1       # 15-30 degrees  
    steep: float = 0.2          # 30-45 degrees
    very_steep: float = 0.3     # >45 degrees
    
    def to_dict(self) -> Dict:
        return {
            "flat_low": self.flat_low,
            "moderate": self.moderate,
            "steep": self.steep,
            "very_steep": self.very_steep
        }


@dataclass
class MaterialCosts:
    """Material costs per square foot for installation"""
    asphalt: float = 4.0
    shingle: float = 4.5
    metal: float = 7.0
    tile: float = 8.0
    concrete: float = 6.0
    
    def to_dict(self) -> Dict:
        return {
            "asphalt": self.asphalt,
            "shingle": self.shingle,
            "metal": self.metal,
            "tile": self.tile,
            "concrete": self.concrete
        }


@dataclass
class ReplacementCosts:
    """Replacement costs per square meter for damaged materials"""
    asphalt: float = 45.0
    shingle: float = 50.0
    metal: float = 90.0
    tile: float = 70.0
    concrete: float = 60.0
    
    def to_dict(self) -> Dict:
        return {
            "asphalt": self.asphalt,
            "shingle": self.shingle,
            "metal": self.metal,
            "tile": self.tile,
            "concrete": self.concrete
        }


@dataclass
class RooferProfile:
    """Complete roofer business profile for quote calculations"""
    
    # Business Information
    business_name: str
    license_id: str
    primary_zip_code: str
    email: str
    
    # Labor Information
    labor_rate: float  # per hour per worker
    daily_productivity: int  # sqft/day per crew
    base_crew_size: int
    crew_scaling_rule: CrewScalingRule
    
    # Cost Adjustments
    slope_cost_adjustment: SlopeCostAdjustment
    material_costs: MaterialCosts
    replacement_costs: ReplacementCosts
    
    # Business Margins
    overhead_percent: float  # e.g., 0.1 for 10%
    profit_margin: float     # e.g., 0.2 for 20%
    
    def to_dict(self) -> Dict:
        """Convert profile to dictionary for JSON serialization"""
        return {
            "business_name": self.business_name,
            "license_id": self.license_id,
            "primary_zip_code": self.primary_zip_code,
            "email": self.email,
            "labor_rate": self.labor_rate,
            "daily_productivity": self.daily_productivity,
            "base_crew_size": self.base_crew_size,
            "crew_scaling_rule": self.crew_scaling_rule.value,
            "slope_cost_adjustment": {
                "flat_low": self.slope_cost_adjustment.flat_low,
                "moderate": self.slope_cost_adjustment.moderate,
                "steep": self.slope_cost_adjustment.steep,
                "very_steep": self.slope_cost_adjustment.very_steep
            },
            "material_costs": {
                "asphalt": self.material_costs.asphalt,
                "shingle": self.material_costs.shingle,
                "metal": self.material_costs.metal,
                "tile": self.material_costs.tile,
                "concrete": self.material_costs.concrete
            },
            "replacement_costs": {
                "asphalt": self.replacement_costs.asphalt,
                "shingle": self.replacement_costs.shingle,
                "metal": self.replacement_costs.metal,
                "tile": self.replacement_costs.tile,
                "concrete": self.replacement_costs.concrete
            },
            "overhead_percent": self.overhead_percent,
            "profit_margin": self.profit_margin
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'RooferProfile':
        """Create profile from dictionary"""
        return cls(
            business_name=data["business_name"],
            license_id=data["license_id"],
            primary_zip_code=data["primary_zip_code"],
            email=data["email"],
            labor_rate=data["labor_rate"],
            daily_productivity=data["daily_productivity"],
            base_crew_size=data["base_crew_size"],
            crew_scaling_rule=CrewScalingRule(data["crew_scaling_rule"]),
            slope_cost_adjustment=SlopeCostAdjustment(**data["slope_cost_adjustment"]),
            material_costs=MaterialCosts(**data["material_costs"]),
            replacement_costs=ReplacementCosts(**data["replacement_costs"]),
            overhead_percent=data["overhead_percent"],
            profit_margin=data["profit_margin"]
        )


@dataclass
class QuoteResult:
    """Result of quote calculation for a single property"""
    address: str
    roof_material: str
    pitch: float
    estimated_quote_range: str  # e.g., "$22,000 - $26,000"
    min_quote: float
    max_quote: float
    region_multiplier: float
    crew_size_used: int
    roof_area: float
    material_cost: float
    labor_cost: float
    repair_cost: float
    subtotal: float
    overhead: float
    profit: float
    total: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "address": self.address,
            "roof_material": self.roof_material,
            "pitch": self.pitch,
            "estimated_quote_range": self.estimated_quote_range,
            "min_quote": self.min_quote,
            "max_quote": self.max_quote,
            "region_multiplier": self.region_multiplier,
            "crew_size_used": self.crew_size_used,
            "roof_area": self.roof_area,
            "material_cost": self.material_cost,
            "labor_cost": self.labor_cost,
            "repair_cost": self.repair_cost,
            "subtotal": self.subtotal,
            "overhead": self.overhead,
            "profit": self.profit,
            "total": self.total
        }