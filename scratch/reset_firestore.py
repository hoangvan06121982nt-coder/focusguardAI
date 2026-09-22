import os
import sys

# Force environments
os.environ["DATABASE_TYPE"] = "firestore"
os.environ["USE_EMULATOR"] = "true"

# Add parent dir to path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from session_manager import SessionManager

def main():
    print("Connecting to SessionManager...")
    sm = SessionManager()
    db = sm.repo.db
    
    collections = ["users", "classes", "sessions", "focus_events"]
    print("Clearing collections...")
    for coll in collections:
        docs = db.collection(coll).stream()
        deleted = 0
        for doc in docs:
            doc.reference.delete()
            deleted += 1
        print(f"Deleted {deleted} documents from '{coll}'")
        
    print("Reseeding default database data...")
    sm.seed_data()
    print("Reseed completed successfully!")

if __name__ == "__main__":
    main()
