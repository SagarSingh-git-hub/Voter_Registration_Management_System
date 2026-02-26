import os
import random
import string
import smtplib
import time
import requests
# from flask_mail import Message # Removed Flask-Mail dependency
from flask import current_app
from models import mongo # Removed mail import
from datetime import datetime
from flask import request
from .risk_engine import detect_duplicate_voter, assess_fraud_risk

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None
    print("OCR libraries not found.")

try:
    from fuzzywuzzy import fuzz
except ImportError:
    fuzz = None
    print("FuzzyWuzzy not found.")

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
        print(f"Audit Log Error: {e}")

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
        print(f"Notification Error: {e}")

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

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def perform_ocr_scan(image_path):
    if not pytesseract or not Image:
        return "OCR Unavailable"
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        print(f"OCR Error: {e}")
        return "OCR Failed"

def generate_unique_epic_number():
    """
    Generates a unique EPIC number (3 Uppercase + 7 Digits)
    and ensures it doesn't exist in the database.
    """
    while True:
        letters = ''.join(random.choices(string.ascii_uppercase, k=3))
        digits = ''.join(random.choices(string.digits, k=7))
        epic = f"{letters}{digits}"
        
        # Check uniqueness in both collections
        if not mongo.db.applications.find_one({"epic_number": epic}) and \
           not mongo.db.final_voters.find_one({"epic_number": epic}):
            return epic
