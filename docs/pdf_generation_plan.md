# PDF Report Generation - Implementation Plan

## Overview
Generate professional PDF estimates/reports for each quote, matching the design shown in the reference image.

## Process Flow

### 1. User Generates Quotes
```
User → Generate Quotes → QuoteResult objects created
```

### 2. PDF Generation Request
```
User clicks "Download PDF" → API endpoint → PDF Generator → PDF file returned
```

### 3. PDF Generation Steps
1. **Collect Data**: Combine QuoteResult + RooferProfile + Client Info
2. **Generate PDF**: Use template engine to create PDF
3. **Return PDF**: Stream file to user or save temporarily

## Technical Implementation

### Required Libraries

**Option 1: ReportLab** (Recommended - Most flexible)
```python
pip install reportlab
```

**Option 2: WeasyPrint** (HTML/CSS to PDF - Easier styling)
```python
pip install weasyprint
```

**Option 3: FPDF** (Lightweight)
```python
pip install fpdf2
```

### Recommended: ReportLab + Pillow (for logos/images)
```python
pip install reportlab pillow
```

### Implementation Structure

```
backend/
├── pdf_generator.py          # Core PDF generation logic
├── templates/
│   └── estimate_template.py  # PDF template/styling
└── [existing files]
```

## PDF Content Structure

### 1. Header Section
- **Company Logo** (optional - can use text logo)
- **Company Name**: `roofer.business_name`
- **Title**: "Roof Repair Estimate" or "Roofing Quote"
- **Contact Info**: 
  - Email: `roofer.email`
  - Phone: (if available)
  - Address: (from ZIP code or roofer profile)

### 2. Client Information Section
- **Name**: Extract from address or use "Property Owner"
- **Address**: `quote.address`
- **Phone**: (if available from CSV)
- **Email**: (if available from CSV)

### 3. Estimate Metadata
- **Date**: Current date
- **Reference Number**: `RE-{YYYYMMDD}-{hash}` or sequential ID
- **Valid Until**: Date + 30 days

### 4. Job Description
- **Property Address**: `quote.address`
- **Roof Material**: `quote.roof_material` (capitalized)
- **Roof Area**: `quote.roof_area` sqft
- **Pitch**: `quote.pitch` degrees
- **Crew Size**: `quote.crew_size_used` workers

### 5. Itemized Breakdown Table

| Item | Description | Quantity | Unit Price | Total |
|------|-------------|----------|------------|-------|
| Materials | [Material type] installation materials | [sqft] | $[cost/sqft] | $[material_cost] |
| Labor | Installation and repair labor | [hours] hours | $[labor_rate]/hr | $[labor_cost] |
| Repairs | Material replacement and repairs | [sqft] | $[repair_rate]/sqft | $[repair_cost] |
| Regional Adjustment | Location-based pricing | 1 | [multiplier]x | $[regional_diff] |
| Overhead | Business overhead costs | 1 | [overhead%]% | $[overhead] |
| Profit Margin | Business profit margin | 1 | [profit%]% | $[profit] |
| **Total Estimate** | | | | **$[total]** |

### 6. Terms and Conditions
- Payment terms
- Warranty information
- Validity period
- Scope change clause

### 7. Signature Section
- Signature line
- Printed name
- Date

### 8. Footer/Disclaimer
- "Note: The listed prices are estimates and are subject to change after further inspection"

## API Endpoints to Add

### 1. Generate Single Quote PDF
```python
GET /api/quotes/<quote_id>/pdf
# or
POST /api/quotes/generate-pdf
```

**Response**: PDF file stream with appropriate headers

### 2. Generate Multiple Quotes PDF (Zip)
```python
POST /api/quotes/generate-pdfs-batch
Body: { "quote_ids": [...] }
```

**Response**: ZIP file containing multiple PDFs

## Implementation Steps

### Step 1: Install Dependencies
```bash
pip install reportlab pillow
```

### Step 2: Create PDF Generator Module
- `backend/pdf_generator.py` - Main PDF generation class
- Template matching the design from image

### Step 3: Add Client Info Extraction
- Parse address for client name (if available)
- Store client contact info in quote data structure

### Step 4: Create API Endpoint
- Add route to generate PDF
- Handle file streaming/download

### Step 5: Frontend Integration
- Add "Download PDF" button to quote display
- Handle PDF download in browser

## Data Requirements

### Additional Data Needed for PDF

1. **Client Information** (if not in quote):
   - Name (may need to extract from address)
   - Phone number
   - Email

2. **Roofer Contact Info**:
   - Phone number (add to RooferProfile)
   - Physical address (add to RooferProfile)
   - Logo/image (optional)

3. **Quote Metadata**:
   - Quote ID/Reference number
   - Generation date
   - Validity period

## Design Considerations

### Colors (from image)
- **Primary Red**: #8B3A3A or similar (for headers/accents)
- **Light Blue**: Border accents
- **White**: Background
- **Black**: Text

### Typography
- **Headers**: Bold, larger font
- **Body**: Regular, readable font
- **Numbers**: Bold for totals

### Layout
- Clean, professional design
- Well-spaced sections
- Clear visual hierarchy
- Print-friendly (8.5x11")

## Example Code Structure

```python
# backend/pdf_generator.py
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from datetime import datetime

class EstimatePDFGenerator:
    def __init__(self, quote: QuoteResult, roofer: RooferProfile):
        self.quote = quote
        self.roofer = roofer
        self.page_width, self.page_height = letter
    
    def generate(self, output_path: str = None):
        """Generate PDF and return file path or bytes"""
        # Implementation here
        pass
    
    def _draw_header(self, canvas):
        """Draw header section"""
        pass
    
    def _draw_client_info(self, canvas):
        """Draw client information section"""
        pass
    
    def _draw_itemized_table(self, canvas):
        """Draw itemized breakdown table"""
        pass
    
    def _draw_terms(self, canvas):
        """Draw terms and conditions"""
        pass
```

## File Storage Strategy

### Option 1: Generate on Demand
- Generate PDF when requested
- No storage needed
- Slower but saves space

### Option 2: Pre-generate and Cache
- Generate PDF when quote is created
- Store in `pdfs/` directory
- Faster but uses storage

### Recommended: Hybrid Approach
- Generate on first request
- Cache for 24 hours
- Clean up old PDFs periodically

## Next Steps

1. ✅ Review quote data structure
2. ⏳ Choose PDF library (ReportLab recommended)
3. ⏳ Implement PDF generator class
4. ⏳ Add API endpoint
5. ⏳ Update RooferProfile model (add phone/address)
6. ⏳ Create PDF template matching design
7. ⏳ Test PDF generation
8. ⏳ Add frontend download button
9. ⏳ Add batch PDF generation (optional)

