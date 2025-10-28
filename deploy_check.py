#!/usr/bin/env python3
"""
Pre-deployment checklist for Tileit
Run this before deploying to catch any issues
"""

import os
import sys

def check_files():
    """Check if required files exist"""
    required_files = [
        'requirements.txt',
        'Procfile',
        'runtime.txt',
        'backend/tileit_app.py',
        'backend/quote_engine.py',
        'backend/utils.py',
    ]
    
    print("📋 Checking required files...")
    missing = []
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} - MISSING")
            missing.append(file)
    
    return len(missing) == 0

def check_requirements():
    """Check requirements.txt has necessary packages"""
    print("\n📦 Checking requirements.txt...")
    
    with open('requirements.txt', 'r') as f:
        content = f.read()
    
    required_packages = ['Flask', 'gunicorn', 'pandas', 'numpy', 'Flask-CORS']
    missing = []
    
    for pkg in required_packages:
        if pkg in content:
            print(f"  ✅ {pkg}")
        else:
            print(f"  ❌ {pkg} - MISSING")
            missing.append(pkg)
    
    return len(missing) == 0

def check_databases():
    """Check if databases exist"""
    print("\n🗄️  Checking databases...")
    
    dbs = ['tileit_users.db', 'roofing_users.db']
    for db in dbs:
        if os.path.exists(db):
            size = os.path.getsize(db)
            print(f"  ✅ {db} ({size} bytes)")
        else:
            print(f"  ⚠️  {db} - Will be created on first run")
    
    return True

def check_data():
    """Check if data files exist"""
    print("\n📊 Checking data files...")
    
    data_path = 'data/nearmap_synthetic_extended_correlated.csv'
    if os.path.exists(data_path):
        size = os.path.getsize(data_path)
        print(f"  ✅ {data_path} ({size:,} bytes)")
        return True
    else:
        print(f"  ❌ {data_path} - MISSING")
        print("     This file is required for property data!")
        return False

def main():
    print("=" * 60)
    print("🚀 Tileit Deployment Readiness Check")
    print("=" * 60)
    
    checks = [
        check_files(),
        check_requirements(),
        check_databases(),
        check_data(),
    ]
    
    print("\n" + "=" * 60)
    if all(checks):
        print("✅ ALL CHECKS PASSED - Ready to deploy!")
        print("\nNext steps:")
        print("  1. git add .")
        print("  2. git commit -m 'Ready for deployment'")
        print("  3. git push")
        print("  4. Deploy on Render.com (see DEPLOYMENT.md)")
    else:
        print("❌ SOME CHECKS FAILED - Fix issues before deploying")
        sys.exit(1)
    print("=" * 60)

if __name__ == '__main__':
    main()

