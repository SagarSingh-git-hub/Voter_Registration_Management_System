from flask import Blueprint, render_template, redirect, url_for, request, jsonify, current_app
from flask_login import login_required, current_user
from models import mongo
from models.faq_data import faq_data
import requests

main = Blueprint('main', __name__)

@main.route('/')
def index():
    # Background "Keep-Alive" Ping for Supabase (Fire and Forget)
    try:
        supabase_rest_url = f"{current_app.config['SUPABASE_URL']}/rest/v1/" if current_app.config.get('SUPABASE_URL') else None
        if supabase_rest_url:
            # We use a very short timeout (0.5s) because we don't care about the response,
            # just that the request is sent to reset the inactivity timer.
            # We catch all exceptions so it never slows down the homepage.
            requests.get(supabase_rest_url, timeout=0.5)
    except:
        pass
    return render_template('index.html')

@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    else:
        # Check application status - Get the LATEST application
        application = mongo.db.applications.find_one(
            {"user_id": current_user.id},
            sort=[('submitted_at', -1)]
        )
        # Get Notifications
        notifications = list(mongo.db.notifications.find({"user_id": current_user.id}).sort("created_at", -1).limit(5))
        return render_template('dashboard.html', application=application, notifications=notifications)

@main.route('/chatbot')
@login_required
def chatbot():
    return render_template('chatbot.html')

@main.route('/chatbot/message', methods=['POST'])
@login_required
def chatbot_message():
    data = request.json
    if not data:
        return jsonify({"reply": "Invalid request: No JSON data found."}), 400
        
    user_message = data.get('message')

    # Webhook URL
    webhook_url = current_app.config.get('N8N_WEBHOOK_URL')
    if not webhook_url:
        return jsonify({"reply": "System Error: Chatbot configuration missing."}), 500

    try:
        # Construct Payload (Validating strict requirement)
        payload = {
            "message": user_message,
            "user_id": str(current_user.id),
            "username": getattr(current_user, 'username', 'Unknown')
        }

        # Send to n8n
        response = requests.post(webhook_url, json=payload, timeout=15)
        
        # Parse Response (Robust Handling)
        try:
            n8n_data = response.json()
        except ValueError:
            n8n_data = response.text

        # Extract Reply Logic
        reply_text = None
        
        # If list (n8n often returns list of items)
        if isinstance(n8n_data, list):
            if len(n8n_data) > 0:
                item = n8n_data[0]
                if isinstance(item, dict):
                    # Try common keys
                    reply_text = (
                        item.get('reply') or 
                        item.get('output_text') or 
                        item.get('text') or 
                        item.get('response') or 
                        item.get('message') or 
                        item.get('output') or
                        item.get('content')
                    )
                    # Fallback: if dict has no known text key, dump the whole dict
                    if not reply_text:
                        import json
                        reply_text = json.dumps(item)
                else:
                    reply_text = str(item)
            else:
                reply_text = "Received empty list from AI Agent."

        # If dict
        elif isinstance(n8n_data, dict):
            reply_text = (
                n8n_data.get('reply') or 
                n8n_data.get('output_text') or 
                n8n_data.get('text') or 
                n8n_data.get('response') or 
                n8n_data.get('message') or 
                n8n_data.get('output') or 
                n8n_data.get('content')
            )
            # Fallback
            if not reply_text:
                import json
                reply_text = json.dumps(n8n_data)

        # If string
        elif isinstance(n8n_data, str):
            reply_text = n8n_data

        # Final Fallback with Local Logic
        if not reply_text:
             # If n8n fails/returns empty, use local fallback logic
             print(f"DEBUG: n8n returned empty. Using local fallback.")
             reply_text = local_chatbot_fallback(user_message)

        return jsonify({"reply": reply_text})

    except Exception as e:
        print("Chatbot Error:", e)
        return jsonify({
            "reply": "An internal error occurred while connecting to the chatbot."
        }), 500

def local_chatbot_fallback(message):
    """
    Simple rule-based fallback when n8n is offline or misconfigured.
    """
    msg = message.lower()
    
    if "hello" in msg or "hi" in msg:
        return "Hello! I am Voter Mitra (Offline Mode). How can I help you?"
    
    elif "status" in msg or "track" in msg:
        return "You can check your application status on your Dashboard."
        
    elif "apply" in msg or "register" in msg:
        return "To apply for a new Voter ID, please fill out Form 6 available in the Forms section."
        
    elif "complaint" in msg:
        return "You can register a complaint using the 'Register Complaint' button on the dashboard."
        
    elif "download" in msg or "form" in msg:
        return "You can download necessary forms from the 'Download Forms' section."
        
    else:
        # Generic Menu Fallback for unknown inputs during outage
        return (
            "I am currently operating in Limited Mode (AI Offline). "
            "I can still assist you with:\n\n"
            "• Tracking Application Status\n"
            "• New Voter Registration\n"
            "• Filing Complaints\n"
            "• Downloading Forms\n\n"
            "Please type one of the topics above."
        )

@main.route('/faq')
def faq():
    return render_template('faq.html', faq_data=faq_data)

@main.route('/download/<type>/<filename>')
@login_required
def download_resource(type, filename):
    if type not in ['forms', 'docs']:
        return "Invalid resource type", 400
    
    # Simple directory traversal protection
    if '..' in filename or '/' in filename or '\\' in filename:
        return "Invalid filename", 400
        
    directory = 'static/forms' if type == 'forms' else 'static/docs'
    return redirect(url_for('static', filename=f"{type}/{filename}"))
