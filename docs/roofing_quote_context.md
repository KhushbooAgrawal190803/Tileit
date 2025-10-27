# Roofing Quote Generator — Technical Context

## 1. Purpose
This app allows roofing companies to:
• Create verified business accounts
• Upload a Nearmap CSV containing roof data
• Receive an aggregated quote range (min–max) for each property

The goal is to generate quotes that factor in:
• Roof slope, height, and shape
• Material and replacement costs
• Labor, crew scaling, and regional price variations
• Overheads and profit margin

## 2. System Flow Summary
```
[ Roofer Registration ] 
      ↓ 
[ Business Profile Setup ] 
      ↓ 
[ CSV Upload (Nearmap Data) ] 
      ↓ 
[ Quote Engine ] 
      ↓ 
[ Aggregated Quote Range Output ]
```

## 3. Roofer Setup Questionnaire (Inputs)

### Business Info (Required)
| Field | Type | Purpose |
|-------|------|---------|
| business_name | string | Display + verification |
| license_id | string | Required legal identifier |
| primary_zip_code | string | Determines region multiplier |
| email | string | Login |
| password | string | Authentication |

### Labor Information
| Question | Variable | Type | Example |
|----------|----------|------|---------|
| Labor cost per worker/hour | labor_rate | float | 45 |
| Avg daily productivity (sqft/day/crew) | daily_productivity | int | 2500 |
| Typical base crew size | base_crew_size | int | 3 |
| Crew scaling rule | crew_scaling_rule | enum: "size_only", "size_and_complexity" | "size_and_complexity" |

### Slope Adjustment
Ask: "For different roof slopes, what extra percentage do you typically charge for labor?"

| Slope Range (°) | Variable Key | Adjustment (%) |
|-----------------|--------------|----------------|
| 0–15° (Flat/Low) | flat_low | 0 |
| 15–30° (Moderate) | moderate | 10 |
| 30–45° (Steep) | steep | 20 |
| >45° (Very Steep) | very_steep | 30 |

### Material & Replacement Costs
| Material | material_costs ($/sqft) | replacement_costs ($/sqm) |
|----------|------------------------|---------------------------|
| Asphalt | 4.0 | 45 |
| Shingle | 4.5 | 50 |
| Metal | 7.0 | 90 |
| Tile | 8.0 | 70 |
| Concrete | 6.0 | 60 |

### Overheads & Profit
| Field | Variable | Type | Example |
|-------|----------|------|---------|
| Overhead % | overhead_percent | float | 0.1 |
| Profit Margin % | profit_margin | float | 0.2 |

## 4. Quote Engine — Core Algorithm

### Inputs
• Roofer profile (JSON)
• Nearmap CSV row (each roof record)

### Derived Fields
If not directly present:
• roof_area: estimated via material + repair area sum
• pitch: slope angle (numeric)
• height_ft: from CSV
• roof_material: categorical (asphalt, tile, etc.)
• roof_condition_summary_score: 0–100
• region_zip: from roofer

