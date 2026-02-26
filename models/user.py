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
        self.phone = user_data.get('phone')
        self.created_at = user_data.get('created_at')
        self.profile_pic = user_data.get('profile_pic')
        self.last_login = user_data.get('last_login')
        
        # Officer-specific fields
        self.officer_id = user_data.get('officer_id')
        self.assigned_area = user_data.get('assigned_area')
        self.assigned_booth = user_data.get('assigned_booth')
        self.department = user_data.get('department')
        self.badge_number = user_data.get('badge_number')
        self.contact_info = user_data.get('contact_info', {})

    def get_id(self):
        return self.id

    @property
    def is_active(self):
        return self.user_data.get('is_active', True)
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_verifier(self):
        return self.role == 'verifier'
    
    @property
    def is_booth_officer(self):
        return self.role == 'booth_officer'
    
    @property
    def is_officer(self):
        return self.role in ['admin', 'verifier', 'booth_officer']
    
    @property
    def role_display_name(self):
        role_names = {
            'admin': 'Administrator',
            'verifier': 'Verifier Officer',
            'booth_officer': 'Booth Officer',
            'voter': 'Voter'
        }
        return role_names.get(self.role, 'Unknown')
    
    @property
    def role_badge_color(self):
        badge_colors = {
            'admin': 'bg-red-500',
            'verifier': 'bg-blue-500',
            'booth_officer': 'bg-green-500',
            'voter': 'bg-gray-500'
        }
        return badge_colors.get(self.role, 'bg-gray-500')

    @staticmethod
    def create_user(username, password, full_name, email, role='voter', otp=None, **kwargs):
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
        
        # Add officer-specific fields if provided
        if role in ['admin', 'verifier', 'booth_officer']:
            user.update({
                "officer_id": kwargs.get('officer_id', username),
                "assigned_area": kwargs.get('assigned_area', ''),
                "assigned_booth": kwargs.get('assigned_booth', ''),
                "department": kwargs.get('department', ''),
                "badge_number": kwargs.get('badge_number', ''),
                "contact_info": kwargs.get('contact_info', {
                    'phone': kwargs.get('phone', ''),
                    'email': email,
                    'address': kwargs.get('address', '')
                })
            })
        
        result = mongo.db.users.insert_one(user)
        return str(result.inserted_id)

    @staticmethod
    def create_officer(officer_id, password, full_name, role, email, **kwargs):
        """Create an officer account with role-specific fields"""
        return User.create_user(
            username=officer_id,
            password=password,
            full_name=full_name,
            email=email,
            role=role,
            officer_id=officer_id,
            **kwargs
        )

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

    @staticmethod
    def find_by_officer_id(officer_id):
        """Find user by officer ID"""
        user_data = mongo.db.users.find_one({"officer_id": officer_id})
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
    
    def update_last_login(self):
        """Update last login timestamp"""
        mongo.db.users.update_one(
            {"_id": ObjectId(self.id)},
            {"$set": {"last_login": datetime.utcnow()}}
        )
    
    def has_permission(self, permission):
        """Check if user has specific permission based on role"""
        permissions = {
            'admin': ['view_all', 'approve_reject', 'create_user', 'view_analytics', 'manage_system'],
            'verifier': ['view_pending', 'approve_reject', 'view_analytics', 'detect_duplicates'],
            'booth_officer': ['create_voter', 'update_voter', 'view_booth_data', 'manage_blo_calls'],
            'voter': ['view_profile', 'update_profile', 'vote']
        }
        return permission in permissions.get(self.role, [])
    
    def can_access_dashboard(self, dashboard_type):
        """Check if user can access specific dashboard type"""
        dashboard_access = {
            'admin': ['admin', 'verifier', 'booth_officer'],
            'verifier': ['verifier'],
            'booth_officer': ['booth_officer'],
            'voter': ['voter']
        }
        return dashboard_type in dashboard_access.get(self.role, [])
