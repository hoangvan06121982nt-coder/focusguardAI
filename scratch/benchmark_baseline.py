import sys, os
sys.path.insert(0, os.path.abspath("."))
import time
import cv2
import numpy as np
from session_manager import SessionManager
from camera_ai import FocusAI
from classroom_ai import ClassroomAI

def benchmark_raw_camera(frames=50):
    print("=== BENCHMARK 1: RAW WEBCAM CAPTURE ===")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera")
        return
    times = []
    # Warmup
    for _ in range(5):
        cap.read()
    start = time.time()
    for _ in range(frames):
        t0 = time.time()
        ret, frame = cap.read()
        times.append(time.time() - t0)
    total_time = time.time() - start
    cap.release()
    avg_ms = np.mean(times) * 1000
    fps = frames / total_time
    print(f"Raw Camera: {fps:.2f} FPS | Avg read time: {avg_ms:.2f} ms")

def benchmark_focus_ai(frames=30):
    print("\n=== BENCHMARK 2: CURRENT FocusAI (Single Student) ===")
    sm = SessionManager()
    ai = FocusAI(sm)
    # Warmup
    for _ in range(5):
        ai.get_frame()
    times = []
    start = time.time()
    for _ in range(frames):
        t0 = time.time()
        frame_bytes, alert, text = ai.get_frame()
        times.append(time.time() - t0)
    total_time = time.time() - start
    ai.release()
    avg_ms = np.mean(times) * 1000
    fps = frames / total_time
    print(f"Current FocusAI: {fps:.2f} FPS | Avg frame cycle: {avg_ms:.2f} ms")

def benchmark_classroom_ai(frames=20):
    print("\n=== BENCHMARK 3: CURRENT ClassroomAI (Multi-Student) ===")
    sm = SessionManager()
    ai = ClassroomAI(sm, class_id=1, camera_index=0)
    # Warmup
    for _ in range(3):
        ai.get_frame()
    times = []
    start = time.time()
    for _ in range(frames):
        t0 = time.time()
        frame_bytes, alert, text = ai.get_frame()
        times.append(time.time() - t0)
    total_time = time.time() - start
    ai.release()
    avg_ms = np.mean(times) * 1000
    fps = frames / total_time
    print(f"Current ClassroomAI: {fps:.2f} FPS | Avg frame cycle: {avg_ms:.2f} ms")

if __name__ == "__main__":
    benchmark_raw_camera(40)
    benchmark_focus_ai(30)
    benchmark_classroom_ai(20)
