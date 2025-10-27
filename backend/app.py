"""
Flask API for Roofing Quote Generator
Main application entry point with REST endpoints
"""

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import os
import json
from typing import Dict, List

from models.roofer_profile import RooferProfile, QuoteResult
from quote_engine import calculate_quote, process_csv_quotes
from utils import (
    parse_nearmap_csv, validate_csv_structure, get_csv_summary,
    save_quotes_to_json, load_roofer_profile, save_roofer_profile,
    validate_roofer_profile
)

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend integration

# Global storage for demo purposes (in production, use a database)
roofer_profiles = {}
uploaded_csv_data = {}


@app.route('/')
def index():
    """Serve the main application page"""
    return render_template_string(INDEX_TEMPLATE)


@app.route('/api/roofer/register', methods=['POST'])
def register_roofer():
    """Register a new roofer profile"""
    try:
        data = request.get_json()
        
        # Validate profile data
        errors = validate_roofer_profile(data)
        if errors:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Create roofer profile
        roofer = RooferProfile.from_dict(data)
        profile_id = data.get('email', 'default')  # Use email as ID for demo
        
        # Store profile
        roofer_profiles[profile_id] = roofer.to_dict()
        
        return jsonify({
            'success': True,
            'message': 'Roofer profile created successfully',
            'profile_id': profile_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/roofer/<profile_id>', methods=['GET'])
def get_roofer_profile(profile_id):
    """Get roofer profile by ID"""
    if profile_id not in roofer_profiles:
        return jsonify({'error': 'Profile not found'}), 404
    
    return jsonify(roofer_profiles[profile_id])


@app.route('/api/csv/upload', methods=['POST'])
def upload_csv():
    """Upload and parse CSV file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file temporarily
        file_path = f"temp_{file.filename}"
        file.save(file_path)
        
        # Parse CSV
        csv_data = parse_nearmap_csv(file_path)
        
        if not csv_data:
            return jsonify({'error': 'Failed to parse CSV file'}), 400
        
        # Validate structure
        if not validate_csv_structure(csv_data):
            return jsonify({'error': 'CSV missing required fields'}), 400
        
        # Generate summary
        summary = get_csv_summary(csv_data)
        
        # Store data
        upload_id = f"upload_{len(uploaded_csv_data)}"
        uploaded_csv_data[upload_id] = csv_data
        
        # Clean up temp file
        os.remove(file_path)
        
        return jsonify({
            'success': True,
            'upload_id': upload_id,
            'summary': summary
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/quotes/calculate', methods=['POST'])
def calculate_quotes():
    """Calculate quotes for uploaded CSV data"""
    try:
        data = request.get_json()
        profile_id = data.get('profile_id')
        upload_id = data.get('upload_id')
        
        if not profile_id or profile_id not in roofer_profiles:
            return jsonify({'error': 'Invalid profile ID'}), 400
        
        if not upload_id or upload_id not in uploaded_csv_data:
            return jsonify({'error': 'Invalid upload ID'}), 400
        
        # Get roofer profile and CSV data
        roofer_data = roofer_profiles[profile_id]
        roofer = RooferProfile.from_dict(roofer_data)
        csv_data = uploaded_csv_data[upload_id]
        
        # Calculate quotes
        quotes = process_csv_quotes(csv_data, roofer)
        
        # Save quotes to file
        quotes_file = f"quotes_{profile_id}_{upload_id}.json"
        save_quotes_to_json(quotes, quotes_file)
        
        return jsonify({
            'success': True,
            'quotes': [quote.__dict__ for quote in quotes],
            'total_quotes': len(quotes)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/quotes/<profile_id>/<upload_id>', methods=['GET'])
def get_quotes(profile_id, upload_id):
    """Get calculated quotes for a specific profile and upload"""
    try:
        quotes_file = f"quotes_{profile_id}_{upload_id}.json"
        
        if not os.path.exists(quotes_file):
            return jsonify({'error': 'Quotes not found'}), 404
        
        with open(quotes_file, 'r') as f:
            quotes = json.load(f)
        
        return jsonify({
            'success': True,
            'quotes': quotes,
            'total_quotes': len(quotes)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'roofing-quote-generator'})


# Simple HTML template for the main page
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Roofing Quote Generator</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
        button { padding: 10px 20px; margin: 5px; background: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer; }
        button:hover { background: #0056b3; }
        input, select { padding: 8px; margin: 5px; width: 200px; }
        .result { margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏠 Roofing Quote Generator</h1>
        <p>Upload your Nearmap CSV data and get instant roofing quotes!</p>
        
        <div class="section">
            <h2>1. Roofer Registration</h2>
            <p>First, create your business profile:</p>
            <button onclick="showRegistration()">Register as Roofer</button>
            <div id="registration-form" style="display: none;">
                <input type="text" id="business_name" placeholder="Business Name">
                <input type="text" id="license_id" placeholder="License ID">
                <input type="text" id="zip_code" placeholder="ZIP Code">
                <input type="email" id="email" placeholder="Email">
                <input type="number" id="labor_rate" placeholder="Labor Rate ($/hr)" value="45">
                <input type="number" id="daily_productivity" placeholder="Daily Productivity (sqft)" value="2500">
                <input type="number" id="base_crew_size" placeholder="Base Crew Size" value="3">
                <button onclick="registerRoofer()">Register</button>
            </div>
        </div>
        
        <div class="section">
            <h2>2. Upload CSV Data</h2>
            <input type="file" id="csv-file" accept=".csv">
            <button onclick="uploadCSV()">Upload CSV</button>
            <div id="upload-result"></div>
        </div>
        
        <div class="section">
            <h2>3. Generate Quotes</h2>
            <button onclick="generateQuotes()">Calculate Quotes</button>
            <div id="quotes-result"></div>
        </div>
    </div>

    <script>
        let currentProfileId = null;
        let currentUploadId = null;
        
        function showRegistration() {
            document.getElementById('registration-form').style.display = 'block';
        }
        
        async function registerRoofer() {
            const data = {
                business_name: document.getElementById('business_name').value,
                license_id: document.getElementById('license_id').value,
                primary_zip_code: document.getElementById('zip_code').value,
                email: document.getElementById('email').value,
                labor_rate: parseFloat(document.getElementById('labor_rate').value),
                daily_productivity: parseInt(document.getElementById('daily_productivity').value),
                base_crew_size: parseInt(document.getElementById('base_crew_size').value),
                crew_scaling_rule: "size_and_complexity",
                slope_cost_adjustment: {
                    flat_low: 0.0,
                    moderate: 0.1,
                    steep: 0.2,
                    very_steep: 0.3
                },
                material_costs: {
                    asphalt: 4.0,
                    shingle: 4.5,
                    metal: 7.0,
                    tile: 8.0,
                    concrete: 6.0
                },
                replacement_costs: {
                    asphalt: 45,
                    shingle: 50,
                    metal: 90,
                    tile: 70,
                    concrete: 60
                },
                overhead_percent: 0.1,
                profit_margin: 0.2
            };
            
            try {
                const response = await fetch('/api/roofer/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                if (result.success) {
                    currentProfileId = result.profile_id;
                    document.getElementById('registration-form').innerHTML = 
                        '<p style="color: green;">✅ Registration successful!</p>';
                } else {
                    alert('Registration failed: ' + result.error);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        async function uploadCSV() {
            const fileInput = document.getElementById('csv-file');
            if (!fileInput.files[0]) {
                alert('Please select a CSV file');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            try {
                const response = await fetch('/api/csv/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                if (result.success) {
                    currentUploadId = result.upload_id;
                    document.getElementById('upload-result').innerHTML = 
                        `<div class="result">✅ CSV uploaded successfully!<br>
                        Records: ${result.summary.total_records}<br>
                        Unique addresses: ${result.summary.unique_addresses}</div>`;
                } else {
                    alert('Upload failed: ' + result.error);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        async function generateQuotes() {
            if (!currentProfileId || !currentUploadId) {
                alert('Please complete registration and upload first');
                return;
            }
            
            try {
                const response = await fetch('/api/quotes/calculate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        profile_id: currentProfileId,
                        upload_id: currentUploadId
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    displayQuotes(result.quotes);
                } else {
                    alert('Quote calculation failed: ' + result.error);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        function displayQuotes(quotes) {
            let html = '<h3>Generated Quotes:</h3>';
            quotes.slice(0, 10).forEach(quote => {
                html += `<div class="result">
                    <strong>${quote.address}</strong><br>
                    Material: ${quote.roof_material} | Pitch: ${quote.pitch}°<br>
                    <strong>Quote: ${quote.estimated_quote_range}</strong><br>
                    Crew Size: ${quote.crew_size_used} | Region Multiplier: ${quote.region_multiplier}
                </div>`;
            });
            
            if (quotes.length > 10) {
                html += `<p>... and ${quotes.length - 10} more quotes</p>`;
            }
            
            document.getElementById('quotes-result').innerHTML = html;
        }
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
