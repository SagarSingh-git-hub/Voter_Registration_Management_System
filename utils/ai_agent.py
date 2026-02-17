import os
import json
import requests
import logging
from flask import current_app
from models import mongo
from bson import ObjectId

class AIAgent:
    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY')
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-3.5-turbo" # Cost-effective and fast
        self.logger = logging.getLogger(__name__)

    def _get_system_prompt(self, user_context):
        """
        Generates the system prompt with context about the current user and available tools.
        """
        user_info = "Guest User"
        user_role = "voter"
        if user_context and user_context.is_authenticated:
            user_info = f"User: {user_context.full_name} (Role: {user_context.role}, ID: {user_context.id})"
            user_role = user_context.role

        prompt = f"""You are 'Voter Mitra', an intelligent AI assistant for the Voter Registration Management System (VRMS).
Your goal is to assist users with voter registration, application tracking, and electoral queries.

Current User Context: {user_info}

CAPABILITIES:
1. Answer questions about voter registration forms (Form 6, 7, 8, etc.).
2. Check application status if a Reference ID is provided.
3. Explain the electoral process.
4. Be polite, professional, and concise.

TOOLS:
You have access to the following tools. To use a tool, your response must be ONLY a JSON object in the following format:
{{ "tool": "tool_name", "params": {{ "param_name": "param_value" }} }}

Available Tools:
- `check_application_status`: Use this when the user asks for the status of an application and provides a Reference ID. params: {{ "reference_id": "..." }}
- `get_faq`: Use this to retrieve official answers for common questions. params: {{ "query": "..." }}
"""
        
        if user_role == 'admin':
            prompt += """
- `get_system_stats`: (Admin Only) Use this to get an overview of system statistics (users, applications). params: {}
"""

        prompt += """
If no tool is needed, just respond naturally in plain text. Do not output JSON unless using a tool.
"""
        return prompt

    def _call_llm(self, messages):
        """
        Calls the OpenAI API. Returns the content of the response.
        """
        if not self.api_key:
            return self._mock_response(messages)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            self.logger.error(f"LLM API Error: {str(e)}")
            return "I apologize, but I'm currently experiencing connection issues. Please try again later."

    def _mock_response(self, messages):
        """
        Fallback mock response when no API key is configured.
        """
        last_msg = messages[-1]['content'].lower()
        
        if "status" in last_msg and "ref" in last_msg:
            # Simulate tool call for status
            import re
            ref_match = re.search(r'[A-Z0-9]{6,}', last_msg.upper())
            ref_id = ref_match.group(0) if ref_match else "REF123"
            return json.dumps({ "tool": "check_application_status", "params": { "reference_id": ref_id } })
            
        if "hello" in last_msg or "hi" in last_msg:
            return "Namaste! I am Voter Mitra. How can I help you with your voter registration today?"
            
        return "I am currently running in offline mode (No API Key). I can simulate checking status if you provide a Reference ID, or answer basic greetings."

    def _execute_tool(self, tool_name, params):
        """
        Executes the requested tool and returns the result.
        """
        self.logger.info(f"Executing tool: {tool_name} with params: {params}")
        
        if tool_name == "check_application_status":
            ref_id = params.get('reference_id')
            # Look up in MongoDB
            # Assuming 'voter_applications' collection exists or similar. 
            # Based on models/forms.py, we might need to check how applications are stored.
            # For now, we'll check 'applications' collection which is standard.
            
            # Try to find in typical collections
            app = mongo.db.applications.find_one({"reference_id": ref_id})
            if not app:
                # Try finding by _id if it looks like an ObjectId
                if ObjectId.is_valid(ref_id):
                    app = mongo.db.applications.find_one({"_id": ObjectId(ref_id)})
            
            if app:
                status = app.get('status', 'Pending')
                return f"Application {ref_id} is currently: {status}"
            else:
                return f"I could not find an application with Reference ID: {ref_id}. Please check the ID and try again."

        elif tool_name == "get_faq":
            # Simple mock FAQ lookup
            return "For detailed guidelines, please visit the FAQ section in the dashboard."

        elif tool_name == "get_system_stats":
            # Admin tool
            try:
                user_count = mongo.db.users.count_documents({})
                app_count = mongo.db.applications.count_documents({})
                return f"System Stats: Total Users: {user_count}, Total Applications: {app_count}"
            except Exception as e:
                return f"Error fetching stats: {str(e)}"

        return "Tool not found."

    def generate_response(self, user_input, user_context, history=[]):
        """
        Main entry point.
        1. Construct messages.
        2. Call LLM.
        3. Check for tool use.
        4. If tool used, execute and call LLM again with result.
        5. Return final response.
        """
        system_prompt = self._get_system_prompt(user_context)
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add history (limit to last 5 turns to save context)
        for msg in history[-5:]:
            messages.append(msg)
            
        messages.append({"role": "user", "content": user_input})
        
        # First Pass
        response_text = self._call_llm(messages)
        
        # Check for Tool Call (JSON)
        try:
            tool_data = json.loads(response_text)
            if isinstance(tool_data, dict) and "tool" in tool_data:
                tool_result = self._execute_tool(tool_data["tool"], tool_data.get("params", {}))
                
                # Feed result back to LLM
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "system", "content": f"Tool Result: {tool_result}"})
                
                # Second Pass
                final_response = self._call_llm(messages)
                return final_response
        except json.JSONDecodeError:
            # Not a tool call, just normal text
            pass
            
        return response_text

# Singleton instance
ai_agent = AIAgent()
