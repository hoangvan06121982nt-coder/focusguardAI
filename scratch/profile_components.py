import sys, os
sys.path.insert(0, os.path.abspath("."))
import time
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from ultralytics import YOLO
from face_recognition import FaceRecognizer

def profile():
    print("=== PROFILING INDIVIDUAL AI COMPONENTS ===")
    
    # Generate test frame 640x480 (typical camera frame)
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # 1. YOLOv8n
    print("[1] Loading YOLOv8n...")
    model = YOLO("yolov8n.pt")
    # Warmup
    for _ in range(3):
        model(frame, classes=[0, 67], verbose=False)
    t0 = time.time()
    n = 20
    for _ in range(n):
        model(frame, classes=[0, 67], verbose=False)
    yolo_time = (time.time() - t0) / n * 1000
    print(f"YOLOv8n (classes=[0, 67]): {yolo_time:.2f} ms")
    
    # 2. YOLO track (ByteTrack)
    for _ in range(3):
        model.track(source=frame, persist=True, tracker="bytetrack.yaml", classes=[0], verbose=False)
    t0 = time.time()
    for _ in range(n):
        model.track(source=frame, persist=True, tracker="bytetrack.yaml", classes=[0], verbose=False)
    track_time = (time.time() - t0) / n * 1000
    print(f"YOLO ByteTrack (classes=[0]): {track_time:.2f} ms")

    # 3. MediaPipe Face Landmarker (Full Frame)
    print("[2] Loading MediaPipe...")
    base_options = python.BaseOptions(model_asset_path='face_landmarker.task')
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=True,
        num_faces=5
    )
    detector = vision.FaceLandmarker.create_from_options(options)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    for _ in range(3):
        detector.detect(mp_image)
    t0 = time.time()
    for _ in range(n):
        detector.detect(mp_image)
    mp_full_time = (time.time() - t0) / n * 1000
    print(f"MediaPipe Full Frame (num_faces=5): {mp_full_time:.2f} ms")
    
    # 4. MediaPipe Face Landmarker (Face Crop 160x160)
    crop = rgb_frame[100:260, 200:360].copy()
    mp_crop_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=crop)
    t0 = time.time()
    for _ in range(n):
        detector.detect(mp_crop_image)
    mp_crop_time = (time.time() - t0) / n * 1000
    print(f"MediaPipe Face Crop (160x160, num_faces=1): {mp_crop_time:.2f} ms")

    # 5. InsightFace full frame vs crop
    print("[3] Loading InsightFace...")
    fr = FaceRecognizer()
    for _ in range(2):
        fr.app.get(frame)
    t0 = time.time()
    n_fr = 10
    for _ in range(n_fr):
        fr.app.get(frame)
    insight_full_time = (time.time() - t0) / n_fr * 1000
    print(f"InsightFace FULL FRAME (640x480): {insight_full_time:.2f} ms")
    
    # InsightFace crop (160x160)
    face_bgr_crop = frame[100:260, 200:360].copy()
    t0 = time.time()
    for _ in range(n_fr):
        fr.app.get(face_bgr_crop)
    insight_crop_time = (time.time() - t0) / n_fr * 1000
    print(f"InsightFace CROP (160x160): {insight_crop_time:.2f} ms")

    # 6. JPEG Encoding
    t0 = time.time()
    for _ in range(n):
        cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
    jpeg_time = (time.time() - t0) / n * 1000
    print(f"cv2.imencode JPEG (Quality 75): {jpeg_time:.2f} ms")

if __name__ == "__main__":
    profile()
