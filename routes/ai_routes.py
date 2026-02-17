from flask import Blueprint, request, jsonify, render_template
from flask_login import current_user, login_required
from utils.ai_agent import ai_agent
import logging

ai_bp = Blueprint('ai', __name__)
logger = logging.getLogger(__name__)

@ai_bp.route('/api/chat', methods=['POST'])
def chat():
    """
    API Endpoint for the AI Chatbot.
    Expects JSON: { "message": "user message", "history": [...] }
    """
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400
            
        user_message = data['message']
        history = data.get('history', [])
        
        # Sanitize history to ensure it matches the expected format
        valid_history = []
        for h in history:
            if isinstance(h, dict) and 'role' in h and 'content' in h:
                valid_history.append(h)
        
        # Get response from AI Agent
        response = ai_agent.generate_response(user_message, current_user, valid_history)
        
        return jsonify({'response': response})
        
    except Exception as e:
        logger.error(f"Chat API Error: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500

@ai_bp.route('/chatbot')
def chatbot_ui():
    """
    Route to render the chatbot page directly if needed (though it's usually embedded).
    """
    return render_template('chatbot.html')
