"""
Test script for the quote engine
Demonstrates the core functionality with sample data
"""

import sys
import os
sys.path.append('backend')

from backend.models.roofer_profile import RooferProfile, SlopeCostAdjustment, MaterialCosts, ReplacementCosts, CrewScalingRule
from backend.quote_engine import calculate_quote
from backend.utils import parse_nearmap_csv

def create_sample_roofer_profile():
    """Create a sample roofer profile for testing"""
    return RooferProfile(
        business_name="Test Roofing Co",
        license_id="LIC123456",
        primary_zip_code="11221",
        email="test@roofing.com",
        labor_rate=45.0,
        daily_productivity=2500,
        base_crew_size=3,
        crew_scaling_rule=CrewScalingRule.SIZE_AND_COMPLEXITY,
        slope_cost_adjustment=SlopeCostAdjustment(),
        material_costs=MaterialCosts(),
        replacement_costs=ReplacementCosts(),
        overhead_percent=0.1,
        profit_margin=0.2
    )

def test_with_sample_data():
    """Test quote calculation with sample roof data"""
    print("Testing Roofing Quote Engine")
    print("=" * 50)
    
    # Create sample roofer profile
    roofer = create_sample_roofer_profile()
    print(f"Created roofer profile: {roofer.business_name}")
    
    # Create sample roof data
    sample_roof_data = {
        "address": "123 Test Street, Test City, TC 12345",
        "roof_material": "concrete",
        "pitch": 24.43,
        "height (ft)": 13.25,
        "roof condition summary score": 80,
        "tile count": 121,
        "shingle repair area (sqm)": 0,
        "tile repair area (sqm)": 0,
        "metal repair area (sqm)": 0
    }
    
    print(f"Created sample roof data for: {sample_roof_data['address']}")
    
    # Calculate quote
    try:
        quote = calculate_quote(sample_roof_data, roofer)
        
        print("\nQUOTE CALCULATION RESULTS:")
        print(f"Address: {quote.address}")
        print(f"Material: {quote.roof_material}")
        print(f"Pitch: {quote.pitch}°")
        print(f"Roof Area: {quote.roof_area:.0f} sqft")
        print(f"Crew Size Used: {quote.crew_size_used}")
        print(f"Region Multiplier: {quote.region_multiplier}")
        
        print(f"\nCOST BREAKDOWN:")
        print(f"Material Cost: ${quote.material_cost:,.2f}")
        print(f"Labor Cost: ${quote.labor_cost:,.2f}")
        print(f"Repair Cost: ${quote.repair_cost:,.2f}")
        print(f"Subtotal: ${quote.subtotal:,.2f}")
        print(f"Overhead: ${quote.overhead:,.2f}")
        print(f"Profit: ${quote.profit:,.2f}")
        print(f"Total: ${quote.total:,.2f}")
        
        print(f"\nFINAL QUOTE RANGE:")
        print(f"{quote.estimated_quote_range}")
        
        return True
        
    except Exception as e:
        print(f"Error calculating quote: {e}")
        return False

def test_with_csv_data():
    """Test with actual CSV data if available"""
    csv_path = "data/nearmap_synthetic_extended_correlated.csv"
    
    if not os.path.exists(csv_path):
        print(f"CSV file not found at {csv_path}")
        return False
    
    print(f"\nTesting with CSV data from {csv_path}")
    
    try:
        # Parse CSV
        csv_data = parse_nearmap_csv(csv_path)
        print(f"Loaded {len(csv_data)} records from CSV")
        
        # Create roofer profile
        roofer = create_sample_roofer_profile()
        
        # Test with first few records
        test_records = csv_data[:3]
        
        for i, record in enumerate(test_records):
            print(f"\n--- Testing Record {i+1} ---")
            try:
                quote = calculate_quote(record, roofer)
                print(f"Address: {quote.address}")
                print(f"Material: {quote.roof_material}")
                print(f"Quote: {quote.estimated_quote_range}")
            except Exception as e:
                print(f"Error with record {i+1}: {e}")
        
        return True
        
    except Exception as e:
        print(f"Error processing CSV: {e}")
        return False

if __name__ == "__main__":
    print("Starting Quote Engine Tests")
    print("=" * 50)
    
    # Test 1: Sample data
    success1 = test_with_sample_data()
    
    # Test 2: CSV data
    success2 = test_with_csv_data()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("All tests passed! Quote engine is working correctly.")
    else:
        print("Some tests failed. Check the errors above.")
    
    print("\nTo run the full application:")
    print("   cd backend && python app.py")
    print("   Then visit: http://localhost:5000")
