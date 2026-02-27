import os
import csv
from io import BytesIO, StringIO
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_file, current_app, make_response, jsonify
from flask_login import login_required, current_user
from models import mongo
from bson.objectid import ObjectId
from functools import wraps
from utils import send_status_email, log_admin_action, create_notification, generate_unique_epic_number
from werkzeug.utils import secure_filename
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from datetime import datetime

admin = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Unauthorized Access: You are not authorized to access the Admin Panel.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin.route('/profile')
@login_required
@admin_required
def profile():
    # Admin Activity Stats
    admin_id = current_user.id
    
    # Count actions from audit logs
    total_approvals = mongo.db.audit_logs.count_documents({
        "admin_id": admin_id, 
        "action": "Approve Application"
    })
    
    total_rejections = mongo.db.audit_logs.count_documents({
        "admin_id": admin_id, 
        "action": "Reject Application"
    })
    
    last_action = mongo.db.audit_logs.find_one(
        {"admin_id": admin_id},
        sort=[("timestamp", -1)]
    )
    
    last_action_time = last_action['timestamp'] if last_action else None
    
    stats = {
        "approvals": total_approvals,
        "rejections": total_rejections,
        "last_action": last_action_time
    }
    
    return render_template('admin_profile.html', stats=stats)

@admin.route('/profile/upload-pic', methods=['POST'])
@login_required
@admin_required
def upload_profile_pic():
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('admin.profile'))
        
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('admin.profile'))
        
    allowed_extensions = {'png', 'jpg', 'jpeg'}
    if file and '.' in file.filename and \
       file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
        
        filename = secure_filename(file.filename)
        # Create unique filename: admin_<id>_<timestamp>.<ext>
        ext = filename.rsplit('.', 1)[1].lower()
        new_filename = f"admin_{current_user.id}_{int(datetime.utcnow().timestamp())}.{ext}"
        
        # Save to static/profile_pics
        save_path = os.path.join(current_app.root_path, 'static', 'profile_pics', new_filename)
        file.save(save_path)
        
        # Update User in DB
        mongo.db.users.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": {"profile_pic": new_filename}}
        )
        
        flash('Profile picture updated successfully!', 'success')
    else:
        flash('Invalid file type. Allowed: PNG, JPG, JPEG', 'danger')
        
    return redirect(url_for('admin.profile'))

@admin.route('/profile/update', methods=['POST'])
@login_required
@admin_required
def update_profile():
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    
    if not full_name or not email:
        flash('Name and Email are required.', 'danger')
        return redirect(url_for('admin.profile'))
    
    # Check if email is already taken by another user
    existing_user = mongo.db.users.find_one({
        "email": email,
        "_id": {"$ne": ObjectId(current_user.id)}
    })
    
    if existing_user:
        flash('Email already in use by another account.', 'danger')
        return redirect(url_for('admin.profile'))
    
    # Update User
    mongo.db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {
            "full_name": full_name,
            "email": email
        }}
    )
    
    flash('Profile updated successfully.', 'success')
    return redirect(url_for('admin.profile'))

@admin.route('/profile/remove-pic', methods=['POST'])
@login_required
@admin_required
def remove_profile_pic():
    if current_user.profile_pic:
        # Construct full path
        file_path = os.path.join(current_app.root_path, 'static', 'profile_pics', current_user.profile_pic)
        
        # Remove file from filesystem if it exists
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error deleting profile pic file: {e}")
        
        # Update User in DB (remove field)
        mongo.db.users.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$unset": {"profile_pic": ""}}
        )
        
        flash('Profile picture removed successfully.', 'success')
    else:
        flash('No profile picture to remove.', 'warning')
        
    return redirect(url_for('admin.profile'))

from werkzeug.security import generate_password_hash, check_password_hash

@admin.route('/profile/change-password', methods=['POST'])
@login_required
@admin_required
def change_password():
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not new_password or not confirm_password:
        flash('All fields are required.', 'danger')
        return redirect(url_for('admin.profile'))
        
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('admin.profile'))
        
    # Update Password without current password verification (as per admin requirement)
    mongo.db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"password_hash": generate_password_hash(new_password)}}
    )
    
    flash('Password changed successfully.', 'success')
    return redirect(url_for('admin.profile'))

