# 🏠 RoofingQuote Pro - Professional Dashboard

A comprehensive roofing quote generation platform for roofing companies. Generate accurate quotes for thousands of properties using your business profile and pricing models.

## Features

- **Professional Authentication**: Secure login/registration for roofing companies
- **Step-by-Step Business Setup**: Intuitive wizard to configure all business parameters
- **Smart Quote Engine**: Calculate quotes based on:
  - Labor rates and crew sizing
  - Slope difficulty adjustments
  - Material and replacement costs
  - Regional pricing multipliers
  - Overhead and profit margins
- **Real-Time Dashboard**: Monitor quotes, properties, and business metrics
- **No Data Upload Required**: Uses pre-loaded property database (25,000+ properties)

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Test the Quote Engine
```bash
python test_quote_engine.py
```

### 3. Run the Application
```bash
cd backend
python app.py
```

### 4. Open in Browser
Visit: http://localhost:5000

## Project Structure

```
/roofing-quote-gen/
├── /backend/
│   ├── app.py                 # Flask API server
│   ├── quote_engine.py       # Core quote calculation logic
│   ├── utils.py              # CSV parsing and utilities
│   └── models/
│       └── roofer_profile.py # Data models
├── /data/
│   └── nearmap_synthetic_extended_correlated.csv
├── /docs/
│   └── roofing_quote_context.md
└── test_quote_engine.py      # Test script
```

## API Endpoints

- `POST /api/roofer/register` - Register new roofer profile
- `GET /api/roofer/<profile_id>` - Get roofer profile
- `POST /api/csv/upload` - Upload CSV file
- `POST /api/quotes/calculate` - Calculate quotes
- `GET /api/quotes/<profile_id>/<upload_id>` - Get calculated quotes

## Quote Calculation Algorithm

The system calculates quotes using:

1. **Material Costs**: Based on roof area and material type
2. **Labor Costs**: Dynamic crew sizing based on project complexity
3. **Slope Adjustments**: Extra charges for steep roofs
4. **Repair Costs**: Additional costs for damaged materials
5. **Regional Multipliers**: Location-based cost adjustments
6. **Overhead & Profit**: Business margins

## Sample Output

```
Address: 123 Test Street, Test City, TC 12345
Material: concrete
Pitch: 24.43°
Quote Range: $1,163 - $1,487
Crew Size: 3 workers
Region Multiplier: 1.25x
```

## Technical Details

- **Backend**: Flask with CORS support
- **Data Models**: Structured roofer profiles and quote results
- **CSV Processing**: Handles Nearmap data format
- **Regional Pricing**: ZIP code-based cost multipliers
- **Quote Ranges**: 90%-115% of calculated total

## Future Enhancements

- Nearmap API integration
- Real-time regional pricing
- Machine learning optimization
- Advanced authentication
- Mobile app support

## License

MIT License - See LICENSE file for details
