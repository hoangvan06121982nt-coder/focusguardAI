from camera_ai import FocusAI
from session_manager import SessionManager
sm = SessionManager()
ai = FocusAI(sm)
frame_bytes, alert, text = ai.get_frame()
print(f"Frame length: {len(frame_bytes)}, Alert: {alert}, Text: {text}")