### Python-Style Pseudocode
```python
def calculate_quote(row, roofer): 
    # --- 1. Extract key data --- 
    area = row.get("roof_area", 2500) 
    pitch = row.get("pitch", 15) 
    height = row.get("height_ft", 15) 
    material = row.get("roof_material", "asphalt").lower() 
    condition = row.get("roof_condition_summary_score", 80) 
    region = roofer["region_zip"] 

    # --- 2. Base material cost --- 
    material_cost = area * roofer["material_costs"].get(material, 5.0) 

    # --- 3. Dynamic crew size --- 
    crew_size = roofer["base_crew_size"] 
    if area > 3000: crew_size += 1 
    if area > 5000: crew_size += 1 
    if pitch > 30 or height > 25: crew_size += 1 

    # --- 4. Labor cost base --- 
    hours = (area / roofer["daily_productivity"]) * 8 
    labor_cost = hours * roofer["labor_rate"] * crew_size 

    # --- 5. Apply slope difficulty adjustment --- 
    slope = pitch 
    if slope <= 15: 
        slope_factor = roofer["slope_cost_adjustment"]["flat_low"] 
    elif slope <= 30: 
        slope_factor = roofer["slope_cost_adjustment"]["moderate"] 
    elif slope <= 45: 
        slope_factor = roofer["slope_cost_adjustment"]["steep"] 
    else: 
        slope_factor = roofer["slope_cost_adjustment"]["very_steep"] 
    labor_cost *= (1 + slope_factor) 

    # --- 6. Repair costs --- 
    repair_cost = 0 
    for f in ["shingle repair area (sqm)", "tile repair area (sqm)", "metal repair area (sqm)"]: 
        if f in row and row[f] > 0: 
            mat = f.split()[0] 
            rate = roofer["replacement_costs"].get(mat, 50) 
            repair_cost += row[f] * rate 

    # --- 7. Regional multiplier --- 
    regional_multiplier = get_region_multiplier(region) 

    # --- 8. Combine totals --- 
    subtotal = (material_cost + labor_cost + repair_cost) * regional_multiplier 
    overhead = subtotal * roofer["overhead_percent"] 
    profit = (subtotal + overhead) * roofer["profit_margin"] 
    total = subtotal + overhead + profit 

    # --- 9. Output quote range --- 
    return round(total * 0.9, 2), round(total * 1.15, 2) 

def get_region_multiplier(zip_code): 
    high_cost_zips = ["100", "90", "94", "11"] 
    low_cost_zips = ["83", "59", "35", "73"] 
    if str(zip_code).startswith(tuple(high_cost_zips)): 
        return 1.25 
    elif str(zip_code).startswith(tuple(low_cost_zips)): 
        return 0.85 
    return 1.0 
```

### Output Example
```json
{ 
  "address": "4041 Wiggins Mount Suite 592, North Kimberly, NM", 
  "roof_material": "concrete", 
  "pitch": 24.43,
  "estimated_quote_range": "$22,000 - $26,000", 
  "region_multiplier": 0.85, 
  "crew_size_used": 4 
}
```

## 5. Business Logic Notes
• Aggregated Only: No itemized breakdowns; display only range (min–max).
• Slope & Height: Affect both labor cost and crew scaling.
• Condition Score: Could later adjust productivity (worse condition → slower work).
• Region Multiplier: Placeholder; later integrate with cost-of-living or contractor cost API (e.g., HomeAdvisor, RSMeans).
• Future Enhancement: Replace manual CSV upload with Nearmap API call returning same schema.

## 6. Future API Hooks (for Later Versions)
| Feature | Source | Description |
|---------|--------|-------------|
| Live Nearmap Data | Nearmap API | Replace CSV upload |
| Regional Pricing Feed | External API | Real-time cost adjustment |
| ML Optimization | Internal model | Learn actual vs. predicted quote delta |
| Authentication | JWT / OAuth | Secure business logins |

## 7. File Structure (recommended for Cursor project)
```
/roofing-quote-gen/ 
│ 
├── /backend/ 
│   ├── app.py                # Flask/FastAPI app 
│   ├── quote_engine.py       # logic from pseudocode above 
│   ├── utils.py              # helpers (region multipliers, CSV parser) 
│   └── models/ 
│       └── roofer_profile.py # schema for onboarding data 
│ 
├── /frontend/ 
│   ├── pages/ 
│   │   ├── signup.jsx 
│   │   ├── onboarding.jsx 
│   │   ├── upload.jsx 
│   │   └── quotes.jsx 
│   └── components/ 
│       ├── RangeDisplayCard.jsx 
│       ├── CsvPreviewTable.jsx 
│       └── SlopeQuestionnaire.jsx 
├── /data/ 
│   └── nearmap_synthetic_extended_correlated.csv 
│ 
└── /docs/ 
    └── roofing_quote_context.md   # this file 
```
