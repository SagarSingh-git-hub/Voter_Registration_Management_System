from app import create_app
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = create_app()

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.environ.get('PORT', 5000))
    
    if debug_mode:
        print(f"Starting Flask server in DEBUG mode (Port {port})...")
        # Enable reloader to pick up code changes automatically
        app.run(debug=True, port=port, use_reloader=True)
    else:
        print(f"Starting Flask server in PRODUCTION mode (Port {port})...")
        # For production, we should ideally use a WSGI server, but for now we run the flask dev server 
        # with debug=False if executed directly.
        app.run(debug=False, port=port)
