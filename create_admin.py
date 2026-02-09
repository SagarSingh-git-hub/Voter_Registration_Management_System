from app import create_app
from models import mongo
from werkzeug.security import generate_password_hash
from models.user import User

app = create_app()

with app.app_context():
    # Ensure collection exists or just check for user
    if not mongo.db.users.find_one({"username": "admin"}):
        mongo.db.users.insert_one({
            "username": "admin",
            "password_hash": generate_password_hash("admin123"),
            "full_name": "System Administrator",
            "email": "admin@gov.vote",
            "role": "admin",
            "has_voted": False
        })
        print("Admin user created (user: admin, pass: admin123)")
    else:
        print("Admin user already exists")
