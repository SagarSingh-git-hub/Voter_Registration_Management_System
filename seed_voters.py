import csv
import random
import string
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app import create_app
from models import mongo

# Constants
CSV_FILE = 'india_state_district_constituency.csv'
NUM_ENTRIES = 200

# Sample Data
FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayan", "Krishna", "Ishaan",
    "Diya", "Saanvi", "Anya", "Aadhya", "Pari", "Ananya", "Myra", "Riya", "Meera", "Isha",
    "Rahul", "Rohan", "Vikram", "Suresh", "Ramesh", "Priya", "Sneha", "Anjali", "Kavita", "Sunita"
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Malhotra", "Bhatia", "Saxena", "Mehta", "Chopra", "Singh", "Kumar",
    "Patel", "Reddy", "Nair", "Iyer", "Rao", "Joshi", "Desai", "Jain", "Agarwal", "Mishra"
]
DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]

def load_location_data():
    locations = []
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                locations.append(row)
    except FileNotFoundError:
        print(f"Warning: {CSV_FILE} not found. Using dummy location data.")
        # Fallback dummy data
        locations = [
            {'State': 'Delhi', 'District': 'New Delhi', 'Constituency': 'Connaught Place'},
            {'State': 'Maharashtra', 'District': 'Mumbai', 'Constituency': 'Andheri West'},
            {'State': 'Karnataka', 'District': 'Bangalore', 'Constituency': 'Indiranagar'}
        ]
    return locations

def generate_phone():
    return f"{random.choice(['6', '7', '8', '9'])}{''.join(random.choices(string.digits, k=9))}"

def generate_aadhar():
    return f"{''.join(random.choices(string.digits, k=12))}"

def generate_dob():
    start_date = datetime(1950, 1, 1)
    end_date = datetime(2005, 12, 31)
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    return start_date + timedelta(days=random_number_of_days)

def seed_voters():
    app = create_app()
    locations = load_location_data()
    
    with app.app_context():
        print(f"Starting to seed {NUM_ENTRIES} voter entries...")
        
        users_created = 0
        applications_created = 0
        
        for i in range(NUM_ENTRIES):
            # Generate random user data
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            full_name = f"{first_name} {last_name}"
            username = f"{first_name.lower()}{last_name.lower()}{random.randint(100, 999)}"
            email = f"{username}@{random.choice(DOMAINS)}"
            phone = generate_phone()
            location = random.choice(locations)
            
            # Check if user exists (skip if username collision)
            if mongo.db.users.find_one({"username": username}):
                continue
                
            # Create User
            user_data = {
                "username": username,
                "password_hash": generate_password_hash("password123"),
                "full_name": full_name,
                "email": email,
                "role": "voter",
                "created_at": datetime.utcnow(),
                "is_active": False, # Inactive until approved
                "has_voted": False
            }
            result = mongo.db.users.insert_one(user_data)
            user_id = str(result.inserted_id)
            users_created += 1
            
            # Create Application
            # Randomize status slightly (mostly Pending, some Approved/Rejected for variety if needed, but usually testing involves Pending)
            # Keeping all as Pending for now as requested "for testing" usually implies testing the workflow
            status = "Pending" 
            
            application_data = {
                "user_id": user_id,
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "dob": generate_dob(),
                "address": f"{random.randint(1, 999)}, Sector {random.randint(1, 50)}, {location['District']}",
                "state": location['State'],
                "district": location['District'],
                "constituency": location['Constituency'],
                "gender": random.choice(['Male', 'Female', 'Other']),
                "id_proof_number": generate_aadhar(),
                "document_path": "dummy_document.pdf", # Placeholder
                "status": status,
                "submitted_at": datetime.utcnow() - timedelta(days=random.randint(0, 30))
            }
            
            mongo.db.applications.insert_one(application_data)
            applications_created += 1
            
            if (i + 1) % 20 == 0:
                print(f"Progress: {i + 1}/{NUM_ENTRIES}")
                
        print(f"Seeding complete!")
        print(f"Users created: {users_created}")
        print(f"Applications created: {applications_created}")

if __name__ == "__main__":
    seed_voters()
