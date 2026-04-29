from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, current_user, logout_user, login_required
from models.user import User
from models.forms import LoginForm, RegistrationForm, OTPForm, ForgotPasswordForm
from utils import generate_otp, send_otp_email, send_emailjs
from utils.firebase_init import verify_token
from models import mongo, limiter
from bson.objectid import ObjectId
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
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
            
            # Update last login
            user.update_last_login()
            
            login_user(user)
            
            # Role-based redirect logic
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            elif user.is_verifier:
                return redirect(url_for('admin.verifier_dashboard'))
            elif user.is_booth_officer:
                return redirect(url_for('admin.booth_officer_dashboard'))
            else:
                return redirect(url_for('main.dashboard'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
            
    return render_template('login.html', form=form)

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.find_by_email(form.email.data.strip().lower())
        # Always show a generic flash to prevent user-enumeration
        flash('If an account exists for that email, we have sent a password reset link. Check your inbox.', 'info')

        if user:
            # Generate a time-limited signed token (expires in 1 hour)
            s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = s.dumps(user.email, salt='password-reset-salt')
            reset_url = url_for('auth.reset_password', token=token, _external=True)

            # Send via EmailJS
            send_emailjs(
                to_email=user.email,
                template_params={
                    'to_email': user.email,
                    'to_name': user.full_name or user.username,
                    'subject': 'VOTE.X — Password Reset Request',
                    'message': (
                        f'Click the link below to reset your password. '
                        f'This link expires in 1 hour.\n\n{reset_url}'
                    ),
                    'reset_url': reset_url,
                }
            )
            current_app.logger.info(f'Password reset link generated for: {user.email}')

        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html', form=form)


@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Validate the reset token and allow the user to set a new password."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)  # 1 hour
    except SignatureExpired:
        flash('The password reset link has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    except BadSignature:
        flash('Invalid or tampered reset link. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not new_password or len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('reset_password.html', token=token)

        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)

        user = User.find_by_email(email)
        if not user:
            flash('User account not found.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        from werkzeug.security import generate_password_hash
        mongo.db.users.update_one(
            {'_id': ObjectId(user.id)},
            {'$set': {'password_hash': generate_password_hash(new_password)}}
        )
        current_app.logger.info(f'Password reset completed for: {email}')
        flash('Your password has been updated successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))
