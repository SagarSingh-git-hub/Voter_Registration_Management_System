#!/usr/bin/env python3
"""
Initialize sample pending applications for the Verifier Dashboard
"""

import os
import sys
import random
from datetime import datetime, timedelta
from bson.objectid import ObjectId

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import mongo

def create_pending_applications():
    """Create sample pending applications"""
    
    app = create_app()
    
    with app.app_context():
        # Clear existing pending applications if needed (optional)
        # mongo.db.applications.delete_many({"status": "Pending"})
        
        # Check current count
        current_pending = mongo.db.applications.count_documents({"status": "Pending"})
        print(f"Current pending applications: {current_pending}")
        
        needed = 10 - current_pending
        if needed <= 0:
            print("✅ Already have enough pending applications.")
            return

        print(f"Creating {needed} new pending applications...")
        
        # Sample Data
        names = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
                 "Diya", "Saanvi", "Ananya", "Aadhya", "Pari", "Kiara", "Myra", "Riya", "Aarohi", "Anvi"]
        surnames = ["Sharma", "Verma", "Gupta", "Malhotra", "Singh", "Kumar", "Patel", "Mehta", "Iyer", "Joshi"]
        districts = ["New Delhi", "Mumbai", "Bangalore", "Chennai", "Kolkata", "Hyderabad", "Pune", "Ahmedabad", "Jaipur", "Surat"]
        
        new_apps = []
        for i in range(needed):
            full_name = f"{random.choice(names)} {random.choice(surnames)}"
            
            # Create a mock user ID (ObjectId)
            user_id = str(ObjectId())
            
            app_data = {
                "user_id": user_id,
                "full_name": full_name,
                "relative_name": f"{random.choice(names)} {random.choice(surnames)}",
                "relative_type": random.choice(["Father", "Mother", "Husband"]),
                "dob": (datetime.now() - timedelta(days=random.randint(6570, 25000))).strftime('%Y-%m-%d'), # 18-70 years old
                "gender": random.choice(["Male", "Female", "Other"]),
                "phone": f"9{random.randint(100000000, 999999999)}",
                "email": f"{full_name.lower().replace(' ', '.')}@example.com",
                "present_address": f"{random.randint(1, 999)}, Sector {random.randint(1, 20)}",
                "permanent_address": f"{random.randint(1, 999)}, Sector {random.randint(1, 20)}",
                "pin_code": f"{random.randint(110000, 800000)}",
                "state": "Delhi" if random.random() > 0.5 else "Maharashtra",
                "district": random.choice(districts),
                "assembly_constituency": f"AC-{random.randint(1, 50)}",
                "loksabha_constituency": f"PC-{random.randint(1, 10)}",
                "id_proof_type": "Aadhaar Card",
                "id_proof_number": f"{random.randint(1000, 9999)} {random.randint(1000, 9999)} {random.randint(1000, 9999)}",
                "photograph_path": "mock_photo.jpg", # Placeholder
                "document_path": "mock_doc.pdf", # Placeholder
                "status": "Pending",
                "submitted_at": datetime.now() - timedelta(hours=random.randint(1, 48)),
                # Adding some fields for the dashboard checks
                "id_proof_path": "mock_id.jpg" if random.random() > 0.2 else None,
                "address_proof_path": "mock_addr.jpg" if random.random() > 0.3 else None
            }
            new_apps.append(app_data)
            
        if new_apps:
            mongo.db.applications.insert_many(new_apps)
            print(f"✅ Successfully inserted {len(new_apps)} pending applications.")
        
        # Verify final count
        final_count = mongo.db.applications.count_documents({"status": "Pending"})
        print(f"📊 Total Pending Applications: {final_count}")

if __name__ == "__main__":
    create_pending_applications()
