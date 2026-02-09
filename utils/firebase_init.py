import firebase_admin
from firebase_admin import credentials, auth
import os

_firebase_app = None

def get_firebase_app():
    global _firebase_app
    if not _firebase_app:
        try:
            # 1. Path to service account key
            # Ideally this is in an env var, but we'll default to the local file as requested
            cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') or os.path.join(os.getcwd(), 'serviceAccountKey.json')
            
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                # 2. Initialize with explicit project_id
                _firebase_app = firebase_admin.initialize_app(cred, {
                    'projectId': 'vrms-app-ec79a'
                })
                print(f"[Firebase] Initialized with service account: {cred_path}")
            else:
                print(f"[Firebase] Service account file not found at: {cred_path}")
                # Fallback to default (might work if running in GCP context)
                _firebase_app = firebase_admin.initialize_app()

        except ValueError:
            # Already initialized
            _firebase_app = firebase_admin.get_app()
        except Exception as e:
            print(f"Warning: Firebase Admin initialization failed: {e}")
            return None
    return _firebase_app

def verify_token(id_token):
    app = get_firebase_app()
    if not app:
        raise Exception("Firebase Admin not initialized")
    
    # Verify the token
    # check_revoked=True checks if the user's session was revoked (security best practice)
    return auth.verify_id_token(id_token, check_revoked=True)
