import sys
import numpy as np

print("Testing imports and instantiations...")
try:
    from face_recognition import FaceRecognizer
    from tracker import PersonTracker
    from seating_manager import SeatingManager
    
    print("1. Instantiating FaceRecognizer...")
    rec = FaceRecognizer()
    
    print("2. Instantiating PersonTracker...")
    track = PersonTracker()
    
    print("3. Instantiating SeatingManager...")
    seat = SeatingManager()
    
    # Create a dummy image
    dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
    
    print("4. Testing PersonTracker on dummy image...")
    res = track.track(dummy_img)
    print(f"   Tracker result on blank frame: {res}")
    
    print("\n[SUCCESS] All modules instantiated and ran successfully on blank frame!")
except Exception as e:
    print(f"\n[ERROR] Testing failed: {e}")
    sys.exit(1)