@admin.route('/dashboard')
@login_required
@admin_required
def dashboard():
    filter_status = request.args.get('status')
    query = {}
    if filter_status:
        query['status'] = filter_status
        
    applications = list(mongo.db.applications.find(query).sort('submitted_at', -1))
    
    # Stats
    total = mongo.db.applications.count_documents({})
    pending = mongo.db.applications.count_documents({"status": "Pending"})
    approved = mongo.db.applications.count_documents({"status": "Approved"})
    rejected = mongo.db.applications.count_documents({"status": "Rejected"})
    
    # Advanced Analytics
    # 1. Daily Registrations
    pipeline_daily = [
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$submitted_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    daily_stats = list(mongo.db.applications.aggregate(pipeline_daily))
    
    # 2. Rejection Reasons
    pipeline_rejection = [
        {"$match": {"status": "Rejected"}},
        {"$group": {"_id": "$rejection_reason", "count": {"$sum": 1}}}
    ]
    rejection_stats = list(mongo.db.applications.aggregate(pipeline_rejection))
    
    # Audit Logs
    audit_logs = list(mongo.db.audit_logs.find().sort("timestamp", -1).limit(20))
    
    return render_template('admin_dashboard.html', 
                           applications=applications, 
                           stats={"total": total, "pending": pending, "approved": approved, "rejected": rejected},
                           daily_stats=daily_stats,
                           rejection_stats=rejection_stats,
                           audit_logs=audit_logs)

@admin.route('/application/<app_id>')
@login_required
@admin_required
def view_application(app_id):
    application = mongo.db.applications.find_one({"_id": ObjectId(app_id)})
    if not application:
        abort(404)
        
    user = mongo.db.users.find_one({"_id": ObjectId(application['user_id'])})
    return render_template('view_application.html', application=application, user=user)

@admin.route('/document/<path:filename>')
@login_required
@admin_required
def view_document(filename):
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        print(f"DEBUG: File not found: {file_path}")
        abort(404)
    return send_file(file_path)

@admin.route('/approve/<app_id>', methods=['POST'])
@login_required
@admin_required
def approve_application(app_id):
    application = mongo.db.applications.find_one({"_id": ObjectId(app_id)})
    if not application:
        abort(404)
        
    # Generate EPIC Number (Idempotent)
    epic_number = application.get('epic_number')
    if not epic_number:
        epic_number = generate_unique_epic_number()

    mongo.db.applications.update_one(
        {"_id": ObjectId(app_id)}, 
        {"$set": {
            "status": "Approved", 
            "epic_number": epic_number,
            "approved_at": datetime.utcnow()
        }}
    )
    
    # Add to Final Voter List
    if not mongo.db.final_voters.find_one({"user_id": application['user_id']}):
        mongo.db.final_voters.insert_one({
            "user_id": application['user_id'],
            "full_name": application['full_name'],
            "voter_id_number": application['id_proof_number'], # Using ID proof as ref
            "epic_number": epic_number,
            "approved_at": datetime.utcnow()
        })
    else:
        # Update existing record if needed
        mongo.db.final_voters.update_one(
            {"user_id": application['user_id']},
            {"$set": {"epic_number": epic_number}}
        )
    
    # Audit Log
    log_admin_action(current_user.id, "Approve Application", app_id, f"Application Approved. Generated EPIC: {epic_number}")

    # Notification & Email
    user = mongo.db.users.find_one({"_id": ObjectId(application['user_id'])})
    email_status = ""
    if user:
        # Determine email to send to: Application email > User email
        target_email = application.get('email') or user['email']
        
        create_notification(user['_id'], "Your voter application has been approved!", "success")
        if send_status_email(target_email, application.get('full_name', 'Applicant'), str(application['_id']), 'Approved'):
             email_status = f" Email sent to {target_email}."
        else:
             email_status = f" (Email simulation logged for {target_email})"
        
    flash(f'Application Approved.{email_status}', 'success')
    return redirect(url_for('admin.dashboard'))

@admin.route('/reject/<app_id>', methods=['POST'])
@login_required
@admin_required
def reject_application(app_id):
    reason = request.form.get('reason')
    mongo.db.applications.update_one(
        {"_id": ObjectId(app_id)}, 
        {"$set": {
            "status": "Rejected", 
            "rejection_reason": reason,
            "rejected_at": datetime.utcnow()
        }}
    )
    
    # Audit Log
    log_admin_action(current_user.id, "Reject Application", app_id, f"Reason: {reason}")

    application = mongo.db.applications.find_one({"_id": ObjectId(app_id)})
    user = mongo.db.users.find_one({"_id": ObjectId(application['user_id'])})
    email_status = ""
    if user:
        # Determine email to send to: Application email > User email
        target_email = application.get('email') or user['email']
        
        create_notification(user['_id'], f"Your voter application was rejected. Reason: {reason}", "error")
        if send_status_email(target_email, application.get('full_name', 'Applicant'), str(application['_id']), 'Rejected', reason):
             email_status = f" Email sent to {target_email}."
        else:
             email_status = f" (Email simulation logged for {target_email})"
        
    flash(f'Application Rejected.{email_status}', 'danger')
    return redirect(url_for('admin.dashboard'))

@admin.route('/export/csv')
@login_required
@admin_required
def export_csv():
    # Fetch ALL applications (Approved, Rejected, Pending)
    applications = list(mongo.db.applications.find({}).sort('submitted_at', -1))
    
    si = StringIO()
    # Add BOM for Excel compatibility with UTF-8
    si.write('\ufeff')
    cw = csv.writer(si)
    
    # Updated Headers as per request
    headers = [
        'Application ID', 'Full Name', 'Gender', 'Date of Birth', 
        'Email', 'Phone', 'EPIC ID Number', 
        'Address', 'State', 'Pincode', 
        'Status', 'Reason', 'Submitted Date'
    ]
    cw.writerow(headers)
    
    for app in applications:
        # Safe extraction & formatting
        submitted = app.get('submitted_at', '')
        if isinstance(submitted, datetime):
            submitted = submitted.strftime('%Y-%m-%d %H:%M')
            
        # Get user details for email/phone if missing in app
        email = app.get('email', '')
        phone = app.get('phone', '')
        
        if not email or not phone:
            user = mongo.db.users.find_one({"_id": ObjectId(app.get('user_id'))})
            if user:
                email = email or user.get('email', '')
                phone = phone or user.get('phone', '')

        # Get Rejection Reason if applicable
        reason = ''
        if app.get('status') == 'Rejected':
            reason = app.get('rejection_reason', '')

        row = [
            str(app.get('_id', '')),
            app.get('full_name', '').title(),
            app.get('gender', '').title(),
            app.get('dob', ''),
            email,
            phone,
            app.get('epic_number', ''),  # EPIC ID Number
            app.get('address', '').replace('\n', ' '),
            app.get('state', ''),
            app.get('pincode', ''),
            app.get('status', 'Pending'),
            reason,
            submitted
        ]
        cw.writerow(row)
        
    output = make_response(si.getvalue())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output.headers["Content-Disposition"] = f"attachment; filename=Voter_Application_Registry_{timestamp}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

@admin.route('/export/pdf')
@login_required
@admin_required
def export_pdf():
    try:
        buffer = BytesIO()
        # Use Landscape for better column fit
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(letter),
            rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # --- Header Section ---
        # Main Title
        title_style = ParagraphStyle(
            'Title', 
            parent=styles['Heading1'], 
            alignment=TA_CENTER, 
            fontSize=24, 
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1e293b'),
            spaceAfter=6
        )
        elements.append(Paragraph("OFFICIAL VOTER REGISTRY", title_style))
        
        # Subtitle / Metadata
        subtitle_style = ParagraphStyle(
            'Subtitle', 
            parent=styles['Normal'], 
            alignment=TA_CENTER, 
            fontSize=10, 
            fontName='Helvetica',
            textColor=colors.HexColor('#64748b'),
            spaceAfter=25
        )
        timestamp = datetime.now().strftime('%B %d, %Y at %H:%M')
        elements.append(Paragraph(f"Generated on: {timestamp} | Classification: CONFIDENTIAL", subtitle_style))
        
        # --- Data Table ---
        # Fetch Approved Data (Sorted Alphabetically)
        applications = list(mongo.db.applications.find({"status": "Approved"}))
        applications.sort(key=lambda x: x.get('full_name', '').strip().lower())
        
        # Table Headers
        data = [['Full Name', 'EPIC Number', 'Gender', 'Date of Birth', 'State', 'Approved Date']]
        
        # Table Rows
        for app in applications:
            # Format Date
            approved = app.get('approved_at', '')
            if isinstance(approved, datetime):
                approved = approved.strftime('%Y-%m-%d')
            else:
                approved = str(approved)[:10]

            # Format DOB
            dob = app.get('dob', '')
            if isinstance(dob, datetime):
                dob = dob.strftime('%Y-%m-%d')
            else:
                dob = str(dob)[:10]

            data.append([
                Paragraph(app.get('full_name', 'N/A').title(), styles['Normal']),
                Paragraph(app.get('epic_number', 'N/A'), styles['Normal']),
                app.get('gender', 'N/A').title(),
                dob,
                app.get('state', 'N/A'),
                approved
            ])
            
        if len(data) == 1:
            data.append(['No records found', '', '', '', '', ''])

        # Responsive Column Widths (Total ~730pts for Landscape Letter)
        # Name(180), EPIC(120), Gender(80), DOB(100), State(120), Date(100)
        table = Table(data, colWidths=[180, 120, 80, 100, 120, 100])
        
        # Styling
        table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            
            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#475569')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            
            # Borders
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#cbd5e1')),
        ]))
        
        elements.append(table)
        
        # --- Footer ---
        elements.append(Spacer(1, 30))
        footer_style = ParagraphStyle(
            'Footer', 
            parent=styles['Normal'], 
            alignment=TA_CENTER, 
            fontSize=8, 
            textColor=colors.HexColor('#94a3b8')
        )
        elements.append(Paragraph("This is a system-generated report. Valid without signature.", footer_style))
        
        doc.build(elements)
        buffer.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Voter_Registry_{timestamp}.pdf'
        
        return response
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        flash('Error generating PDF report. Please try again.', 'danger')
        return redirect(url_for('admin.dashboard'))

