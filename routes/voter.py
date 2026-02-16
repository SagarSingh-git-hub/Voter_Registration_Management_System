from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, session, send_file, abort
from flask_login import login_required, current_user
from models.forms import VoterApplicationForm
from models import mongo
from werkzeug.utils import secure_filename
import os
import csv
import uuid
import io
from datetime import datetime
from utils import perform_ocr_scan, check_smart_duplicate, allowed_file, generate_otp, send_otp_email
from functools import wraps
from bson.objectid import ObjectId
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from PIL import Image as PILImage, ImageOps
from functools import lru_cache
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CSV_FILE = os.path.join(BASE_DIR, "All_28_States_Districts_PinCodes_with_Constituency.csv")

voter = Blueprint('voter', __name__)

def voter_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'voter':
            flash('Unauthorized Access', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@voter.route('/profile')
@login_required
@voter_required
def profile():
    application = mongo.db.applications.find_one(
        {'user_id': str(current_user.id)},
        sort=[('submitted_at', -1)]
    )
    return render_template('voter_profile.html', application=application)

@voter.route('/profile/update', methods=['POST'])
@login_required
@voter_required
def update_profile():
    phone = request.form.get('phone')
    email = request.form.get('email')
    
    application = mongo.db.applications.find_one(
        {'user_id': str(current_user.id)},
        sort=[('submitted_at', -1)]
    )
    
    if application and application.get('status') == 'Approved':
        flash('Cannot edit profile after approval.', 'warning')
        return redirect(url_for('voter.profile'))

    update_data = {}
    if phone: update_data['phone'] = phone
    if email: update_data['email'] = email
    
    if update_data:
        update_data['last_updated'] = datetime.utcnow()
        if application:
             mongo.db.applications.update_one({'_id': application['_id']}, {'$set': update_data})
        else:
             mongo.db.users.update_one({'_id': ObjectId(current_user.id)}, {'$set': update_data})

    flash('Profile updated successfully', 'success')
    return redirect(url_for('voter.profile'))

@voter.route('/application', methods=['GET', 'POST'])
@login_required
@voter_required
def voter_application():
    form = VoterApplicationForm()
    if form.validate_on_submit():
        existing_app = mongo.db.applications.find_one({
            'user_id': str(current_user.id),
            'status': {'$ne': 'Rejected'}
        })
        if existing_app:
            flash('You have already submitted an application.', 'warning')
            return redirect(url_for('voter.profile'))

        photo_path = None
        if form.photograph.data:
            f = form.photograph.data
            filename = secure_filename(f.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            f.save(save_path)
            
            # Fix orientation (EXIF)
            try:
                img = PILImage.open(save_path)
                img = ImageOps.exif_transpose(img)
                img.save(save_path)
            except Exception as e:
                print(f"Error fixing image orientation: {e}")
                
            photo_path = unique_filename

        # Handle ID Proof Document
        doc_path = None
        if form.document.data:
            f = form.document.data
            filename = secure_filename(f.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            f.save(save_path)
            doc_path = unique_filename

        application_data = {
            'user_id': str(current_user.id),
            'full_name': form.full_name.data,
            'relative_name': form.relative_name.data,
            'relative_type': form.relative_type.data,
            'dob': form.dob.data.strftime('%Y-%m-%d') if form.dob.data else None,
            'gender': form.gender.data,
            'phone': form.phone.data,
            'email': form.email.data,
            'present_address': form.present_address.data,
            'permanent_address': form.permanent_address.data,
            'pin_code': form.pin_code.data,
            'state': form.state.data,
            'district': form.district.data,
            'assembly_constituency': form.assembly_constituency.data,
            'loksabha_constituency': form.loksabha_constituency.data,
            'id_proof_type': form.id_proof_type.data,
            'id_proof_number': form.id_proof_number.data,
            'photograph_path': photo_path,
            'document_path': doc_path,
            'status': 'Pending',
            'submitted_at': datetime.utcnow()
        }
        
        mongo.db.applications.insert_one(application_data)
        flash('Application submitted successfully!', 'success')
        return redirect(url_for('voter.profile'))
        
    return render_template('voter_application.html', form=form)

@voter.route('/service/<service_type>', methods=['GET', 'POST'])
@login_required
@voter_required
def service_form(service_type):
    service_names = {
        'search': 'Search Voter List',
        'complaint': 'Register Complaint',
        'blo_call': 'Book BLO Call',
        'appeal': 'Submit Appeal',
        'form7': 'Deletion of Name (Form 7)',
        'form8': 'Correction of Entries (Form 8)',
        'form6a': 'Overseas Elector (Form 6A)'
    }
    
    service_name = service_names.get(service_type, 'Service Request')
    
    if request.method == 'POST':
        # TODO: Implement actual logic for each service type
        flash(f'Your request for {service_name} has been submitted successfully.', 'success')
        return redirect(url_for('voter.profile'))
        
    return render_template('service_form.html', service_type=service_type, service_name=service_name)

@voter.route('/search')
def search_voter_page():
    return render_template('search_voter.html')

@voter.route('/api/search')
def api_search_voter():
    search_type = request.args.get('type')
    query = {}
    
    if search_type == 'epic':
        epic = request.args.get('epic')
        if epic:
            query['epic_number'] = epic
    else:
        name = request.args.get('name')
        age = request.args.get('age')
        state = request.args.get('state')
        district = request.args.get('district')
        assembly = request.args.get('assembly')
        
        if name:
            query['full_name'] = {'$regex': name, '$options': 'i'}
        if state:
            query['state'] = state
        if district:
            query['district'] = {'$regex': district, '$options': 'i'}
        if assembly:
            query['assembly_constituency'] = {'$regex': assembly, '$options': 'i'}

    # Search only approved applications
    query['status'] = 'Approved'
    
    results = mongo.db.applications.find(query)
    
    data = []
    for app in results:
        # Calculate age
        dob = app.get('dob')
        age_val = 'N/A'
        if dob:
            try:
                dob_date = datetime.strptime(dob, '%Y-%m-%d')
                today = datetime.today()
                age_val = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
            except:
                pass

        data.append({
            "full_name": app.get('full_name'),
            "relative_name": app.get('relative_name'),
            "epic_number": app.get('epic_number'),
            "gender": app.get('gender'),
            "age": age_val,
            "assembly_constituency": app.get('assembly_constituency', 'N/A'),
            "loksabha_constituency": app.get('loksabha_constituency', 'N/A'),
            "polling_station": app.get('polling_station'),
            "polling_address": app.get('present_address'), 
            "part_number": app.get('booth_number', '01'), 
            "serial_number": str(int(str(app.get('_id'))[-4:], 16)),
            "photo_url": app.get('photograph_path')
        })
        
    return jsonify(data)

@lru_cache(maxsize=1)
def _csv_rows():
    rows = []
    try:
        with open(CSV_FILE, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append({
                    'State': (r.get('State') or '').strip(),
                    'District': (r.get('District') or '').strip(),
                    'Pin Code': (r.get('Pin Code') or '').strip(),
                    'Constituency': (r.get('Constituency') or '').strip()
                })
    except Exception:
        pass
    return tuple(rows)

@voter.route('/api/states')
@login_required
@voter_required
def get_states():
    states = sorted({r['State'] for r in _csv_rows() if r['State']})
    return jsonify(states)

@voter.route('/api/districts')
@login_required
@voter_required
def get_districts():
    state = request.args.get('state', '').strip()
    districts = sorted({r['District'] for r in _csv_rows() if (not state or r['State'] == state) and r['District']})
    return jsonify(districts)

@voter.route('/api/pincodes')
@login_required
@voter_required
def get_pincodes():
    state = request.args.get('state', '').strip()
    district = request.args.get('district', '').strip()
    pins = sorted({r['Pin Code'] for r in _csv_rows() if (not state or r['State'] == state) and (not district or r['District'] == district) and r['Pin Code']})
    return jsonify(pins)

@voter.route('/api/lookup')
@login_required
@voter_required
def constituency_lookup():
    state = request.args.get('state', '').strip()
    district = request.args.get('district', '').strip()
    pin_code = request.args.get('pin_code', '').strip()
    for r in _csv_rows():
        if (not state or r['State'] == state) and (not district or r['District'] == district) and (not pin_code or r['Pin Code'] == pin_code):
            return jsonify({
                'state': r['State'],
                'district': r['District'],
                'pin_code': r['Pin Code'],
                'assembly_constituency': r['Constituency'],
                'loksabha_constituency': r['Constituency']
            })
    return jsonify({
        'state': state,
        'district': district,
        'pin_code': pin_code,
        'assembly_constituency': '',
        'loksabha_constituency': ''
    })

@voter.route('/photo/<path:filename>')
@login_required
def view_photo(filename):
    # Ensure the file path is safe and within the uploads directory
    uploads_dir = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(uploads_dir, filename)
    
    # Security check to prevent directory traversal
    if not os.path.abspath(file_path).startswith(os.path.abspath(uploads_dir)):
        abort(403)
        
    if not os.path.exists(file_path):
        abort(404)
        
    return send_file(file_path)

@voter.route('/print-slip/<epic_number>')
def print_voter_slip(epic_number):
    app = mongo.db.applications.find_one({'epic_number': epic_number, 'status': 'Approved'})
    if not app:
        abort(404)

    # Colors (VOTE.X Palette)
    DEEP_BLUE = HexColor('#0f172a')
    ELECTRIC_BLUE = HexColor('#00B4FF') 
    LIGHT_BLUE_BG = HexColor('#f0f9ff')
    TEXT_DARK = HexColor('#1e293b')
    TEXT_GRAY = HexColor('#64748b')
    WHITE = colors.white
    BORDER_COLOR = HexColor('#e2e8f0')

    # Calculate Age
    age_val = 'N/A'
    dob = app.get('dob')
    if dob:
        try:
            dob_date = datetime.strptime(dob, '%Y-%m-%d')
            today = datetime.today()
            age_val = str(today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day)))
        except:
            pass

    # Setup PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    style_header_title = ParagraphStyle('HeaderTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, textColor=WHITE, alignment=TA_LEFT, leading=18)
    style_header_sub = ParagraphStyle('HeaderSub', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=colors.Color(1,1,1,0.8), alignment=TA_LEFT)
    style_header_epic_label = ParagraphStyle('HeaderEpicLabel', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.Color(1,1,1,0.8), alignment=TA_RIGHT)
    style_header_epic_val = ParagraphStyle('HeaderEpicVal', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=16, textColor=ELECTRIC_BLUE, alignment=TA_RIGHT, leading=20)
    
    style_voter_name = ParagraphStyle('VoterName', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=22, textColor=TEXT_DARK, spaceAfter=6, leading=26)
    style_voter_meta = ParagraphStyle('VoterMeta', parent=styles['Normal'], fontName='Helvetica', fontSize=11, textColor=TEXT_GRAY, leading=14)
    
    style_label = ParagraphStyle('Label', parent=styles['Normal'], fontName='Helvetica', fontSize=9, textColor=TEXT_GRAY, spaceAfter=2)
    style_value = ParagraphStyle('Value', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, textColor=TEXT_DARK, leading=14)
    
    style_section_head = ParagraphStyle('SectionHead', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=ELECTRIC_BLUE, spaceAfter=6)
    
    # --- HEADER ---
    header_data = [
        [
            [Paragraph("ELECTION COMMISSION OF INDIA", style_header_title), Paragraph("Electoral Roll Entry – Verified Record", style_header_sub)],
            [Paragraph("EPIC NUMBER", style_header_epic_label), Paragraph(app.get('epic_number') or 'N/A', style_header_epic_val)]
        ]
    ]
    header_table = Table(header_data, colWidths=[4*inch, 3.5*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), DEEP_BLUE),
        ('LEFTPADDING', (0,0), (-1,-1), 20),
        ('RIGHTPADDING', (0,0), (-1,-1), 20),
        ('TOPPADDING', (0,0), (-1,-1), 20),
        ('BOTTOMPADDING', (0,0), (-1,-1), 20),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 30))

    # --- VOTER IDENTITY & PHOTO ---
    # Photo
    img_obj = None
    if app.get('photograph_path'):
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], app.get('photograph_path'))
        if os.path.exists(full_path):
            try:
                # Open with PIL to handle EXIF rotation
                pil_img = PILImage.open(full_path)
                pil_img = ImageOps.exif_transpose(pil_img)
                
                # Resize/Resample and crop to square using ImageOps.fit
                # This ensures the face remains centered and not stretched
                # Target size: 300x300 pixels (high quality for PDF)
                pil_img = ImageOps.fit(pil_img, (300, 300), method=PILImage.LANCZOS, centering=(0.5, 0.5))
                
                # Save to buffer to pass to ReportLab
                img_buffer = io.BytesIO()
                pil_img.save(img_buffer, format=pil_img.format or 'JPEG')
                img_buffer.seek(0)
                
                img_obj = Image(img_buffer, 1.4*inch, 1.4*inch)
            except Exception as e:
                print(f"Error processing image: {e}")
                img_obj = None
    
    if not img_obj:
         # Placeholder text if no image
         img_obj = Paragraph("NO PHOTO", style_label)

    # Voter Info
    voter_info = [
        Paragraph(app.get('full_name') or 'Unknown', style_voter_name),
        Paragraph(f"{age_val} Years  •  {app.get('gender') or 'N/A'}", style_voter_meta),
        Spacer(1, 8),
        Paragraph(f"Relative Name: {app.get('relative_name') or 'N/A'}", style_value)
    ]
    
    # Increased colWidths for gap and explicitly added padding
    identity_data = [[img_obj, voter_info]]
    identity_table = Table(identity_data, colWidths=[2.0*inch, 5.3*inch])
    identity_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (0,0), 20), # Explicit gap between photo and text
        ('BOTTOMPADDING', (0,0), (-1,-1), 20),
        # Removed 'BOX' border around photo as per user request
    ]))
    elements.append(identity_table)
    elements.append(Spacer(1, 10))
    
    # --- DETAILS GRID ---
    # Row 1
    r1c1 = [Paragraph("EPIC Number", style_label), Paragraph(app.get('epic_number') or 'N/A', style_value)]
    r1c2 = [Paragraph("Part No. / Serial No.", style_label), Paragraph(f"{app.get('booth_number') or '01'} / {str(int(str(app.get('_id'))[-4:], 16))}", style_value)]
    
    # Row 2
    r2c1 = [Paragraph("Assembly Constituency", style_label), Paragraph(app.get('assembly_constituency') or 'N/A', style_value)]
    r2c2 = [Paragraph("Parliamentary Constituency", style_label), Paragraph(app.get('loksabha_constituency') or 'N/A', style_value)]
    
    details_data = [
        [r1c1, r1c2],
        [r2c1, r2c2]
    ]
    
    details_table = Table(details_data, colWidths=[3.6*inch, 3.6*inch])
    details_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 15),
        ('BOTTOMPADDING', (0,0), (-1,-1), 15),
        ('LINEBELOW', (0,0), (-1,0), 1, BORDER_COLOR), # Divider between rows
        ('RIGHTPADDING', (0,0), (0,-1), 20), # Gap between cols
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 30))
    
    # --- POLLING STATION ---
    elements.append(Paragraph("POLLING STATION DETAILS", style_section_head))
    
    ps_content = [
        [Paragraph(app.get('polling_station') or 'To be assigned', style_value)],
        [Spacer(1, 4)],
        [Paragraph(app.get('present_address') or 'N/A', style_label)]
    ]
    
    ps_table = Table(ps_content, colWidths=[7.2*inch])
    ps_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_BLUE_BG),
        ('BOX', (0,0), (-1,-1), 1, ELECTRIC_BLUE),
        ('LEFTPADDING', (0,0), (-1,-1), 15),
        ('RIGHTPADDING', (0,0), (-1,-1), 15),
        ('TOPPADDING', (0,0), (-1,-1), 15),
        ('BOTTOMPADDING', (0,0), (-1,-1), 15),
    ]))
    elements.append(ps_table)
    elements.append(Spacer(1, 50))
    
    # --- FOOTER ---
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=TEXT_GRAY, alignment=TA_CENTER)
    elements.append(Paragraph("This is a computer-generated slip. No signature is required.", footer_style))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %B, %Y at %I:%M %p')}", footer_style))
    
    doc.build(elements)
    
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Voter_Slip_{epic_number}.pdf",
        mimetype='application/pdf'
    )
