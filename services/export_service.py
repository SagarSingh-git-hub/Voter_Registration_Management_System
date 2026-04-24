import csv
from io import StringIO
from datetime import datetime
from bson.objectid import ObjectId

def generate_csv_stream(mongo):
    """Generator function to stream CSV data row by row."""
    # Add BOM for Excel compatibility
    yield '\ufeff'
    
    si = StringIO()
    cw = csv.writer(si)
    
    headers = [
        'Application ID', 'Full Name', 'Gender', 'Date of Birth', 
        'Email', 'Phone', 'EPIC ID Number', 
        'Address', 'State', 'Pincode', 
        'Status', 'Reason', 'Submitted Date'
    ]
    cw.writerow(headers)
    yield si.getvalue()
    si.seek(0)
    si.truncate(0)
    
    # Process records in chunks using a cursor
    cursor = mongo.db.applications.find({}).sort('submitted_at', -1)
    
    for app in cursor:
        submitted = app.get('submitted_at', '')
        if isinstance(submitted, datetime):
            submitted = submitted.strftime('%Y-%m-%d %H:%M')
            
        email = app.get('email', '')
        phone = app.get('phone', '')
        
        if not email or not phone:
            user = mongo.db.users.find_one({"_id": ObjectId(app.get('user_id'))})
            if user:
                email = email or user.get('email', '')
                phone = phone or user.get('phone', '')

        reason = app.get('rejection_reason', '') if app.get('status') == 'Rejected' else ''

        row = [
            str(app.get('_id', '')),
            app.get('full_name', '').title() if app.get('full_name') else '',
            app.get('gender', '').title() if app.get('gender') else '',
            app.get('dob', ''),
            email,
            phone,
            app.get('epic_number', ''),
            app.get('address', '').replace('\n', ' ') if app.get('address') else '',
            app.get('state', ''),
            app.get('pincode', ''),
            app.get('status', 'Pending'),
            reason,
            submitted
        ]
        
        cw.writerow(row)
        yield si.getvalue()
        si.seek(0)
        si.truncate(0)