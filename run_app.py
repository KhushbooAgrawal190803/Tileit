#!/usr/bin/env python3
"""
Simple runner script for the Roofing Quote Generator
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Import and run the Flask app
from backend.tileit_app import app

if __name__ == '__main__':
    print("Starting Roofing Quote Generator...")
    print("Server will be available at: http://localhost:5000")
    print("API endpoints:")
    print("   - GET  / (main interface)")
    print("   - POST /api/roofer/register")
    print("   - POST /api/csv/upload") 
    print("   - POST /api/quotes/calculate")
    print("   - GET  /api/health")
    print("\nStarting Flask server...")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
