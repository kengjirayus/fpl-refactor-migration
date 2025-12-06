import firebase_admin
from firebase_admin import credentials, firestore
import os

_db = None

def get_firestore_client():
    global _db
    if _db is not None:
        return _db

    try:
        # Check if app is already initialized
        if not firebase_admin._apps:
            # Look for serviceAccountKey.json in the backend root
            key_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "serviceAccountKey.json")
            if os.path.exists(key_path):
                cred = credentials.Certificate(key_path)
                firebase_admin.initialize_app(cred)
                _db = firestore.client()
                print("Firebase initialized successfully.")
            else:
                print("Warning: serviceAccountKey.json not found. Firebase features will be disabled.")
                return None
        else:
            _db = firestore.client()
        
        return _db
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return None
