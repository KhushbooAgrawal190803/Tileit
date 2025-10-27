"""
Enhanced Roofing Quote Generator
With filtering, pagination, and comprehensive property management
"""

from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_cors import CORS
import os
import json
from typing import Dict, List, Optional
import math

from fixed_auth import auth_manager
from models.roofer_profile import RooferProfile, SlopeCostAdjustment, MaterialCosts, ReplacementCosts, CrewScalingRule
from quote_engine import calculate_quote, process_csv_quotes
from utils import parse_nearmap_csv, save_quotes_to_json

app = Flask(__name__)
CORS(app)
app.secret_key = 'roofing-quote-generator-secret-key-2024'

# Load existing CSV data
CSV_DATA = None
def load_csv_data():
    global CSV_DATA
    if CSV_DATA is None:
        csv_path = "data/nearmap_synthetic_extended_correlated.csv"
        if os.path.exists(csv_path):
            CSV_DATA = parse_nearmap_csv(csv_path)
            print(f"Loaded {len(CSV_DATA)} properties from CSV")
        else:
            CSV_DATA = []
            print("No CSV data found")

# Load data on startup
load_csv_data()

# Authentication decorator
def require_auth(f):
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_manager.get_user_from_session(token)
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        return f(user, *args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template_string(ENHANCED_DASHBOARD_TEMPLATE)

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register new roofing company"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'password', 'business_name', 'license_id', 'primary_zip_code']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create user
        user = auth_manager.create_user(
            email=data['email'],
            password=data['password'],
            business_name=data['business_name'],
            license_id=data['license_id'],
            primary_zip_code=data['primary_zip_code']
        )
        
        if not user:
            return jsonify({'error': 'Email already exists'}), 400
        
        # Create session
        token = auth_manager.create_session(user)
        
        return jsonify({
            'success': True,
            'message': 'Registration successful',
            'token': token,
            'user': user.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login existing user"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        user = auth_manager.authenticate_user(email, password)
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Create session
        token = auth_manager.create_session(user)
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': user.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout(user):
    """Logout user"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    auth_manager.logout(token)
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/profile', methods=['GET'])
@require_auth
def get_profile(user):
    """Get user profile"""
    return jsonify({
        'success': True,
        'user': user.to_dict()
    })

@app.route('/api/profile/roofer', methods=['GET'])
@require_auth
def get_roofer_profile(user):
    """Get roofer business profile"""
    try:
        profile_file = f"profiles/{user.id}_roofer_profile.json"
        if os.path.exists(profile_file):
            with open(profile_file, 'r') as f:
                profile_data = json.load(f)
            return jsonify({'success': True, 'profile': profile_data})
        else:
            return jsonify({'success': False, 'message': 'No roofer profile found'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/profile/roofer', methods=['POST'])
@require_auth
def save_roofer_profile(user):
    """Save roofer business profile"""
    try:
        data = request.get_json()
        
        # Create roofer profile
        roofer = RooferProfile(
            business_name=user.business_name,
            license_id=user.license_id,
            primary_zip_code=user.primary_zip_code,
            email=user.email,
            labor_rate=float(data.get('labor_rate', 45)),
            daily_productivity=int(data.get('daily_productivity', 2500)),
            base_crew_size=int(data.get('base_crew_size', 3)),
            crew_scaling_rule=CrewScalingRule(data.get('crew_scaling_rule', 'size_and_complexity')),
            slope_cost_adjustment=SlopeCostAdjustment(
                flat_low=float(data.get('slope_adjustments', {}).get('flat_low', 0.0)),
                moderate=float(data.get('slope_adjustments', {}).get('moderate', 0.1)),
                steep=float(data.get('slope_adjustments', {}).get('steep', 0.2)),
                very_steep=float(data.get('slope_adjustments', {}).get('very_steep', 0.3))
            ),
            material_costs=MaterialCosts(
                asphalt=float(data.get('material_costs', {}).get('asphalt', 4.0)),
                shingle=float(data.get('material_costs', {}).get('shingle', 4.5)),
                metal=float(data.get('material_costs', {}).get('metal', 7.0)),
                tile=float(data.get('material_costs', {}).get('tile', 8.0)),
                concrete=float(data.get('material_costs', {}).get('concrete', 6.0))
            ),
            replacement_costs=ReplacementCosts(
                asphalt=float(data.get('replacement_costs', {}).get('asphalt', 45)),
                shingle=float(data.get('replacement_costs', {}).get('shingle', 50)),
                metal=float(data.get('replacement_costs', {}).get('metal', 90)),
                tile=float(data.get('replacement_costs', {}).get('tile', 70)),
                concrete=float(data.get('replacement_costs', {}).get('concrete', 60))
            ),
            overhead_percent=float(data.get('overhead_percent', 0.1)),
            profit_margin=float(data.get('profit_margin', 0.2))
        )
        
        # Save profile
        os.makedirs('profiles', exist_ok=True)
        profile_file = f"profiles/{user.id}_roofer_profile.json"
        with open(profile_file, 'w') as f:
            json.dump(roofer.to_dict(), f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Roofer profile saved successfully',
            'profile': roofer.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/properties', methods=['GET'])
@require_auth
def get_properties(user):
    """Get properties with filtering and pagination"""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Filter parameters
        min_area = request.args.get('min_area', type=float)
        max_area = request.args.get('max_area', type=float)
        material = request.args.get('material', '').lower()
        min_pitch = request.args.get('min_pitch', type=float)
        max_pitch = request.args.get('max_pitch', type=float)
        condition_min = request.args.get('condition_min', type=float)
        condition_max = request.args.get('condition_max', type=float)
        search_address = request.args.get('search', '').lower()
        
        # Apply filters
        filtered_data = CSV_DATA.copy()
        
        if min_area is not None:
            filtered_data = [p for p in filtered_data if p.get('roof_area', 0) >= min_area]
        
        if max_area is not None:
            filtered_data = [p for p in filtered_data if p.get('roof_area', 0) <= max_area]
        
        if material:
            filtered_data = [p for p in filtered_data if p.get('roof_material', '').lower() == material]
        
        if min_pitch is not None:
            filtered_data = [p for p in filtered_data if p.get('pitch', 0) >= min_pitch]
        
        if max_pitch is not None:
            filtered_data = [p for p in filtered_data if p.get('pitch', 0) <= max_pitch]
        
        if condition_min is not None:
            filtered_data = [p for p in filtered_data if p.get('roof condition summary score', 0) >= condition_min]
        
        if condition_max is not None:
            filtered_data = [p for p in filtered_data if p.get('roof condition summary score', 0) <= condition_max]
        
        if search_address:
            filtered_data = [p for p in filtered_data if search_address in p.get('address', '').lower()]
        
        # Calculate pagination
        total_properties = len(filtered_data)
        total_pages = math.ceil(total_properties / per_page)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        # Get page data
        page_data = filtered_data[start_idx:end_idx]
        
        # Calculate statistics
        if filtered_data:
            areas = [p.get('roof_area', 0) for p in filtered_data if p.get('roof_area', 0) > 0]
            pitches = [p.get('pitch', 0) for p in filtered_data if p.get('pitch', 0) > 0]
            conditions = [p.get('roof condition summary score', 0) for p in filtered_data if p.get('roof condition summary score', 0) > 0]
            
            stats = {
                'avg_area': sum(areas) / len(areas) if areas else 0,
                'min_area': min(areas) if areas else 0,
                'max_area': max(areas) if areas else 0,
                'avg_pitch': sum(pitches) / len(pitches) if pitches else 0,
                'avg_condition': sum(conditions) / len(conditions) if conditions else 0
            }
        else:
            stats = {'avg_area': 0, 'min_area': 0, 'max_area': 0, 'avg_pitch': 0, 'avg_condition': 0}
        
        return jsonify({
            'success': True,
            'properties': page_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_properties': total_properties,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            },
            'stats': stats,
            'filters_applied': {
                'min_area': min_area,
                'max_area': max_area,
                'material': material,
                'min_pitch': min_pitch,
                'max_pitch': max_pitch,
                'condition_min': condition_min,
                'condition_max': condition_max,
                'search': search_address
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/properties/filters', methods=['GET'])
@require_auth
def get_filter_options(user):
    """Get available filter options"""
    try:
        # Get unique values for filters
        materials = list(set(p.get('roof_material', '') for p in CSV_DATA if p.get('roof_material')))
        materials = [m for m in materials if m]
        
        # Get area ranges
        areas = [p.get('roof_area', 0) for p in CSV_DATA if p.get('roof_area', 0) > 0]
        min_area = min(areas) if areas else 0
        max_area = max(areas) if areas else 0
        
        # Get pitch ranges
        pitches = [p.get('pitch', 0) for p in CSV_DATA if p.get('pitch', 0) > 0]
        min_pitch = min(pitches) if pitches else 0
        max_pitch = max(pitches) if pitches else 0
        
        # Get condition ranges
        conditions = [p.get('roof condition summary score', 0) for p in CSV_DATA if p.get('roof condition summary score', 0) > 0]
        min_condition = min(conditions) if conditions else 0
        max_condition = max(conditions) if conditions else 0
        
        return jsonify({
            'success': True,
            'materials': materials,
            'area_range': {'min': min_area, 'max': max_area},
            'pitch_range': {'min': min_pitch, 'max': max_pitch},
            'condition_range': {'min': min_condition, 'max': max_condition}
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotes/generate', methods=['POST'])
@require_auth
def generate_quotes(user):
    """Generate quotes for filtered properties"""
    try:
        data = request.get_json()
        filters = data.get('filters', {})
        
        # Load user's roofer profile
        profile_file = f"profiles/{user.id}_roofer_profile.json"
        if not os.path.exists(profile_file):
            return jsonify({'error': 'Please complete your roofer profile first'}), 400
        
        with open(profile_file, 'r') as f:
            profile_data = json.load(f)
        
        roofer = RooferProfile.from_dict(profile_data)
        
        # Apply filters to CSV data
        filtered_data = CSV_DATA.copy()
        
        if filters.get('min_area'):
            filtered_data = [p for p in filtered_data if p.get('roof_area', 0) >= filters['min_area']]
        
        if filters.get('max_area'):
            filtered_data = [p for p in filtered_data if p.get('roof_area', 0) <= filters['max_area']]
        
        if filters.get('material'):
            filtered_data = [p for p in filtered_data if p.get('roof_material', '').lower() == filters['material'].lower()]
        
        if filters.get('min_pitch'):
            filtered_data = [p for p in filtered_data if p.get('pitch', 0) >= filters['min_pitch']]
        
        if filters.get('max_pitch'):
            filtered_data = [p for p in filtered_data if p.get('pitch', 0) <= filters['max_pitch']]
        
        if filters.get('condition_min'):
            filtered_data = [p for p in filtered_data if p.get('roof condition summary score', 0) >= filters['condition_min']]
        
        if filters.get('condition_max'):
            filtered_data = [p for p in filtered_data if p.get('roof condition summary score', 0) <= filters['condition_max']]
        
        if filters.get('search'):
            search_term = filters['search'].lower()
            filtered_data = [p for p in filtered_data if search_term in p.get('address', '').lower()]
        
        # Limit to reasonable number for performance
        max_quotes = 1000
        if len(filtered_data) > max_quotes:
            filtered_data = filtered_data[:max_quotes]
        
        # Generate quotes
        quotes = process_csv_quotes(filtered_data, roofer)
        
        # Save quotes
        quotes_file = f"quotes/{user.id}_quotes.json"
        os.makedirs('quotes', exist_ok=True)
        save_quotes_to_json(quotes, quotes_file)
        
        return jsonify({
            'success': True,
            'quotes': [quote.__dict__ for quote in quotes],
            'total_quotes': len(quotes),
            'filters_applied': filters,
            'properties_processed': len(filtered_data)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotes', methods=['GET'])
@require_auth
def get_quotes(user):
    """Get user's generated quotes with pagination"""
    try:
        quotes_file = f"quotes/{user.id}_quotes.json"
        if not os.path.exists(quotes_file):
            return jsonify({'success': False, 'message': 'No quotes found'})
        
        with open(quotes_file, 'r') as f:
            all_quotes = json.load(f)
        
        # Pagination
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        total_quotes = len(all_quotes)
        total_pages = math.ceil(total_quotes / per_page)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        page_quotes = all_quotes[start_idx:end_idx]
        
        return jsonify({
            'success': True,
            'quotes': page_quotes,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_quotes': total_quotes,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotes/export', methods=['GET'])
@require_auth
def export_quotes(user):
    """Export quotes as CSV"""
    try:
        quotes_file = f"quotes/{user.id}_quotes.json"
        if not os.path.exists(quotes_file):
            return jsonify({'error': 'No quotes found'}), 404
        
        with open(quotes_file, 'r') as f:
            quotes = json.load(f)
        
        # Create CSV content
        csv_content = "Address,Material,Pitch,Quote Range,Crew Size,Region Multiplier,Total Cost\n"
        for quote in quotes:
            csv_content += f'"{quote["address"]}","{quote["roof_material"]}",{quote["pitch"]},"{quote["estimated_quote_range"]}",{quote["crew_size_used"]},{quote["region_multiplier"]},{quote["total"]}\n'
        
        return jsonify({
            'success': True,
            'csv_content': csv_content,
            'filename': f'roofing_quotes_{user.business_name.replace(" ", "_")}.csv'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'roofing-company-dashboard',
        'properties_loaded': len(CSV_DATA) if CSV_DATA else 0
    })

# Enhanced HTML template with filtering and pagination
ENHANCED_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RoofingQuote Pro - Enhanced Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            background: #f5f5f7;
            color: #1d1d1f;
            line-height: 1.47;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 20px;
        }
        
        /* Header */
        .header {
            background: rgba(255, 255, 255, 0.8);
            backdrop-filter: saturate(180%) blur(20px);
            border-bottom: 1px solid rgba(0, 0, 0, 0.1);
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
        }
        
        .logo {
            font-size: 21px;
            font-weight: 600;
            color: #1d1d1f;
            text-decoration: none;
        }
        
        .nav {
            display: flex;
            gap: 30px;
            align-items: center;
        }
        
        .nav-item {
            color: #1d1d1f;
            text-decoration: none;
            font-size: 17px;
            font-weight: 400;
            transition: color 0.3s ease;
        }
        
        .nav-item:hover {
            color: #007aff;
        }
        
        .user-menu {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .user-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: #007aff;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 14px;
        }
        
        .btn {
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 17px;
            font-weight: 400;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
        }
        
        .btn-primary {
            background: #007aff;
            color: white;
        }
        
        .btn-primary:hover {
            background: #0056cc;
        }
        
        .btn-secondary {
            background: #f2f2f7;
            color: #1d1d1f;
            border: 1px solid #d1d1d6;
        }
        
        .btn-secondary:hover {
            background: #e5e5ea;
        }
        
        /* Auth Section */
        .auth-container {
            max-width: 400px;
            margin: 60px auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        
        .auth-header {
            background: #f2f2f7;
            padding: 24px;
            text-align: center;
            border-bottom: 1px solid #e5e5ea;
        }
        
        .auth-title {
            font-size: 28px;
            font-weight: 600;
            color: #1d1d1f;
            margin-bottom: 8px;
        }
        
        .auth-subtitle {
            color: #86868b;
            font-size: 17px;
        }
        
        .auth-tabs {
            display: flex;
            background: #f2f2f7;
        }
        
        .auth-tab {
            flex: 1;
            padding: 16px;
            background: none;
            border: none;
            cursor: pointer;
            font-size: 17px;
            font-weight: 500;
            color: #86868b;
            transition: all 0.3s ease;
        }
        
        .auth-tab.active {
            background: white;
            color: #1d1d1f;
            border-bottom: 2px solid #007aff;
        }
        
        .auth-form {
            padding: 32px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-size: 17px;
            font-weight: 500;
            color: #1d1d1f;
        }
        
        .form-group input {
            width: 100%;
            padding: 12px 16px;
            border: 1px solid #d1d1d6;
            border-radius: 8px;
            font-size: 17px;
            transition: border-color 0.3s ease;
            background: white;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: #007aff;
            box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.1);
        }
        
        .form-row {
            display: flex;
            gap: 12px;
        }
        
        .form-row .form-group {
            flex: 1;
        }
        
        /* Dashboard */
        .dashboard {
            display: none;
        }
        
        .dashboard.active {
            display: block;
        }
        
        .dashboard-header {
            background: white;
            border-radius: 12px;
            padding: 32px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        
        .dashboard-title {
            font-size: 32px;
            font-weight: 600;
            color: #1d1d1f;
            margin-bottom: 8px;
        }
        
        .dashboard-subtitle {
            color: #86868b;
            font-size: 19px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }
        
        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border-left: 4px solid #007aff;
        }
        
        .stat-card h3 {
            color: #86868b;
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        
        .stat-card .number {
            font-size: 32px;
            font-weight: 600;
            color: #1d1d1f;
        }
        
        /* Filters */
        .filters-container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 24px;
            padding: 24px;
        }
        
        .filters-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .filters-title {
            font-size: 20px;
            font-weight: 600;
            color: #1d1d1f;
        }
        
        .filters-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }
        
        .filter-group {
            display: flex;
            flex-direction: column;
        }
        
        .filter-group label {
            font-size: 14px;
            font-weight: 500;
            color: #1d1d1f;
            margin-bottom: 6px;
        }
        
        .filter-group input,
        .filter-group select {
            padding: 8px 12px;
            border: 1px solid #d1d1d6;
            border-radius: 6px;
            font-size: 14px;
        }
        
        .filter-actions {
            display: flex;
            gap: 12px;
            align-items: center;
        }
        
        .btn-filter {
            background: #34c759;
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-size: 14px;
        }
        
        .btn-clear {
            background: #ff3b30;
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-size: 14px;
        }
        
        /* Properties Table */
        .properties-container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 24px;
        }
        
        .properties-header {
            padding: 24px;
            border-bottom: 1px solid #e5e5ea;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .properties-title {
            font-size: 20px;
            font-weight: 600;
            color: #1d1d1f;
        }
        
        .properties-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .properties-table th,
        .properties-table td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #e5e5ea;
        }
        
        .properties-table th {
            background: #f2f2f7;
            font-weight: 600;
            color: #1d1d1f;
            font-size: 14px;
        }
        
        .properties-table td {
            font-size: 14px;
            color: #1d1d1f;
        }
        
        .properties-table tr:hover {
            background: #f8f9fa;
        }
        
        /* Pagination */
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            padding: 20px;
        }
        
        .pagination button {
            padding: 8px 12px;
            border: 1px solid #d1d1d6;
            background: white;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .pagination button:hover:not(:disabled) {
            background: #f2f2f7;
        }
        
        .pagination button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .pagination .active {
            background: #007aff;
            color: white;
            border-color: #007aff;
        }
        
        /* Quotes Section */
        .quotes-section {
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            padding: 32px;
        }
        
        .quotes-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }
        
        .quotes-title {
            font-size: 24px;
            font-weight: 600;
            color: #1d1d1f;
        }
        
        .quotes-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 20px;
        }
        
        .quote-card {
            border: 1px solid #e5e5ea;
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s ease;
            background: white;
        }
        
        .quote-card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            transform: translateY(-2px);
        }
        
        .quote-address {
            font-weight: 600;
            color: #1d1d1f;
            margin-bottom: 8px;
            font-size: 17px;
        }
        
        .quote-range {
            font-size: 24px;
            font-weight: 700;
            color: #34c759;
            margin-bottom: 16px;
        }
        
        .quote-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 15px;
            color: #86868b;
        }
        
        .quote-detail {
            display: flex;
            justify-content: space-between;
        }
        
        .loading {
            text-align: center;
            padding: 48px;
            color: #86868b;
            font-size: 17px;
        }
        
        .error {
            background: #ff3b30;
            color: white;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 16px;
            font-size: 15px;
        }
        
        .success {
            background: #34c759;
            color: white;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 16px;
            font-size: 15px;
        }
        
        /* Action Buttons */
        .action-buttons {
            display: flex;
            gap: 16px;
            margin-bottom: 32px;
        }
        
        .btn-action {
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 17px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            border: none;
        }
        
        .btn-generate {
            background: #34c759;
            color: white;
        }
        
        .btn-generate:hover {
            background: #30b54d;
        }
        
        .btn-profile {
            background: #ff9500;
            color: white;
        }
        
        .btn-profile:hover {
            background: #e6850e;
        }
        
        .btn-export {
            background: #007aff;
            color: white;
        }
        
        .btn-export:hover {
            background: #0056cc;
        }
        
        /* Wizard */
        .wizard-container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 32px;
        }
        
        .wizard-header {
            background: #f2f2f7;
            padding: 24px 32px;
            border-bottom: 1px solid #e5e5ea;
        }
        
        .wizard-title {
            font-size: 24px;
            font-weight: 600;
            color: #1d1d1f;
            margin-bottom: 8px;
        }
        
        .wizard-progress {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .progress-bar {
            flex: 1;
            height: 6px;
            background: #e5e5ea;
            border-radius: 3px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: #007aff;
            transition: width 0.3s ease;
        }
        
        .progress-text {
            font-size: 15px;
            color: #86868b;
            font-weight: 500;
        }
        
        .wizard-content {
            padding: 32px;
        }
        
        .wizard-step {
            display: none;
        }
        
        .wizard-step.active {
            display: block;
        }
        
        .step-title {
            font-size: 28px;
            font-weight: 600;
            color: #1d1d1f;
            margin-bottom: 12px;
        }
        
        .step-description {
            color: #86868b;
            font-size: 19px;
            margin-bottom: 32px;
            line-height: 1.47;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 24px;
        }
        
        .form-section {
            background: #f2f2f7;
            padding: 24px;
            border-radius: 12px;
            border: 1px solid #e5e5ea;
        }
        
        .form-section h4 {
            color: #1d1d1f;
            margin-bottom: 16px;
            font-size: 19px;
            font-weight: 600;
        }
        
        .wizard-navigation {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 24px 32px;
            background: #f2f2f7;
            border-top: 1px solid #e5e5ea;
        }
        
        .wizard-buttons {
            display: flex;
            gap: 12px;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 0 16px;
            }
            
            .form-grid {
                grid-template-columns: 1fr;
            }
            
            .form-row {
                flex-direction: column;
            }
            
            .wizard-navigation {
                flex-direction: column;
                gap: 16px;
            }
            
            .wizard-buttons {
                width: 100%;
            }
            
            .wizard-buttons .btn {
                flex: 1;
            }
            
            .action-buttons {
                flex-direction: column;
            }
            
            .filters-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <div class="header-content">
                <a href="#" class="logo">RoofingQuote Pro</a>
                <div class="nav">
                    <a href="#" class="nav-item">Dashboard</a>
                    <a href="#" class="nav-item">Properties</a>
                    <a href="#" class="nav-item">Quotes</a>
                    <a href="#" class="nav-item">Support</a>
                </div>
                <div class="user-menu" id="userMenu" style="display: none;">
                    <div class="user-avatar" id="userAvatar">U</div>
                    <span id="userName">User</span>
                    <button class="btn btn-secondary" onclick="logout()">Logout</button>
                </div>
            </div>
        </div>
    </div>

    <div class="container">
        <!-- Authentication Section -->
        <div id="authSection" class="auth-container">
            <div class="auth-header">
                <div class="auth-title">Welcome to RoofingQuote Pro</div>
                <div class="auth-subtitle">Professional quote generation for roofing companies</div>
            </div>
            
            <div class="auth-tabs">
                <button class="auth-tab active" onclick="showLogin()">Sign In</button>
                <button class="auth-tab" onclick="showRegister()">Create Account</button>
            </div>
            
            <div id="loginForm" class="auth-form">
                <div class="form-group">
                    <label>Email Address</label>
                    <input type="email" id="loginEmail" placeholder="your@company.com">
                </div>
                
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" id="loginPassword" placeholder="Enter your password">
                </div>
                
                <button class="btn btn-primary" onclick="login()" style="width: 100%;">Sign In</button>
            </div>
            
            <div id="registerForm" class="auth-form" style="display: none;">
                <div class="form-group">
                    <label>Business Name</label>
                    <input type="text" id="regBusinessName" placeholder="Your Roofing Company">
                </div>
                
                <div class="form-group">
                    <label>Email Address</label>
                    <input type="email" id="regEmail" placeholder="your@company.com">
                </div>
                
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" id="regPassword" placeholder="Create a secure password">
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>License ID</label>
                        <input type="text" id="regLicenseId" placeholder="LIC123456">
                    </div>
                    <div class="form-group">
                        <label>ZIP Code</label>
                        <input type="text" id="regZipCode" placeholder="11221">
                    </div>
                </div>
                
                <button class="btn btn-primary" onclick="register()" style="width: 100%;">Create Account</button>
            </div>
        </div>
        
        <!-- Dashboard Section -->
        <div id="dashboard" class="dashboard">
            <div class="dashboard-header">
                <div class="dashboard-title">Business Dashboard</div>
                <div class="dashboard-subtitle">Manage your roofing quotes and business settings</div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Available Properties</h3>
                    <div class="number" id="totalProperties">0</div>
                </div>
                <div class="stat-card">
                    <h3>Generated Quotes</h3>
                    <div class="number" id="totalQuotes">0</div>
                </div>
                <div class="stat-card">
                    <h3>Profile Status</h3>
                    <div id="profileStatus">Incomplete</div>
                </div>
            </div>
            
            <!-- Business Profile Wizard -->
            <div class="wizard-container" id="wizardContainer">
                <div class="wizard-header">
                    <div class="wizard-title">Business Profile Setup</div>
                    <div class="wizard-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                        </div>
                        <div class="progress-text" id="progressText">Step 1 of 5</div>
                    </div>
                </div>
                
                <div class="wizard-content">
                    <!-- Step 1: Labor Information -->
                    <div class="wizard-step active" id="step1">
                        <div class="step-title">Labor & Crew Information</div>
                        <div class="step-description">
                            Tell us about your labor costs and crew structure. This helps us calculate accurate quotes based on your business model.
                        </div>
                        
                        <div class="form-grid">
                            <div class="form-section">
                                <h4>Labor Rates</h4>
                                <div class="form-group">
                                    <label>Hourly Labor Rate ($)</label>
                                    <input type="number" id="laborRate" placeholder="45" min="20" max="100">
                                </div>
                                
                                <div class="form-group">
                                    <label>Daily Productivity (sqft)</label>
                                    <input type="number" id="dailyProductivity" placeholder="2500" min="1000" max="5000">
                                </div>
                            </div>
                            
                            <div class="form-section">
                                <h4>Crew Structure</h4>
                                <div class="form-group">
                                    <label>Base Crew Size</label>
                                    <input type="number" id="baseCrewSize" placeholder="3" min="1" max="10">
                                </div>
                                
                                <div class="form-group">
                                    <label>Crew Scaling</label>
                                    <select id="crewScaling" style="width: 100%; padding: 12px 16px; border: 1px solid #d1d1d6; border-radius: 8px; font-size: 17px;">
                                        <option value="size_only">Size Only - Crew grows with project size</option>
                                        <option value="size_and_complexity">Size & Complexity - Crew grows with size and difficulty</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Step 2: Slope Adjustments -->
                    <div class="wizard-step" id="step2">
                        <div class="step-title">Slope Difficulty Pricing</div>
                        <div class="step-description">
                            How much extra do you charge for different roof slopes? Steeper roofs require more safety equipment and take longer.
                        </div>
                        
                        <div class="form-grid">
                            <div class="form-section">
                                <h4>Slope Adjustments (%)</h4>
                                <div class="form-group">
                                    <label>Flat/Low Slope (0-15°)</label>
                                    <input type="number" id="slopeFlat" placeholder="0" min="0" max="50" step="5">
                                </div>
                                
                                <div class="form-group">
                                    <label>Moderate Slope (15-30°)</label>
                                    <input type="number" id="slopeModerate" placeholder="10" min="0" max="50" step="5">
                                </div>
                                
                                <div class="form-group">
                                    <label>Steep Slope (30-45°)</label>
                                    <input type="number" id="slopeSteep" placeholder="20" min="0" max="50" step="5">
                                </div>
                                
                                <div class="form-group">
                                    <label>Very Steep (>45°)</label>
                                    <input type="number" id="slopeVerySteep" placeholder="30" min="0" max="50" step="5">
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Step 3: Material Costs -->
                    <div class="wizard-step" id="step3">
                        <div class="step-title">Material Installation Costs</div>
                        <div class="step-description">
                            What do you charge per square foot for installing different roofing materials? Include material costs only.
                        </div>
                        
                        <div class="form-grid">
                            <div class="form-section">
                                <h4>Installation Costs ($/sqft)</h4>
                                <div class="form-group">
                                    <label>Asphalt Shingles</label>
                                    <input type="number" id="materialAsphalt" placeholder="4.00" min="1" max="20" step="0.25">
                                </div>
                                
                                <div class="form-group">
                                    <label>Shingles</label>
                                    <input type="number" id="materialShingle" placeholder="4.50" min="1" max="20" step="0.25">
                                </div>
                                
                                <div class="form-group">
                                    <label>Metal Roofing</label>
                                    <input type="number" id="materialMetal" placeholder="7.00" min="1" max="20" step="0.25">
                                </div>
                                
                                <div class="form-group">
                                    <label>Tile Roofing</label>
                                    <input type="number" id="materialTile" placeholder="8.00" min="1" max="20" step="0.25">
                                </div>
                                
                                <div class="form-group">
                                    <label>Concrete Tiles</label>
                                    <input type="number" id="materialConcrete" placeholder="6.00" min="1" max="20" step="0.25">
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Step 4: Replacement Costs -->
                    <div class="wizard-step" id="step4">
                        <div class="step-title">Replacement & Repair Costs</div>
                        <div class="step-description">
                            What do you charge for replacing damaged materials? Include removal, disposal, and installation.
                        </div>
                        
                        <div class="form-grid">
                            <div class="form-section">
                                <h4>Replacement Costs ($/sqm)</h4>
                                <div class="form-group">
                                    <label>Asphalt Replacement</label>
                                    <input type="number" id="replaceAsphalt" placeholder="45" min="20" max="200" step="5">
                                </div>
                                
                                <div class="form-group">
                                    <label>Shingle Replacement</label>
                                    <input type="number" id="replaceShingle" placeholder="50" min="20" max="200" step="5">
                                </div>
                                
                                <div class="form-group">
                                    <label>Metal Replacement</label>
                                    <input type="number" id="replaceMetal" placeholder="90" min="20" max="200" step="5">
                                </div>
                                
                                <div class="form-group">
                                    <label>Tile Replacement</label>
                                    <input type="number" id="replaceTile" placeholder="70" min="20" max="200" step="5">
                                </div>
                                
                                <div class="form-group">
                                    <label>Concrete Replacement</label>
                                    <input type="number" id="replaceConcrete" placeholder="60" min="20" max="200" step="5">
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Step 5: Business Margins -->
                    <div class="wizard-step" id="step5">
                        <div class="step-title">Business Margins</div>
                        <div class="step-description">
                            Set your overhead and profit margins. These are added to your base costs to determine final pricing.
                        </div>
                        
                        <div class="form-grid">
                            <div class="form-section">
                                <h4>Business Margins</h4>
                                <div class="form-group">
                                    <label>Overhead Percentage (%)</label>
                                    <input type="number" id="overheadPercent" placeholder="10" min="0" max="50" step="1">
                                </div>
                                
                                <div class="form-group">
                                    <label>Profit Margin (%)</label>
                                    <input type="number" id="profitMargin" placeholder="20" min="0" max="50" step="1">
                                </div>
                            </div>
                            
                            <div class="form-section">
                                <h4>Summary</h4>
                                <div style="background: #f2f2f7; padding: 20px; border-radius: 12px; border: 1px solid #e5e5ea;">
                                    <p style="margin-bottom: 8px; font-size: 15px;"><strong>Labor Rate:</strong> $<span id="summaryLaborRate">45</span>/hour</p>
                                    <p style="margin-bottom: 8px; font-size: 15px;"><strong>Daily Output:</strong> <span id="summaryDailyProd">2500</span> sqft</p>
                                    <p style="margin-bottom: 8px; font-size: 15px;"><strong>Crew Size:</strong> <span id="summaryCrewSize">3</span> workers</p>
                                    <p style="margin-bottom: 8px; font-size: 15px;"><strong>Overhead:</strong> <span id="summaryOverhead">10</span>%</p>
                                    <p style="font-size: 15px;"><strong>Profit:</strong> <span id="summaryProfit">20</span>%</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="wizard-navigation">
                    <button class="btn btn-secondary" id="prevBtn" onclick="previousStep()" style="display: none;">Previous</button>
                    <div style="flex: 1;"></div>
                    <div class="wizard-buttons">
                        <button class="btn btn-primary" id="nextBtn" onclick="nextStep()">Next Step</button>
                        <button class="btn btn-primary" id="saveBtn" onclick="saveProfile()" style="display: none;">Save Profile</button>
                    </div>
                </div>
            </div>
            
            <!-- Filters Section -->
            <div class="filters-container">
                <div class="filters-header">
                    <div class="filters-title">Property Filters</div>
                    <div class="filter-actions">
                        <button class="btn-filter" onclick="applyFilters()">Apply Filters</button>
                        <button class="btn-clear" onclick="clearFilters()">Clear All</button>
                    </div>
                </div>
                
                <div class="filters-grid">
                    <div class="filter-group">
                        <label>Search Address</label>
                        <input type="text" id="searchAddress" placeholder="Enter address...">
                    </div>
                    
                    <div class="filter-group">
                        <label>Material Type</label>
                        <select id="filterMaterial">
                            <option value="">All Materials</option>
                        </select>
                    </div>
                    
                    <div class="filter-group">
                        <label>Min Area (sqft)</label>
                        <input type="number" id="minArea" placeholder="0">
                    </div>
                    
                    <div class="filter-group">
                        <label>Max Area (sqft)</label>
                        <input type="number" id="maxArea" placeholder="10000">
                    </div>
                    
                    <div class="filter-group">
                        <label>Min Pitch (°)</label>
                        <input type="number" id="minPitch" placeholder="0">
                    </div>
                    
                    <div class="filter-group">
                        <label>Max Pitch (°)</label>
                        <input type="number" id="maxPitch" placeholder="60">
                    </div>
                    
                    <div class="filter-group">
                        <label>Min Condition Score</label>
                        <input type="number" id="minCondition" placeholder="0" min="0" max="100">
                    </div>
                    
                    <div class="filter-group">
                        <label>Max Condition Score</label>
                        <input type="number" id="maxCondition" placeholder="100" min="0" max="100">
                    </div>
                </div>
            </div>
            
            <!-- Properties Table -->
            <div class="properties-container">
                <div class="properties-header">
                    <div class="properties-title">Properties</div>
                    <div id="propertiesStats" style="color: #86868b; font-size: 14px;"></div>
                </div>
                
                <div id="propertiesTable">
                    <div class="loading">Loading properties...</div>
                </div>
                
                <div class="pagination" id="propertiesPagination" style="display: none;">
                    <button onclick="previousPage()" id="prevPageBtn">Previous</button>
                    <span id="pageInfo">Page 1 of 1</span>
                    <button onclick="nextPage()" id="nextPageBtn">Next</button>
                </div>
            </div>
            
            <!-- Action Buttons -->
            <div class="action-buttons">
                <button class="btn-action btn-generate" onclick="generateQuotes()" id="generateBtn" style="display: none;">Generate Quotes</button>
                <button class="btn-action btn-profile" onclick="editProfile()">Edit Profile</button>
                <button class="btn-action btn-export" onclick="exportQuotes()" id="exportBtn" style="display: none;">Export Quotes</button>
            </div>
            
            <!-- Quotes Section -->
            <div class="quotes-section">
                <div class="quotes-header">
                    <div class="quotes-title">Generated Quotes</div>
                    <div id="quotesCount" style="color: #86868b; font-size: 15px;"></div>
                </div>
                <div id="quotesContainer">
                    <div class="loading">Complete your business profile to generate quotes.</div>
                </div>
                
                <div class="pagination" id="quotesPagination" style="display: none;">
                    <button onclick="previousQuotesPage()" id="prevQuotesBtn">Previous</button>
                    <span id="quotesPageInfo">Page 1 of 1</span>
                    <button onclick="nextQuotesPage()" id="nextQuotesBtn">Next</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentUser = null;
        let authToken = null;
        let currentStep = 1;
        let totalSteps = 5;
        let currentPage = 1;
        let currentQuotesPage = 1;
        let filterOptions = {};
        
        // Check for existing session
        window.onload = function() {
            const savedToken = localStorage.getItem('authToken');
            if (savedToken) {
                authToken = savedToken;
                loadDashboard();
            }
        };
        
        function showLogin() {
            document.getElementById('loginForm').style.display = 'block';
            document.getElementById('registerForm').style.display = 'none';
            document.querySelectorAll('.auth-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.auth-tab')[0].classList.add('active');
        }
        
        function showRegister() {
            document.getElementById('loginForm').style.display = 'none';
            document.getElementById('registerForm').style.display = 'block';
            document.querySelectorAll('.auth-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.auth-tab')[1].classList.add('active');
        }
        
        async function login() {
            const email = document.getElementById('loginEmail').value;
            const password = document.getElementById('loginPassword').value;
            
            if (!email || !password) {
                alert('Please fill in all fields');
                return;
            }
            
            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email, password})
                });
                
                const result = await response.json();
                
                if (result.success) {
                    authToken = result.token;
                    currentUser = result.user;
                    localStorage.setItem('authToken', authToken);
                    loadDashboard();
                } else {
                    alert('Login failed: ' + result.error);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        async function register() {
            const businessName = document.getElementById('regBusinessName').value;
            const email = document.getElementById('regEmail').value;
            const password = document.getElementById('regPassword').value;
            const licenseId = document.getElementById('regLicenseId').value;
            const zipCode = document.getElementById('regZipCode').value;
            
            if (!businessName || !email || !password || !licenseId || !zipCode) {
                alert('Please fill in all fields');
                return;
            }
            
            try {
                const response = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        business_name: businessName,
                        email,
                        password,
                        license_id: licenseId,
                        primary_zip_code: zipCode
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    authToken = result.token;
                    currentUser = result.user;
                    localStorage.setItem('authToken', authToken);
                    loadDashboard();
                } else {
                    alert('Registration failed: ' + result.error);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        function logout() {
            authToken = null;
            currentUser = null;
            localStorage.removeItem('authToken');
            document.getElementById('authSection').style.display = 'block';
            document.getElementById('dashboard').classList.remove('active');
            document.getElementById('userMenu').style.display = 'none';
        }
        
        async function loadDashboard() {
            try {
                // Load user info
                const userResponse = await fetch('/api/profile', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const userResult = await userResponse.json();
                
                if (userResult.success) {
                    currentUser = userResult.user;
                    document.getElementById('userName').textContent = currentUser.business_name;
                    document.getElementById('userAvatar').textContent = currentUser.business_name.charAt(0).toUpperCase();
                    document.getElementById('userMenu').style.display = 'flex';
                }
                
                // Load filter options
                await loadFilterOptions();
                
                // Load properties
                await loadProperties();
                
                // Check if profile exists
                const profileResponse = await fetch('/api/profile/roofer', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const profileResult = await profileResponse.json();
                
                if (profileResult.success) {
                    // Profile exists, hide wizard
                    document.getElementById('wizardContainer').style.display = 'none';
                    document.getElementById('generateBtn').style.display = 'inline-block';
                    document.getElementById('exportBtn').style.display = 'inline-block';
                    document.getElementById('profileStatus').textContent = 'Complete';
                    await loadQuotes();
                } else {
                    // No profile, show wizard
                    document.getElementById('profileStatus').textContent = 'Incomplete';
                }
                
                // Show dashboard
                document.getElementById('authSection').style.display = 'none';
                document.getElementById('dashboard').classList.add('active');
                
            } catch (error) {
                console.error('Error loading dashboard:', error);
            }
        }
        
        async function loadFilterOptions() {
            try {
                const response = await fetch('/api/properties/filters', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const result = await response.json();
                
                if (result.success) {
                    filterOptions = result;
                    
                    // Populate material filter
                    const materialSelect = document.getElementById('filterMaterial');
                    materialSelect.innerHTML = '<option value="">All Materials</option>';
                    result.materials.forEach(material => {
                        const option = document.createElement('option');
                        option.value = material;
                        option.textContent = material;
                        materialSelect.appendChild(option);
                    });
                }
            } catch (error) {
                console.error('Error loading filter options:', error);
            }
        }
        
        async function loadProperties(page = 1) {
            try {
                const params = new URLSearchParams({
                    page: page,
                    per_page: 20
                });
                
                // Add filters
                const searchAddress = document.getElementById('searchAddress').value;
                const material = document.getElementById('filterMaterial').value;
                const minArea = document.getElementById('minArea').value;
                const maxArea = document.getElementById('maxArea').value;
                const minPitch = document.getElementById('minPitch').value;
                const maxPitch = document.getElementById('maxPitch').value;
                const minCondition = document.getElementById('minCondition').value;
                const maxCondition = document.getElementById('maxCondition').value;
                
                if (searchAddress) params.append('search', searchAddress);
                if (material) params.append('material', material);
                if (minArea) params.append('min_area', minArea);
                if (maxArea) params.append('max_area', maxArea);
                if (minPitch) params.append('min_pitch', minPitch);
                if (maxPitch) params.append('max_pitch', maxPitch);
                if (minCondition) params.append('condition_min', minCondition);
                if (maxCondition) params.append('condition_max', maxCondition);
                
                const response = await fetch(`/api/properties?${params}`, {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('totalProperties').textContent = result.pagination.total_properties;
                    document.getElementById('propertiesStats').textContent = 
                        `Showing ${result.properties.length} of ${result.pagination.total_properties} properties`;
                    
                    displayProperties(result.properties);
                    updatePropertiesPagination(result.pagination);
                }
            } catch (error) {
                console.error('Error loading properties:', error);
            }
        }
        
        function displayProperties(properties) {
            const container = document.getElementById('propertiesTable');
            
            if (properties.length === 0) {
                container.innerHTML = '<div class="loading">No properties found matching your filters.</div>';
                return;
            }
            
            const tableHTML = `
                <table class="properties-table">
                    <thead>
                        <tr>
                            <th>Address</th>
                            <th>Material</th>
                            <th>Area (sqft)</th>
                            <th>Pitch (°)</th>
                            <th>Condition</th>
                            <th>Height (ft)</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${properties.map(prop => `
                            <tr>
                                <td>${prop.address || 'N/A'}</td>
                                <td>${prop.roof_material || 'N/A'}</td>
                                <td>${prop.roof_area ? prop.roof_area.toFixed(0) : 'N/A'}</td>
                                <td>${prop.pitch ? prop.pitch.toFixed(1) : 'N/A'}</td>
                                <td>${prop['roof condition summary score'] || 'N/A'}</td>
                                <td>${prop['height (ft)'] ? prop['height (ft)'].toFixed(1) : 'N/A'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            
            container.innerHTML = tableHTML;
        }
        
        function updatePropertiesPagination(pagination) {
            const container = document.getElementById('propertiesPagination');
            const prevBtn = document.getElementById('prevPageBtn');
            const nextBtn = document.getElementById('nextPageBtn');
            const pageInfo = document.getElementById('pageInfo');
            
            if (pagination.total_pages > 1) {
                container.style.display = 'flex';
                prevBtn.disabled = !pagination.has_prev;
                nextBtn.disabled = !pagination.has_next;
                pageInfo.textContent = `Page ${pagination.page} of ${pagination.total_pages}`;
            } else {
                container.style.display = 'none';
            }
        }
        
        function previousPage() {
            if (currentPage > 1) {
                currentPage--;
                loadProperties(currentPage);
            }
        }
        
        function nextPage() {
            currentPage++;
            loadProperties(currentPage);
        }
        
        function applyFilters() {
            currentPage = 1;
            loadProperties();
        }
        
        function clearFilters() {
            document.getElementById('searchAddress').value = '';
            document.getElementById('filterMaterial').value = '';
            document.getElementById('minArea').value = '';
            document.getElementById('maxArea').value = '';
            document.getElementById('minPitch').value = '';
            document.getElementById('maxPitch').value = '';
            document.getElementById('minCondition').value = '';
            document.getElementById('maxCondition').value = '';
            currentPage = 1;
            loadProperties();
        }
        
        function nextStep() {
            if (currentStep < totalSteps) {
                document.getElementById(`step${currentStep}`).classList.remove('active');
                currentStep++;
                document.getElementById(`step${currentStep}`).classList.add('active');
                updateProgress();
                updateNavigation();
                updateSummary();
            }
        }
        
        function previousStep() {
            if (currentStep > 1) {
                document.getElementById(`step${currentStep}`).classList.remove('active');
                currentStep--;
                document.getElementById(`step${currentStep}`).classList.add('active');
                updateProgress();
                updateNavigation();
            }
        }
        
        function updateProgress() {
            const progress = (currentStep / totalSteps) * 100;
            document.getElementById('progressFill').style.width = progress + '%';
            document.getElementById('progressText').textContent = `Step ${currentStep} of ${totalSteps}`;
        }
        
        function updateNavigation() {
            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');
            const saveBtn = document.getElementById('saveBtn');
            
            prevBtn.style.display = currentStep > 1 ? 'inline-block' : 'none';
            
            if (currentStep === totalSteps) {
                nextBtn.style.display = 'none';
                saveBtn.style.display = 'inline-block';
            } else {
                nextBtn.style.display = 'inline-block';
                saveBtn.style.display = 'none';
            }
        }
        
        function updateSummary() {
            document.getElementById('summaryLaborRate').textContent = document.getElementById('laborRate').value || '45';
            document.getElementById('summaryDailyProd').textContent = document.getElementById('dailyProductivity').value || '2500';
            document.getElementById('summaryCrewSize').textContent = document.getElementById('baseCrewSize').value || '3';
            document.getElementById('summaryOverhead').textContent = document.getElementById('overheadPercent').value || '10';
            document.getElementById('summaryProfit').textContent = document.getElementById('profitMargin').value || '20';
        }
        
        async function saveProfile() {
            try {
                const profileData = {
                    labor_rate: parseFloat(document.getElementById('laborRate').value) || 45,
                    daily_productivity: parseInt(document.getElementById('dailyProductivity').value) || 2500,
                    base_crew_size: parseInt(document.getElementById('baseCrewSize').value) || 3,
                    crew_scaling_rule: document.getElementById('crewScaling').value,
                    slope_adjustments: {
                        flat_low: parseFloat(document.getElementById('slopeFlat').value) || 0,
                        moderate: parseFloat(document.getElementById('slopeModerate').value) || 10,
                        steep: parseFloat(document.getElementById('slopeSteep').value) || 20,
                        very_steep: parseFloat(document.getElementById('slopeVerySteep').value) || 30
                    },
                    material_costs: {
                        asphalt: parseFloat(document.getElementById('materialAsphalt').value) || 4.0,
                        shingle: parseFloat(document.getElementById('materialShingle').value) || 4.5,
                        metal: parseFloat(document.getElementById('materialMetal').value) || 7.0,
                        tile: parseFloat(document.getElementById('materialTile').value) || 8.0,
                        concrete: parseFloat(document.getElementById('materialConcrete').value) || 6.0
                    },
                    replacement_costs: {
                        asphalt: parseFloat(document.getElementById('replaceAsphalt').value) || 45,
                        shingle: parseFloat(document.getElementById('replaceShingle').value) || 50,
                        metal: parseFloat(document.getElementById('replaceMetal').value) || 90,
                        tile: parseFloat(document.getElementById('replaceTile').value) || 70,
                        concrete: parseFloat(document.getElementById('replaceConcrete').value) || 60
                    },
                    overhead_percent: parseFloat(document.getElementById('overheadPercent').value) / 100 || 0.1,
                    profit_margin: parseFloat(document.getElementById('profitMargin').value) / 100 || 0.2
                };
                
                const response = await fetch('/api/profile/roofer', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify(profileData)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('wizardContainer').style.display = 'none';
                    document.getElementById('generateBtn').style.display = 'inline-block';
                    document.getElementById('exportBtn').style.display = 'inline-block';
                    document.getElementById('profileStatus').textContent = 'Complete';
                    alert('Profile saved successfully! You can now generate quotes.');
                } else {
                    alert('Error saving profile: ' + result.error);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        async function generateQuotes() {
            try {
                document.getElementById('quotesContainer').innerHTML = '<div class="loading">Generating quotes for filtered properties... This may take a moment.</div>';
                
                // Get current filters
                const filters = {
                    search: document.getElementById('searchAddress').value,
                    material: document.getElementById('filterMaterial').value,
                    min_area: document.getElementById('minArea').value ? parseFloat(document.getElementById('minArea').value) : null,
                    max_area: document.getElementById('maxArea').value ? parseFloat(document.getElementById('maxArea').value) : null,
                    min_pitch: document.getElementById('minPitch').value ? parseFloat(document.getElementById('minPitch').value) : null,
                    max_pitch: document.getElementById('maxPitch').value ? parseFloat(document.getElementById('maxPitch').value) : null,
                    condition_min: document.getElementById('minCondition').value ? parseFloat(document.getElementById('minCondition').value) : null,
                    condition_max: document.getElementById('maxCondition').value ? parseFloat(document.getElementById('maxCondition').value) : null
                };
                
                const response = await fetch('/api/quotes/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify({filters})
                });
                
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('totalQuotes').textContent = result.total_quotes;
                    document.getElementById('quotesCount').textContent = `${result.total_quotes} quotes generated for ${result.properties_processed} properties`;
                    displayQuotes(result.quotes.slice(0, 12));
                } else {
                    document.getElementById('quotesContainer').innerHTML = `<div class="error">Error: ${result.error}</div>`;
                }
            } catch (error) {
                document.getElementById('quotesContainer').innerHTML = `<div class="error">Error: ${error.message}</div>`;
            }
        }
        
        async function loadQuotes(page = 1) {
            try {
                const response = await fetch(`/api/quotes?page=${page}&per_page=12`, {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const result = await response.json();
                
                if (result.success && result.quotes.length > 0) {
                    document.getElementById('totalQuotes').textContent = result.pagination.total_quotes;
                    document.getElementById('quotesCount').textContent = `${result.pagination.total_quotes} quotes generated`;
                    displayQuotes(result.quotes);
                    updateQuotesPagination(result.pagination);
                } else {
                    document.getElementById('totalQuotes').textContent = '0';
                    document.getElementById('quotesCount').textContent = 'No quotes generated';
                }
            } catch (error) {
                console.error('Error loading quotes:', error);
            }
        }
        
        function displayQuotes(quotes) {
            const container = document.getElementById('quotesContainer');
            
            if (quotes.length === 0) {
                container.innerHTML = '<div class="loading">No quotes generated yet. Complete your profile and click "Generate Quotes".</div>';
                return;
            }
            
            const quotesHTML = quotes.map(quote => `
                <div class="quote-card">
                    <div class="quote-address">${quote.address}</div>
                    <div class="quote-range">${quote.estimated_quote_range}</div>
                    <div class="quote-details">
                        <div class="quote-detail">
                            <span>Material:</span>
                            <span>${quote.roof_material}</span>
                        </div>
                        <div class="quote-detail">
                            <span>Pitch:</span>
                            <span>${quote.pitch}°</span>
                        </div>
                        <div class="quote-detail">
                            <span>Crew:</span>
                            <span>${quote.crew_size_used} workers</span>
                        </div>
                        <div class="quote-detail">
                            <span>Region:</span>
                            <span>${quote.region_multiplier}x</span>
                        </div>
                    </div>
                </div>
            `).join('');
            
            container.innerHTML = `<div class="quotes-grid">${quotesHTML}</div>`;
        }
        
        function updateQuotesPagination(pagination) {
            const container = document.getElementById('quotesPagination');
            const prevBtn = document.getElementById('prevQuotesBtn');
            const nextBtn = document.getElementById('nextQuotesBtn');
            const pageInfo = document.getElementById('quotesPageInfo');
            
            if (pagination.total_pages > 1) {
                container.style.display = 'flex';
                prevBtn.disabled = !pagination.has_prev;
                nextBtn.disabled = !pagination.has_next;
                pageInfo.textContent = `Page ${pagination.page} of ${pagination.total_pages}`;
            } else {
                container.style.display = 'none';
            }
        }
        
        function previousQuotesPage() {
            if (currentQuotesPage > 1) {
                currentQuotesPage--;
                loadQuotes(currentQuotesPage);
            }
        }
        
        function nextQuotesPage() {
            currentQuotesPage++;
            loadQuotes(currentQuotesPage);
        }
        
        async function exportQuotes() {
            try {
                const response = await fetch('/api/quotes/export', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const result = await response.json();
                
                if (result.success) {
                    // Create and download CSV file
                    const blob = new Blob([result.csv_content], { type: 'text/csv' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = result.filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                } else {
                    alert('Error exporting quotes: ' + result.error);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        function editProfile() {
            document.getElementById('wizardContainer').style.display = 'block';
            document.getElementById('generateBtn').style.display = 'none';
            document.getElementById('exportBtn').style.display = 'none';
        }
        
        // Update summary on input changes
        document.addEventListener('input', function(e) {
            if (e.target.id === 'laborRate' || e.target.id === 'dailyProductivity' || e.target.id === 'baseCrewSize' || 
                e.target.id === 'overheadPercent' || e.target.id === 'profitMargin') {
                updateSummary();
            }
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
