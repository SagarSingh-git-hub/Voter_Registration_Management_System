from flask import Blueprint, render_template, request, flash, redirect, url_for, session, send_file
from models import mongo
from utils import generate_otp
import io
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from datetime import datetime

e_epic = Blueprint('e_epic', __name__)

@e_epic.route('/e-epic', methods=['GET'])
def index():
    return render_template('e_epic.html', step='login')

@e_epic.route('/e-epic/login', methods=['POST'])
def login():
    identifier = request.form.get('identifier')
    if not identifier:
        flash('Please enter EPIC Number or Mobile Number', 'danger')
        return redirect(url_for('e_epic.index'))
    
    # Try to find in final_voters first (approved voters)
    # If not found, check applications (pending/rejected) for better error messaging
    voter = mongo.db.final_voters.find_one({
        "$or": [{"voter_id_number": identifier}, {"phone": identifier}]
    })
    
    if not voter:
        # Check applications for better error messaging
        application = mongo.db.voter_applications.find_one({
             "$or": [{"voter_id_number": identifier}, {"phone": identifier}]
        })
        
        if application:
             status = application.get('status', 'pending')
             flash(f'Your application found but status is: {status.upper()}. Approval required for E-EPIC.', 'warning')
             return redirect(url_for('e_epic.index'))
        else:
             flash('No voter record found with these details.', 'danger')
             return redirect(url_for('e_epic.index'))
    
    # Generate OTP
    otp = generate_otp()
    session['e_epic_otp'] = otp
    session['e_epic_identifier'] = identifier
    # In production, store this securely with expiry
    
    # Mock sending OTP
    flash(f'OTP sent to your registered mobile. (DEV: {otp})', 'info')
    
    return render_template('e_epic.html', step='otp', identifier=identifier)

@e_epic.route('/e-epic/verify', methods=['POST'])
def verify():
    entered_otp = request.form.get('otp')
    if entered_otp == session.get('e_epic_otp'):
        identifier = session.get('e_epic_identifier')
        
        # Fetch voter details again
        voter = mongo.db.final_voters.find_one({
            "$or": [{"voter_id_number": identifier}, {"phone": identifier}]
        })
        
        # Check if voter found
        if not voter:
            # Check if pending in applications
            application = mongo.db.voter_applications.find_one({
                "$or": [{"voter_id_number": identifier}, {"phone": identifier}, {"email": identifier}]
            })
            
            if application:
                status = application.get('status', 'pending')
                if status == 'approved':
                    # Should have been in final_voters, maybe sync issue
                    flash('Your application is approved but record synchronization is pending. Please contact admin.', 'warning')
                else:
                    flash(f'Your application status is currently: {status.upper()}. You can download E-EPIC only after approval.', 'warning')
            else:
                flash('No approved voter record found. Please register or check your details.', 'danger')
                
            return render_template('e_epic.html', step='otp', identifier=session.get('e_epic_identifier'))
        
        # Create a session-safe voter object (exclude ObjectId and other non-serializable fields)
        session_voter = {
            "full_name": voter.get("full_name"),
            "voter_id_number": voter.get("voter_id_number"),
            "dob": voter.get("dob"),
            "gender": voter.get("gender"),
            "assembly_constituency": voter.get("assembly_constituency"),
            "part_number": voter.get("part_number", ""),
            "serial_number": voter.get("serial_number", ""),
            "phone": voter.get("phone", "")
        }
            
        session['e_epic_voter'] = session_voter
        return render_template('e_epic.html', step='preview', voter=session_voter)
    else:
        flash('Invalid OTP. Please try again.', 'danger')
        return render_template('e_epic.html', step='otp', identifier=session.get('e_epic_identifier'))

@e_epic.route('/e-epic/download')
def download():
    # Re-validate session voter from DB to ensure no stale/mock data is used
    session_voter = session.get('e_epic_voter')
    if not session_voter:
        return redirect(url_for('e_epic.index'))
    
    voter_id = session_voter.get('voter_id_number')
    if not voter_id:
        return redirect(url_for('e_epic.index'))
        
    # Fetch fresh data from DB
    voter = mongo.db.final_voters.find_one({"voter_id_number": voter_id})
    if not voter:
        flash('Security Alert: Voter record mismatch. Please login again.', 'danger')
        return redirect(url_for('e_epic.index'))

    # Log the download history
    mongo.db.e_epic_downloads.insert_one({
        "voter_id_number": voter.get('voter_id_number'),
        "full_name": voter.get('full_name'),
        "downloaded_at": datetime.now(),
        "ip_address": request.remote_addr,
        "user_agent": request.user_agent.string
    })

    # Generate PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Draw Background/Watermark
    c.saveState()
    c.setFillColor(colors.grey)
    c.setFont("Helvetica-Bold", 60)
    c.translate(width/2, height/2)
    c.rotate(45)
    c.setFillAlpha(0.1)
    c.drawCentredString(0, 0, "ELECTION COMMISSION OF INDIA")
    c.restoreState()
    
    # Header
    c.setFillColor(colors.navy)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height - 100, "ELECTION COMMISSION OF INDIA")
    
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, height - 130, "ELECTOR'S PHOTO IDENTITY CARD")
    
    # Border
    c.setStrokeColor(colors.navy)
    c.setLineWidth(2)
    c.rect(50, height - 400, width - 100, 320)
    
    # Photo Placeholder
    c.rect(70, height - 250, 100, 120)
    c.setFont("Helvetica", 10)
    c.drawCentredString(120, height - 200, "PHOTO")
    
    # Details
    c.setFont("Helvetica-Bold", 14)
    c.drawString(200, height - 180, f"Name: {voter.get('full_name')}")
    c.drawString(200, height - 210, f"EPIC No: {voter.get('voter_id_number')}")
    c.drawString(200, height - 240, f"Gender: {voter.get('gender')}")
    c.drawString(200, height - 270, f"DOB: {voter.get('dob')}")
    c.drawString(200, height - 300, f"Constituency: {voter.get('assembly_constituency')}")
    
    # QR Code (In-memory)
    qr_data = f"EPIC:{voter.get('voter_id_number')}|Name:{voter.get('full_name')}"
    qr = qrcode.make(qr_data)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    
    from reportlab.lib.utils import ImageReader
    qr_image = ImageReader(qr_buffer)
    c.drawImage(qr_image, width - 180, height - 250, width=100, height=100)
    
    # Footer
    c.setFont("Helvetica", 10)
    c.drawCentredString(width/2, height - 380, "This is a computer generated digital card.")
    c.drawCentredString(width/2, height - 395, f"Downloaded on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    c.showPage()
    c.save()
    
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"e-epic_{voter.get('voter_id_number')}.pdf", mimetype='application/pdf')
