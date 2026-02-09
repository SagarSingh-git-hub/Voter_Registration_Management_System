import os
import csv
from io import BytesIO, StringIO
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_file, current_app, make_response
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

@admin.route('/admin/profile')
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

@admin.route('/admin/profile/upload-pic', methods=['POST'])
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

@admin.route('/admin/profile/update', methods=['POST'])
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

@admin.route('/admin/profile/remove-pic', methods=['POST'])
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

@admin.route('/admin/profile/change-password', methods=['POST'])
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

@admin.route('/admin/dashboard')
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

@admin.route('/admin/application/<app_id>')
@login_required
@admin_required
def view_application(app_id):
    application = mongo.db.applications.find_one({"_id": ObjectId(app_id)})
    if not application:
        abort(404)
        
    user = mongo.db.users.find_one({"_id": ObjectId(application['user_id'])})
    return render_template('view_application.html', application=application, user=user)

@admin.route('/admin/document/<path:filename>')
@login_required
@admin_required
def view_document(filename):
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        print(f"DEBUG: File not found: {file_path}")
        abort(404)
    return send_file(file_path)

@admin.route('/admin/approve/<app_id>', methods=['POST'])
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

@admin.route('/admin/reject/<app_id>', methods=['POST'])
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

@admin.route('/admin/export/csv')
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

@admin.route('/admin/export/pdf')
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
        
        # Professional Table Styling
        style = TableStyle([
            # Header Row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')), # Dark Slate
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('LEFTPADDING', (0, 0), (-1, 0), 10),
            
            # Content Rows
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#334155')),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('LEFTPADDING', (0, 1), (-1, -1), 10),
            
            # Borders & Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Zebra Striping
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ])
        
        table.setStyle(style)
        elements.append(table)
        
        # --- Footer ---
        elements.append(Spacer(1, 40))
        footer_style = ParagraphStyle(
            'Footer', 
            parent=styles['Normal'], 
            alignment=TA_CENTER, 
            fontSize=8, 
            textColor=colors.gray
        )
        elements.append(Paragraph("This is a system-generated official document. Valid without signature.", footer_style))
        elements.append(Paragraph("ELECTION COMMISSION OF INDIA • OFFICIAL RECORD", footer_style))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d")
        return send_file(
            buffer, 
            as_attachment=True, 
            download_name=f'Official_Voter_Registry_{timestamp}.pdf', 
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        flash('Error generating PDF. Please contact support.', 'danger')
        return redirect(url_for('admin.dashboard'))
