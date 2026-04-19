import os
import random
import string
import smtplib
import time
import requests
import logging
from enum import Enum
try:
    import filetype  # Replaces deprecated imghdr (safe on Python 3.13+)
except ImportError:
    filetype = None
# from flask_mail import Message # Removed Flask-Mail dependency
from flask import current_app
from models import mongo # Removed mail import
from datetime import datetime
from flask import request
from .risk_engine import detect_duplicate_voter, assess_fraud_risk

logger = logging.getLogger(__name__)


class ApplicationStatus(Enum):
    """Centralised application status constants to avoid magic strings."""
    PENDING = 'Pending'
    APPROVED = 'Approved'
    REJECTED = 'Rejected'
    FLAGGED = 'Flagged'
    UNDER_REVIEW = 'Under Review'

    @classmethod
    def values(cls):
        return [e.value for e in cls]

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None
    logger.warning("OCR libraries (Pillow/pytesseract) not found. OCR features disabled.")

try:
    from fuzzywuzzy import fuzz
except ImportError:
    fuzz = None
    logger.warning("FuzzyWuzzy not found. Fuzzy matching disabled.")

def log_admin_action(admin_id, action, target_id=None, details=None):
    try:
        log = {
            "admin_id": str(admin_id),
            "action": action,
            "target_id": str(target_id) if target_id else None,
            "details": details,
            "timestamp": datetime.utcnow(),
            "ip_address": request.remote_addr
        }
        mongo.db.audit_logs.insert_one(log)
    except Exception as e:
        logger.error(f"Audit Log Error: {e}")

def create_notification(user_id, message, type='info'):
    try:
        notification = {
            "user_id": str(user_id),
            "message": message,
            "type": type,
            "read": False,
            "created_at": datetime.utcnow()
        }
        mongo.db.notifications.insert_one(notification)
    except Exception as e:
        logger.error(f"Notification Error: {e}")

def generate_otp():
    return str(random.randint(100000, 999999))

def send_emailjs(to_email, template_params):
    """
    Helper function to send email via EmailJS REST API.
    """
    service_id = current_app.config.get('EMAILJS_SERVICE_ID')
    template_id = current_app.config.get('EMAILJS_TEMPLATE_ID')
    user_id = current_app.config.get('EMAILJS_PUBLIC_KEY')
    api_url = current_app.config.get('EMAILJS_API_URL')
    
    if not all([service_id, template_id, user_id, api_url]):
        print("EmailJS configuration missing.")
        return False

    payload = {
        "service_id": service_id,
        "template_id": template_id,
        "user_id": user_id,
        "template_params": template_params
    }
    
    try:
        response = requests.post(api_url, json=payload)
        if response.status_code == 200:
            print(f"[EMAILJS] Email sent successfully to {to_email}")
            return True
        else:
            print(f"[EMAILJS] Failed to send email: {response.text}")
            return False
    except Exception as e:
        print(f"[EMAILJS] Exception sending email: {e}")
        return False

def send_otp_email(to_email, otp):
    print(f"\n[EMAILJS] Preparing OTP email for: {to_email}")
    
    # Template params - attempting to map to common EmailJS template variables
    template_params = {
        "to_email": to_email,
        "to_name": "Voter", # Generic name
        "subject": "Voter Verification OTP",
        "message": f"Your verification OTP is: {otp}. It is valid for registration.",
        "otp": otp # Specific param if template uses it
    }
    
    if send_emailjs(to_email, template_params):
        return True
        
    # Fallback to mock if EmailJS fails
    print(f"\n[FALLBACK MOCK EMAIL] To: {to_email}")
    print(f"[FALLBACK MOCK EMAIL] OTP: {otp}\n")
    return True

def send_status_email(to_email, name, app_id, status, comment=None):
    subject = f'Update on your Voter Application - {status}'
    
    if status == 'Approved':
        message = f"Dear {name},\n\nYour application (ID: {app_id}) has been APPROVED.\n\nYou can now log in to your dashboard to download your digital Voter ID card."
    else:
        message = f"Dear {name},\n\nYour application (ID: {app_id}) has been REJECTED.\n\nReason: {comment}\n\nPlease log in to correct your application."

    template_params = {
        "to_email": to_email,
        "to_name": name,
        "subject": subject,
        "message": message,
        "app_id": app_id,
        "status": status,
        "reason": comment if comment else ""
    }

    if send_emailjs(to_email, template_params):
        return True
            
    # Fallback to mock if EmailJS fails
    print(f"\n[FALLBACK MOCK EMAIL] To: {to_email}")
    print(f"[FALLBACK MOCK EMAIL] Subject: {subject}")
    print(f"[FALLBACK MOCK EMAIL] Reason: EmailJS Failed.")
    return False

# BUG-014 FIX: Replaced imghdr (deprecated Python 3.13+) with 'filetype' library
# Maps image MIME types to accepted extensions
_ALLOWED_IMAGE_MIMES = {
    'image/jpeg': {'jpg', 'jpeg'},
    'image/png':  {'png'},
    'image/gif':  {'gif'},
}


def allowed_file(filename, file_stream=None):
    """Check extension AND (optionally) the actual MIME type via file magic bytes."""
    if '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1].lower()
    allowed_exts = {e.lower() for e in current_app.config.get('ALLOWED_EXTENSIONS', set())}

    # 1. Extension whitelist check
    if ext not in allowed_exts:
        return False

    # 2. Optional: MIME magic-byte check for image files (skip for PDF)
    if file_stream is not None and ext != 'pdf' and filetype is not None:
        header = file_stream.read(261)  # filetype needs up to 261 bytes
        file_stream.seek(0)  # Always rewind after reading
        kind = filetype.guess(header)
        if kind is None:
            logger.warning(f"allowed_file: could not detect MIME for '{filename}'")
            return False
        allowed_exts_for_mime = _ALLOWED_IMAGE_MIMES.get(kind.mime, set())
        if ext not in allowed_exts_for_mime:
            logger.warning(f"allowed_file: extension '{ext}' doesn't match detected MIME '{kind.mime}'")
            return False

    return True


def perform_ocr_scan(image_path):
    if not pytesseract or not Image:
        return "OCR Unavailable"
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        logger.error(f"OCR Error: {e}")
        return "OCR Failed"


def generate_unique_epic_number():
    """
    Generates a unique EPIC number (3 Uppercase + 7 Digits).
    BUG-007 FIX: Capped at 100 attempts to prevent infinite looping.
    """
    MAX_RETRIES = 100
    for attempt in range(MAX_RETRIES):
        letters = ''.join(random.choices(string.ascii_uppercase, k=3))
        digits = ''.join(random.choices(string.digits, k=7))
        epic = f"{letters}{digits}"

        if not mongo.db.applications.find_one({"epic_number": epic}) and \
           not mongo.db.final_voters.find_one({"epic_number": epic}):
            return epic

    raise RuntimeError(
        f"EPIC number generation failed after {MAX_RETRIES} attempts. "
        "Database may be corrupt or full."
    )
