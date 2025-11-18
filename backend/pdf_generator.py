"""
PDF Report Generator for Roofing Quotes
Generates professional PDF estimates matching the design specification
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from datetime import datetime
from typing import Optional
import os

from models.roofer_profile import RooferProfile, QuoteResult


class EstimatePDFGenerator:
    """Generates professional PDF estimates for roofing quotes"""
    
    # Color scheme matching the design
    PRIMARY_RED = colors.HexColor('#8B3A3A')
    WHITE = colors.white
    BLACK = colors.black
    
    def __init__(self, quote: QuoteResult, roofer: RooferProfile, 
                 client_name: Optional[str] = None,
                 client_phone: Optional[str] = None,
                 client_email: Optional[str] = None,
                 roofer_phone: Optional[str] = None,
                 roofer_address: Optional[str] = None):
        """
        Initialize PDF generator
        """
        self.quote = quote
        self.roofer = roofer
        self.client_name = client_name or "Property Owner"
        self.client_phone = client_phone or "N/A"
        self.client_email = client_email or "N/A"
        self.roofer_phone = roofer_phone or "N/A"
        self.roofer_address = roofer_address or f"{roofer.primary_zip_code}"
        
        # Generate reference number
        date_str = datetime.now().strftime("%Y%m%d")
        hash_str = abs(hash(quote.address)) % 10000
        self.reference_number = f"RE-{date_str}-{hash_str:04d}"
    
    def generate(self, output_path: str) -> str:
        """
        Generate PDF file - Compact single page design
        """
        # Create directory if it doesn't exist
        dir_path = os.path.dirname(output_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        else:
            output_path = os.path.join('.', os.path.basename(output_path))
        
        # Create PDF document with smaller margins for more space
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.4*inch,
            bottomMargin=0.4*inch
        )
        
        # Build PDF content
        story = []
        story.extend(self._build_header())
        story.extend(self._build_metadata())
        story.extend(self._build_job_description())
        story.extend(self._build_itemized_table())
        story.extend(self._build_terms_signature())
        
        # Generate PDF
        doc.build(story)
        
        return output_path
    
    def _build_header(self):
        """Build improved header section with better formatting"""
        elements = []
        
        # Multi-row header for better organization
        # Row 1: Company name (left) and Title (right)
        header_row1_data = [[self.roofer.business_name, 'Roof Repair Estimate']]
        header_row1_table = Table(header_row1_data, colWidths=[4*inch, 3*inch])
        header_row1_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.PRIMARY_RED),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 16),
            ('FONTSIZE', (1, 0), (1, 0), 18),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (0, 0), 12),
            ('RIGHTPADDING', (0, 0), (0, 0), 8),
            ('LEFTPADDING', (1, 0), (1, 0), 8),
            ('RIGHTPADDING', (1, 0), (1, 0), 12),
        ]))
        elements.append(header_row1_table)
        
        # Row 2: Contact information
        contact_info = f"{self.roofer_phone} | {self.roofer_address} | {self.roofer.email}"
        header_row2_data = [[contact_info]]
        header_row2_table = Table(header_row2_data, colWidths=[7*inch])
        header_row2_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.PRIMARY_RED),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(header_row2_table)
        elements.append(Spacer(1, 0.15*inch))
        
        return elements
    
    def _build_client_info(self):
        """Build compact client information section"""
        styles = getSampleStyleSheet()
        
        elements = []
        
        # Section title
        title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=self.BLACK,
            spaceAfter=6,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )
        elements.append(Paragraph("<b>Client Information</b>", title_style))
        
        # Client info table - compact
        client_data = [
            ['Name', self.client_name, 'Phone Number', self.client_phone],
            ['Address', self.quote.address, 'Email', self.client_email]
        ]
        
        client_table = Table(client_data, colWidths=[1.0*inch, 2.7*inch, 1.0*inch, 2.3*inch])
        client_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.PRIMARY_RED),
            ('BACKGROUND', (2, 0), (2, -1), self.PRIMARY_RED),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.white),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('BACKGROUND', (3, 0), (3, -1), colors.white),
            ('TEXTCOLOR', (1, 0), (1, -1), self.BLACK),
            ('TEXTCOLOR', (3, 0), (3, -1), self.BLACK),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(client_table)
        elements.append(Spacer(1, 0.1*inch))
        
        return elements
    
    def _build_metadata(self):
        """Build compact estimate date and reference number"""
        elements = []
        
        date_str = datetime.now().strftime("%B %d, %Y")
        metadata_text = f"Date: {date_str} | Reference Number: {self.reference_number}"
        
        metadata_data = [[metadata_text]]
        metadata_table = Table(metadata_data, colWidths=[7*inch])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.PRIMARY_RED),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(metadata_table)
        elements.append(Spacer(1, 0.12*inch))
        
        return elements
    
    def _build_job_description(self):
        """Build compact job description"""
        styles = getSampleStyleSheet()
        
        elements = []
        
        title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=self.BLACK,
            spaceAfter=5,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )
        elements.append(Paragraph("<b>Job Description:</b>", title_style))
        
        material_name = self.quote.roof_material.capitalize()
        
        # Compact description
        description = (
            f"This estimate covers the inspection, repair, and replacement of materials "
            f"for the roof of the property located at {self.quote.address}. "
            f"Our team will conduct a thorough inspection to identify any damage and "
            f"provide the necessary repairs. The roof is made of {material_name} material, "
            f"covers approximately {self.quote.roof_area:.0f} square feet, and has a pitch "
            f"of {self.quote.pitch:.1f} degrees. The estimated crew size for this project "
            f"is {self.quote.crew_size_used} workers."
        )
        
        desc_style = ParagraphStyle(
            'Description',
            parent=styles['Normal'],
            fontSize=9,
            textColor=self.BLACK,
            spaceAfter=8,
            alignment=TA_LEFT,
            leading=11
        )
        elements.append(Paragraph(description, desc_style))
        
        return elements
    
    def _build_itemized_table(self):
        """Build compact itemized breakdown table"""
        elements = []
        
        # Calculate quantities and unit prices
        material_qty = f"{self.quote.roof_area:.0f} sqft"
        if self.quote.roof_area > 0:
            material_unit_price = f"${self.quote.material_cost / self.quote.roof_area:.2f}/sqft"
        else:
            material_unit_price = "$0.00/sqft"
        
        hours = (self.quote.roof_area / (self.roofer.daily_productivity / 8)) if self.roofer.daily_productivity > 0 else 0
        labor_qty = f"{hours:.1f} hours"
        labor_unit_price = f"${self.roofer.labor_rate:.2f}/hr"
        
        repair_qty = "As needed" if self.quote.repair_cost > 0 else "-"
        repair_unit_price = "-" if self.quote.repair_cost == 0 else "Per sqft"
        
        regional_diff = self.quote.subtotal - (self.quote.material_cost + self.quote.labor_cost + self.quote.repair_cost)
        
        # Table data
        table_data = [
            ['Item', 'Description', 'Quantity', 'Unit Price', 'Total'],
            [
                'Roof Inspection',
                'Inspection of roof for damage and leaks',
                '1',
                '$150',
                '$150'
            ],
            [
                'Materials',
                f'{self.quote.roof_material.capitalize()} installation materials',
                material_qty,
                material_unit_price,
                f'${self.quote.material_cost:,.2f}'
            ],
            [
                'Labor',
                'Installation and repair labor',
                labor_qty,
                labor_unit_price,
                f'${self.quote.labor_cost:,.2f}'
            ],
        ]
        
        # Add repair row if applicable
        if self.quote.repair_cost > 0:
            table_data.append([
                'Repairs',
                'Material replacement and repairs',
                repair_qty,
                repair_unit_price,
                f'${self.quote.repair_cost:,.2f}'
            ])
        
        # Add regional adjustment if applicable
        if abs(regional_diff) > 0.01:
            table_data.append([
                'Regional Adjustment',
                'Location-based pricing adjustment',
                '1',
                f'{self.quote.region_multiplier:.2f}x',
                f'${regional_diff:,.2f}'
            ])
        
        # Add overhead and profit
        table_data.append([
            'Overhead',
            'Business overhead costs',
            '1',
            f'{self.roofer.overhead_percent*100:.0f}%',
            f'${self.quote.overhead:,.2f}'
        ])
        
        table_data.append([
            'Profit Margin',
            'Business profit margin',
            '1',
            f'{self.roofer.profit_margin*100:.0f}%',
            f'${self.quote.profit:,.2f}'
        ])
        
        # Total row
        table_data.append([
            'Total Estimate',
            '',
            '',
            '',
            f'${self.quote.total:,.2f}'
        ])
        
        # Create table with compact widths
        itemized_table = Table(table_data, colWidths=[1.1*inch, 2.4*inch, 0.85*inch, 1.0*inch, 1.05*inch])
        
        # Style table - improved alignment
        itemized_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), self.PRIMARY_RED),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),      # Item column - left
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),      # Description column - left
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),    # Quantity column - center
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),     # Unit Price column - right
            ('ALIGN', (4, 0), (4, -1), 'RIGHT'),     # Total column - right
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Data rows
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -2), 8),
            ('TEXTCOLOR', (0, 1), (-1, -2), self.BLACK),
            ('BACKGROUND', (0, 1), (-1, -2), colors.white),
            
            # Total row - red background on total column only
            ('BACKGROUND', (0, -1), (3, -1), colors.white),
            ('BACKGROUND', (4, -1), (4, -1), self.PRIMARY_RED),
            ('TEXTCOLOR', (0, -1), (3, -1), self.BLACK),
            ('TEXTCOLOR', (4, -1), (4, -1), colors.white),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 10),
            
            # Cell padding - compact
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (0, -1), 6),
            ('RIGHTPADDING', (0, 0), (0, -1), 6),
            ('LEFTPADDING', (1, 0), (1, -1), 6),
            ('RIGHTPADDING', (1, 0), (1, -1), 6),
            ('LEFTPADDING', (2, 0), (2, -1), 4),
            ('RIGHTPADDING', (2, 0), (2, -1), 4),
            ('LEFTPADDING', (3, 0), (3, -1), 4),
            ('RIGHTPADDING', (3, 0), (3, -1), 6),
            ('LEFTPADDING', (4, 0), (4, -1), 4),
            ('RIGHTPADDING', (4, 0), (4, -1), 6),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(itemized_table)
        elements.append(Spacer(1, 0.15*inch))
        
        return elements
    
    def _build_terms_signature(self):
        """Build compact terms, signature, and disclaimer section"""
        styles = getSampleStyleSheet()
        
        elements = []
        
        # Terms and Conditions
        title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=self.BLACK,
            spaceAfter=5,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )
        elements.append(Paragraph("<b>Terms and Conditions:</b>", title_style))
        
        terms = [
            "Full payment is required upon completion of the job.",
            "Estimated prices may change based on necessary scope changes.",
            "Warranty is provided for work performed for a certain period."
        ]
        
        term_style = ParagraphStyle(
            'Term',
            parent=styles['Normal'],
            fontSize=8,
            textColor=self.BLACK,
            spaceAfter=3,
            alignment=TA_LEFT,
            leftIndent=15,
            leading=10
        )
        
        for i, term in enumerate(terms, 1):
            elements.append(Paragraph(f"{i}. {term}", term_style))
        
        elements.append(Spacer(1, 0.1*inch))
        
        # Signature section - compact
        sig_data = [
            ['Signature:', '_________________________', '', 'Printed Name:', self.client_name]
        ]
        
        sig_table = Table(sig_data, colWidths=[0.8*inch, 2.0*inch, 0.5*inch, 0.9*inch, 2.8*inch])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(sig_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # Disclaimer - compact
        disclaimer_text = "Note: The listed prices are estimates and are subject to change after further inspection."
        
        disclaimer_data = [[disclaimer_text]]
        disclaimer_table = Table(disclaimer_data, colWidths=[3.5*inch])
        disclaimer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.PRIMARY_RED),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(disclaimer_table)
        
        return elements


def generate_pdf_for_quote(quote: QuoteResult, roofer: RooferProfile, 
                           output_dir: str = "pdfs",
                           **kwargs) -> str:
    """
    Convenience function to generate PDF for a quote
    """
    generator = EstimatePDFGenerator(quote, roofer, **kwargs)
    
    # Ensure output_dir is absolute or relative to project root
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(backend_dir)
    
    # Create absolute path
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(project_root, output_dir)
    
    # Ensure directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename
    filename = f"estimate_{abs(hash(quote.address)) % 10000:04d}_{datetime.now().strftime('%Y%m%d')}.pdf"
    output_path = os.path.join(output_dir, filename)
    
    return generator.generate(output_path)