@admin.route('/blo-calls')
@login_required
@admin_required
def blo_calls():
    status_filter = request.args.get('status')
    query = {}
    if status_filter:
        query['status'] = status_filter
        
    calls = list(mongo.db.blo_calls.find(query).sort('created_at', -1))
    
    # Stats
    stats = {
        'total': mongo.db.blo_calls.count_documents({}),
        'pending': mongo.db.blo_calls.count_documents({'status': 'Pending'}),
        'scheduled': mongo.db.blo_calls.count_documents({'status': 'Scheduled'}),
        'completed': mongo.db.blo_calls.count_documents({'status': 'Completed'})
    }
    
    return render_template('admin_blo_calls.html', calls=calls, stats=stats)

@admin.route('/blo-call/<call_id>/update', methods=['POST'])
@login_required
@admin_required
def update_blo_call(call_id):
    action = request.form.get('action')
    update_data = {}
    message = ""
    status_type = "success"
    
    # Preserve scroll position by using an anchor
    redirect_url = url_for('admin.blo_calls', _anchor=f"call-{call_id}")

    if action == 'assign':
        blo_name = request.form.get('blo_name')
        if not blo_name:
            flash("BLO Name is required.", "danger")
            return redirect(redirect_url)
            
        update_data = {
            'blo_name': blo_name,
            'status': 'Assigned',
            'updated_at': datetime.utcnow()
        }
        # No notification for assignment as per request
        message = f"BLO {blo_name} assigned successfully."
        
    elif action == 'schedule':
        # Check if BLO is assigned first
        call = mongo.db.blo_calls.find_one({'_id': ObjectId(call_id)})
        if not call or not call.get('blo_name'):
             flash("Please assign a BLO before scheduling.", "danger")
             return redirect(redirect_url)

        scheduled_time = request.form.get('scheduled_time')
        if not scheduled_time:
            flash("Scheduled time is required.", "danger")
            return redirect(redirect_url)

        update_data = {
            'scheduled_time': scheduled_time,
            'status': 'Scheduled',
            'updated_at': datetime.utcnow()
        }
        
        # Format date for notification
        try:
            # Input comes as YYYY-MM-DDTHH:MM (datetime-local)
            dt = datetime.strptime(scheduled_time, '%Y-%m-%dT%H:%M')
            formatted_time = dt.strftime('%d-%m-%Y %I:%M %p')
        except:
            formatted_time = scheduled_time

        message = f"Call scheduled for {formatted_time}."
        
        # Notify User with Custom Message
        # "BLO (blo_name) assigned successfully and Call scheduled for (dd-mm-yyyy with time)"
        notification_msg = f"BLO {call.get('blo_name')} assigned successfully and Call scheduled for {formatted_time}"
        create_notification(ObjectId(call['user_id']), notification_msg, "success")
        
    elif action == 'complete':
        update_data = {
            'status': 'Completed',
            'updated_at': datetime.utcnow()
        }
        message = "Request marked as completed."
        # Optional: Notify completion
        call = mongo.db.blo_calls.find_one({'_id': ObjectId(call_id)})
        if call:
             create_notification(ObjectId(call['user_id']), "Your BLO Call request has been marked as Completed.", "success")
        
    elif action == 'reject':
        update_data = {
            'status': 'Rejected',
            'updated_at': datetime.utcnow()
        }
        message = "Request rejected."
        status_type = "warning"
        # Optional: Notify rejection
        call = mongo.db.blo_calls.find_one({'_id': ObjectId(call_id)})
        if call:
             create_notification(ObjectId(call['user_id']), "Your BLO Call request was rejected.", "error")

    if update_data:
        mongo.db.blo_calls.update_one(
            {'_id': ObjectId(call_id)},
            {'$set': update_data}
        )
        
        # Only flash if it's not the "assign" action (user asked to suppress notification/scroll jump feeling, but flash is okay for admin feedback)
        # Actually user said "assign ka Notifications na aaye" -> referring to User Notification? Or Admin Flash?
        # "assign krte hi assign ka Notifications na aaye" -> Context was "Citizen / Voter dashboard Notifications".
        # So I suppressed the create_notification for 'assign' above.
        
        flash(message, status_type)
        
    return redirect(redirect_url)

