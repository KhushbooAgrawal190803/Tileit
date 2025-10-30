"""
Tileit - Professional Roofing Quote Generator
Modular, scalable application with advanced features
"""

from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_cors import CORS
import os
import json
import hashlib
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
import math
from datetime import datetime, timedelta
import sqlite3

from models.roofer_profile import RooferProfile, SlopeCostAdjustment, MaterialCosts, ReplacementCosts, CrewScalingRule
from quote_engine import calculate_quote, process_csv_quotes
from utils import parse_nearmap_csv, save_quotes_to_json

app = Flask(__name__)
CORS(app)
app.secret_key = 'tileit-roofing-quote-generator-secret-key-2024'

# Load existing CSV data
CSV_DATA = None
def load_csv_data():
    global CSV_DATA
    if CSV_DATA is None:
        # Get the absolute path relative to this file's directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_path = os.path.join(base_dir, "data", "nearmap_synthetic_extended_correlated.csv")
        print(f"Looking for CSV at: {csv_path}")
        if os.path.exists(csv_path):
            CSV_DATA = parse_nearmap_csv(csv_path)
            print(f"✅ Loaded {len(CSV_DATA)} properties from CSV")
        else:
            CSV_DATA = []
            print(f"❌ No CSV data found at {csv_path}")

# Load data on startup
load_csv_data()

# Enhanced Authentication System
class TileitAuth:
    def __init__(self):
        self.db_path = "tileit_users.db"
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with enhanced schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                business_name TEXT NOT NULL,
                license_id TEXT NOT NULL,
                primary_zip_code TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                reset_token TEXT,
                reset_token_expires TEXT
            )
        ''')
        
        # Create sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password: str) -> str:
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
    
    def verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify password against stored hash"""
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash
    
    def generate_session_token(self) -> str:
        """Generate secure session token"""
        return secrets.token_urlsafe(32)
    
    def create_user(self, email: str, password: str, business_name: str, 
                   license_id: str, primary_zip_code: str) -> Optional[Dict]:
        """Create new user account"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if email already exists
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                return None  # Email already exists
            
            user_id = secrets.token_urlsafe(16)
            now = datetime.now().isoformat()
            
            # Hash password
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            # Insert user
            cursor.execute('''
                INSERT INTO users (id, email, password_hash, business_name, license_id, primary_zip_code, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, email, password_hash, business_name, license_id, primary_zip_code, now, now))
            
            conn.commit()
            
            return {
                'id': user_id,
                'email': email,
                'business_name': business_name,
                'license_id': license_id,
                'primary_zip_code': primary_zip_code,
                'created_at': now,
                'last_login': now
            }
            
        except Exception as e:
            print(f"Error creating user: {e}")
            return None
        finally:
            conn.close()
    
    def authenticate_user(self, email: str, password: str, ip_address: str = None, user_agent: str = None) -> Optional[Dict]:
        """Authenticate user login"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT id, email, password_hash, business_name, license_id, primary_zip_code, created_at, last_login, is_active
                FROM users WHERE email = ? AND is_active = 1
            ''', (email,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            user_id, email, password_hash, business_name, license_id, primary_zip_code, created_at, last_login, is_active = row
            
            if self.verify_password(password, password_hash):
                # Update last login
                now = datetime.now().isoformat()
                cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, user_id))
                conn.commit()
                
                return {
                    'id': user_id,
                    'email': email,
                    'business_name': business_name,
                    'license_id': license_id,
                    'primary_zip_code': primary_zip_code,
                    'created_at': created_at,
                    'last_login': now,
                    'is_active': bool(is_active)
                }
            
            return None
            
        except Exception as e:
            print(f"Error authenticating user: {e}")
            return None
        finally:
            conn.close()
    
    def create_session(self, user: Dict, ip_address: str = None, user_agent: str = None) -> str:
        """Create user session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            token = self.generate_session_token()
            now = datetime.now().isoformat()
            expires_at = (datetime.now() + timedelta(hours=24)).isoformat()
            
            # Store session in database
            cursor.execute('''
                INSERT OR REPLACE INTO sessions (token, user_id, created_at, expires_at, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (token, user['id'], now, expires_at, ip_address, user_agent))
            
            conn.commit()
            return token
            
        except Exception as e:
            print(f"Error creating session: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_from_session(self, token: str) -> Optional[Dict]:
        """Get user from session token"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check session validity
            cursor.execute('''
                SELECT s.user_id, s.expires_at, u.id, u.email, u.password_hash, u.business_name, 
                       u.license_id, u.primary_zip_code, u.created_at, u.last_login, u.is_active
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ? AND s.expires_at > ? AND u.is_active = 1
            ''', (token, datetime.now().isoformat()))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            user_id, expires_at, id, email, password_hash, business_name, license_id, primary_zip_code, created_at, last_login, is_active = row
            
            return {
                'id': id,
                'email': email,
                'business_name': business_name,
                'license_id': license_id,
                'primary_zip_code': primary_zip_code,
                'created_at': created_at,
                'last_login': last_login,
                'is_active': bool(is_active)
            }
            
        except Exception as e:
            print(f"Error getting user from session: {e}")
            return None
        finally:
            conn.close()
    
    def logout(self, token: str):
        """Logout user and remove session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
        except Exception as e:
            print(f"Error logging out: {e}")
        finally:
            conn.close()
    
    def generate_reset_token(self, email: str) -> Optional[str]:
        """Generate password reset token"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id FROM users WHERE email = ? AND is_active = 1", (email,))
            user = cursor.fetchone()
            if not user:
                return None
            
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.now() + timedelta(hours=1)).isoformat()
            
            cursor.execute('''
                UPDATE users SET reset_token = ?, reset_token_expires = ? WHERE email = ?
            ''', (token, expires_at, email))
            
            conn.commit()
            return token
            
        except Exception as e:
            print(f"Error generating reset token: {e}")
            return None
        finally:
            conn.close()
    
    def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using token"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT id FROM users WHERE reset_token = ? AND reset_token_expires > ? AND is_active = 1
            ''', (token, datetime.now().isoformat()))
            
            user = cursor.fetchone()
            if not user:
                return False
            
            password_hash = hashlib.sha256(new_password.encode()).hexdigest()
            
            cursor.execute('''
                UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expires = NULL 
                WHERE reset_token = ?
            ''', (password_hash, token))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error resetting password: {e}")
            return False
        finally:
            conn.close()

# Global auth instance
auth = TileitAuth()

