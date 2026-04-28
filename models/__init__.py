from flask_pymongo import PyMongo
from flask_login import LoginManager
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
import redis

mongo = PyMongo()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
mail = Mail()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])
csrf = CSRFProtect()

# Global Redis Client
redis_client = None

def init_redis(app):
    global redis_client
    redis_client = redis.from_url(app.config['REDIS_URL'])

def init_indexes(app):
    with app.app_context():
        # Users Collection
        mongo.db.users.create_index("username", unique=True, sparse=True)
        mongo.db.users.create_index("email", unique=True, sparse=True)
        mongo.db.users.create_index("role")

        # Applications Collection
        mongo.db.applications.create_index("user_id")
        mongo.db.applications.create_index("status")
        mongo.db.applications.create_index("epic_number")
        mongo.db.applications.create_index("submitted_at")
        mongo.db.applications.create_index("id_proof_number")

        # Final Voters Collection
        mongo.db.final_voters.create_index("user_id", unique=True, sparse=True)
        mongo.db.final_voters.create_index("epic_number", unique=True, sparse=True)
        mongo.db.final_voters.create_index("voter_id_number")
