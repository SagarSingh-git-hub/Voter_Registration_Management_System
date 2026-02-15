from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, current_user, logout_user, login_required
from models.user import User
from models.forms import LoginForm, RegistrationForm, OTPForm, ForgotPasswordForm
from utils import generate_otp, send_otp_email
from utils.firebase_init import verify_token
from models import mongo, limiter
from bson.objectid import ObjectId
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    # Extract ID Token from Authorization Header
    auth_header = request.headers.get('Authorization')
    id_token = None
    if auth_header and auth_header.startswith('Bearer '):
        id_token = auth_header.split(' ')[1]
    
    # Check if this is a Firebase sync request (OTP skipped + ID Token present)
    skip_otp = request.form.get('skip_otp') == 'true'
    
    # Exempt OTP-based registration from CSRF protection
    if skip_otp and id_token:
        form = RegistrationForm(request.form, meta={'csrf': False})
    else:
        form = RegistrationForm()

    if form.validate_on_submit():
        otp = None if skip_otp else generate_otp()
        
        # Verify Firebase Token before proceeding
        if skip_otp:
            if not id_token:
                logger.warning("Registration Attempt Failed: Missing Auth Token in Headers")
                return {"success": False, "message": "Missing Auth Token"}, 401
            try:
                decoded_token = verify_token(id_token)
                uid = decoded_token.get('uid')
                email = decoded_token.get('email')

                # Verify consistency
                if email != form.email.data:
                     logger.warning(f"Registration Security Mismatch: Token Email {email} != Form Email {form.email.data}")
                     return {"success": False, "message": "Security Error: Email mismatch"}, 400
                
                # Check for Token Replay (Existing User)
                existing_user = User.find_by_email(email)
                if existing_user:
                    logger.info(f"Token Replay Detected: User {email} already exists. Attempting recovery/sync.")
                    # If user is active, strict reject. If inactive (zombie), allow sync.
                    if existing_user.is_active:
                         return {"success": False, "message": "User already exists and is verified. Please login."}, 409
                    else:
                         # Zombie user case: allow update but don't create new
                         logger.info(f"Recovering Zombie User: {email}")
                         user_id = existing_user.id
                         # Update existing user data
                         mongo.db.users.update_one(
                            {"_id": ObjectId(user_id)},
                            {"$set": {
                                "username": form.username.data,
                                "full_name": form.full_name.data,
                                "password_hash": User.hash_password(form.password.data), # Re-hash password
                                "is_active": True
                            }}
                         )
                         return {"success": True, "message": "Account recovered and synced"}

            except Exception as e:
                logger.error(f"Token Verification Error: {e}")
                return {"success": False, "message": "Invalid or Expired Auth Token", "error": str(e)}, 401

        # Create new user if not replay
        try:
            user_id = User.create_user(
                username=form.username.data,
                password=form.password.data,
                full_name=form.full_name.data,
                email=form.email.data,
                otp=otp
            )
            logger.info(f"User Created: {form.email.data} (ID: {user_id})")
        except Exception as e:
            logger.error(f"Database User Creation Failed: {e}")
            return {"success": False, "message": "Database Error: Could not create user", "error": str(e)}, 500
        
        if skip_otp:
            # Mark as active immediately since verified by Firebase
            try:
                mongo.db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"is_active": True}}
                )
                logger.info(f"Backend Sync Success: {form.email.data}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                     return {"success": True, "message": "Registration successful"}
                else:
                    flash('Registration successful! Please login.', 'success')
                    return redirect(url_for('auth.login'))
            except Exception as e:
                logger.error(f"Sync Update Failed: {e}")
                return {"success": False, "message": "Sync Error", "error": str(e)}, 500

        # Standard flow continues...
        session['register_user_id'] = user_id
        # Send OTP
        if not skip_otp:
            try:
                send_otp_email(form.email.data, otp)
                flash('OTP sent to your email.', 'info')
                return redirect(url_for('auth.verify_otp'))
            except Exception as e:
                logger.error(f"OTP Send Error: {e}")
                flash('Error sending OTP. Please try again.', 'danger')
                return redirect(url_for('auth.register'))

    return render_template('register.html', form=form)

@auth.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'register_user_id' not in session:
        return redirect(url_for('auth.register'))
    
    form = OTPForm()
    if form.validate_on_submit():
        user_id = session['register_user_id']
        user = User.find_by_id(user_id)
        
        if user and user.otp == form.otp.data:
            mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"is_active": True, "otp": None}} # Clear OTP after use
            )
            session.pop('register_user_id', None)
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid OTP. Please try again.', 'danger')
            
    return render_template('verify_otp.html', form=form)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.find_by_username(form.username.data)
        
        # Check password
        if user and user.check_password(form.password.data):
            if not user.is_active:
                 flash('Account not verified. Please complete registration.', 'warning')
                 return redirect(url_for('auth.register'))
            
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
            
    return render_template('login.html', form=form)

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        # In a real app, we would generate a token and send an email here
        # For now, we'll just simulate the success to satisfy the flow
        flash('If an account exists for that email, we have sent a password reset link.', 'info')
        return redirect(url_for('auth.login'))
        
    return render_template('forgot_password.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))
