
def get_approval_email_html(name, app_id):
    return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px; background-color: #f9f9f9; }}
        .header {{ background-color: #1a5f7a; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
        .content {{ padding: 20px; background-color: white; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #777; }}
        .status-badge {{ background-color: #28a745; color: white; padding: 5px 10px; border-radius: 4px; font-weight: bold; }}
        .details-box {{ background-color: #f8f9fa; padding: 15px; border-left: 4px solid #1a5f7a; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Voter Registration Status Update</h2>
        </div>
        <div class="content">
            <p>Dear <strong>{name}</strong>,</p>
            <p>We are pleased to inform you that your application for voter registration has been reviewed and <strong>APPROVED</strong>.</p>
            
            <div class="details-box">
                <p><strong>Application ID:</strong> {app_id}</p>
                <p><strong>Status:</strong> <span class="status-badge">APPROVED</span></p>
                <p><strong>Date:</strong> {get_current_date()}</p>
            </div>

            <p>You can now log in to your dashboard to download your digital Voter ID card.</p>
            
            <p>Thank you for participating in the democratic process.</p>
            
            <p>Sincerely,<br>
            <strong>Chief Electoral Officer</strong><br>
            Election Commission</p>
        </div>
        <div class="footer">
            <p>This is an automated message. Please do not reply to this email.</p>
            <p>&copy; {get_current_year()} Election Commission. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

def get_rejection_email_html(name, app_id, reason):
    return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px; background-color: #f9f9f9; }}
        .header {{ background-color: #c0392b; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
        .content {{ padding: 20px; background-color: white; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #777; }}
        .status-badge {{ background-color: #dc3545; color: white; padding: 5px 10px; border-radius: 4px; font-weight: bold; }}
        .details-box {{ background-color: #f8f9fa; padding: 15px; border-left: 4px solid #c0392b; margin: 20px 0; }}
        .reason-box {{ background-color: #fff3f3; padding: 15px; border: 1px solid #ffcccc; border-radius: 4px; color: #c0392b; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Voter Registration Status Update</h2>
        </div>
        <div class="content">
            <p>Dear <strong>{name}</strong>,</p>
            <p>We regret to inform you that your application for voter registration has been <strong>REJECTED</strong>.</p>
            
            <div class="details-box">
                <p><strong>Application ID:</strong> {app_id}</p>
                <p><strong>Status:</strong> <span class="status-badge">REJECTED</span></p>
                <p><strong>Date:</strong> {get_current_date()}</p>
            </div>

            <p><strong>Reason for Rejection:</strong></p>
            <div class="reason-box">
                {reason}
            </div>

            <p>Please log in to your dashboard to review the details and submit a new application with the correct information/documents.</p>
            
            <p>Sincerely,<br>
            <strong>Chief Electoral Officer</strong><br>
            Election Commission</p>
        </div>
        <div class="footer">
            <p>This is an automated message. Please do not reply to this email.</p>
            <p>&copy; {get_current_year()} Election Commission. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

def get_approval_email_text(name, app_id):
    return f"""
Subject: Update on your Voter Application - APPROVED

Dear {name},

We are pleased to inform you that your voter application (ID: {app_id}) has been APPROVED.

You can now log in to your dashboard to download your digital Voter ID card.

Thank you for participating in the democratic process.

Sincerely,
Chief Electoral Officer
Election Commission
"""

def get_rejection_email_text(name, app_id, reason):
    return f"""
Subject: Update on your Voter Application - REJECTED

Dear {name},

We regret to inform you that your voter application (ID: {app_id}) has been REJECTED.

Reason for Rejection:
{reason}

Please log in to your dashboard to review the details and submit a new application.

Sincerely,
Chief Electoral Officer
Election Commission
"""

from datetime import datetime

def get_current_date():
    return datetime.now().strftime("%B %d, %Y")

def get_current_year():
    return datetime.now().year