@admin.route('/demographics')
@login_required
def voter_demographics():
    # Check permission
    if not getattr(current_user, 'is_verifier', False) and not getattr(current_user, 'is_admin', False):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))

    # 1. Overview Stats
    total = mongo.db.applications.count_documents({})
    
    start_of_month = datetime(datetime.utcnow().year, datetime.utcnow().month, 1)
    new_month = mongo.db.applications.count_documents({"submitted_at": {"$gte": start_of_month}})
    
    active = mongo.db.applications.count_documents({"status": "Approved"})
    inactive = total - active
    
    # 2. Age Groups
    age_groups = {"18-25": 0, "26-35": 0, "36-50": 0, "50+": 0}
    
    all_apps = list(mongo.db.applications.find({}, {"dob": 1}))
    for app in all_apps:
        dob = app.get('dob')
        if dob:
            try:
                if isinstance(dob, str):
                    dob = datetime.strptime(dob, '%Y-%m-%d')
                age = (datetime.utcnow() - dob).days / 365.25
                if 18 <= age <= 25: age_groups["18-25"] += 1
                elif 26 <= age <= 35: age_groups["26-35"] += 1
                elif 36 <= age <= 50: age_groups["36-50"] += 1
                elif age > 50: age_groups["50+"] += 1
            except: pass
            
    # 3. Gender Ratio
    pipeline = [{"$group": {"_id": "$gender", "count": {"$sum": 1}}}]
    gender_data = list(mongo.db.applications.aggregate(pipeline))
    gender_stats = {d['_id']: d['count'] for d in gender_data if d['_id']}
    
    # 4. Area Prediction (Mock)
    area_pipeline = [
        {"$group": {"_id": "$assembly_constituency", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 6}
    ]
    area_data = list(mongo.db.applications.aggregate(area_pipeline))
    area_stats = []
    import random
    for area in area_data:
        pred = random.randint(65, 92)
        badge = "High" if pred > 80 else ("Medium" if pred > 70 else "Low")
        
        if badge == "High":
             badge_class = "bg-emerald/20 text-emerald border border-emerald/20"
             progress_color = "bg-emerald"
        elif badge == "Medium":
             badge_class = "bg-yellow-400/20 text-yellow-400 border border-yellow-400/20"
             progress_color = "bg-yellow-400"
        else:
             badge_class = "bg-red-400/20 text-red-400 border border-red-400/20"
             progress_color = "bg-red-400"
             
        area_stats.append({
            "name": area['_id'] or "Unknown",
            "count": area['count'],
            "turnout": pred,
            "badge": badge,
            "badge_class": badge_class,
            "progress_color": progress_color,
            "progress_style": f"width: {pred}%"
        })
        
    # Prepare chart data for safer template rendering
    age_chart_data = [age_groups["18-25"], age_groups["26-35"], age_groups["36-50"], age_groups["50+"]]
    gender_chart_data = [gender_stats.get('Male', 0), gender_stats.get('Female', 0), gender_stats.get('Other', 0)]
        
    return render_template('admin_demographics.html', 
                           total=total, new_month=new_month, active=active, inactive=inactive,
                           age_groups=age_groups, gender_stats=gender_stats, area_stats=area_stats,
                           age_chart_data=age_chart_data, gender_chart_data=gender_chart_data)

@admin.route('/verifier-dashboard')
@login_required
def verifier_dashboard():
    # Check if user has permission to access verifier dashboard
    if not current_user.is_verifier and not current_user.is_admin:
        flash('Unauthorized access to Verifier Dashboard', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get verification statistics
    pending_count = mongo.db.applications.count_documents({"status": "pending"})
    verified_today = mongo.db.applications.count_documents({
        "status": "verified",
        "verified_date": {"$gte": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}
    })
    rejected_today = mongo.db.applications.count_documents({
        "status": "rejected",
        "rejected_date": {"$gte": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}
    })
    duplicate_alerts = mongo.db.duplicate_alerts.count_documents({"status": "active"})
    
    # Get duplicate alerts data
    duplicate_alerts_data = list(mongo.db.duplicate_alerts.find({"status": "active"}).sort("created_at", -1))
    
    return render_template('verifier_dashboard.html',
                         pending_count=pending_count,
                         verified_today=verified_today,
                         rejected_today=rejected_today,
                         duplicate_alerts=duplicate_alerts,
                         duplicate_alerts_data=duplicate_alerts_data)

@admin.route('/dismiss-alert/<alert_id>', methods=['POST'])
@login_required
def dismiss_alert(alert_id):
    # Check if user has permission to dismiss alerts
    if not current_user.is_verifier and not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        # Update alert status to dismissed
        result = mongo.db.duplicate_alerts.update_one(
            {'_id': ObjectId(alert_id)},
            {'$set': {
                'status': 'dismissed',
                'dismissed_at': datetime.utcnow(),
                'dismissed_by': current_user.id
            }}
        )
        
        if result.modified_count > 0:
            return jsonify({'success': True, 'message': 'Alert dismissed successfully'})
        else:
            return jsonify({'success': False, 'message': 'Alert not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin.route('/export-verification-report')
@login_required
def export_verification_report():
    # Check permission
    if not getattr(current_user, 'is_verifier', False) and not getattr(current_user, 'is_admin', False):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
        
    format_type = request.args.get('format', 'csv')
    
    # Get verification data (limit to 100 latest for performance)
    pipeline = [
        {"$match": {
            "$or": [
                {"status": {"$in": ["verified", "rejected"]}},
                {"status": "pending"}
            ]
        }},
        {"$sort": {"submitted_at": -1}},
        {"$limit": 100}
    ]
    
    applications = list(mongo.db.applications.aggregate(pipeline))
    
    # Prepare data rows
    data_rows = []
    for app in applications:
        status = app.get('status', 'Unknown')
        status_date = app.get('verified_date') if status == 'verified' else app.get('rejected_date')
        if not status_date:
            status_date = app.get('submitted_at')
            
        date_str = status_date.strftime('%Y-%m-%d %H:%M') if status_date else 'N/A'
        
        data_rows.append({
            'id': str(app.get('_id')),
            'name': app.get('full_name', 'N/A'),
            'status': status.title(),
            'date': date_str,
            'epic': app.get('epic_number', 'N/A')
        })
    
    if format_type in ['csv', 'excel']:
        # For Excel, we use CSV format
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Application ID', 'Name', 'Status', 'Date', 'EPIC Number'])
        
        for row in data_rows:
            writer.writerow([row['id'], row['name'], row['status'], row['date'], row['epic']])
            
        output.seek(0)
        response = make_response(output.getvalue())
        
        filename = f'verification_report_{datetime.now().strftime("%Y%m%d")}.csv'
        
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-type'] = 'text/csv'
        return response
        
    elif format_type == 'pdf':
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
        elements = []
        
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"Verification Report", styles['Title']))
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Table Data
        table_data = [['Application ID', 'Name', 'Status', 'Date', 'EPIC No.']]
        for row in data_rows:
            table_data.append([
                row['id'][-8:], # Short ID for PDF to fit
                row['name'][:20], # Truncate long names
                row['status'],
                row['date'],
                row['epic']
            ])
            
        t = Table(table_data, colWidths=[100, 150, 80, 120, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(t)
        
        doc.build(elements)
        buffer.seek(0)
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=verification_report_{datetime.now().strftime("%Y%m%d")}.pdf'
        response.headers['Content-type'] = 'application/pdf'
        return response
        
    return redirect(url_for('admin.verifier_dashboard'))

@admin.route('/booth-officer-dashboard')
@login_required
def booth_officer_dashboard():
    # Check if user has permission to access booth officer dashboard
    if not current_user.is_booth_officer and not current_user.is_admin:
        flash('Unauthorized access to Booth Officer Dashboard', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get booth-specific statistics
    booth_filter = {"assigned_booth": current_user.assigned_booth} if current_user.assigned_booth else {}
    
    total_voters = mongo.db.voters.count_documents(booth_filter)
    new_registrations = mongo.db.applications.count_documents({
        **booth_filter,
        "created_at": {"$gte": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}
    })
    blo_calls = mongo.db.blo_requests.count_documents({
        **booth_filter,
        "status": {"$in": ["pending", "urgent"]}
    })
    today_visits = mongo.db.visit_logs.count_documents({
        **booth_filter,
        "visit_date": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    })
    
    return render_template('booth_officer_dashboard.html',
                         total_voters=total_voters,
                         new_registrations=new_registrations,
                         blo_calls=blo_calls,
                         today_visits=today_visits)

@admin.route('/officer-profile')
@login_required
def officer_profile():
    """Officer profile page for both verifier and booth officer roles"""
    if not current_user.is_officer:
        flash('Unauthorized access to Officer Profile', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get officer activity history
    activity_logs = list(mongo.db.audit_logs.find(
        {"admin_id": current_user.id},
        sort=[("timestamp", -1)]
    ).limit(10))
    
    return render_template('officer_profile.html',
                         activity_logs=activity_logs)

@admin.route('/export-demographics')
@login_required
def export_demographics():
    # Check permission
    if not getattr(current_user, 'is_verifier', False) and not getattr(current_user, 'is_admin', False):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))

    # Get format from query parameter (default: csv)
    export_format = request.args.get('format', 'csv').lower()
    
    # Get current date for report title
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Collect demographics data
    total = mongo.db.applications.count_documents({})
    
    # Age groups
    age_groups = []
    for group in ["18-25", "26-35", "36-45", "46-60", "60+"]:
        if group == "18-25":
            count = mongo.db.applications.count_documents({"age": {"$gte": 18, "$lte": 25}})
        elif group == "26-35":
            count = mongo.db.applications.count_documents({"age": {"$gte": 26, "$lte": 35}})
        elif group == "36-45":
            count = mongo.db.applications.count_documents({"age": {"$gte": 36, "$lte": 45}})
        elif group == "46-60":
            count = mongo.db.applications.count_documents({"age": {"$gte": 46, "$lte": 60}})
        else:  # 60+
            count = mongo.db.applications.count_documents({"age": {"$gte": 60}})
        age_groups.append({"group": group, "count": count})
    
    # Gender stats
    male_count = mongo.db.applications.count_documents({"gender": "Male"})
    female_count = mongo.db.applications.count_documents({"gender": "Female"})
    other_count = mongo.db.applications.count_documents({"gender": {"$nin": ["Male", "Female"]}})
    
    # Area stats
    urban_count = mongo.db.applications.count_documents({"area_type": "Urban"})
    rural_count = mongo.db.applications.count_documents({"area_type": "Rural"})
    
    if export_format == 'excel':
        return export_demographics_excel(current_date, total, age_groups, male_count, female_count, other_count, urban_count, rural_count)
    elif export_format == 'pdf':
        return export_demographics_pdf(current_date, total, age_groups, male_count, female_count, other_count, urban_count, rural_count)
    else:  # csv
        return export_demographics_csv(current_date, total, age_groups, male_count, female_count, other_count, urban_count, rural_count)

def export_demographics_csv(current_date, total, age_groups, male_count, female_count, other_count, urban_count, rural_count):
    # Create CSV content
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Voter Demographics Report'])
    writer.writerow(['Generated on:', current_date])
    writer.writerow([])
    
    # Overview stats
    writer.writerow(['Overview Statistics'])
    writer.writerow(['Total Voters', total])
    writer.writerow([])
    
    # Age distribution
    writer.writerow(['Age Distribution'])
    writer.writerow(['Age Group', 'Count', 'Percentage'])
    for age_group in age_groups:
        percentage = (age_group['count'] / total * 100) if total > 0 else 0
        writer.writerow([age_group['group'], age_group['count'], f"{percentage:.1f}%"])
    writer.writerow([])
    
    # Gender distribution
    writer.writerow(['Gender Distribution'])
    writer.writerow(['Gender', 'Count', 'Percentage'])
    writer.writerow(['Male', male_count, f"{(male_count/total*100):.1f}%" if total > 0 else "0%"])
    writer.writerow(['Female', female_count, f"{(female_count/total*100):.1f}%" if total > 0 else "0%"])
    writer.writerow(['Other', other_count, f"{(other_count/total*100):.1f}%" if total > 0 else "0%"])
    writer.writerow([])
    
    # Area distribution
    writer.writerow(['Area Distribution'])
    writer.writerow(['Area Type', 'Count', 'Percentage'])
    writer.writerow(['Urban', urban_count, f"{(urban_count/total*100):.1f}%" if total > 0 else "0%"])
    writer.writerow(['Rural', rural_count, f"{(rural_count/total*100):.1f}%" if total > 0 else "0%"])
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=voter_demographics_{current_date}.csv'
    response.headers['Content-type'] = 'text/csv'
    
    # Log the export action
    log_admin_action("Export Demographics Report (CSV)", f"Generated demographics CSV report with {total} total voters")
    
    return response

def export_demographics_excel(current_date, total, age_groups, male_count, female_count, other_count, urban_count, rural_count):
    try:
        import pandas as pd
        import io
        
        # Create data for Excel
        data = []
        
        # Header
        data.append(['Voter Demographics Report'])
        data.append(['Generated on:', current_date])
        data.append([])
        
        # Overview stats
        data.append(['Overview Statistics'])
        data.append(['Total Voters', total])
        data.append([])
        
        # Age distribution
        data.append(['Age Distribution'])
        data.append(['Age Group', 'Count', 'Percentage'])
        for age_group in age_groups:
            percentage = (age_group['count'] / total * 100) if total > 0 else 0
            data.append([age_group['group'], age_group['count'], f"{percentage:.1f}%"])
        data.append([])
        
        # Gender distribution
        data.append(['Gender Distribution'])
        data.append(['Gender', 'Count', 'Percentage'])
        data.append(['Male', male_count, f"{(male_count/total*100):.1f}%" if total > 0 else "0%"])
        data.append(['Female', female_count, f"{(female_count/total*100):.1f}%" if total > 0 else "0%"])
        data.append(['Other', other_count, f"{(other_count/total*100):.1f}%" if total > 0 else "0%"])
        data.append([])
        
        # Area distribution
        data.append(['Area Distribution'])
        data.append(['Area Type', 'Count', 'Percentage'])
        data.append(['Urban', urban_count, f"{(urban_count/total*100):.1f}%" if total > 0 else "0%"])
        data.append(['Rural', rural_count, f"{(rural_count/total*100):.1f}%" if total > 0 else "0%"])
        
        # Create DataFrame and save to Excel
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, header=False, sheet_name='Demographics Report')
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=voter_demographics_{current_date}.xlsx'
        response.headers['Content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        # Log the export action
        log_admin_action("Export Demographics Report (Excel)", f"Generated demographics Excel report with {total} total voters")
        
        return response
        
    except ImportError:
        # Fallback to CSV if pandas is not available
        flash('Excel export requires pandas library. Falling back to CSV format.', 'warning')
        return export_demographics_csv(current_date, total, age_groups, male_count, female_count, other_count, urban_count, rural_count)

def export_demographics_pdf(current_date, total, age_groups, male_count, female_count, other_count, urban_count, rural_count):
    # Create PDF content
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.white
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.white
    )
    
    content = []
    
    # Title
    content.append(Paragraph("Voter Demographics Report", title_style))
    content.append(Paragraph(f"Generated on: {current_date}", styles['Normal']))
    content.append(Spacer(1, 20))
    
    # Overview stats
    content.append(Paragraph("Overview Statistics", heading_style))
    overview_data = [['Total Voters', str(total)]]
    overview_table = Table(overview_data)
    overview_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    content.append(overview_table)
    content.append(Spacer(1, 20))
    
    # Age distribution
    content.append(Paragraph("Age Distribution", heading_style))
    age_data = [['Age Group', 'Count', 'Percentage']]
    for age_group in age_groups:
        percentage = (age_group['count'] / total * 100) if total > 0 else 0
        age_data.append([age_group['group'], str(age_group['count']), f"{percentage:.1f}%"])
    
    age_table = Table(age_data)
    age_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    content.append(age_table)
    content.append(Spacer(1, 20))
    
    # Gender distribution
    content.append(Paragraph("Gender Distribution", heading_style))
    gender_data = [['Gender', 'Count', 'Percentage']]
    gender_data.extend([
        ['Male', str(male_count), f"{(male_count/total*100):.1f}%" if total > 0 else "0%"],
        ['Female', str(female_count), f"{(female_count/total*100):.1f}%" if total > 0 else "0%"],
        ['Other', str(other_count), f"{(other_count/total*100):.1f}%" if total > 0 else "0%"]
    ])
    
    gender_table = Table(gender_data)
    gender_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    content.append(gender_table)
    content.append(Spacer(1, 20))
    
    # Area distribution
    content.append(Paragraph("Area Distribution", heading_style))
    area_data = [['Area Type', 'Count', 'Percentage']]
    area_data.extend([
        ['Urban', str(urban_count), f"{(urban_count/total*100):.1f}%" if total > 0 else "0%"],
        ['Rural', str(rural_count), f"{(rural_count/total*100):.1f}%" if total > 0 else "0%"]
    ])
    
    area_table = Table(area_data)
    area_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    content.append(area_table)
    
    # Build PDF
    doc.build(content)
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=voter_demographics_{current_date}.pdf'
    response.headers['Content-type'] = 'application/pdf'
    
    # Log the export action
    log_admin_action("Export Demographics Report (PDF)", f"Generated demographics PDF report with {total} total voters")
    
    return response