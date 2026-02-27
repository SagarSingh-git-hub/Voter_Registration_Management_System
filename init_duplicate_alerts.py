#!/usr/bin/env python3
"""
Initialize sample duplicate alerts for testing the Verifier Dashboard
"""

import os
import sys
from datetime import datetime, timedelta
from pymongo import MongoClient

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import mongo

def create_duplicate_alerts():
    """Create sample duplicate alerts for testing"""
    
    app = create_app()
    
    with app.app_context():
        # Clear existing alerts
        mongo.db.duplicate_alerts.delete_many({})
        
        # Sample duplicate alerts
        alerts = [
            {
                "type": "potential_duplicate",
                "application_id": "VR2024-0842",
                "existing_voter_id": "VOT2023-0147",
                "description": "Application matches existing voter ID",
                "similarity_score": 0.95,
                "status": "active",
                "created_at": datetime.now() - timedelta(hours=2),
                "priority": "high",
                "details": {
                    "matched_fields": ["aadhaar", "name", "dob"],
                    "application_name": "Rahul Kumar",
                    "existing_name": "Rahul Kumar Sharma"
                }
            },
            {
                "type": "similar_name",
                "application_ids": ["VR2024-0840", "VR2024-0841"],
                "description": "2 applications with similar names found",
                "similarity_score": 0.87,
                "status": "active",
                "created_at": datetime.now() - timedelta(hours=4),
                "priority": "medium",
                "details": {
                    "names": ["Amit Kumar", "Amit Kumar Singh"],
                    "matched_fields": ["first_name", "last_name"]
                }
            },
            {
                "type": "address_duplicate",
                "application_id": "VR2024-0839",
                "existing_applications": ["VR2024-0835", "VR2024-0836"],
                "description": "Same address as multiple existing applications",
                "similarity_score": 0.92,
                "status": "active",
                "created_at": datetime.now() - timedelta(hours=6),
                "priority": "medium",
                "details": {
                    "address": "123 Main Street, Delhi",
                    "application_count": 3
                }
            },
            {
                "type": "phone_duplicate",
                "application_id": "VR2024-0838",
                "existing_application_id": "VR2024-0832",
                "description": "Phone number already registered",
                "similarity_score": 1.0,
                "status": "active",
                "created_at": datetime.now() - timedelta(hours=8),
                "priority": "high",
                "details": {
                    "phone": "9876543210",
                    "existing_name": "Priya Singh"
                }
            },
            {
                "type": "email_duplicate",
                "application_id": "VR2024-0837",
                "existing_application_id": "VR2024-0830",
                "description": "Email address already registered",
                "similarity_score": 1.0,
                "status": "active",
                "created_at": datetime.now() - timedelta(hours=10),
                "priority": "low",
                "details": {
                    "email": "user@example.com",
                    "existing_name": "Anita Sharma"
                }
            }
        ]
        
        # Insert alerts
        mongo.db.duplicate_alerts.insert_many(alerts)
        
        print(f"✅ Created {len(alerts)} sample duplicate alerts")
        print("📊 Duplicate Detection Alerts are now ready for testing!")
        
        # Verify the alerts were created
        count = mongo.db.duplicate_alerts.count_documents({"status": "active"})
        print(f"🔍 Active duplicate alerts: {count}")

if __name__ == "__main__":
    create_duplicate_alerts()
