"""
Utility functions for CSV parsing, data processing, and regional calculations
"""

import csv
import json
from typing import Dict, List, Optional
from pathlib import Path


def parse_nearmap_csv(file_path: str) -> List[Dict]:
    """
    Parse Nearmap CSV file and return list of dictionaries
    Handles the specific format of the roofing data CSV
    """
    data = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Convert numeric fields
                numeric_fields = [
                    'roof condition summary score', 'pitch', 'height (m)', 'height (ft)',
                    'num stories', 'tile count', 'zinc staining count', 'metal clipped area (sqm)',
                    'gable ratio', 'shingle units needing fix', 'shingle repair area (sqm)',
                    'tile units needing fix', 'tile repair area (sqm)', 'metal units needing fix',
                    'metal repair area (sqm)'
                ]
                
                for field in numeric_fields:
                    if field in row and row[field]:
                        try:
                            row[field] = float(row[field])
                        except ValueError:
                            row[field] = 0.0
                    else:
                        row[field] = 0.0
                
                # Convert boolean fields
                boolean_fields = ['building', 'ponding', 'zinc staining (flag)', 'cracking', 
                                'debris', 'algae', 'roof with temporary repair presence']
                
                for field in boolean_fields:
                    if field in row:
                        row[field] = row[field].upper() == 'TRUE' if row[field] else False
                
                # Normalize key names - convert "roof material" to "roof_material"
                if 'roof material' in row:
                    row['roof_material'] = row['roof material']
                
                data.append(row)
                
    except FileNotFoundError:
        print(f"Error: CSV file not found at {file_path}")
        return []
    except Exception as e:
        print(f"Error parsing CSV: {e}")
        return []
    
    return data


def validate_csv_structure(data: List[Dict]) -> bool:
    """
    Validate that CSV has required fields for quote calculations
    """
    if not data:
        return False
    
    required_fields = [
        'address', 'roof_material', 'pitch', 'height (ft)',
        'roof condition summary score'
    ]
    
    sample_row = data[0]
    missing_fields = [field for field in required_fields if field not in sample_row]
    
    if missing_fields:
        print(f"Missing required fields: {missing_fields}")
        return False
    
    return True


def get_csv_summary(data: List[Dict]) -> Dict:
    """
    Generate summary statistics for the CSV data
    """
    if not data:
        return {}
    
    # Count by entity type
    entity_counts = {}
    for row in data:
        entity = row.get('entity', 'unknown')
        entity_counts[entity] = entity_counts.get(entity, 0) + 1
    
    # Material distribution
    material_counts = {}
    for row in data:
        material = row.get('roof_material', 'unknown')
        material_counts[material] = material_counts.get(material, 0) + 1
    
    # Condition score statistics
    condition_scores = [row.get('roof condition summary score', 0) for row in data if row.get('roof condition summary score')]
    avg_condition = sum(condition_scores) / len(condition_scores) if condition_scores else 0
    
    return {
        'total_records': len(data),
        'entity_breakdown': entity_counts,
        'material_breakdown': material_counts,
        'average_condition_score': round(avg_condition, 2),
        'unique_addresses': len(set(row.get('address', '') for row in data))
    }


def save_quotes_to_json(quotes: List, output_path: str) -> bool:
    """
    Save quote results to JSON file
    """
    try:
        # Convert QuoteResult objects to dictionaries
        quotes_data = []
        for quote in quotes:
            if hasattr(quote, 'to_dict'):
                quotes_data.append(quote.to_dict())
            else:
                quotes_data.append(quote)
        
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(quotes_data, file, indent=2, default=str)
        
        return True
    except Exception as e:
        print(f"Error saving quotes: {e}")
        return False


def load_roofer_profile(file_path: str) -> Optional[Dict]:
    """
    Load roofer profile from JSON file
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading roofer profile: {e}")
        return None


def save_roofer_profile(profile: Dict, file_path: str) -> bool:
    """
    Save roofer profile to JSON file
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(profile, file, indent=2)
        return True
    except Exception as e:
        print(f"Error saving roofer profile: {e}")
        return False


def format_currency(amount: float) -> str:
    """
    Format currency amount for display
    """
    return f"${amount:,.2f}"


def format_quote_range(min_quote: float, max_quote: float) -> str:
    """
    Format quote range for display
    """
    return f"${min_quote:,.0f} - ${max_quote:,.0f}"


def get_roof_material_display_name(material: str) -> str:
    """
    Get display-friendly name for roof material
    """
    material_names = {
        'asphalt': 'Asphalt Shingles',
        'shingle': 'Shingles',
        'metal': 'Metal Roofing',
        'tile': 'Tile Roofing',
        'concrete': 'Concrete Tiles'
    }
    return material_names.get(material.lower(), material.title())


def validate_roofer_profile(profile_data: Dict) -> List[str]:
    """
    Validate roofer profile data and return list of errors
    """
    errors = []
    
    required_fields = [
        'business_name', 'license_id', 'primary_zip_code', 'email',
        'labor_rate', 'daily_productivity', 'base_crew_size', 'crew_scaling_rule',
        'overhead_percent', 'profit_margin'
    ]
    
    for field in required_fields:
        if field not in profile_data:
            errors.append(f"Missing required field: {field}")
    
    # Validate numeric fields
    numeric_fields = ['labor_rate', 'daily_productivity', 'base_crew_size', 'overhead_percent', 'profit_margin']
    for field in numeric_fields:
        if field in profile_data:
            try:
                value = float(profile_data[field])
                if value < 0:
                    errors.append(f"{field} must be non-negative")
            except (ValueError, TypeError):
                errors.append(f"{field} must be a valid number")
    
    # Validate ZIP code format
    if 'primary_zip_code' in profile_data:
        zip_code = str(profile_data['primary_zip_code'])
        if not zip_code.isdigit() or len(zip_code) != 5:
            errors.append("ZIP code must be 5 digits")
    
    return errors
