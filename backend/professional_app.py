"""
Professional Roofing Quote Generator
Native-looking interface with proper authentication and database
"""

from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_cors import CORS
import os
import json
from typing import Dict, List

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
    return render_template_string(NATIVE_DASHBOARD_TEMPLATE)

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

@app.route('/api/quotes/generate', methods=['POST'])
@require_auth
def generate_quotes(user):
    """Generate quotes for all properties using user's profile"""
    try:
        # Load user's roofer profile
        profile_file = f"profiles/{user.id}_roofer_profile.json"
        if not os.path.exists(profile_file):
            return jsonify({'error': 'Please complete your roofer profile first'}), 400
        
        with open(profile_file, 'r') as f:
            profile_data = json.load(f)
        
        roofer = RooferProfile.from_dict(profile_data)
        
        # Generate quotes for all properties
        quotes = process_csv_quotes(CSV_DATA, roofer)
        
        # Save quotes
        quotes_file = f"quotes/{user.id}_quotes.json"
        os.makedirs('quotes', exist_ok=True)
        save_quotes_to_json(quotes, quotes_file)
        
        return jsonify({
            'success': True,
            'quotes': [quote.__dict__ for quote in quotes],
            'total_quotes': len(quotes)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotes', methods=['GET'])
@require_auth
def get_quotes(user):
    """Get user's generated quotes"""
    try:
        quotes_file = f"quotes/{user.id}_quotes.json"
        if not os.path.exists(quotes_file):
            return jsonify({'success': False, 'message': 'No quotes found'})
        
        with open(quotes_file, 'r') as f:
            quotes = json.load(f)
        
        return jsonify({
            'success': True,
            'quotes': quotes,
            'total_quotes': len(quotes)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/properties', methods=['GET'])
@require_auth
def get_properties(user):
    """Get available properties for quoting"""
    try:
        # Return sample of properties for preview
        sample_properties = CSV_DATA[:50] if CSV_DATA else []
        return jsonify({
            'success': True,
            'properties': sample_properties,
            'total_properties': len(CSV_DATA) if CSV_DATA else 0
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

# Native-looking HTML template
NATIVE_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RoofingQuote Pro</title>
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
            max-width: 1200px;
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
        
        /* Quotes */
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
                    <a href="#" class="nav-item">Pricing</a>
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
            <div class="wizard-container">
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
            
            <!-- Action Buttons -->
            <div class="action-buttons">
                <button class="btn-action btn-generate" onclick="generateQuotes()" id="generateBtn" style="display: none;">Generate Quotes</button>
                <button class="btn-action btn-profile" onclick="editProfile()">Edit Profile</button>
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
            </div>
        </div>
    </div>

    <script>
        let currentUser = null;
        let authToken = null;
        let currentStep = 1;
        let totalSteps = 5;
        
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
                
                // Load properties count
                const propsResponse = await fetch('/api/properties', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const propsResult = await propsResponse.json();
                
                if (propsResult.success) {
                    document.getElementById('totalProperties').textContent = propsResult.total_properties;
                }
                
                // Check if profile exists
                const profileResponse = await fetch('/api/profile/roofer', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const profileResult = await profileResponse.json();
                
                if (profileResult.success) {
                    // Profile exists, hide wizard
                    document.querySelector('.wizard-container').style.display = 'none';
                    document.getElementById('generateBtn').style.display = 'inline-block';
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
                    document.querySelector('.wizard-container').style.display = 'none';
                    document.getElementById('generateBtn').style.display = 'inline-block';
                    document.getElementById('profileStatus').textContent = 'Complete';
                    alert('Profile saved successfully! You can now generate quotes.');
                } else {
                    alert('Error saving profile: ' + result.error);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        async function loadQuotes() {
            try {
                const response = await fetch('/api/quotes', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const result = await response.json();
                
                if (result.success && result.quotes.length > 0) {
                    document.getElementById('totalQuotes').textContent = result.quotes.length;
                    document.getElementById('quotesCount').textContent = `${result.quotes.length} quotes generated`;
                    displayQuotes(result.quotes.slice(0, 12)); // Show first 12 quotes
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
        
        async function generateQuotes() {
            try {
                document.getElementById('quotesContainer').innerHTML = '<div class="loading">Generating quotes for all properties... This may take a moment.</div>';
                
                const response = await fetch('/api/quotes/generate', {
                    method: 'POST',
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('totalQuotes').textContent = result.total_quotes;
                    document.getElementById('quotesCount').textContent = `${result.total_quotes} quotes generated`;
                    displayQuotes(result.quotes.slice(0, 12));
                } else {
                    document.getElementById('quotesContainer').innerHTML = `<div class="error">Error: ${result.error}</div>`;
                }
            } catch (error) {
                document.getElementById('quotesContainer').innerHTML = `<div class="error">Error: ${error.message}</div>`;
            }
        }
        
        function editProfile() {
            document.querySelector('.wizard-container').style.display = 'block';
            document.getElementById('generateBtn').style.display = 'none';
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