# Authentication decorator
def require_auth(f):
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth.get_user_from_session(token)
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        return f(user, *args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Enhanced Property Processing
def calculate_roof_area_from_csv(prop: Dict) -> float:
    """
    Calculate roof area from CSV data
    Uses multiple methods to estimate roof area
    """
    # Method 1: Use metal clipped area if available (already in sqm, convert to sqft)
    metal_area_sqm = prop.get('metal clipped area (sqm)', 0)
    if metal_area_sqm > 0:
        return metal_area_sqm * 10.764  # Convert sqm to sqft
    
    # Method 2: Estimate from tile count (assume ~1 sqft per tile)
    tile_count = prop.get('tile count', 0)
    if tile_count > 0:
        return float(tile_count)
    
    # Method 3: Estimate from repair areas (assume repairs are 10-15% of total)
    total_repair_sqm = (
        prop.get('shingle repair area (sqm)', 0) +
        prop.get('tile repair area (sqm)', 0) +
        prop.get('metal repair area (sqm)', 0)
    )
    if total_repair_sqm > 0:
        # Assume repairs represent 12.5% of total area
        estimated_sqm = total_repair_sqm * 8
        return estimated_sqm * 10.764  # Convert to sqft
    
    # Method 4: Default estimate based on building size and stories
    # Average single-family home is 1500-2500 sqft
    num_stories = prop.get('num stories', 1)
    if num_stories >= 3:
        return 3000
    elif num_stories == 2:
        return 2500
    else:
        return 2000

def process_properties_with_deduplication():
    """Process properties and combine duplicates by address"""
    if not CSV_DATA:
        return []
    
    # Group by address
    address_groups = {}
    for prop in CSV_DATA:
        address = prop.get('address', '').strip()
        if not address:
            continue
            
        if address not in address_groups:
            address_groups[address] = []
        address_groups[address].append(prop)
    
    # Combine properties with same address
    processed_properties = []
    for address, props in address_groups.items():
        if len(props) == 1:
            # Single property - calculate roof area
            prop = props[0]
            prop['roof_area'] = calculate_roof_area_from_csv(prop)
            prop['roof_layers'] = 1
            processed_properties.append(prop)
        else:
            # Combine multiple roof layers
            combined_prop = props[0].copy()
            combined_prop['roof_layers'] = len(props)
            combined_prop['all_pitches'] = [p.get('pitch', 0) for p in props]
            combined_prop['all_conditions'] = [p.get('roof condition summary score', 0) for p in props]
            combined_prop['all_heights'] = [p.get('height (ft)', 0) for p in props]
            combined_prop['all_materials'] = [p.get('roof_material', '') for p in props]
            
            # Calculate total roof area from all layers
            total_area = sum(calculate_roof_area_from_csv(p) for p in props)
            combined_prop['roof_area'] = total_area
            
            # Calculate averages
            combined_prop['avg_pitch'] = sum(combined_prop['all_pitches']) / len(combined_prop['all_pitches'])
            combined_prop['avg_condition'] = sum(combined_prop['all_conditions']) / len(combined_prop['all_conditions'])
            combined_prop['avg_height'] = sum(combined_prop['all_heights']) / len(combined_prop['all_heights'])
            
            # Use the most common material
            materials = [m for m in combined_prop['all_materials'] if m]
            if materials:
                combined_prop['roof_material'] = max(set(materials), key=materials.count)
            
            processed_properties.append(combined_prop)
    
    return processed_properties

# Routes
@app.route('/')
def index():
    """Main dashboard page"""
    return render_template_string(TILEIT_DASHBOARD_TEMPLATE)

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
        user = auth.create_user(
            email=data['email'],
            password=data['password'],
            business_name=data['business_name'],
            license_id=data['license_id'],
            primary_zip_code=data['primary_zip_code']
        )
        
        if not user:
            return jsonify({'error': 'Email already exists'}), 400
        
        # Create session
        token = auth.create_session(user, request.remote_addr, request.headers.get('User-Agent'))
        
        return jsonify({
            'success': True,
            'message': 'Registration successful',
            'token': token,
            'user': user
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
        
        user = auth.authenticate_user(email, password, request.remote_addr, request.headers.get('User-Agent'))
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Create session
        token = auth.create_session(user, request.remote_addr, request.headers.get('User-Agent'))
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': user
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Send password reset email"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'Email required'}), 400
        
        token = auth.generate_reset_token(email)
        if not token:
            return jsonify({'error': 'Email not found'}), 404
        
        # In production, send actual email
        # For now, return the token for testing
        reset_url = f"http://localhost:5000/reset-password?token={token}"
        
        return jsonify({
            'success': True,
            'message': 'Password reset email sent',
            'reset_url': reset_url  # For testing only
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """Reset password using token"""
    try:
        data = request.get_json()
        token = data.get('token')
        new_password = data.get('new_password')
        
        if not token or not new_password:
            return jsonify({'error': 'Token and new password required'}), 400
        
        success = auth.reset_password(token, new_password)
        if not success:
            return jsonify({'error': 'Invalid or expired token'}), 400
        
        return jsonify({
            'success': True,
            'message': 'Password reset successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout_route():
    """Logout user"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if token:
            auth.logout(token)
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    except Exception as e:
        return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/profile', methods=['GET'])
@require_auth
def get_profile(user):
    """Get user profile"""
    return jsonify({
        'success': True,
        'user': user
    })

@app.route('/api/profile', methods=['PUT'])
@require_auth
def update_profile(user):
    """Update user profile"""
    try:
        data = request.get_json()
        
        # Update user profile in database
        conn = sqlite3.connect(auth.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET business_name = ?, license_id = ?, primary_zip_code = ?
            WHERE id = ?
        ''', (data.get('business_name', user['business_name']),
              data.get('license_id', user['license_id']),
              data.get('primary_zip_code', user['primary_zip_code']),
              user['id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/profile/roofer', methods=['GET'])
@require_auth
def get_roofer_profile(user):
    """Get roofer business profile"""
    try:
        profile_file = f"profiles/{user['id']}_roofer_profile.json"
        if os.path.exists(profile_file):
            with open(profile_file, 'r') as f:
                profile = json.load(f)
                return jsonify({'success': True, 'profile': profile, 'profile_exists': True})
        else:
            # Return default profile with profile_exists = False
            return jsonify({
                'success': True,
                'profile_exists': False,
                'profile': {
                    'labor_rate': 45,
                    'daily_productivity': 2500,
                    'base_crew_size': 3,
                    'crew_scaling_rule': 'size_and_complexity',
                    'slope_cost_adjustment': {'flat_low': 0.0, 'moderate': 0.1, 'steep': 0.2, 'very_steep': 0.3},
                    'material_costs': {'asphalt': 4.0, 'shingle': 4.5, 'metal': 7.0, 'tile': 8.0, 'concrete': 6.0},
                    'replacement_costs': {'asphalt': 45, 'shingle': 50, 'metal': 90, 'tile': 70, 'concrete': 60},
                    'overhead_percent': 0.1,
                    'profit_margin': 0.2
                }
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/profile/roofer', methods=['POST'])
@require_auth
def save_roofer_profile(user):
    """Save roofer business profile"""
    try:
        data = request.get_json()
        
        # Create profile data
        profile = {
            'business_name': user['business_name'],
            'license_id': user['license_id'],
            'primary_zip_code': user['primary_zip_code'],
            'email': user['email'],
            'labor_rate': float(data.get('labor_rate', 45)),
            'daily_productivity': int(data.get('daily_productivity', 2500)),
            'base_crew_size': int(data.get('base_crew_size', 3)),
            'crew_scaling_rule': data.get('crew_scaling_rule', 'size_and_complexity'),
            'slope_cost_adjustment': data.get('slope_cost_adjustment', {}),
            'material_costs': data.get('material_costs', {}),
            'replacement_costs': data.get('replacement_costs', {}),
            'overhead_percent': float(data.get('overhead_percent', 0.1)),
            'profit_margin': float(data.get('profit_margin', 0.2))
        }
        
        # Save to file
        os.makedirs('profiles', exist_ok=True)
        profile_file = f"profiles/{user['id']}_roofer_profile.json"
        with open(profile_file, 'w') as f:
            json.dump(profile, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Business profile saved successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotes/generate', methods=['POST'])
@require_auth
def generate_quotes(user):
    """Generate quotes for selected properties"""
    try:
        print(f"\n=== GENERATING QUOTES FOR USER: {user['id']} ===")
        
        # Load roofer profile
        profile_file = f"profiles/{user['id']}_roofer_profile.json"
        if not os.path.exists(profile_file):
            print(f"ERROR: Profile file not found at {profile_file}")
            return jsonify({'error': 'Please complete your business profile first'}), 400
        
        with open(profile_file, 'r') as f:
            profile_data = json.load(f)
        
        print(f"Loaded profile: {profile_data.get('business_name')}")
        print(f"Labor rate: ${profile_data.get('labor_rate')}/hr")
        print(f"Crew size: {profile_data.get('base_crew_size')}")
        
        # Create RooferProfile object
        roofer_profile = RooferProfile.from_dict(profile_data)
        
        # Get address filters from request
        data = request.get_json() or {}
        addresses = data.get('addresses', [])
        
        # Process all CSV data and group by address
        processed_data = process_properties_with_deduplication()
        print(f"\nProcessed {len(processed_data)} unique properties")
        
        quotes = []
        errors = []
        
        # Process properties
        properties_to_process = processed_data if not addresses else [p for p in processed_data if p.get('address') in addresses]
        print(f"Processing {len(properties_to_process)} properties...")
        
        for i, prop in enumerate(properties_to_process):
            try:
                address = prop.get('address', 'Unknown')
                print(f"\n[{i+1}/{len(properties_to_process)}] Processing: {address}")
                print(f"  - Area: {prop.get('roof_area', 'N/A')} sqft")
                print(f"  - Material: {prop.get('roof_material', 'N/A')}")
                print(f"  - Pitch: {prop.get('pitch', 'N/A')}°")
                
                quote = calculate_quote(prop, roofer_profile)
                quotes.append(quote.to_dict())
                
                print(f"  [OK] Quote: {quote.estimated_quote_range}")
                
            except Exception as e:
                error_msg = f"Error for {prop.get('address')}: {str(e)}"
                print(f"  [ERROR] {error_msg}")
                errors.append(error_msg)
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\n=== SUMMARY ===")
        print(f"Successfully generated: {len(quotes)} quotes")
        print(f"Errors: {len(errors)}")
        
        if errors:
            print("\nErrors encountered:")
            for err in errors[:5]:  # Show first 5 errors
                print(f"  - {err}")
        
        # Save quotes to file
        os.makedirs('quotes', exist_ok=True)
        quotes_file = f"quotes/{user['id']}_quotes.json"
        with open(quotes_file, 'w') as f:
            json.dump(quotes, f, indent=2)
        
        print(f"Saved quotes to: {quotes_file}\n")
        
        return jsonify({
            'success': True,
            'quotes': quotes,
            'count': len(quotes),
            'errors': errors if errors else None
        })
        
    except Exception as e:
        print(f"\nFATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotes', methods=['GET'])
@require_auth
def get_quotes(user):
    """Get saved quotes"""
    try:
        quotes_file = f"quotes/{user['id']}_quotes.json"
        if os.path.exists(quotes_file):
            with open(quotes_file, 'r') as f:
                quotes = json.load(f)
            return jsonify({'success': True, 'quotes': quotes})
        else:
            return jsonify({'success': True, 'quotes': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotes/saved', methods=['GET'])
@require_auth
def get_saved_quotes(user):
    """Get all saved quotes for user"""
    try:
        quotes_file = f"quotes/{user['id']}_quotes.json"
        if os.path.exists(quotes_file):
            with open(quotes_file, 'r') as f:
                quotes = json.load(f)
            return jsonify({'success': True, 'quotes': quotes})
        else:
            return jsonify({'success': True, 'quotes': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotes/save', methods=['POST'])
@require_auth
def save_quote(user):
    """Save a new quote"""
    try:
        data = request.json
        print(f"📥 Backend received data: {data}")
        print(f"📥 Data type: {type(data)}")
        print(f"📥 Data keys: {data.keys() if data else 'None'}")
        
        # Validate required fields
        required_fields = ['property_address', 'material', 'area', 'min_quote', 'max_quote']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': f'Missing required field: {field}'}), 400
        
        quotes_file = f"quotes/{user['id']}_quotes.json"
        
        # Load existing quotes
        if os.path.exists(quotes_file):
            with open(quotes_file, 'r') as f:
                quotes = json.load(f)
        else:
            quotes = []
        
        # Check if quote already exists for this property
        existing_quote = next((q for q in quotes if q['property_address'] == data['property_address']), None)
        if existing_quote:
            return jsonify({'success': False, 'message': 'Quote already exists for this property'}), 400
        
        # Create new quote
        import uuid
        import datetime
        new_quote = {
            'id': str(uuid.uuid4()),
            'property_address': data['property_address'],
            'material': data['material'],
            'area': data['area'],
            'min_quote': data['min_quote'],
            'max_quote': data['max_quote'],
            'crew_size': data.get('crew_size', 3),
            'time_estimate': data.get('time_estimate', 0),
            'notes': data.get('notes', ''),
            'saved_date': datetime.datetime.now().isoformat()
        }
        
        quotes.append(new_quote)
        
        # Ensure quotes directory exists
        os.makedirs('quotes', exist_ok=True)
        
        # Save quotes
        with open(quotes_file, 'w') as f:
            json.dump(quotes, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Quote saved successfully', 'quote': new_quote})
    
    except Exception as e:
        print(f"Error saving quote: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/quotes/<quote_id>', methods=['DELETE'])
@require_auth
def delete_quote(user, quote_id):
    """Delete a saved quote"""
    try:
        quotes_file = f"quotes/{user['id']}_quotes.json"
        
        if not os.path.exists(quotes_file):
            return jsonify({'success': False, 'message': 'No quotes found'}), 404
        
        with open(quotes_file, 'r') as f:
            quotes = json.load(f)
        
        # Filter out the quote to delete
        original_length = len(quotes)
        quotes = [q for q in quotes if q['id'] != quote_id]
        
        if len(quotes) == original_length:
            return jsonify({'success': False, 'message': 'Quote not found'}), 404
        
        # Save updated quotes
        with open(quotes_file, 'w') as f:
            json.dump(quotes, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Quote deleted successfully'})
    
    except Exception as e:
        print(f"Error deleting quote: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings', methods=['GET'])
@require_auth
def get_settings(user):
    """Get user settings"""
    try:
        settings_file = f"settings/{user['id']}_settings.json"
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
        else:
            settings = {
                'notifications': True,
                'email_alerts': True,
                'quote_auto_save': True,
                'default_filters': {},
                'theme': 'light'
            }
        
        return jsonify({
            'success': True,
            'settings': settings
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['PUT'])
@require_auth
def update_settings(user):
    """Update user settings"""
    try:
        data = request.get_json()
        
        os.makedirs('settings', exist_ok=True)
        settings_file = f"settings/{user['id']}_settings.json"
        
        with open(settings_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Settings updated successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/properties', methods=['GET'])
@require_auth
def get_properties(user):
    """Get properties with enhanced filtering and pagination"""
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
        
        print(f"\n=== PROPERTIES FILTER REQUEST ===")
        print(f"Page: {page}, Per page: {per_page}")
        print(f"Filters: min_area={min_area}, max_area={max_area}, material={material}")
        print(f"         min_pitch={min_pitch}, max_pitch={max_pitch}")
        print(f"         condition_min={condition_min}, condition_max={condition_max}")
        print(f"         search={search_address}")
        
        # Get processed properties (with deduplication)
        processed_data = process_properties_with_deduplication()
        print(f"Total properties before filtering: {len(processed_data)}")
        
        # Apply filters
        filtered_data = processed_data.copy()
        
        if min_area is not None:
            before = len(filtered_data)
            filtered_data = [p for p in filtered_data if p.get('roof_area', 0) >= min_area]
            print(f"After min_area filter: {before} -> {len(filtered_data)}")
        
        if max_area is not None:
            before = len(filtered_data)
            filtered_data = [p for p in filtered_data if p.get('roof_area', 0) <= max_area]
            print(f"After max_area filter: {before} -> {len(filtered_data)}")
        
        if material:
            before = len(filtered_data)
            filtered_data = [p for p in filtered_data if p.get('roof_material', '').lower() == material]
            print(f"After material filter ({material}): {before} -> {len(filtered_data)}")
        
        if min_pitch is not None:
            before = len(filtered_data)
            filtered_data = [p for p in filtered_data if p.get('avg_pitch', p.get('pitch', 0)) >= min_pitch]
            print(f"After min_pitch filter: {before} -> {len(filtered_data)}")
        
        if max_pitch is not None:
            before = len(filtered_data)
            filtered_data = [p for p in filtered_data if p.get('avg_pitch', p.get('pitch', 0)) <= max_pitch]
            print(f"After max_pitch filter: {before} -> {len(filtered_data)}")
        
        if condition_min is not None:
            before = len(filtered_data)
            filtered_data = [p for p in filtered_data if p.get('avg_condition', p.get('roof condition summary score', 0)) >= condition_min]
            print(f"After condition_min filter: {before} -> {len(filtered_data)}")
        
        if condition_max is not None:
            before = len(filtered_data)
            filtered_data = [p for p in filtered_data if p.get('avg_condition', p.get('roof condition summary score', 0)) <= condition_max]
            print(f"After condition_max filter: {before} -> {len(filtered_data)}")
        
        if search_address:
            before = len(filtered_data)
            filtered_data = [p for p in filtered_data if search_address in p.get('address', '').lower()]
            print(f"After search filter ({search_address}): {before} -> {len(filtered_data)}")
        
        # Calculate pagination
        total_properties = len(filtered_data)
        total_pages = math.ceil(total_properties / per_page)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        # Get page data
        page_data = filtered_data[start_idx:end_idx]
        
        print(f"\nFinal results: {total_properties} properties, returning page {page}/{total_pages} ({len(page_data)} items)")
        print("=" * 40 + "\n")
        
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

@app.route('/api/properties/<property_id>', methods=['GET'])
@require_auth
def get_property_details(user, property_id):
    """Get detailed property information"""
    try:
        # Find property by address (using property_id as address for now)
        processed_data = process_properties_with_deduplication()
        property_data = None
        
        for prop in processed_data:
            if prop.get('address', '').replace(' ', '').lower() == property_id.replace('_', ' ').lower():
                property_data = prop
                break
        
        if not property_data:
            return jsonify({'error': 'Property not found'}), 404
        
        return jsonify({
            'success': True,
            'property': property_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'tileit-roofing-dashboard',
        'properties_loaded': len(CSV_DATA) if CSV_DATA else 0
    })

# Enhanced HTML template with all best practices
TILEIT_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Professional roofing quote generator for contractors. Generate accurate quotes based on roof area, pitch, condition, and materials.">
    <meta name="keywords" content="roofing, quotes, contractors, roofing estimate, roof calculator">
    <meta name="author" content="Tileit">
    <meta property="og:title" content="Tileit - Professional Roofing Solutions">
    <meta property="og:description" content="Generate accurate roofing quotes in seconds">
    <meta property="og:type" content="website">
    <title>Tileit - Professional Roofing Solutions</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🏠</text></svg>">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            background: #fafafa;
            color: #1d1d1f;
            line-height: 1.47;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 20px;
        }
        
        /* Header */
        .header {
            background: #ffffff;
            border-bottom: 1px solid #e5e7eb;
            position: sticky;
            top: 0;
            z-index: 1000;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 0;
        }
        
        .logo {
            font-size: 28px;
            font-weight: 700;
            color: #1d1d1f;
            text-decoration: none;
        }
        
        .nav {
            display: flex;
            gap: 32px;
            align-items: center;
        }
        
        .nav-item {
            color: #1d1d1f;
            text-decoration: none;
            font-size: 17px;
            font-weight: 500;
            transition: all 0.3s ease;
            padding: 8px 16px;
            border-radius: 8px;
        }
        
        .nav-item:hover {
            color: #1d9bf0;
            background: rgba(29, 155, 240, 0.1);
        }
        
        .nav-item.active {
            color: #1d9bf0;
            background: rgba(29, 155, 240, 0.1);
        }
        
        .user-menu {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: #1d9bf0;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 16px;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }
        
        .btn {
            padding: 12px 24px;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 500;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        
        .btn-primary {
            background: #1d9bf0;
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
        }
        
        .btn-secondary {
            background: #f8f9fa;
            color: #1d1d1f;
            border: 2px solid #e9ecef;
        }
        
        .btn-secondary:hover {
            background: #e9ecef;
            transform: translateY(-2px);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #ff6b6b, #ee5a52);
            color: white;
        }
        
        .btn-danger:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(255, 107, 107, 0.4);
        }
        
        /* Auth Section */
        .auth-container {
            max-width: 450px;
            margin: 80px auto;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            border: 1px solid #e5e7eb;
        }
        
        .auth-header {
            background: #1d9bf0;
            padding: 32px;
            text-align: center;
            color: white;
        }
        
        .auth-title {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 12px;
        }
        
        .auth-subtitle {
            font-size: 18px;
            opacity: 0.9;
        }
        
        .auth-tabs {
            display: flex;
            background: #f8f9fa;
        }
        
        .auth-tab {
            flex: 1;
            padding: 20px;
            background: none;
            border: none;
            cursor: pointer;
            font-size: 18px;
            font-weight: 600;
            color: #6c757d;
            transition: all 0.3s ease;
        }
        
        .auth-tab.active {
            background: white;
            color: #1d9bf0;
            border-bottom: 3px solid #1d9bf0;
        }
        
        .auth-form {
            padding: 40px;
        }
        
        .form-group {
            margin-bottom: 24px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-size: 16px;
            font-weight: 600;
            color: #1d1d1f;
        }
        
        .form-group input {
            width: 100%;
            padding: 16px 20px;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            font-size: 16px;
            transition: all 0.3s ease;
            background: white;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: #1d9bf0;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
        }
        
        .form-row {
            display: flex;
            gap: 16px;
        }
        
        .form-row .form-group {
            flex: 1;
        }
        
        .forgot-password {
            text-align: right;
            margin-top: 16px;
        }
        
        .forgot-password a {
            color: #1d9bf0;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
        }
        
        .forgot-password a:hover {
            text-decoration: underline;
        }
        
        /* Dashboard */
        .dashboard {
            display: none;
        }
        
        .dashboard.active {
            display: block;
        }
        
        .dashboard-header {
            background: #ffffff;
            border-radius: 12px;
            padding: 32px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid #e5e7eb;
        }
        
        .dashboard-title {
            font-size: 32px;
            font-weight: 700;
            color: #1d1d1f;
            margin-bottom: 8px;
        }
        
        .dashboard-subtitle {
            color: #6c757d;
            font-size: 20px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 24px;
            margin-bottom: 40px;
        }
        
        .stat-card {
            background: #ffffff;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid #e5e7eb;
            transition: all 0.2s ease;
        }
        
        .stat-card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            border-color: #1d9bf0;
        }
        
        .stat-card h3 {
            color: #6c757d;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
        }
        
        .stat-card .number {
            font-size: 36px;
            font-weight: 700;
            color: #1d1d1f;
        }
        
        /* Filters */
        .filters-container {
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 24px;
            padding: 24px;
            border: 1px solid #e5e7eb;
        }
        
        .filters-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }
        
        .filters-title {
            font-size: 24px;
            font-weight: 700;
            color: #1d1d1f;
        }
        
        .filters-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }
        
        .filter-group {
            display: flex;
            flex-direction: column;
        }
        
        .filter-group label {
            font-size: 14px;
            font-weight: 600;
            color: #1d1d1f;
            margin-bottom: 8px;
        }
        
        .filter-group input,
        .filter-group select {
            padding: 12px 16px;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            font-size: 16px;
            transition: all 0.3s ease;
        }
        
        .filter-group input:focus,
        .filter-group select:focus {
            outline: none;
            border-color: #1d9bf0;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
        }
        
        .filter-actions {
            display: flex;
            gap: 16px;
            align-items: center;
        }
        
        .btn-filter {
            background: linear-gradient(135deg, #28a745, #20c997);
            color: white;
            padding: 12px 24px;
            border-radius: 12px;
            border: none;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .btn-filter:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(40, 167, 69, 0.4);
        }
        
        .btn-clear {
            background: linear-gradient(135deg, #dc3545, #c82333);
            color: white;
            padding: 12px 24px;
            border-radius: 12px;
            border: none;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .btn-clear:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(220, 53, 69, 0.4);
        }
        
        /* Properties Table */
        .properties-container {
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 24px;
            border: 1px solid #e5e7eb;
        }
        
        .properties-header {
            padding: 20px 24px;
            border-bottom: 1px solid #e5e7eb;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .properties-title {
            font-size: 24px;
            font-weight: 700;
            color: #1d1d1f;
        }
        
        .properties-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .properties-table th,
        .properties-table td {
            padding: 16px 20px;
            text-align: left;
            border-bottom: 1px solid #e9ecef;
        }
        
        .properties-table th {
            background: #f8f9fa;
            font-weight: 600;
            color: #1d1d1f;
            font-size: 16px;
        }
        
        .properties-table td {
            font-size: 16px;
            color: #1d1d1f;
        }
        
        .properties-table tbody tr {
            transition: all 0.2s ease;
        }
        
        .properties-table tbody tr:hover {
            background: #eff6ff;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(79, 70, 229, 0.1);
            transform: translateY(-2px);
        }
        
        .property-link {
            color: #1d9bf0;
            text-decoration: none;
            font-weight: 500;
        }
        
        .property-link:hover {
            text-decoration: underline;
        }
        
        /* Modal */
        .modal {
            display: none;
            position: fixed;
            z-index: 2000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(10px);
        }
        
        .modal-content {
            background: white;
            margin: 5% auto;
            padding: 0;
            border-radius: 20px;
            width: 90%;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.3);
        }
        
        .modal-header {
            background: #1d9bf0;
            color: white;
            padding: 24px 32px;
            border-radius: 20px 20px 0 0;
        }
        
        .modal-title {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 8px;
        }
        
        .modal-body {
            padding: 32px;
        }
        
        .close {
            color: white;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .close:hover {
            opacity: 0.7;
        }
        
        /* Pagination */
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 12px;
            padding: 24px;
        }
        
        .pagination button {
            padding: 12px 20px;
            border: 2px solid #e9ecef;
            background: white;
            border-radius: 12px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        
        .pagination button:hover:not(:disabled) {
            border-color: #1d9bf0;
            color: #1d9bf0;
        }
        
        .pagination button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .pagination .active {
            background: #1d9bf0;
            color: white;
            border-color: #1d9bf0;
        }
        
        /* Loading */
        .loading {
            text-align: center;
            padding: 60px;
            color: #6c757d;
            font-size: 18px;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #1d9bf0;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .error {
            background: linear-gradient(135deg, #dc3545, #c82333);
            color: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            font-size: 16px;
        }
        
        .success {
            background: linear-gradient(135deg, #28a745, #20c997);
            color: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            font-size: 16px;
        }
        
        /* Toast Notifications */
        .toast-container {
            position: fixed;
            top: 80px;
            right: 20px;
            z-index: 3000;
            display: flex;
            flex-direction: column;
            gap: 12px;
            max-width: 400px;
        }
        
        .toast {
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            padding: 16px 20px;
            display: flex;
            align-items: center;
            gap: 12px;
            animation: slideIn 0.3s ease-out;
            min-width: 300px;
        }
        
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
        
        .toast.hiding {
            animation: slideOut 0.3s ease-out forwards;
        }
        
        .toast-icon {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            flex-shrink: 0;
        }
        
        .toast-success .toast-icon {
            background: #28a745;
            color: white;
        }
        
        .toast-error .toast-icon {
            background: #dc3545;
            color: white;
        }
        
        .toast-info .toast-icon {
            background: #17a2b8;
            color: white;
        }
        
        .toast-warning .toast-icon {
            background: #ffc107;
            color: #1d1d1f;
        }
        
        .toast-content {
            flex: 1;
        }
        
        .toast-title {
            font-weight: 600;
            margin-bottom: 4px;
            color: #1d1d1f;
        }
        
        .toast-message {
            font-size: 14px;
            color: #6c757d;
        }
        
        .toast-close {
            background: none;
            border: none;
            font-size: 20px;
            color: #6c757d;
            cursor: pointer;
            padding: 0;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: color 0.2s;
        }
        
        .toast-close:hover {
            color: #1d1d1f;
        }
        
        /* User Dropdown Menu */
        .user-menu {
            position: relative;
        }
        
        .user-info {
            display: flex;
            align-items: center;
            gap: 12px;
            cursor: pointer;
            padding: 8px 12px;
            border-radius: 12px;
            transition: all 0.3s ease;
        }
        
        .user-info:hover {
            background: rgba(102, 126, 234, 0.1);
        }
        
        .user-name {
            font-weight: 500;
            color: #1d1d1f;
        }
        
        .user-dropdown {
            position: absolute;
            top: 100%;
            right: 0;
            margin-top: 8px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            min-width: 200px;
            display: none;
            opacity: 0;
            transform: translateY(-10px);
            transition: all 0.3s ease;
        }
        
        .user-dropdown.active {
            display: block;
            opacity: 1;
            transform: translateY(0);
        }
        
        .dropdown-item {
            padding: 12px 20px;
            color: #1d1d1f;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 12px;
            transition: all 0.2s;
            cursor: pointer;
            border: none;
            background: none;
            width: 100%;
            text-align: left;
            font-size: 15px;
        }
        
        .dropdown-item:first-child {
            border-radius: 12px 12px 0 0;
        }
        
        .dropdown-item:last-child {
            border-radius: 0 0 12px 12px;
        }
        
        .dropdown-item:hover {
            background: rgba(102, 126, 234, 0.1);
        }
        
        .dropdown-divider {
            height: 1px;
            background: #e9ecef;
            margin: 8px 0;
        }
        
        .dropdown-item.danger {
            color: #dc3545;
        }
        
        .dropdown-item.danger:hover {
            background: rgba(220, 53, 69, 0.1);
        }
        
        /* Password Strength Indicator */
        .password-strength {
            margin-top: 8px;
            height: 4px;
            background: #e9ecef;
            border-radius: 2px;
            overflow: hidden;
            display: none;
        }
        
        .password-strength.active {
            display: block;
        }
        
        .password-strength-bar {
            height: 100%;
            transition: all 0.3s ease;
            border-radius: 2px;
        }
        
        .password-strength-weak .password-strength-bar {
            width: 33%;
            background: #dc3545;
        }
        
        .password-strength-medium .password-strength-bar {
            width: 66%;
            background: #ffc107;
        }
        
        .password-strength-strong .password-strength-bar {
            width: 100%;
            background: #28a745;
        }
        
        .password-hint {
            font-size: 12px;
            color: #6c757d;
            margin-top: 4px;
        }
        
        /* Confirmation Dialog */
        .confirm-dialog {
            display: none;
            position: fixed;
            z-index: 3000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(10px);
            align-items: center;
            justify-content: center;
        }
        
        .confirm-dialog.active {
            display: flex;
        }
        
        .confirm-content {
            background: white;
            border-radius: 20px;
            padding: 32px;
            max-width: 400px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
        }
        
        .confirm-title {
            font-size: 24px;
            font-weight: 700;
            color: #1d1d1f;
            margin-bottom: 12px;
        }
        
        .confirm-message {
            color: #6c757d;
            font-size: 16px;
            margin-bottom: 24px;
            line-height: 1.5;
        }
        
        .confirm-actions {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
        }
        
        /* Loading Button State */
        .btn.loading {
            position: relative;
            color: transparent;
            pointer-events: none;
        }
        
        .btn.loading::after {
            content: '';
            position: absolute;
            width: 16px;
            height: 16px;
            top: 50%;
            left: 50%;
            margin-left: -8px;
            margin-top: -8px;
            border: 2px solid #ffffff;
            border-radius: 50%;
            border-top-color: transparent;
            animation: spin 0.6s linear infinite;
        }
        
        /* Footer */
        .footer {
            background: rgba(255, 255, 255, 0.95);
            border-top: 1px solid rgba(0, 0, 0, 0.1);
            padding: 40px 0;
            margin-top: 80px;
        }
        
        .footer-content {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 32px;
        }
        
        .footer-section h4 {
            font-size: 16px;
            font-weight: 600;
            color: #1d1d1f;
            margin-bottom: 16px;
        }
        
        .footer-links {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .footer-link {
            color: #6c757d;
            text-decoration: none;
            font-size: 14px;
            transition: color 0.2s;
        }
        
        .footer-link:hover {
            color: #1d9bf0;
        }
        
        .footer-bottom {
            border-top: 1px solid #e9ecef;
            margin-top: 32px;
            padding-top: 24px;
            text-align: center;
            color: #6c757d;
            font-size: 14px;
        }
        
        /* Session Timeout Warning */
        .session-warning {
            display: none;
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: linear-gradient(135deg, #ffc107, #ff9800);
            color: #1d1d1f;
            padding: 20px 24px;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
            max-width: 350px;
            z-index: 2000;
        }
        
        .session-warning.active {
            display: block;
            animation: slideIn 0.3s ease-out;
        }
        
        .session-warning-title {
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .session-warning-message {
            font-size: 14px;
            margin-bottom: 12px;
        }
        
        .session-warning-actions {
            display: flex;
            gap: 12px;
        }
        
        .btn-small {
            padding: 8px 16px;
            font-size: 14px;
        }
        
        /* Accessibility improvements */
        .sr-only {
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border-width: 0;
        }
        
        *:focus-visible {
            outline: 3px solid #1d9bf0;
            outline-offset: 2px;
        }
        
        /* Property Details Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            animation: fadeIn 0.3s ease-out;
        }
        
        .modal-content {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 800px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            animation: slideUp 0.3s ease-out;
        }
        
        @keyframes slideUp {
            from {
                transform: translateY(30px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }
        
        .modal-header {
            padding: 24px 32px;
            border-bottom: 1px solid #e9ecef;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .modal-header h2 {
            margin: 0;
            font-size: 24px;
            font-weight: 600;
            color: #1d1d1f;
        }
        
        .btn-close {
            background: none;
            border: none;
            font-size: 32px;
            color: #6c757d;
            cursor: pointer;
            padding: 0;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 6px;
            transition: all 0.2s;
        }
        
        .btn-close:hover {
            background: #f8f9fa;
            color: #1d1d1f;
        }
        
        .modal-body {
            padding: 32px;
        }
        
        .property-details-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 32px;
        }
        
        .detail-section {
            background: #ffffff;
            padding: 0;
            border-radius: 0;
        }
        
        .detail-section h3 {
            margin: 0 0 20px 0;
            font-size: 18px;
            font-weight: 600;
            color: #1d1d1f;
        }
        
        .detail-row {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #dee2e6;
        }
        
        .detail-row:last-child {
            border-bottom: none;
        }
        
        .detail-label {
            font-weight: 500;
            color: #6c757d;
        }
        
        .detail-value {
            font-weight: 600;
            color: #1d1d1f;
        }
        
        /* New Modern Info Item Styling */
        .info-item {
            display: flex;
            flex-direction: column;
            gap: 6px;
            padding: 14px 0;
            border-bottom: 1px solid #e5e7eb;
        }
        
        .info-item:last-child {
            border-bottom: none;
        }
        
        .info-label {
            font-size: 13px;
            font-weight: 500;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .info-value {
            font-size: 16px;
            font-weight: 600;
            color: #111827;
        }
        
        .quote-summary {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        
        .quote-range {
            background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%);
            padding: 24px;
            border-radius: 12px;
            color: white;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2);
        }
        
        .quote-range h4 {
            margin: 0 0 16px 0;
            font-size: 16px;
            font-weight: 500;
            opacity: 0.9;
        }
        
        .quote-amounts {
            display: flex;
            gap: 20px;
        }
        
        .quote-amount {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        
        .amount-label {
            font-size: 12px;
            opacity: 0.8;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }
        
        .amount-value {
            font-size: 28px;
            font-weight: 700;
        }
        
        .modal-footer {
            padding: 20px 32px;
            border-top: 1px solid #e9ecef;
            display: flex;
            gap: 12px;
            justify-content: flex-end;
        }
        
        .btn-sm {
            padding: 8px 16px;
            font-size: 14px;
        }
        
        /* Property Analysis Section */
        .analysis-section {
            padding: 24px 32px;
            background: #f9fafb;
            border-top: 1px solid #e5e7eb;
        }
        
        .analysis-section h3 {
            margin: 0 0 20px 0;
            font-size: 18px;
            font-weight: 600;
            color: #111827;
        }
        
        .analysis-content {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .analysis-item {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .analysis-label {
            font-size: 13px;
            font-weight: 600;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .analysis-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            width: fit-content;
        }
        
        .status-excellent {
            background: #d1fae5;
            color: #065f46;
        }
        
        .status-good {
            background: #dbeafe;
            color: #1e40af;
        }
        
        .status-fair {
            background: #fef3c7;
            color: #92400e;
        }
        
        .status-poor {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .analysis-list {
            margin: 0;
            padding-left: 20px;
            color: #374151;
            line-height: 1.6;
        }
        
        .analysis-list li {
            margin: 6px 0;
        }
        
        /* Shimmer Loader */
        @keyframes shimmer {
            0% {
                background-position: -1000px 0;
            }
            100% {
                background-position: 1000px 0;
            }
        }
        
        .shimmer {
            animation: shimmer 2s infinite linear;
            background: linear-gradient(to right, #f0f0f0 8%, #e0e0e0 18%, #f0f0f0 33%);
            background-size: 1000px 100%;
        }
        
        .loading-shimmer {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9998;
        }
        
        .shimmer-box {
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            text-align: center;
        }
        
        .shimmer-spinner {
            width: 50px;
            height: 50px;
            border: 4px solid #e5e7eb;
            border-top-color: #4f46e5;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .shimmer-text {
            font-size: 16px;
            font-weight: 500;
            color: #374151;
        }
        
        /* Fade animations for modals */
        @keyframes fadeIn {
            from {
                opacity: 0;
            }
            to {
                opacity: 1;
            }
        }
        
        @keyframes slideUp {
            from {
                transform: translateY(30px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .container {
                padding: 0 16px;
            }
            
            .filters-grid {
                grid-template-columns: 1fr;
            }
            
            .form-row {
                flex-direction: column;
            }
            
            .nav {
                gap: 16px;
            }
            
            .nav-item {
                font-size: 14px;
                padding: 6px 12px;
            }
            
            .property-details-grid {
                grid-template-columns: 1fr;
            }
            
            .modal-content {
                width: 95%;
                max-height: 95vh;
            }
            
            .modal-header,
            .modal-body,
            .modal-footer {
                padding: 16px 20px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <div class="header-content">
                <a href="#" class="logo">Tileit</a>
                <div class="nav">
                    <a href="#" class="nav-item active" onclick="showSection('dashboard')">Dashboard</a>
                    <a href="#" class="nav-item" onclick="showSection('properties')">Properties</a>
                    <a href="#" class="nav-item" onclick="showSection('quotes')">Quotes</a>
                    <a href="#" class="nav-item" onclick="showSection('settings')">Settings</a>
                    <a href="#" class="nav-item" onclick="showSection('profile')">Profile</a>
                </div>
                <div class="user-menu" id="userMenu" style="display: none;">
                    <div class="user-avatar" id="userAvatar">U</div>
                    <span id="userName" style="margin-right: 16px; font-weight: 500;">User</span>
                    <button class="btn btn-danger" onclick="confirmLogout()" style="padding: 8px 20px;">Logout</button>
                </div>
            </div>
        </div>
    </div>

    <div class="container">
        <!-- Authentication Section -->
        <div id="authSection" class="auth-container">
            <div class="auth-header">
                <div class="auth-title">Welcome to Tileit</div>
                <div class="auth-subtitle">Professional roofing solutions for modern businesses</div>
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
                
                <div class="forgot-password">
                    <a href="#" onclick="showForgotPassword()">Forgot Password?</a>
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
                    <input type="password" id="regPassword" placeholder="Create a secure password" oninput="checkPasswordStrength(this.value)">
                    <div class="password-strength" id="passwordStrength">
                        <div class="password-strength-bar"></div>
                    </div>
                    <div class="password-hint" id="passwordHint">Use at least 8 characters with a mix of letters, numbers & symbols</div>
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
            
            <div id="forgotPasswordForm" class="auth-form" style="display: none;">
                <div class="form-group">
                    <label>Email Address</label>
                    <input type="email" id="forgotEmail" placeholder="your@company.com">
                </div>
                
                <button class="btn btn-primary" onclick="forgotPassword()" style="width: 100%;">Send Reset Link</button>
                <button class="btn btn-secondary" onclick="showLogin()" style="width: 100%; margin-top: 12px;">Back to Login</button>
            </div>
        </div>
        
        <!-- Dashboard Section (Stats Only) -->
        <div id="dashboard" class="dashboard">
            <div class="dashboard-header">
                <div class="dashboard-title">Business Dashboard</div>
                <div class="dashboard-subtitle">Overview of your roofing business metrics</div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Available Properties</h3>
                    <div class="number" id="totalProperties">0</div>
                    <p style="font-size: 14px; color: #6c757d; margin-top: 8px;">Properties in database</p>
                </div>
                <div class="stat-card">
                    <h3>Saved Quotes</h3>
                    <div class="number" id="totalQuotes">0</div>
                    <p style="font-size: 14px; color: #6c757d; margin-top: 8px;">Quotes you've saved</p>
                </div>
                <div class="stat-card" id="profileStatusCard" style="cursor: pointer;" onclick="handleProfileStatusClick()">
                    <h3>Profile Status</h3>
                    <div id="profileStatus">Incomplete</div>
                    <p style="font-size: 14px; color: #6c757d; margin-top: 8px;">Click to complete</p>
                </div>
            </div>
            
            <div class="filters-container">
                <h3 style="margin-bottom: 16px; color: #1d1d1f;">Quick Actions</h3>
                <div style="display: flex; gap: 16px; flex-wrap: wrap;">
                    <button class="btn btn-primary" onclick="showSection('properties')">Browse Properties</button>
                    <button class="btn btn-primary" onclick="showSection('quotes')">View Saved Quotes</button>
                    <button class="btn btn-secondary" onclick="showSection('profile')">Update Profile</button>
                </div>
            </div>
        </div>
        
        <!-- Properties Section -->
        <div id="properties" class="dashboard" style="display: none;">
            <div class="dashboard-header">
                <div class="dashboard-title">Property Browser</div>
                <div class="dashboard-subtitle">Browse and filter 25,000+ properties</div>
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
                            <option value="asphalt">Asphalt</option>
                            <option value="shingle">Shingle</option>
                            <option value="metal">Metal</option>
                            <option value="tile">Tile</option>
                            <option value="concrete">Concrete</option>
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
                    <div style="display: flex; gap: 16px; align-items: center;">
                        <div id="propertiesStats" style="color: #6c757d; font-size: 16px;"></div>
                    </div>
                </div>
                
                <div id="propertiesTable">
                    <div class="loading">
                        <div class="spinner"></div>
                        Loading properties...
                    </div>
                </div>
                
                <div class="pagination" id="propertiesPagination" style="display: none;">
                    <button onclick="previousPage()" id="prevPageBtn">Previous</button>
                    <span id="pageInfo">Page 1 of 1</span>
                    <button onclick="nextPage()" id="nextPageBtn">Next</button>
                </div>
            </div>
        </div>
        
        <!-- Saved Quotes Section -->
        <div id="quotes" class="dashboard" style="display: none;">
            <div class="dashboard-header">
                <div class="dashboard-title">Saved Quotes</div>
                <div class="dashboard-subtitle">View and manage your saved property quotes</div>
            </div>
            
            <div class="properties-container">
                <div class="properties-header">
                    <div class="properties-title">Your Saved Quotes</div>
                    <div style="display: flex; gap: 16px; align-items: center;">
                        <div id="savedQuotesStats" style="color: #6c757d; font-size: 16px;"></div>
                    </div>
                </div>
                
                <div id="savedQuotesTable">
                    <div class="loading">
                        <div class="spinner"></div>
                        Loading saved quotes...
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Settings Section -->
        <div id="settings" class="dashboard" style="display: none;">
            <div class="dashboard-header">
                <div class="dashboard-title">Settings</div>
                <div class="dashboard-subtitle">Customize your Tileit experience</div>
            </div>
            
            <div class="filters-container">
                <h3 style="margin-bottom: 24px; color: #1d1d1f;">Notification Settings</h3>
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="notifications" checked> 
                        Enable notifications
                    </label>
                </div>
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="emailAlerts" checked> 
                        Email alerts for new quotes
                    </label>
                </div>
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="autoSave" checked> 
                        Auto-save quotes
                    </label>
                </div>
                
                <button class="btn btn-primary" onclick="saveSettings()">Save Settings</button>
            </div>
            
            <div class="filters-container" style="margin-top: 32px;">
                <h3 style="margin-bottom: 24px; color: #1d1d1f;">Account Actions</h3>
                <button class="btn btn-danger" onclick="confirmLogout()" style="width: 200px;">
                    🚪 Logout
                </button>
            </div>
        </div>
        
        <!-- Profile Section -->
        <div id="profile" class="dashboard" style="display: none;">
            <div class="dashboard-header">
                <div class="dashboard-title">Business Profile</div>
                <div class="dashboard-subtitle">Configure your business information and pricing</div>
            </div>
            
            <!-- Business Information -->
            <div class="filters-container">
                <h3 style="margin-bottom: 24px; color: #1d1d1f;">Business Information</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Business Name</label>
                        <input type="text" id="profileBusinessName" placeholder="Your Roofing Company">
                    </div>
                    <div class="form-group">
                        <label>Email Address</label>
                        <input type="email" id="profileEmail" placeholder="your@company.com" readonly>
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>License ID</label>
                        <input type="text" id="profileLicenseId" placeholder="LIC123456">
                    </div>
                    <div class="form-group">
                        <label>Primary ZIP Code</label>
                        <input type="text" id="profileZipCode" placeholder="11221">
                    </div>
                </div>
            </div>
            
            <!-- Labor Information -->
            <div class="filters-container">
                <h3 style="margin-bottom: 24px; color: #1d1d1f;">Labor Information</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Labor Rate ($/hour per worker)</label>
                        <input type="number" id="profileLaborRate" placeholder="45" step="1" min="0">
                    </div>
                    <div class="form-group">
                        <label>Daily Productivity (sqft/day per crew)</label>
                        <input type="number" id="profileDailyProductivity" placeholder="2500" step="100" min="0">
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>Base Crew Size</label>
                        <input type="number" id="profileBaseCrewSize" placeholder="3" step="1" min="1">
                    </div>
                    <div class="form-group">
                        <label>Crew Scaling Rule</label>
                        <select id="profileCrewScalingRule">
                            <option value="size_only">Size Only</option>
                            <option value="size_and_complexity">Size and Complexity</option>
                        </select>
                    </div>
                </div>
            </div>
            
            <!-- Slope Adjustments -->
            <div class="filters-container">
                <h3 style="margin-bottom: 24px; color: #1d1d1f;">Slope Cost Adjustments (%)</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Flat/Low (0-15°)</label>
                        <input type="number" id="profileSlopeFlatLow" placeholder="0" step="0.1" min="0">
                    </div>
                    <div class="form-group">
                        <label>Moderate (15-30°)</label>
                        <input type="number" id="profileSlopeModerate" placeholder="0.1" step="0.1" min="0">
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>Steep (30-45°)</label>
                        <input type="number" id="profileSlopeSteep" placeholder="0.2" step="0.1" min="0">
                    </div>
                    <div class="form-group">
                        <label>Very Steep (>45°)</label>
                        <input type="number" id="profileSlopeVerySteep" placeholder="0.3" step="0.1" min="0">
                    </div>
                </div>
            </div>
            
            <!-- Material Costs -->
            <div class="filters-container">
                <h3 style="margin-bottom: 24px; color: #1d1d1f;">Material Costs ($/sqft)</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Asphalt</label>
                        <input type="number" id="profileMaterialAsphalt" placeholder="4.0" step="0.5" min="0">
                    </div>
                    <div class="form-group">
                        <label>Shingle</label>
                        <input type="number" id="profileMaterialShingle" placeholder="4.5" step="0.5" min="0">
                    </div>
                    <div class="form-group">
                        <label>Metal</label>
                        <input type="number" id="profileMaterialMetal" placeholder="7.0" step="0.5" min="0">
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>Tile</label>
                        <input type="number" id="profileMaterialTile" placeholder="8.0" step="0.5" min="0">
                    </div>
                    <div class="form-group">
                        <label>Concrete</label>
                        <input type="number" id="profileMaterialConcrete" placeholder="6.0" step="0.5" min="0">
                    </div>
                </div>
            </div>
            
            <!-- Replacement Costs -->
            <div class="filters-container">
                <h3 style="margin-bottom: 24px; color: #1d1d1f;">Replacement Costs ($/sqm)</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Asphalt</label>
                        <input type="number" id="profileReplacementAsphalt" placeholder="45" step="5" min="0">
                    </div>
                    <div class="form-group">
                        <label>Shingle</label>
                        <input type="number" id="profileReplacementShingle" placeholder="50" step="5" min="0">
                    </div>
                    <div class="form-group">
                        <label>Metal</label>
                        <input type="number" id="profileReplacementMetal" placeholder="90" step="5" min="0">
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>Tile</label>
                        <input type="number" id="profileReplacementTile" placeholder="70" step="5" min="0">
                    </div>
                    <div class="form-group">
                        <label>Concrete</label>
                        <input type="number" id="profileReplacementConcrete" placeholder="60" step="5" min="0">
                    </div>
                </div>
            </div>
            
            <!-- Business Margins -->
            <div class="filters-container">
                <h3 style="margin-bottom: 24px; color: #1d1d1f;">Business Margins</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Overhead Percentage</label>
                        <input type="number" id="profileOverhead" placeholder="0.1" step="0.01" min="0" max="1">
                    </div>
                    <div class="form-group">
                        <label>Profit Margin</label>
                        <input type="number" id="profileProfit" placeholder="0.2" step="0.01" min="0" max="1">
                    </div>
                </div>
                
                <button class="btn btn-primary" onclick="saveRooferProfile()">Save Business Profile</button>
            </div>
        </div>
    </div>
    
    <!-- Property Details Modal -->
    <div id="propertyModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <span class="close" onclick="closeModal()">&times;</span>
                <div class="modal-title">Property Details</div>
            </div>
            <div class="modal-body" id="modalBody">
                <!-- Property details will be loaded here -->
            </div>
        </div>
    </div>
    
    <!-- Toast Notification Container -->
    <div class="toast-container" id="toastContainer" role="region" aria-live="polite" aria-label="Notifications"></div>
    
    <!-- Confirmation Dialog -->
    <div class="confirm-dialog" id="confirmDialog" role="dialog" aria-modal="true" aria-labelledby="confirmTitle" aria-describedby="confirmMessage">
        <div class="confirm-content">
            <div class="confirm-title" id="confirmTitle">Confirm Action</div>
            <div class="confirm-message" id="confirmMessage">Are you sure you want to proceed?</div>
            <div class="confirm-actions">
                <button class="btn btn-secondary" onclick="closeConfirmDialog()" id="confirmCancel">Cancel</button>
                <button class="btn btn-danger" onclick="executeConfirmedAction()" id="confirmOk">Confirm</button>
            </div>
        </div>
    </div>
    
    <!-- Session Timeout Warning -->
    <div class="session-warning" id="sessionWarning">
        <div class="session-warning-title">⏰ Session Expiring Soon</div>
        <div class="session-warning-message">Your session will expire in <span id="sessionTimer">5:00</span> minutes. Would you like to extend your session?</div>
        <div class="session-warning-actions">
            <button class="btn btn-primary btn-small" onclick="extendSession()">Extend Session</button>
            <button class="btn btn-secondary btn-small" onclick="dismissSessionWarning()">Dismiss</button>
        </div>
    </div>
    
    <!-- Footer -->
    <footer class="footer">
        <div class="container">
            <div class="footer-content">
                <div class="footer-section">
                    <h4>Tileit</h4>
                    <div class="footer-links">
                        <a href="#" class="footer-link">About Us</a>
                        <a href="#" class="footer-link">Features</a>
                        <a href="#" class="footer-link">Pricing</a>
                        <a href="#" class="footer-link">Blog</a>
                    </div>
                </div>
                <div class="footer-section">
                    <h4>Support</h4>
                    <div class="footer-links">
                        <a href="#" class="footer-link">Help Center</a>
                        <a href="#" class="footer-link">Contact Us</a>
                        <a href="#" class="footer-link">Documentation</a>
                        <a href="#" class="footer-link">API Reference</a>
                    </div>
                </div>
                <div class="footer-section">
                    <h4>Legal</h4>
                    <div class="footer-links">
                        <a href="#" class="footer-link">Privacy Policy</a>
                        <a href="#" class="footer-link">Terms of Service</a>
                        <a href="#" class="footer-link">Cookie Policy</a>
                        <a href="#" class="footer-link">GDPR Compliance</a>
                    </div>
                </div>
                <div class="footer-section">
                    <h4>Connect</h4>
                    <div class="footer-links">
                        <a href="#" class="footer-link">Twitter</a>
                        <a href="#" class="footer-link">LinkedIn</a>
                        <a href="#" class="footer-link">Facebook</a>
                        <a href="#" class="footer-link">Instagram</a>
                    </div>
                </div>
            </div>
            <div class="footer-bottom">
                <p>&copy; 2024 Tileit. All rights reserved. Built with ❤️ for roofing professionals.</p>
            </div>
        </div>
    </footer>

    <script>
        let currentUser = null;
        let authToken = null;
        let currentPage = 1;
        let currentSection = 'dashboard';
        let sessionTimer = null;
        let sessionWarningTimer = null;
        let confirmCallback = null;
        
        // Toast Notification System
        function showToast(message, type = 'info', title = null) {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            
            const icons = {
                success: '✓',
                error: '✕',
                warning: '⚠',
                info: 'ℹ'
            };
            
            const titles = {
                success: 'Success',
                error: 'Error',
                warning: 'Warning',
                info: 'Info'
            };
            
            toast.innerHTML = `
                <div class="toast-icon">${icons[type] || icons.info}</div>
                <div class="toast-content">
                    <div class="toast-title">${title || titles[type]}</div>
                    <div class="toast-message">${message}</div>
                </div>
                <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
            `;
            
            container.appendChild(toast);
            
            // Auto remove after 5 seconds
            setTimeout(() => {
                toast.classList.add('hiding');
                setTimeout(() => toast.remove(), 300);
            }, 5000);
        }
        
        // Confirmation Dialog
        function showConfirmDialog(title, message, onConfirm, confirmText = 'Confirm', cancelText = 'Cancel') {
            document.getElementById('confirmTitle').textContent = title;
            document.getElementById('confirmMessage').textContent = message;
            document.getElementById('confirmOk').textContent = confirmText;
            document.getElementById('confirmCancel').textContent = cancelText;
            document.getElementById('confirmDialog').classList.add('active');
            confirmCallback = onConfirm;
        }
        
        function closeConfirmDialog() {
            document.getElementById('confirmDialog').classList.remove('active');
            confirmCallback = null;
        }
        
        function executeConfirmedAction() {
            if (confirmCallback) {
                confirmCallback();
            }
            closeConfirmDialog();
        }
        
        
        // Password Strength Checker
        function checkPasswordStrength(password) {
            const strengthIndicator = document.getElementById('passwordStrength');
            const hint = document.getElementById('passwordHint');
            
            if (!password) {
                strengthIndicator.classList.remove('active');
                strengthIndicator.className = 'password-strength';
                hint.textContent = 'Use at least 8 characters with a mix of letters, numbers & symbols';
                return;
            }
            
            strengthIndicator.classList.add('active');
            
            let strength = 0;
            if (password.length >= 8) strength++;
            if (password.length >= 12) strength++;
            if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
            if (/\d/.test(password)) strength++;
            if (/[^a-zA-Z0-9]/.test(password)) strength++;
            
            strengthIndicator.classList.remove('password-strength-weak', 'password-strength-medium', 'password-strength-strong');
            
            if (strength <= 2) {
                strengthIndicator.classList.add('password-strength-weak');
                hint.textContent = 'Weak password - add more characters and variety';
                hint.style.color = '#dc3545';
            } else if (strength <= 4) {
                strengthIndicator.classList.add('password-strength-medium');
                hint.textContent = 'Medium password - consider adding special characters';
                hint.style.color = '#ffc107';
            } else {
                strengthIndicator.classList.add('password-strength-strong');
                hint.textContent = 'Strong password!';
                hint.style.color = '#28a745';
            }
        }
        
        // Session Management
        function startSessionTimer() {
            // Clear existing timers
            if (sessionTimer) clearTimeout(sessionTimer);
            if (sessionWarningTimer) clearTimeout(sessionWarningTimer);
            
            // Show warning 5 minutes before expiration (after 19 minutes)
            sessionWarningTimer = setTimeout(() => {
                showSessionWarning();
            }, 19 * 60 * 1000); // 19 minutes
            
            // Auto logout after 24 minutes
            sessionTimer = setTimeout(() => {
                showToast('Session expired. Please login again.', 'warning');
                logout();
            }, 24 * 60 * 1000); // 24 minutes
        }
        
        function showSessionWarning() {
            const warning = document.getElementById('sessionWarning');
            warning.classList.add('active');
            
            let timeLeft = 5 * 60; // 5 minutes in seconds
            const timerEl = document.getElementById('sessionTimer');
            
            const countdown = setInterval(() => {
                timeLeft--;
                const minutes = Math.floor(timeLeft / 60);
                const seconds = timeLeft % 60;
                timerEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
                
                if (timeLeft <= 0) {
                    clearInterval(countdown);
                }
            }, 1000);
        }
        
        function dismissSessionWarning() {
            document.getElementById('sessionWarning').classList.remove('active');
        }
        
        async function extendSession() {
            try {
                // Reload user profile to extend session
                const response = await fetch('/api/profile', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                
                if (response.ok) {
                    dismissSessionWarning();
                    startSessionTimer();
                    showToast('Session extended successfully', 'success');
                } else {
                    showToast('Failed to extend session', 'error');
                }
            } catch (error) {
                showToast('Error extending session', 'error');
            }
        }
        
        // Loading Button State
        function setButtonLoading(button, isLoading) {
            if (isLoading) {
                button.classList.add('loading');
                button.disabled = true;
            } else {
                button.classList.remove('loading');
                button.disabled = false;
            }
        }
        
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
            document.getElementById('forgotPasswordForm').style.display = 'none';
            document.querySelectorAll('.auth-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.auth-tab')[0].classList.add('active');
        }
        
        function showRegister() {
            document.getElementById('loginForm').style.display = 'none';
            document.getElementById('registerForm').style.display = 'block';
            document.getElementById('forgotPasswordForm').style.display = 'none';
            document.querySelectorAll('.auth-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.auth-tab')[1].classList.add('active');
        }
        
        function showForgotPassword() {
            document.getElementById('loginForm').style.display = 'none';
            document.getElementById('registerForm').style.display = 'none';
            document.getElementById('forgotPasswordForm').style.display = 'block';
        }
        
        async function login(event) {
            if (event) event.preventDefault();
            
            const email = document.getElementById('loginEmail').value.trim();
            const password = document.getElementById('loginPassword').value;
            const submitBtn = event ? event.target : document.querySelector('#loginForm .btn-primary');
            
            if (!email || !password) {
                showToast('Please fill in all fields', 'error');
                return;
            }
            
            // Email validation
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(email)) {
                showToast('Please enter a valid email address', 'error');
                return;
            }
            
            setButtonLoading(submitBtn, true);
            
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
                    showToast('Welcome back, ' + result.user.business_name + '!', 'success');
                    startSessionTimer();
                    setTimeout(() => loadDashboard(), 500);
                } else {
                    showToast(result.error || 'Login failed', 'error');
                }
            } catch (error) {
                showToast('Network error. Please try again.', 'error');
                console.error('Login error:', error);
            } finally {
                setButtonLoading(submitBtn, false);
            }
        }
        
        async function register(event) {
            if (event) event.preventDefault();
            
            const businessName = document.getElementById('regBusinessName').value.trim();
            const email = document.getElementById('regEmail').value.trim();
            const password = document.getElementById('regPassword').value;
            const licenseId = document.getElementById('regLicenseId').value.trim();
            const zipCode = document.getElementById('regZipCode').value.trim();
            const submitBtn = event ? event.target : document.querySelector('#registerForm .btn-primary');
            
            // Validation
            if (!businessName || !email || !password || !licenseId || !zipCode) {
                showToast('Please fill in all fields', 'error');
                return;
            }
            
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(email)) {
                showToast('Please enter a valid email address', 'error');
                return;
            }
            
            if (password.length < 8) {
                showToast('Password must be at least 8 characters long', 'error');
                return;
            }
            
            const zipRegex = /^\d{5}$/;
            if (!zipRegex.test(zipCode)) {
                showToast('Please enter a valid 5-digit ZIP code', 'error');
                return;
            }
            
            setButtonLoading(submitBtn, true);
            
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
                    showToast('Account created successfully! Welcome to Tileit!', 'success');
                    startSessionTimer();
                    setTimeout(() => loadDashboard(), 500);
                } else {
                    showToast(result.error || 'Registration failed', 'error');
                }
            } catch (error) {
                showToast('Network error. Please try again.', 'error');
                console.error('Registration error:', error);
            } finally {
                setButtonLoading(submitBtn, false);
            }
        }
        
        async function forgotPassword(event) {
            if (event) event.preventDefault();
            
            const email = document.getElementById('forgotEmail').value.trim();
            const submitBtn = event ? event.target : document.querySelector('#forgotPasswordForm .btn-primary');
            
            if (!email) {
                showToast('Please enter your email address', 'error');
                return;
            }
            
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(email)) {
                showToast('Please enter a valid email address', 'error');
                return;
            }
            
            setButtonLoading(submitBtn, true);
            
            try {
                const response = await fetch('/api/auth/forgot-password', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email})
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast('Password reset link sent to your email. Check your inbox.', 'success');
                    setTimeout(() => showLogin(), 2000);
                } else {
                    showToast(result.error || 'Failed to send reset link', 'error');
                }
            } catch (error) {
                showToast('Network error. Please try again.', 'error');
                console.error('Forgot password error:', error);
            } finally {
                setButtonLoading(submitBtn, false);
            }
        }
        
        function confirmLogout() {
            showConfirmDialog(
                'Confirm Logout',
                'Are you sure you want to logout?',
                () => logout(),
                'Logout',
                'Cancel'
            );
        }
        
        async function logout() {
            try {
                // Call logout API
                if (authToken) {
                    await fetch('/api/auth/logout', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer ' + authToken
                        }
                    });
                }
            } catch (error) {
                console.error('Logout API error:', error);
            } finally {
                // Clear session data
                authToken = null;
                currentUser = null;
                localStorage.removeItem('authToken');
                
                // Clear timers
                if (sessionTimer) clearTimeout(sessionTimer);
                if (sessionWarningTimer) clearTimeout(sessionWarningTimer);
                
                // Reset UI
                document.getElementById('authSection').style.display = 'block';
                document.getElementById('dashboard').classList.remove('active');
                document.getElementById('dashboard').style.display = 'none';
                document.getElementById('userMenu').style.display = 'none';
                document.getElementById('sessionWarning').classList.remove('active');
                
                // Hide all sections
                document.querySelectorAll('.dashboard').forEach(el => el.style.display = 'none');
                
                showToast('You have been logged out successfully', 'info');
            }
        }
        
        function showSection(section) {
            // Hide all sections
            document.querySelectorAll('.dashboard').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
            
            // Show selected section and load data
            if (section === 'dashboard') {
                document.getElementById('dashboard').style.display = 'block';
                document.querySelectorAll('.nav-item')[0].classList.add('active');
                // Dashboard loads stats automatically on init
            } else if (section === 'properties') {
                document.getElementById('properties').style.display = 'block';
                document.querySelectorAll('.nav-item')[1].classList.add('active');
                loadProperties(); // Load properties when viewing this page
            } else if (section === 'quotes') {
                document.getElementById('quotes').style.display = 'block';
                document.querySelectorAll('.nav-item')[2].classList.add('active');
                loadSavedQuotes(); // Load saved quotes
            } else if (section === 'settings') {
                document.getElementById('settings').style.display = 'block';
                document.querySelectorAll('.nav-item')[3].classList.add('active');
            } else if (section === 'profile') {
                document.getElementById('profile').style.display = 'block';
                document.querySelectorAll('.nav-item')[4].classList.add('active');
                loadRooferProfile();
            }
            
            currentSection = section;
        }
        
        function handleProfileStatusClick() {
            const statusElement = document.getElementById('profileStatus');
            if (statusElement && statusElement.textContent.includes('Incomplete')) {
                showSection('profile');
            }
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
                    
                    // Populate profile form
                    document.getElementById('profileBusinessName').value = currentUser.business_name;
                    document.getElementById('profileEmail').value = currentUser.email;
                    document.getElementById('profileLicenseId').value = currentUser.license_id;
                    document.getElementById('profileZipCode').value = currentUser.primary_zip_code;
                    
                    // Make email readonly
                    document.getElementById('profileEmail').setAttribute('readonly', 'true');
                }
                
                // Load roofer profile to check status
                await loadRooferProfile();
                
                // Load properties
                await loadProperties();
                
                // Load quotes count
                try {
                    const quotesResponse = await fetch('/api/quotes', {
                        headers: {'Authorization': 'Bearer ' + authToken}
                    });
                    const quotesResult = await quotesResponse.json();
                    if (quotesResult.success && quotesResult.quotes) {
                        document.getElementById('totalQuotes').textContent = quotesResult.quotes.length;
                    }
                } catch (error) {
                    console.log('No quotes yet');
                }
                
                // Show dashboard
                document.getElementById('authSection').style.display = 'none';
                document.getElementById('dashboard').classList.add('active');
                document.getElementById('dashboard').style.display = 'block';
                
            } catch (error) {
                console.error('Error loading dashboard:', error);
                showToast('Error loading dashboard data', 'error');
                logout();
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
                            <th>Layers</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${properties.map(prop => `
                            <tr onclick="showPropertyDetails('${prop.address.replace(/'/g, "\\'")}')">
                                <td><a href="#" class="property-link">${prop.address || 'N/A'}</a></td>
                                <td>${prop.roof_material || 'N/A'}</td>
                                <td>${prop.roof_area ? prop.roof_area.toFixed(0) : 'N/A'}</td>
                                <td>${prop.avg_pitch ? prop.avg_pitch.toFixed(1) : (prop.pitch ? prop.pitch.toFixed(1) : 'N/A')}</td>
                                <td>${prop.avg_condition ? prop.avg_condition.toFixed(1) : (prop['roof condition summary score'] || 'N/A')}</td>
                                <td>${prop.avg_height ? prop.avg_height.toFixed(1) : (prop['height (ft)'] ? prop['height (ft)'].toFixed(1) : 'N/A')}</td>
                                <td>${prop.roof_layers || 1}</td>
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
        
        // Load Saved Quotes
        async function loadSavedQuotes() {
            try {
                const response = await fetch('/api/quotes/saved', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const result = await response.json();
                
                if (result.success) {
                    savedQuotesArray = result.quotes; // Store globally
                    document.getElementById('totalQuotes').textContent = result.quotes.length;
                    document.getElementById('savedQuotesStats').textContent = 
                        `${result.quotes.length} saved ${result.quotes.length === 1 ? 'quote' : 'quotes'}`;
                    displaySavedQuotes(result.quotes);
                } else {
                    savedQuotesArray = [];
                    document.getElementById('savedQuotesTable').innerHTML = '<div class="loading">No saved quotes yet.</div>';
                }
            } catch (error) {
                console.error('Error loading saved quotes:', error);
                savedQuotesArray = [];
                document.getElementById('savedQuotesTable').innerHTML = '<div class="loading">No saved quotes yet. Browse properties to create some!</div>';
            }
        }
        
        function displaySavedQuotes(quotes) {
            const container = document.getElementById('savedQuotesTable');
            
            if (quotes.length === 0) {
                container.innerHTML = '<div class="loading">No saved quotes yet. Browse properties and click "Save Quote" to add them here!</div>';
                return;
            }
            
            const tableHTML = `
                <table class="properties-table">
                    <thead>
                        <tr>
                            <th>Property Address</th>
                            <th>Material</th>
                            <th>Area (sqft)</th>
                            <th>Quote Range</th>
                            <th>Saved On</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${quotes.map((quote, index) => `
                            <tr>
                                <td>${quote.property_address || 'N/A'}</td>
                                <td>${quote.material || 'N/A'}</td>
                                <td>${quote.area ? Math.round(quote.area) : 'N/A'}</td>
                                <td>$${quote.min_quote ? Math.round(quote.min_quote).toLocaleString() : 'N/A'} - $${quote.max_quote ? Math.round(quote.max_quote).toLocaleString() : 'N/A'}</td>
                                <td>${quote.saved_date ? new Date(quote.saved_date).toLocaleDateString() : 'N/A'}</td>
                                <td>
                                    <button class="btn btn-sm btn-primary" onclick="viewSavedQuoteDetails(${index})">View Details</button>
                                    <button class="btn btn-sm btn-secondary" onclick="deleteSavedQuote('${quote.id}')" style="margin-left: 8px;">Delete</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            
            container.innerHTML = tableHTML;
        }
        
        // Show Property Details Modal
        function showLoadingShimmer(text = 'Loading...') {
            const shimmerHTML = `
                <div id="loadingShimmer" class="loading-shimmer">
                    <div class="shimmer-box">
                        <div class="shimmer-spinner"></div>
                        <div class="shimmer-text">${text}</div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', shimmerHTML);
        }
        
        function hideLoadingShimmer() {
            const shimmer = document.getElementById('loadingShimmer');
            if (shimmer) shimmer.remove();
        }
        
        async function showPropertyDetails(address) {
            try {
                showLoadingShimmer('Loading property details...');
                
                // Find the property data
                const params = new URLSearchParams({ search: address, per_page: 1 });
                const response = await fetch(`/api/properties?${params}`, {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const result = await response.json();
                
                if (!result.success || result.properties.length === 0) {
                    hideLoadingShimmer();
                    showToast('Property not found', 'error');
                    return;
                }
                
                const property = result.properties[0];
                
                // Update shimmer text
                hideLoadingShimmer();
                showLoadingShimmer('Generating quote...');
                
                // Generate quote for this property
                const quoteResponse = await fetch('/api/quotes/generate', {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + authToken,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        addresses: [property.address]
                    })
                });
                
                hideLoadingShimmer();
                
                if (!quoteResponse.ok) {
                    throw new Error(`Quote calculation failed! status: ${quoteResponse.status}`);
                }
                
                const quoteResult = await quoteResponse.json();
                
                if (!quoteResult.success || !quoteResult.quotes || quoteResult.quotes.length === 0) {
                    showToast('Failed to generate quote', 'error');
                    return;
                }
                
                const quote = quoteResult.quotes[0];
                showPropertyModal(property, quote);
                
            } catch (error) {
                hideLoadingShimmer();
                console.error('Error loading property details:', error);
                showToast('Error: ' + error.message, 'error');
            }
        }
        
        function generatePropertyAnalysis(property, quote) {
            const condition = property.avg_condition || property['roof condition summary score'] || 75;
            const pitch = property.avg_pitch || property.pitch || 20;
            const layers = property.roof_layers || 1;
            
            // Condition Category
            let conditionCategory, conditionClass;
            if (condition >= 80) {
                conditionCategory = 'Excellent';
                conditionClass = 'status-excellent';
            } else if (condition >= 60) {
                conditionCategory = 'Good';
                conditionClass = 'status-good';
            } else if (condition >= 40) {
                conditionCategory = 'Fair';
                conditionClass = 'status-fair';
            } else {
                conditionCategory = 'Poor';
                conditionClass = 'status-poor';
            }
            
            // Issues & Recommendations
            let issues = [];
            let recommendations = [];
            
            if (condition < 50) {
                issues.push('Low condition score indicates potential damage');
                recommendations.push('Schedule inspection within 3 months');
                recommendations.push('Consider full roof replacement');
            } else if (condition < 70) {
                issues.push('Moderate wear detected');
                recommendations.push('Schedule inspection within 6 months');
                recommendations.push('Monitor for leaks or damage');
            }
            
            if (pitch > 30) {
                issues.push('Steep pitch requires specialized crew');
                recommendations.push('Use safety equipment and experienced crew');
            }
            
            if (layers > 1) {
                issues.push(`Multiple layers (${layers}) may require removal`);
                recommendations.push('Factor in additional removal costs');
            }
            
            if (issues.length === 0) {
                issues.push('No major issues detected');
            }
            if (recommendations.length === 0) {
                recommendations.push('Standard maintenance schedule recommended');
            }
            
            return `
                <div class="analysis-item">
                    <span class="analysis-label">Condition Category</span>
                    <span class="analysis-badge ${conditionClass}">${conditionCategory} (${condition.toFixed(1)}/100)</span>
                </div>
                <div class="analysis-item">
                    <span class="analysis-label">Potential Issues</span>
                    <ul class="analysis-list">
                        ${issues.map(issue => `<li>${issue}</li>`).join('')}
                    </ul>
                </div>
                <div class="analysis-item">
                    <span class="analysis-label">Recommended Actions</span>
                    <ul class="analysis-list">
                        ${recommendations.map(rec => `<li>${rec}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        
        // Store current property and quote globally for save function
        let currentPropertyData = null;
        let currentQuoteData = null;
        let savedQuotesArray = [];
        
        function showPropertyModal(property, quote) {
            // Store in global variables
            currentPropertyData = property;
            currentQuoteData = quote;
            
            const modalHTML = `
                <div id="propertyModal" class="modal-overlay" onclick="closePropertyModal(event)">
                    <div class="modal-content" onclick="event.stopPropagation()">
                        <div class="modal-header">
                            <h2>Property Details</h2>
                            <button class="btn-close" onclick="closePropertyModal()">×</button>
                        </div>
                        <div class="modal-body">
                            <div class="property-details-grid">
                                <div class="detail-section">
                                    <h3>Property Information</h3>
                                    <div class="info-item">
                                        <span class="info-label">Address</span>
                                        <span class="info-value">${property.address || 'N/A'}</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">Roof Material</span>
                                        <span class="info-value">${property.roof_material ? property.roof_material.charAt(0).toUpperCase() + property.roof_material.slice(1) : 'N/A'}</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">Roof Area</span>
                                        <span class="info-value">${property.roof_area ? property.roof_area.toFixed(0) + ' sqft' : 'N/A'}</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">Pitch</span>
                                        <span class="info-value">${property.avg_pitch ? property.avg_pitch.toFixed(1) : (property.pitch ? property.pitch.toFixed(1) : 'N/A')}°</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">Condition Score</span>
                                        <span class="info-value">${property.avg_condition ? property.avg_condition.toFixed(1) : (property['roof condition summary score'] || 'N/A')}/100</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">Height</span>
                                        <span class="info-value">${property.avg_height ? property.avg_height.toFixed(1) : (property['height (ft)'] ? property['height (ft)'].toFixed(1) : 'N/A')} ft</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">Roof Layers</span>
                                        <span class="info-value">${property.roof_layers || 1}</span>
                                    </div>
                                </div>
                                
                                <div class="detail-section">
                                    <h3>Quote Details</h3>
                                    <div class="quote-summary">
                                        <div class="quote-range">
                                            <h4>Estimated Cost Range</h4>
                                            <div class="quote-amounts">
                                                <div class="quote-amount">
                                                    <span class="amount-label">Minimum</span>
                                                    <span class="amount-value">$${quote.min_quote ? Math.round(quote.min_quote).toLocaleString() : 'N/A'}</span>
                                                </div>
                                                <div class="quote-amount">
                                                    <span class="amount-label">Maximum</span>
                                                    <span class="amount-value">$${quote.max_quote ? Math.round(quote.max_quote).toLocaleString() : 'N/A'}</span>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="info-item">
                                            <span class="info-label">Recommended Crew Size</span>
                                            <span class="info-value">${quote.crew_size_used || 'N/A'} workers</span>
                                        </div>
                                        ${quote.notes ? `
                                        <div class="detail-row">
                                            <span class="detail-label">Notes:</span>
                                            <span class="detail-value">${quote.notes}</span>
                                        </div>
                                        ` : ''}
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Property Analysis Section -->
                            <div class="analysis-section">
                                <h3>🔍 Property Analysis</h3>
                                <div class="analysis-content">
                                    ${generatePropertyAnalysis(property, quote)}
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-secondary" onclick="closePropertyModal()">Close</button>
                            <button class="btn btn-primary" onclick="saveCurrentQuote()">Save Quote</button>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        }
        
        function closePropertyModal(event) {
            if (!event || event.target.classList.contains('modal-overlay')) {
                const modal = document.getElementById('propertyModal');
                if (modal) modal.remove();
            }
        }
        
        // Function to save the currently displayed property quote
        async function saveCurrentQuote() {
            if (!currentPropertyData || !currentQuoteData) {
                showToast('No quote data available', 'error');
                return;
            }
            
            console.log('💾 Saving quote...');
            console.log('Current Property Data:', currentPropertyData);
            console.log('Current Quote Data:', currentQuoteData);
            
            // Build the payload
            const payload = {
                property_address: currentPropertyData.address || currentPropertyData.Address || currentPropertyData['Address'] || 'Unknown',
                material: currentPropertyData.roof_material || currentPropertyData.Material || currentPropertyData['Roof Material'] || 'Unknown',
                area: currentPropertyData.roof_area || currentPropertyData.Area || currentPropertyData['Area (sqft)'] || 0,
                min_quote: currentQuoteData.min_quote,
                max_quote: currentQuoteData.max_quote,
                crew_size: currentQuoteData.crew_size_used || 3,
                time_estimate: 0,
                notes: currentQuoteData.estimated_quote_range || ''
            };
            
            console.log('📤 Payload being sent:', payload);
            
            try {
                const response = await fetch('/api/quotes/save', {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + authToken,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast('Quote saved successfully!', 'success');
                    closePropertyModal();
                    // Refresh saved quotes count
                    loadSavedQuotes();
                } else {
                    showToast(result.message || 'Failed to save quote', 'error');
                }
            } catch (error) {
                console.error('Error saving quote:', error);
                showToast('Error saving quote', 'error');
            }
        }
        
        // Legacy function for saved quotes view
        async function saveQuote(property, quote) {
            currentPropertyData = property;
            currentQuoteData = quote;
            await saveCurrentQuote();
        }
        
        function viewSavedQuoteDetails(index) {
            const quote = savedQuotesArray[index];
            if (!quote) {
                showToast('Quote not found', 'error');
                return;
            }
            
            // Reconstruct property and quote objects from saved quote
            const property = {
                address: quote.property_address,
                roof_material: quote.material,
                roof_area: quote.area
            };
            
            const quoteData = {
                min_quote: quote.min_quote,
                max_quote: quote.max_quote,
                crew_size_used: quote.crew_size,
                estimated_quote_range: quote.notes
            };
            
            showPropertyModal(property, quoteData);
        }
        
        async function deleteSavedQuote(quoteId) {
            if (!confirm('Are you sure you want to delete this quote?')) return;
            
            console.log('Deleting quote with ID:', quoteId);
            
            try {
                const response = await fetch(`/api/quotes/${quoteId}`, {
                    method: 'DELETE',
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast('Quote deleted successfully', 'success');
                    loadSavedQuotes();
                } else {
                    showToast('Failed to delete quote', 'error');
                }
            } catch (error) {
                console.error('Error deleting quote:', error);
                showToast('Error deleting quote', 'error');
            }
        }
        
        function applyFilters() {
            currentPage = 1;
            showToast('Applying filters...', 'info');
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
            showToast('Filters cleared', 'info');
            loadProperties();
        }
        
        async function saveSettings(event) {
            if (event) event.preventDefault();
            
            const submitBtn = event ? event.target : document.querySelector('#settings .btn-primary');
            setButtonLoading(submitBtn, true);
            
            try {
                const settings = {
                    notifications: document.getElementById('notifications').checked,
                    email_alerts: document.getElementById('emailAlerts').checked,
                    auto_save: document.getElementById('autoSave').checked
                };
                
                const response = await fetch('/api/settings', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify(settings)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast('Settings saved successfully!', 'success');
                } else {
                    showToast(result.error || 'Error saving settings', 'error');
                }
            } catch (error) {
                showToast('Network error. Please try again.', 'error');
                console.error('Save settings error:', error);
            } finally {
                setButtonLoading(submitBtn, false);
            }
        }
        
        async function updateProfile(event) {
            if (event) event.preventDefault();
            
            const businessName = document.getElementById('profileBusinessName').value.trim();
            const licenseId = document.getElementById('profileLicenseId').value.trim();
            const zipCode = document.getElementById('profileZipCode').value.trim();
            const submitBtn = event ? event.target : document.querySelector('#profile .btn-primary');
            
            // Validation
            if (!businessName || !licenseId || !zipCode) {
                showToast('Please fill in all fields', 'error');
                return;
            }
            
            const zipRegex = /^\d{5}$/;
            if (!zipRegex.test(zipCode)) {
                showToast('Please enter a valid 5-digit ZIP code', 'error');
                return;
            }
            
            setButtonLoading(submitBtn, true);
            
            try {
                const profileData = {
                    business_name: businessName,
                    license_id: licenseId,
                    primary_zip_code: zipCode
                };
                
                const response = await fetch('/api/profile', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify(profileData)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Update current user info
                    currentUser.business_name = businessName;
                    currentUser.license_id = licenseId;
                    currentUser.primary_zip_code = zipCode;
                    
                    // Update display
                    document.getElementById('userName').textContent = businessName;
                    document.getElementById('userAvatar').textContent = businessName.charAt(0).toUpperCase();
                    
                    showToast('Profile updated successfully!', 'success');
                } else {
                    showToast(result.error || 'Error updating profile', 'error');
                }
            } catch (error) {
                showToast('Network error. Please try again.', 'error');
                console.error('Update profile error:', error);
            } finally {
                setButtonLoading(submitBtn, false);
            }
        }
        
        // Roofer Profile Functions
        async function loadRooferProfile() {
            try {
                const response = await fetch('/api/profile/roofer', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const result = await response.json();
                
                if (result.success && result.profile) {
                    const profile = result.profile;
                    
                    // Check if profile is actually saved (not just default values)
                    // A saved profile will have all required fields set to non-zero values
                    const isComplete = result.profile_exists && 
                                      profile.labor_rate && profile.labor_rate > 0 && 
                                      profile.daily_productivity && profile.daily_productivity > 0 && 
                                      profile.base_crew_size && profile.base_crew_size > 0 && 
                                      profile.overhead_percent !== null && 
                                      profile.profit_margin !== null;
                    
                    // Update profile status
                    const statusElement = document.getElementById('profileStatus');
                    const statusCard = document.getElementById('profileStatusCard');
                    if (isComplete) {
                        statusElement.textContent = 'Complete ✓';
                        statusElement.style.color = '#4caf50';
                        if (statusCard) {
                            statusCard.style.cursor = 'default';
                            statusCard.onclick = null;
                        }
                    } else {
                        statusElement.textContent = 'Incomplete - Click to complete';
                        statusElement.style.color = '#ff9800';
                        if (statusCard) {
                            statusCard.style.cursor = 'pointer';
                        }
                    }
                    
                    // Labor Information
                    document.getElementById('profileLaborRate').value = profile.labor_rate || 45;
                    document.getElementById('profileDailyProductivity').value = profile.daily_productivity || 2500;
                    document.getElementById('profileBaseCrewSize').value = profile.base_crew_size || 3;
                    document.getElementById('profileCrewScalingRule').value = profile.crew_scaling_rule || 'size_and_complexity';
                    
                    // Slope Adjustments
                    const slope = profile.slope_cost_adjustment || {};
                    document.getElementById('profileSlopeFlatLow').value = slope.flat_low || 0;
                    document.getElementById('profileSlopeModerate').value = slope.moderate || 0.1;
                    document.getElementById('profileSlopeSteep').value = slope.steep || 0.2;
                    document.getElementById('profileSlopeVerySteep').value = slope.very_steep || 0.3;
                    
                    // Material Costs
                    const materials = profile.material_costs || {};
                    document.getElementById('profileMaterialAsphalt').value = materials.asphalt || 4.0;
                    document.getElementById('profileMaterialShingle').value = materials.shingle || 4.5;
                    document.getElementById('profileMaterialMetal').value = materials.metal || 7.0;
                    document.getElementById('profileMaterialTile').value = materials.tile || 8.0;
                    document.getElementById('profileMaterialConcrete').value = materials.concrete || 6.0;
                    
                    // Replacement Costs
                    const replacement = profile.replacement_costs || {};
                    document.getElementById('profileReplacementAsphalt').value = replacement.asphalt || 45;
                    document.getElementById('profileReplacementShingle').value = replacement.shingle || 50;
                    document.getElementById('profileReplacementMetal').value = replacement.metal || 90;
                    document.getElementById('profileReplacementTile').value = replacement.tile || 70;
                    document.getElementById('profileReplacementConcrete').value = replacement.concrete || 60;
                    
                    // Business Margins
                    document.getElementById('profileOverhead').value = profile.overhead_percent || 0.1;
                    document.getElementById('profileProfit').value = profile.profit_margin || 0.2;
                } else {
                    // No profile found, mark as incomplete
                    const statusElement = document.getElementById('profileStatus');
                    const statusCard = document.getElementById('profileStatusCard');
                    statusElement.textContent = 'Incomplete - Click to complete';
                    statusElement.style.color = '#ff9800';
                    if (statusCard) {
                        statusCard.style.cursor = 'pointer';
                    }
                }
            } catch (error) {
                console.error('Error loading roofer profile:', error);
                // Mark as incomplete
                const statusElement = document.getElementById('profileStatus');
                const statusCard = document.getElementById('profileStatusCard');
                statusElement.textContent = 'Incomplete - Click to complete';
                statusElement.style.color = '#ff9800';
                if (statusCard) {
                    statusCard.style.cursor = 'pointer';
                }
            }
        }
        
        async function saveRooferProfile(event) {
            if (event) event.preventDefault();
            
            const submitBtn = event ? event.target : document.querySelector('#profile .btn-primary');
            setButtonLoading(submitBtn, true);
            
            try {
                const profileData = {
                    labor_rate: parseFloat(document.getElementById('profileLaborRate').value),
                    daily_productivity: parseInt(document.getElementById('profileDailyProductivity').value),
                    base_crew_size: parseInt(document.getElementById('profileBaseCrewSize').value),
                    crew_scaling_rule: document.getElementById('profileCrewScalingRule').value,
                    slope_cost_adjustment: {
                        flat_low: parseFloat(document.getElementById('profileSlopeFlatLow').value),
                        moderate: parseFloat(document.getElementById('profileSlopeModerate').value),
                        steep: parseFloat(document.getElementById('profileSlopeSteep').value),
                        very_steep: parseFloat(document.getElementById('profileSlopeVerySteep').value)
                    },
                    material_costs: {
                        asphalt: parseFloat(document.getElementById('profileMaterialAsphalt').value),
                        shingle: parseFloat(document.getElementById('profileMaterialShingle').value),
                        metal: parseFloat(document.getElementById('profileMaterialMetal').value),
                        tile: parseFloat(document.getElementById('profileMaterialTile').value),
                        concrete: parseFloat(document.getElementById('profileMaterialConcrete').value)
                    },
                    replacement_costs: {
                        asphalt: parseFloat(document.getElementById('profileReplacementAsphalt').value),
                        shingle: parseFloat(document.getElementById('profileReplacementShingle').value),
                        metal: parseFloat(document.getElementById('profileReplacementMetal').value),
                        tile: parseFloat(document.getElementById('profileReplacementTile').value),
                        concrete: parseFloat(document.getElementById('profileReplacementConcrete').value)
                    },
                    overhead_percent: parseFloat(document.getElementById('profileOverhead').value),
                    profit_margin: parseFloat(document.getElementById('profileProfit').value)
                };
                
                // Also update basic profile info
                const businessName = document.getElementById('profileBusinessName').value.trim();
                const licenseId = document.getElementById('profileLicenseId').value.trim();
                const zipCode = document.getElementById('profileZipCode').value.trim();
                
                // Update basic profile first
                await fetch('/api/profile', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify({
                        business_name: businessName,
                        license_id: licenseId,
                        primary_zip_code: zipCode
                    })
                });
                
                // Then save roofer profile
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
                    showToast('Business profile saved successfully!', 'success');
                } else {
                    showToast(result.error || 'Error saving profile', 'error');
                }
            } catch (error) {
                showToast('Network error. Please try again.', 'error');
                console.error('Save roofer profile error:', error);
            } finally {
                setButtonLoading(submitBtn, false);
            }
        }
        
        // Quote Functions
        async function generateAllQuotes(event) {
            if (event) event.preventDefault();
            
            const submitBtn = event ? event.target : null;
            if (submitBtn) setButtonLoading(submitBtn, true);
            
            try {
                // Check if profile is complete first
                const profileResponse = await fetch('/api/profile/roofer', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const profileResult = await profileResponse.json();
                
                if (!profileResult.success || !profileResult.profile) {
                    showToast('Please complete your business profile before generating quotes', 'warning');
                    showSection('profile');
                    if (submitBtn) setButtonLoading(submitBtn, false);
                    return;
                }
                
                const profile = profileResult.profile;
                const isComplete = profile.labor_rate && profile.daily_productivity && 
                                  profile.base_crew_size && profile.overhead_percent && 
                                  profile.profit_margin;
                
                if (!isComplete) {
                    showToast('Please complete your business profile before generating quotes', 'warning');
                    showSection('profile');
                    if (submitBtn) setButtonLoading(submitBtn, false);
                    return;
                }
                
                showToast('Generating quotes, please wait...', 'info');
                
                const response = await fetch('/api/quotes/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify({})
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast(`Generated ${result.count} quotes successfully!`, 'success');
                    // Update total quotes counter
                    document.getElementById('totalQuotes').textContent = result.count;
                    
                    // Show the generated quotes in the properties table
                    await loadGeneratedQuotes();
                } else {
                    showToast(result.error || 'Error generating quotes', 'error');
                }
            } catch (error) {
                showToast('Network error. Please try again.', 'error');
                console.error('Generate quotes error:', error);
            } finally {
                if (submitBtn) setButtonLoading(submitBtn, false);
            }
        }
        
        async function loadGeneratedQuotes() {
            try {
                const response = await fetch('/api/quotes', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const result = await response.json();
                
                if (result.success && result.quotes && result.quotes.length > 0) {
                    displayQuotesInProperties(result.quotes);
                }
            } catch (error) {
                console.error('Error loading quotes:', error);
            }
        }
        
        function displayQuotesInProperties(quotes) {
            const container = document.getElementById('propertiesTable');
            
            if (quotes.length === 0) {
                container.innerHTML = '<div class="loading">No quotes generated yet.</div>';
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
                            <th>Crew Size</th>
                            <th>Quote Range</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${quotes.map(quote => `
                            <tr onclick="showQuoteDetails('${quote.address.replace(/'/g, "\\'")}')">
                                <td><a href="#" class="property-link">${quote.address || 'N/A'}</a></td>
                                <td>${quote.roof_material || 'N/A'}</td>
                                <td>${quote.roof_area ? quote.roof_area.toFixed(0) : 'N/A'}</td>
                                <td>${quote.pitch ? quote.pitch.toFixed(1) : 'N/A'}</td>
                                <td>${quote.crew_size_used || 'N/A'}</td>
                                <td><strong>${quote.estimated_quote_range || 'N/A'}</strong></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            
            container.innerHTML = tableHTML;
        }
        
        async function showQuoteDetails(address) {
            try {
                const response = await fetch('/api/quotes', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const result = await response.json();
                
                if (result.success) {
                    const quote = result.quotes.find(q => q.address === address);
                    if (!quote) return;
                    
                    const modalBody = document.getElementById('modalBody');
                    
                    modalBody.innerHTML = `
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
                            <div>
                                <h4 style="margin-bottom: 16px; color: #1d1d1f;">Quote Details</h4>
                                <p><strong>Address:</strong> ${quote.address}</p>
                                <p><strong>Material:</strong> ${quote.roof_material || 'N/A'}</p>
                                <p><strong>Area:</strong> ${quote.roof_area ? quote.roof_area.toFixed(0) + ' sqft' : 'N/A'}</p>
                                <p><strong>Pitch:</strong> ${quote.pitch ? quote.pitch.toFixed(1) + '°' : 'N/A'}</p>
                                <p><strong>Crew Size:</strong> ${quote.crew_size_used || 'N/A'}</p>
                                <p><strong>Region Multiplier:</strong> ${quote.region_multiplier ? quote.region_multiplier.toFixed(2) + 'x' : 'N/A'}</p>
                            </div>
                            <div>
                                <h4 style="margin-bottom: 16px; color: #1d1d1f;">Cost Breakdown</h4>
                                <p><strong>Material Cost:</strong> $${quote.material_cost ? quote.material_cost.toFixed(2) : 'N/A'}</p>
                                <p><strong>Labor Cost:</strong> $${quote.labor_cost ? quote.labor_cost.toFixed(2) : 'N/A'}</p>
                                <p><strong>Repair Cost:</strong> $${quote.repair_cost ? quote.repair_cost.toFixed(2) : 'N/A'}</p>
                                <p><strong>Subtotal:</strong> $${quote.subtotal ? quote.subtotal.toFixed(2) : 'N/A'}</p>
                                <p><strong>Overhead:</strong> $${quote.overhead ? quote.overhead.toFixed(2) : 'N/A'}</p>
                                <p><strong>Profit:</strong> $${quote.profit ? quote.profit.toFixed(2) : 'N/A'}</p>
                                <p style="font-size: 18px; margin-top: 16px;"><strong>Total Quote Range:</strong><br>${quote.estimated_quote_range || 'N/A'}</p>
                            </div>
                        </div>
                    `;
                    
                    document.getElementById('propertyModal').style.display = 'flex';
                }
            } catch (error) {
                console.error('Error loading quote details:', error);
            }
        }
        
        async function loadQuotes() {
            try {
                const response = await fetch('/api/quotes', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                });
                const result = await response.json();
                
                if (result.success) {
                    displayQuotes(result.quotes);
                } else {
                    showToast('Error loading quotes', 'error');
                }
            } catch (error) {
                console.error('Error loading quotes:', error);
                showToast('Error loading quotes', 'error');
            }
        }
        
        function displayQuotes(quotes) {
            const container = document.getElementById('quotesTable');
            
            if (!quotes || quotes.length === 0) {
                container.innerHTML = '<div class="loading">No quotes generated yet. Click "Generate All Quotes" to create quotes.</div>';
                document.getElementById('totalQuotesCount').textContent = '0';
                document.getElementById('totalValueRange').textContent = '$0 - $0';
                return;
            }
            
            // Calculate totals
            const totalMin = quotes.reduce((sum, q) => sum + q.min_quote, 0);
            const totalMax = quotes.reduce((sum, q) => sum + q.max_quote, 0);
            
            document.getElementById('totalQuotesCount').textContent = quotes.length;
            document.getElementById('totalValueRange').textContent = `$${totalMin.toLocaleString()} - $${totalMax.toLocaleString()}`;
            
            // Create table
            const tableHTML = `
                <table class="properties-table">
                    <thead>
                        <tr>
                            <th>Address</th>
                            <th>Material</th>
                            <th>Area (sqft)</th>
                            <th>Pitch (°)</th>
                            <th>Crew Size</th>
                            <th>Quote Range</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${quotes.map(quote => `
                            <tr onclick="showQuoteDetails('${quote.address.replace(/'/g, "\\'")}')">
                                <td><a href="#" class="property-link">${quote.address || 'N/A'}</a></td>
                                <td>${quote.roof_material || 'N/A'}</td>
                                <td>${quote.roof_area ? quote.roof_area.toFixed(0) : 'N/A'}</td>
                                <td>${quote.pitch ? quote.pitch.toFixed(1) : 'N/A'}</td>
                                <td>${quote.crew_size_used || 'N/A'}</td>
                                <td><strong>${quote.estimated_quote_range}</strong></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            
            container.innerHTML = tableHTML;
        }
        
        function showQuoteDetails(address) {
            // TODO: Implement detailed quote view
            showToast('Quote details coming soon', 'info');
        }
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('propertyModal');
            if (event.target === modal) {
                modal.style.display = 'none';
            }
            
            const confirmDialog = document.getElementById('confirmDialog');
            if (event.target === confirmDialog) {
                closeConfirmDialog();
            }
        }
        
        // Keyboard accessibility
        document.addEventListener('keydown', function(event) {
            // Escape key closes modals and dialogs
            if (event.key === 'Escape') {
                // Close property modal
                const propertyModal = document.getElementById('propertyModal');
                if (propertyModal.style.display === 'block') {
                    closeModal();
                }
                
                // Close confirmation dialog
                const confirmDialog = document.getElementById('confirmDialog');
                if (confirmDialog.classList.contains('active')) {
                    closeConfirmDialog();
                }
                
                // Close user dropdown
                const dropdown = document.getElementById('userDropdown');
                if (dropdown && dropdown.classList.contains('active')) {
                    dropdown.classList.remove('active');
                }
            }
            
            // Enter key on login/register forms
            if (event.key === 'Enter') {
                const loginForm = document.getElementById('loginForm');
                const registerForm = document.getElementById('registerForm');
                const forgotPasswordForm = document.getElementById('forgotPasswordForm');
                
                if (loginForm && loginForm.style.display !== 'none' && document.activeElement.closest('#loginForm')) {
                    event.preventDefault();
                    login();
                }
                
                if (registerForm && registerForm.style.display !== 'none' && document.activeElement.closest('#registerForm')) {
                    event.preventDefault();
                    register();
                }
                
                if (forgotPasswordForm && forgotPasswordForm.style.display !== 'none' && document.activeElement.closest('#forgotPasswordForm')) {
                    event.preventDefault();
                    forgotPassword();
                }
            }
        });
        
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
