"""
Example API Endpoints for PDF Generation
Add these routes to your Flask app to enable PDF generation
"""

from flask import Flask, send_file, jsonify, request
from typing import Optional
import os
import json
from datetime import datetime

from models.roofer_profile import RooferProfile, QuoteResult
from pdf_generator import EstimatePDFGenerator, generate_pdf_for_quote


def add_pdf_routes(app: Flask):
    """
    Add PDF generation routes to Flask app
    
    Usage:
        from backend.pdf_api import add_pdf_routes
        add_pdf_routes(app)
    """
    
    @app.route('/api/quotes/<quote_id>/pdf', methods=['GET'])
    def generate_single_pdf(quote_id):
        """
        Generate PDF for a single quote
        
        Query params:
            - profile_id: Roofer profile ID
            - client_name: Optional client name
            - client_phone: Optional client phone
            - client_email: Optional client email
        
        Returns:
            PDF file download
        """
        try:
            # Get query parameters
            profile_id = request.args.get('profile_id')
            client_name = request.args.get('client_name')
            client_phone = request.args.get('client_phone')
            client_email = request.args.get('client_email')
            
            if not profile_id:
                return jsonify({'error': 'profile_id required'}), 400
            
            # Load roofer profile (adjust based on your storage method)
            # This is an example - adapt to your actual storage
            profile_file = f"profiles/{profile_id}_roofer_profile.json"
            if not os.path.exists(profile_file):
                return jsonify({'error': 'Roofer profile not found'}), 404
            
            with open(profile_file, 'r') as f:
                profile_data = json.load(f)
            
            roofer = RooferProfile.from_dict(profile_data)
            
            # Load quote (adjust based on your storage method)
            # This assumes quotes are stored in a JSON file
            quotes_file = f"quotes/{profile_id}_quotes.json"
            if not os.path.exists(quotes_file):
                return jsonify({'error': 'Quotes not found'}), 404
            
            with open(quotes_file, 'r') as f:
                quotes_data = json.load(f)
            
            # Find quote by ID (you may need to adjust quote_id format)
            quote_dict = None
            if isinstance(quotes_data, list):
                # If quote_id is an index
                try:
                    idx = int(quote_id)
                    if 0 <= idx < len(quotes_data):
                        quote_dict = quotes_data[idx]
                except ValueError:
                    # Search by address hash or other identifier
                    for q in quotes_data:
                        if str(abs(hash(q.get('address', ''))) % 10000) == quote_id:
                            quote_dict = q
                            break
            
            if not quote_dict:
                return jsonify({'error': 'Quote not found'}), 404
            
            # Convert to QuoteResult object
            quote = QuoteResult(**quote_dict)
            
            # Generate PDF
            output_dir = "pdfs"
            os.makedirs(output_dir, exist_ok=True)
            
            pdf_path = generate_pdf_for_quote(
                quote=quote,
                roofer=roofer,
                output_dir=output_dir,
                client_name=client_name,
                client_phone=client_phone,
                client_email=client_email
            )
            
            # Return PDF file
            return send_file(
                pdf_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"Roofing_Estimate_{quote_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
            )
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/quotes/generate-pdf', methods=['POST'])
    def generate_pdf_from_data():
        """
        Generate PDF from quote data sent in request body
        
        Request body:
            {
                "quote": {...quote data...},
                "roofer_profile": {...roofer profile data...},
                "client_name": "Optional",
                "client_phone": "Optional",
                "client_email": "Optional"
            }
        
        Returns:
            PDF file download
        """
        try:
            data = request.get_json()
            
            if 'quote' not in data or 'roofer_profile' not in data:
                return jsonify({'error': 'quote and roofer_profile required'}), 400
            
            # Create objects
            quote = QuoteResult(**data['quote'])
            roofer = RooferProfile.from_dict(data['roofer_profile'])
            
            # Optional client info
            client_name = data.get('client_name')
            client_phone = data.get('client_phone')
            client_email = data.get('client_email')
            
            # Generate PDF
            output_dir = "pdfs"
            os.makedirs(output_dir, exist_ok=True)
            
            pdf_path = generate_pdf_for_quote(
                quote=quote,
                roofer=roofer,
                output_dir=output_dir,
                client_name=client_name,
                client_phone=client_phone,
                client_email=client_email
            )
            
            # Return PDF file
            return send_file(
                pdf_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"Roofing_Estimate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/quotes/batch-pdf', methods=['POST'])
    def generate_batch_pdfs():
        """
        Generate multiple PDFs and return as ZIP file
        
        Request body:
            {
                "profile_id": "...",
                "quote_ids": [0, 1, 2, ...],
                "client_info": {...optional client info...}
            }
        
        Returns:
            ZIP file containing multiple PDFs
        """
        try:
            import zipfile
            import tempfile
            
            data = request.get_json()
            profile_id = data.get('profile_id')
            quote_ids = data.get('quote_ids', [])
            
            if not profile_id:
                return jsonify({'error': 'profile_id required'}), 400
            
            # Load roofer profile
            profile_file = f"profiles/{profile_id}_roofer_profile.json"
            if not os.path.exists(profile_file):
                return jsonify({'error': 'Roofer profile not found'}), 404
            
            with open(profile_file, 'r') as f:
                profile_data = json.load(f)
            
            roofer = RooferProfile.from_dict(profile_data)
            
            # Load quotes
            quotes_file = f"quotes/{profile_id}_quotes.json"
            if not os.path.exists(quotes_file):
                return jsonify({'error': 'Quotes not found'}), 404
            
            with open(quotes_file, 'r') as f:
                quotes_data = json.load(f)
            
            # Create temporary ZIP file
            temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            zip_path = temp_zip.name
            temp_zip.close()
            
            # Generate PDFs and add to ZIP
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for quote_id in quote_ids:
                    try:
                        idx = int(quote_id)
                        if 0 <= idx < len(quotes_data):
                            quote_dict = quotes_data[idx]
                            quote = QuoteResult(**quote_dict)
                            
                            # Generate PDF
                            pdf_path = generate_pdf_for_quote(
                                quote=quote,
                                roofer=roofer,
                                output_dir=tempfile.gettempdir(),
                                client_name=data.get('client_info', {}).get('client_name'),
                                client_phone=data.get('client_info', {}).get('client_phone'),
                                client_email=data.get('client_info', {}).get('client_email')
                            )
                            
                            # Add to ZIP
                            zipf.write(
                                pdf_path,
                                f"Estimate_{quote_id}_{abs(hash(quote.address)) % 10000:04d}.pdf"
                            )
                            
                            # Clean up temp PDF
                            os.unlink(pdf_path)
                    except Exception as e:
                        print(f"Error generating PDF for quote {quote_id}: {e}")
                        continue
            
            # Return ZIP file
            return send_file(
                zip_path,
                mimetype='application/zip',
                as_attachment=True,
                download_name=f"Roofing_Estimates_{datetime.now().strftime('%Y%m%d')}.zip"
            )
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

