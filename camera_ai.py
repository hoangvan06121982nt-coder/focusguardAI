import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
import math
import time
from ultralytics import YOLO

class FocusAI:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        
        self.yolo_model = YOLO("yolov8n.pt")
        
        # Initialize MediaPipe Face Landmarker
        base_options = python.BaseOptions(model_asset_path='face_landmarker.task')
        options = vision.FaceLandmarkerOptions(base_options=base_options,
                                               output_face_blendshapes=False,
                                               output_facial_transformation_matrixes=True,
                                               num_faces=5)
        self.detector = vision.FaceLandmarker.create_from_options(options)
        
        self.cap = cv2.VideoCapture(0)
        
        # macOS AVFoundation needs time to warm up — discard initial empty frames
        print("[CAMERA] Warming up camera...")
        for _ in range(30):
            ret, _ = self.cap.read()
            if ret:
                print("[CAMERA] Camera ready.")
                break
            time.sleep(0.1)
        else:
            print("[CAMERA] Warning: camera warm-up did not produce a valid frame.")
        
        self.looking_away_start = None
        self.drowsy_start = None
        
        custom_settings = getattr(self.session_manager, 'settings', {})
        self.EAR_THRESHOLD = custom_settings.get('ear_threshold', 0.22)
        self.DROWSY_TIME_THRESH = custom_settings.get('drowsy_threshold', 1.5)
        self.DISTRACTION_TIME_THRESH = custom_settings.get('distraction_threshold', 2.0)
        self.current_state = "TAP TRUNG"
        
    def calculate_ear(self, landmarks, eye_indices):
        def distance(p1, p2):
            return math.dist([p1.x, p1.y], [p2.x, p2.y])
            
        v1 = distance(landmarks[eye_indices[1]], landmarks[eye_indices[5]])
        v2 = distance(landmarks[eye_indices[2]], landmarks[eye_indices[4]])
        h = distance(landmarks[eye_indices[0]], landmarks[eye_indices[3]])
        
        if h == 0: return 0
        return (v1 + v2) / (2.0 * h)

    def get_frame(self):
        if not self.cap.isOpened():
            self.cap.open(0)
            
        success, frame = self.cap.read()
        if not success:
            self.cap.release()
            self.cap.open(0)
            success, frame = self.cap.read()
            
        if not success:
            # Reset timers so stale state doesn't carry over when camera recovers
            self.looking_away_start = None
            self.drowsy_start = None
            # Create a dummy frame to avoid infinite loop in app.py
            dummy = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(dummy, "CAMERA KHONG KHA DUNG", (130, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            ret, buffer = cv2.imencode('.jpg', dummy)
            time.sleep(0.5) # prevent burning CPU
            return buffer.tobytes(), False, "Không có Camera"
            
        frame = cv2.flip(frame, 1)
        h, w, c = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        results = self.yolo_model(rgb_frame, classes=[0, 67], verbose=False)
        phone_detected = False
        person_count = 0
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                if cls_id == 67:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(frame, "PHAT HIEN DIEN THOAI", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    phone_detected = True
                elif cls_id == 0:
                    person_count += 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 1)
        
        # MediaPipe Tasks API
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        detection_result = self.detector.detect(mp_image)
        
        drowsy = False
        distracted = False
        multiple_people_detected = False
        status_text = "TAP TRUNG"
        color = (0, 255, 0)
        
        num_faces_detected = len(detection_result.face_landmarks) if detection_result.face_landmarks else 0
        if num_faces_detected >= 2 or person_count >= 2:
            multiple_people_detected = True
            
        if detection_result.face_landmarks:
            face_landmarks = detection_result.face_landmarks[0]
            matrix = detection_result.facial_transformation_matrixes[0]
            
            # EAR calculation
            left_eye_indices = [362, 385, 387, 263, 373, 380]
            right_eye_indices = [33, 160, 158, 133, 153, 144]
            
            left_ear = self.calculate_ear(face_landmarks, left_eye_indices)
            right_ear = self.calculate_ear(face_landmarks, right_eye_indices)
            avg_ear = (left_ear + right_ear) / 2.0
            
            if avg_ear < self.EAR_THRESHOLD:
                if self.drowsy_start is None:
                    self.drowsy_start = time.time()
                elif time.time() - self.drowsy_start > self.DROWSY_TIME_THRESH:
                    drowsy = True
            else:
                self.drowsy_start = None
            
            # Head Pose from transformation matrix
            rmat = matrix[0:3, 0:3]
            angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
            pitch, yaw, roll = angles[0], angles[1], angles[2]
            
            if yaw < -20 or yaw > 20 or pitch < -20 or pitch > 20:
                if self.looking_away_start is None:
                    self.looking_away_start = time.time()
                elif time.time() - self.looking_away_start > self.DISTRACTION_TIME_THRESH:
                    distracted = True
            else:
                self.looking_away_start = None
                
            # Draw Viewfinder Bounding Box for the first face
            x_min, y_min = w, h
            x_max, y_max = 0, 0
            for lm in face_landmarks:
                x, y = int(lm.x * w), int(lm.y * h)
                if x < x_min: x_min = x
                if x > x_max: x_max = x
                if y < y_min: y_min = y
                if y > y_max: y_max = y
                
            # Add padding
            padding = 20
            x_min = max(0, x_min - padding)
            y_min = max(0, y_min - padding)
            x_max = min(w, x_max + padding)
            y_max = min(h, y_max + padding)
            
            # Determine color based on state
            if multiple_people_detected:
                box_color = (0, 0, 255) # Red
            elif phone_detected or drowsy:
                box_color = (0, 0, 255) # Red
            elif distracted:
                box_color = (0, 165, 255) # Orange
            else:
                box_color = (255, 210, 0) # Cyan (Light Blue)
                
            length = 30
            thickness = 3
            # Draw corners
            cv2.line(frame, (x_min, y_min), (x_min + length, y_min), box_color, thickness)
            cv2.line(frame, (x_min, y_min), (x_min, y_min + length), box_color, thickness)
            
            cv2.line(frame, (x_max, y_min), (x_max - length, y_min), box_color, thickness)
            cv2.line(frame, (x_max, y_min), (x_max, y_min + length), box_color, thickness)
            
            cv2.line(frame, (x_min, y_max), (x_min + length, y_max), box_color, thickness)
            cv2.line(frame, (x_min, y_max), (x_min, y_max - length), box_color, thickness)
            
            cv2.line(frame, (x_max, y_max), (x_max - length, y_max), box_color, thickness)
            cv2.line(frame, (x_max, y_max), (x_max, y_max - length), box_color, thickness)
            
            # Text on top
            if multiple_people_detected:
                status_text = "PHAT HIEN NHIEU NGUOI"
                cv2.putText(frame, "CANH BAO: CO 2 NGUOI TRO LEN", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            elif phone_detected:
                status_text = "DUNG DIEN THOAI"
            elif drowsy:
                status_text = "BUON NGU"
            elif distracted:
                status_text = "NGOANH MAT DI"
                
            color = box_color
        else:
            if person_count >= 2:
                multiple_people_detected = True
                status_text = "PHAT HIEN NHIEU NGUOI"
                color = (0, 0, 255)
                cv2.putText(frame, "CANH BAO: CO 2 NGUOI TRO LEN", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                if self.looking_away_start is None:
                    self.looking_away_start = time.time()
                elif time.time() - self.looking_away_start > self.DISTRACTION_TIME_THRESH:
                    distracted = True
                    status_text = "KHONG THAY KHUON MAT"
                    color = (0, 165, 255)
                
        if self.session_manager.is_active:
            self.session_manager.record_history(status_text)
            
            if multiple_people_detected:
                self.session_manager.update_score(2.0, "Phát hiện nhiều người")
            elif phone_detected:
                self.session_manager.update_score(1.5, "Dùng điện thoại")
            elif drowsy:
                self.session_manager.update_score(1.0, "Buồn ngủ / Ngủ gật")
            elif distracted:
                self.session_manager.update_score(0.5, "Ngoảnh mặt đi")
                
        self.current_state = status_text
        ret, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes(), status_text != "TAP TRUNG", status_text
        
    def release(self):
        self.cap.release()
