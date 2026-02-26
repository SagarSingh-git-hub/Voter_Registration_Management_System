#!/usr/bin/env python3
"""
Initialize Officer Accounts Script
Creates default officer accounts for VRMS system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models.user import User
from models import mongo
from datetime import datetime

def create_officer_accounts():
    """Create default officer accounts"""
    
    # Check if officers already exist
    verifier_exists = User.find_by_officer_id('verifier')
    booth_exists = User.find_by_officer_id('booth')
    
    if verifier_exists and booth_exists:
        print("✅ Officer accounts already exist!")
        return
    
    try:
        # Create Verifier Officer
        if not verifier_exists:
            verifier_id = User.create_officer(
                officer_id='verifier',
                password='verifier123',
                full_name='Rajesh Kumar',
                role='verifier',
                email='verifier@vrms.gov.in',
                phone='+91-98765-43210',
                department='Voter Verification Department',
                badge_number='VR-2024-001',
                assigned_area='North District',
                address='Verification Office, Sector 12, New Delhi'
            )
            print(f"✅ Created Verifier Officer (ID: {verifier_id})")
        
        # Create Booth Officer
        if not booth_exists:
            booth_id = User.create_officer(
                officer_id='booth',
                password='booth123',
                full_name='Anita Sharma',
                role='booth_officer',
                email='booth@vrms.gov.in',
                phone='+91-98765-54321',
                department='Booth Level Operations',
                badge_number='BO-2024-042',
                assigned_area='South District',
                assigned_booth='Booth No. 42, Ward 7',
                address='Booth Office, Community Center, South Delhi'
            )
            print(f"✅ Created Booth Officer (ID: {booth_id})")
        
        print("\n🎉 Officer accounts created successfully!")
        print("\n📋 Login Credentials:")
        print("┌─────────────────────────────────────────────────┐")
        print("│ VERIFIER OFFICER                              │")
        print("│ Officer ID: verifier                           │")
        print("│ Password: verifier123                          │")
        print("│ Role: Verifier Officer                         │")
        print("├─────────────────────────────────────────────────┤")
        print("│ BOOTH OFFICER                                 │")
        print("│ Officer ID: booth                              │")
        print("│ Password: booth123                             │")
        print("│ Role: Booth Officer                            │")
        print("└─────────────────────────────────────────────────┘")
        
    except Exception as e:
        print(f"❌ Error creating officer accounts: {e}")
        raise

if __name__ == "__main__":
    print("🚀 Initializing Officer Accounts...")
    
    # Initialize Flask app to get MongoDB connection
    app = create_app()
    with app.app_context():
        create_officer_accounts()
    
    print("✅ Officer account initialization completed!")
