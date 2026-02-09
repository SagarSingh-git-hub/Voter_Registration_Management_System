import os
from dotenv import load_dotenv

# Load environment variables from .env file to ensure Config gets the correct values
load_dotenv()

class Config:
    # Use absolute path based on this file's location
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/voter_db'
    
    # Mail Settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # EmailJS Settings
    EMAILJS_SERVICE_ID = os.environ.get('EMAILJS_SERVICE_ID') or 'service_vrms'
    EMAILJS_TEMPLATE_ID = os.environ.get('EMAILJS_TEMPLATE_ID') or 'template_vrms'
    EMAILJS_PUBLIC_KEY = os.environ.get('EMAILJS_PUBLIC_KEY')
    EMAILJS_API_URL = 'https://api.emailjs.com/api/v1.0/email/send'

    # Supabase Settings
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')

    # n8n Settings
    N8N_WEBHOOK_URL = os.environ.get('N8N_WEBHOOK_URL')

    # Firebase Settings
    FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY')
    FIREBASE_AUTH_DOMAIN = os.environ.get('FIREBASE_AUTH_DOMAIN')
    FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID')
    FIREBASE_STORAGE_BUCKET = os.environ.get('FIREBASE_STORAGE_BUCKET')
    FIREBASE_MESSAGING_SENDER_ID = os.environ.get('FIREBASE_MESSAGING_SENDER_ID')
    FIREBASE_APP_ID = os.environ.get('FIREBASE_APP_ID')

    # Upload Settings
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg'}

    # Rate Limiting
    # Defaults to memory storage for local development. Use Redis in production.
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI') or 'memory://'
    RATELIMIT_STRATEGY = 'fixed-window'
    
    # Environment
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
