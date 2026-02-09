from flask_login import UserMixin
from models import mongo, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user_data:
        return None
    return User(user_data)

class User(UserMixin):
    def __init__(self, user_data):
        self.user_data = user_data
        self.id = str(user_data.get('_id'))
        self.username = user_data.get('username')
        self.role = user_data.get('role', 'voter')
        self.full_name = user_data.get('full_name')
        self.email = user_data.get('email')
        self.created_at = user_data.get('created_at')
        self.profile_pic = user_data.get('profile_pic')
        self.last_login = user_data.get('last_login') # Also add last_login since we used it in the template

    def get_id(self):
        return self.id

    @property
    def is_active(self):
        return self.user_data.get('is_active', True)

    @staticmethod
    def create_user(username, password, full_name, email, role='voter', otp=None):
        user = {
            "username": username,
            "password_hash": generate_password_hash(password),
            "full_name": full_name,
            "email": email,
            "role": role,
            "created_at": datetime.utcnow(),
            "is_active": False if role == 'voter' else True,
            "otp": otp,
            "has_voted": False
        }
        result = mongo.db.users.insert_one(user)
        return str(result.inserted_id)

    @staticmethod
    def find_by_username(username):
        user_data = mongo.db.users.find_one({"username": username})
        if user_data:
            return User(user_data)
        return None

    @staticmethod
    def find_by_email(email):
        user_data = mongo.db.users.find_one({"email": email})
        if user_data:
            return User(user_data)
        return None
        
    @staticmethod
    def find_by_id(user_id):
        user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if user_data:
            return User(user_data)
        return None

    def check_password(self, password):
        return check_password_hash(self.user_data['password_hash'], password)
        
    def verify_otp(self, otp):
        if self.user_data.get('otp') == otp:
            mongo.db.users.update_one(
                {"_id": ObjectId(self.id)},
                {"$set": {"is_active": True, "otp": None}}
            )
            return True
        return False
