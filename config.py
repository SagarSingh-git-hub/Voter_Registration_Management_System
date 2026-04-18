import os
from dotenv import load_dotenv

# Load environment variables from .env file to ensure Config gets the correct values
load_dotenv(override=True)


class Config:
    # Use absolute path based on this file's location
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # --- SECURITY: Never fall back to an insecure default ---
    # If SECRET_KEY is not set, the app will fail loudly instead of silently using a weak key.
    _secret_key = os.environ.get('SECRET_KEY')
    if not _secret_key:
        raise RuntimeError(
            "CRITICAL: SECRET_KEY environment variable is not set. "
            "Set a strong random secret key before running the application. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    SECRET_KEY = _secret_key

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

    # NVIDIA Settings
    NVIDIA_API_KEY = os.environ.get('NVIDIA_API_KEY')

    # Firebase Settings
    FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY')
    FIREBASE_AUTH_DOMAIN = os.environ.get('FIREBASE_AUTH_DOMAIN')
    FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID')
    FIREBASE_STORAGE_BUCKET = os.environ.get('FIREBASE_STORAGE_BUCKET')
    FIREBASE_MESSAGING_SENDER_ID = os.environ.get('FIREBASE_MESSAGING_SENDER_ID')
    FIREBASE_APP_ID = os.environ.get('FIREBASE_APP_ID')

    # Upload Settings — BUG-005 FIX: 2MB to match UI
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2MB max upload (matches UI text)
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}  # BUG-013 FIX: added 'png'

    # Redis Settings
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'

    # Rate Limiting (uses Redis now instead of memory by default)
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI') or REDIS_URL
    RATELIMIT_STRATEGY = 'fixed-window'

    # Session / Cookie Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'

    # Environment
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'



class TestConfig(Config):
    """Config override for pytest — bypasses SECRET_KEY check."""
    SECRET_KEY = 'test-secret-key-not-for-production'  # type: ignore[assignment]
    TESTING = True
    WTF_CSRF_ENABLED = False
    MONGO_URI = 'mongodb://localhost:27017/votex_test'
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    RATELIMIT_ENABLED = False
