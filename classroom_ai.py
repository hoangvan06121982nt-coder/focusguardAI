import cv2
import time
import json
import numpy as np
import threading
from datetime import datetime
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from tracker import PersonTracker
from face_recognition import FaceRecognizer
from seating_manager import SeatingManager

class ClassroomAI:
    def __init__(self, session_manager, class_id=1, camera_index=0):
        self.session_manager = session_manager
        self.class_id = int(class_id)
        
        # Load sub-modules
        self.tracker = PersonTracker()
        self.face_recognizer = FaceRecognizer()
        self.seating_manager = SeatingManager(rows=7, cols=4)
        
        # Initialize MediaPipe Face Landmarker for cropped faces
        base_options = python.BaseOptions(model_asset_path='face_landmarker.task')
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=True,
            num_faces=1 # only 1 face per crop
        )
        self.detector = vision.FaceLandmarker.create_from_options(options)
        
        # Open camera
        self.cap = cv2.VideoCapture(camera_index)
        print(f"[CLASSROOM AI] Opening camera {camera_index}...")
        for _ in range(15):
            ret, _ = self.cap.read()
            if ret:
                break
            time.sleep(0.1)
            
        # Get active class details
        self.known_students = self.session_manager.repo.get_student_embeddings_by_class(self.class_id)
        print(f"[CLASSROOM AI] Loaded {len(self.known_students)} students with face embeddings for Class ID {self.class_id}")
        
        # Real-time state cache
        # track_id -> student_id
        self.track_to_student = {}
        # track_id -> last face recognition timestamp
        self.last_recognition_time = {}
        # track_id -> last MediaPipe landmark timestamp
        self.last_landmarked_time = {}
        
        # student_name -> focus stats state
        self.student_states = {}
        # track_id -> previous frame EAR/headpose metrics
        self.last_metrics = {}
        
        # For attendance timing
        self.class_start_time = self.session_manager.offline_class_start_time or time.time()
        
        # Initialize all mock student records as offline by default
        for name, student in self.session_manager.mock_students.items():
            if student.get("class_id") == self.class_id:
                student["online"] = False
                student["state"] = "Offline"
                student["focus_score"] = 0
                student["attendance"] = "Vắng mặt"
                student["checkin_time"] = "—"
                student["seat_leaving_count"] = 0
                student["seat_leaving_duration"] = 0
                
        # Set phone warning config
        self.yolo_phone_model = self.tracker.model # share YOLO model weight
        self.EAR_THRESHOLD = 0.22
        
    def calculate_ear(self, landmarks, eye_indices):
        import math
        def distance(p1, p2):
            return math.dist([p1.x, p1.y], [p2.x, p2.y])
            
        v1 = distance(landmarks[eye_indices[1]], landmarks[eye_indices[5]])
        v2 = distance(landmarks[eye_indices[2]], landmarks[eye_indices[4]])
        h = distance(landmarks[eye_indices[0]], landmarks[eye_indices[3]])
        
        if h == 0: return 0
        return (v1 + v2) / (2.0 * h)

    def release(self):
        if self.cap.isOpened():
            self.cap.release()
        print("[CLASSROOM AI] Camera released.")

    def get_frame(self):
        if not self.cap.isOpened():
            self.cap.open(0)
            
        success, frame = self.cap.read()
        if not success:
            dummy = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(dummy, "CLASSROOM CAMERA OFFLINE", (120, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            ret, buffer = cv2.imencode('.jpg', dummy)
            return buffer.tobytes(), False, "Không có Camera"
            
        # Draw grid visualization guide on raw frame (dark overlays)
        h, w, c = frame.shape
        overlay = frame.copy()
        
        # Columns overlay
        for c_idx in range(1, 4):
            x_line = int(w * c_idx / 4)
            cv2.line(overlay, (x_line, 0), (x_line, h), (255, 255, 255), 1)
        # Rows overlay
        for r_idx in range(1, 7):
            y_line = int(h * r_idx / 7)
            cv2.line(overlay, (0, y_line), (w, y_line), (255, 255, 255), 1)
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
        
        # 1. Run YOLOv8 + ByteTrack tracking
        tracked_persons = self.tracker.track(frame)
        
        # 2. Seating Assignment
        seat_assignments = self.seating_manager.assign_seats(tracked_persons, w, h)
        
        now = time.time()
        active_student_ids = set()
        
        # Gather phone detections in full frame to check if any phone overlaps with a student box
        phone_results = self.yolo_phone_model(frame, classes=[67], verbose=False)
        phones = []
        for r in phone_results:
            for box in r.boxes:
                px1, py1, px2, py2 = map(int, box.xyxy[0].tolist())
                phones.append([px1, py1, px2, py2])

        # Run InsightFace face detection and extraction on the full frame
        faces = []
        try:
            faces = self.face_recognizer.app.get(frame)
        except Exception as fe:
            print(f"[CLASSROOM AI] Face detection error: {fe}")

        # Process each tracked person
        for p in tracked_persons:
            track_id = p['track_id']
            px1, py1, px2, py2 = p['bbox']
            
            # Find the best matching face for this person (closest to their head area)
            best_face = None
            best_dist = float('inf')
            
            p_head_xc = (px1 + px2) / 2.0
            p_head_yc = py1 + (py2 - py1) * 0.15
            
            for face in faces:
                fx1, fy1, fx2, fy2 = map(int, face.bbox)
                f_xc = (fx1 + fx2) / 2.0
                f_yc = (fy1 + fy2) / 2.0
                
                # Check if face center falls inside the person bounding box
                if px1 <= f_xc <= px2 and py1 <= f_yc <= py2:
                    dist = np.hypot(f_xc - p_head_xc, f_yc - p_head_yc)
                    if dist < best_dist:
                        best_dist = dist
                        best_face = face
            
            student_id = self.track_to_student.get(track_id)
            # Perform face recognition if not cached or every 8 seconds to verify
            should_recognize = (student_id is None) or (now - self.last_recognition_time.get(track_id, 0) > 8.0)
            
            if should_recognize and best_face is not None:
                self.last_recognition_time[track_id] = now
                emb = np.array(best_face.embedding)
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                    
                best_id = None
                best_score = 0.0
                
                for s in self.known_students:
                    s_emb = np.array(s['embedding'])
                    s_norm = np.linalg.norm(s_emb)
                    if s_norm > 0:
                        s_emb = s_emb / s_norm
                    sim = np.dot(emb, s_emb)
                    # Proximity angle matching threshold (0.38)
                    if sim > 0.38 and sim > best_score:
                        best_score = sim
                        best_id = s['student_id']
                        
                if best_id is not None:
                    self.track_to_student[track_id] = best_id
                    student_id = best_id
                    print(f"[CLASSROOM AI] Recognized Track {track_id} as Student {student_id} (conf: {best_score:.2f})")
            
            if student_id is None:
                # Unrecognized student label
                if best_face is not None:
                    fx1, fy1, fx2, fy2 = map(int, best_face.bbox)
                    cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), (128, 128, 128), 2)
                    cv2.putText(frame, f"Track {track_id} (Unrecognized)", (fx1, fy1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
                else:
                    cv2.rectangle(frame, (px1, py1), (px2, py2), (128, 128, 128), 2)
                    cv2.putText(frame, f"Track {track_id} (Unrecognized)", (px1, py1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
                continue
                
            active_student_ids.add(student_id)
            
            # Get student name
            student_meta = next((s for s in self.known_students if s['student_id'] == student_id), None)
            if not student_meta:
                continue
            student_name = student_meta['full_name']
            
            # Get seat coordinates assigned to this track
            s_row, s_col = seat_assignments.get(track_id, (0, 0))
            
            # Initialize or retrieve student state
            if student_name not in self.student_states:
                self.student_states[student_name] = {
                    "focus_score": 100.0,
                    "distractions": 0,
                    "state": "Focused",
                    "attendance": "Có mặt",
                    "checkin_time": datetime.now().strftime("%H:%M:%S"),
                    "seat_row": s_row,
                    "seat_col": s_col,
                    "focus_history": [100],
                    "phone_streak": 0,
                    "sleepy_streak": 0,
                    "distracted_streak": 0
                }
                
                # Check-in delay logic (Late or Present)
                elapsed_class = now - self.class_start_time
                if elapsed_class > 300: # 5 minutes
                    self.student_states[student_name]["attendance"] = "Đi muộn"
                else:
                    self.student_states[student_name]["attendance"] = "Có mặt"
                
                # Push log to Teacher Dashboard
                log_msg = f"{student_name} điểm danh thành công ({self.student_states[student_name]['attendance']})"
                self.session_manager.offline_activity_logs.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "message": log_msg,
                    "type": "info"
                })
            
            state_data = self.student_states[student_name]
            state_data["seat_row"] = s_row
            state_data["seat_col"] = s_col
            
            # Check phone violation inside person box
            has_phone = False
            for pbox in phones:
                # Check intersection of phone box with student body box
                ix1 = max(px1, pbox[0])
                iy1 = max(py1, pbox[1])
                ix2 = min(px2, pbox[2])
                iy2 = min(py2, pbox[3])
                if ix1 < ix2 and iy1 < iy2:
                    has_phone = True
                    break
                    
            # MediaPipe Landmarker throttling: run only once every 300ms per track
            drowsy = False
            distracted = False
            
            face_crop = None
            if best_face is not None:
                fx1, fy1, fx2, fy2 = map(int, best_face.bbox)
                fw = fx2 - fx1
                fh = fy2 - fy1
                m_x1 = max(0, fx1 - fw // 4)
                m_y1 = max(0, fy1 - fh // 4)
                m_x2 = min(w, fx2 + fw // 4)
                m_y2 = min(h, fy2 + fh // 4)
                face_crop = frame[m_y1:m_y2, m_x1:m_x2]
                
            should_run_mp = (now - self.last_landmarked_time.get(track_id, 0) > 0.3)
            if should_run_mp and face_crop is not None and face_crop.size > 0:
                self.last_landmarked_time[track_id] = now
                rgb_face = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_face)
                det_res = self.detector.detect(mp_image)
                
                if det_res.face_landmarks:
                    face_landmarks = det_res.face_landmarks[0]
                    matrix = det_res.facial_transformation_matrixes[0]
                    
                    # EAR calculation
                    left_eye_indices = [362, 385, 387, 263, 373, 380]
                    right_eye_indices = [33, 160, 158, 133, 153, 144]
                    left_ear = self.calculate_ear(face_landmarks, left_eye_indices)
                    right_ear = self.calculate_ear(face_landmarks, right_eye_indices)
                    avg_ear = (left_ear + right_ear) / 2.0
                    
                    if avg_ear < self.EAR_THRESHOLD:
                        drowsy = True
                        
                    # Head pose angles
                    rmat = matrix[0:3, 0:3]
                    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
                    pitch, yaw, roll = angles[0], angles[1], angles[2]
                    if yaw < -20 or yaw > 20 or pitch < -20 or pitch > 20:
                        distracted = True
                        
                    self.last_metrics[track_id] = (drowsy, distracted)
            else:
                # Reuse last computed metrics
                drowsy, distracted = self.last_metrics.get(track_id, (False, False))
                
            # Compute current state
            old_state = state_data["state"]
            if has_phone:
                state_data["phone_streak"] += 1
                if state_data["phone_streak"] >= 3:
                    state_data["state"] = "Phone"
            else:
                state_data["phone_streak"] = 0
                
            if drowsy and not has_phone:
                state_data["sleepy_streak"] += 1
                if state_data["sleepy_streak"] >= 3:
                    state_data["state"] = "Sleepy"
            else:
                state_data["sleepy_streak"] = 0
                
            if distracted and not drowsy and not has_phone:
                state_data["distracted_streak"] += 1
                if state_data["distracted_streak"] >= 3:
                    state_data["state"] = "Distracted"
            else:
                state_data["distracted_streak"] = 0
                
            if not has_phone and not drowsy and not distracted:
                state_data["state"] = "Focused"
                
            current_state = state_data["state"]
            
            # Penalties and Recovery
            if current_state == "Phone":
                state_data["focus_score"] = max(0, state_data["focus_score"] - 0.2)
            elif current_state == "Sleepy":
                state_data["focus_score"] = max(0, state_data["focus_score"] - 0.3)
            elif current_state == "Distracted":
                state_data["focus_score"] = max(0, state_data["focus_score"] - 0.1)
            else:
                state_data["focus_score"] = min(100.0, state_data["focus_score"] + 0.1)
                
            # Log changes
            if old_state != current_state:
                log_msg = ""
                log_type = "info"
                if current_state == "Focused":
                    log_msg = f"{student_name} đã tập trung trở lại"
                elif current_state == "Sleepy":
                    log_msg = f"{student_name} (Ghế H{s_row+1}-C{s_col+1}) ngủ gật"
                    log_type = "warning"
                    state_data["distractions"] += 1
                elif current_state == "Distracted":
                    log_msg = f"{student_name} ngoảnh mặt đi, không nhìn bảng"
                    log_type = "danger"
                    state_data["distractions"] += 1
                elif current_state == "Phone":
                    log_msg = f"{student_name} đang lén sử dụng điện thoại"
                    log_type = "danger"
                    state_data["distractions"] += 1
                    
                if log_msg:
                    self.session_manager.offline_activity_logs.append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "message": log_msg,
                        "type": log_type
                    })
                    if len(self.session_manager.offline_activity_logs) > 30:
                        self.session_manager.offline_activity_logs.pop(0)

            # Draw visual boxes and overlays on classroom stream
            color_map = {
                "Focused": (0, 255, 0),    # green
                "Sleepy": (0, 165, 255),  # orange
                "Distracted": (0, 255, 255), # yellow
                "Phone": (0, 0, 255)       # red
            }
            box_color = color_map.get(current_state, (0, 255, 0))
            if best_face is not None:
                fx1, fy1, fx2, fy2 = map(int, best_face.bbox)
                cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), box_color, 2)
                label = f"{student_name} ({int(state_data['focus_score'])}%)"
                cv2.putText(frame, label, (fx1, fy1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
            else:
                cv2.rectangle(frame, (px1, py1), (px2, py2), box_color, 2)
                label = f"{student_name} ({int(state_data['focus_score'])}%)"
                cv2.putText(frame, label, (px1, py1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
            
            # Sync back to session_manager mock_students data structure so Teacher Dashboard reads it
            if student_name in self.session_manager.mock_students:
                student_record = self.session_manager.mock_students[student_name]
                student_record["online"] = True
                student_record["state"] = current_state
                student_record["focus_score"] = int(state_data["focus_score"])
                student_record["distractions"] = state_data["distractions"]
                student_record["attendance"] = state_data["attendance"]
                student_record["checkin_time"] = state_data["checkin_time"]
                student_record["seat_row"] = s_row
                student_record["seat_col"] = s_col

        # 3. Handle Seat Leaving & Offline students
        for name, student in self.session_manager.mock_students.items():
            if student.get("class_id") == self.class_id:
                # Find matching user record
                student_meta = next((s for s in self.known_students if s['full_name'] == name), None)
                if not student_meta:
                    continue
                s_id = student_meta['student_id']
                
                # If they were active but now missing, increment seat leaving duration/count
                if s_id not in active_student_ids:
                    student["online"] = False
                    
                    if name in self.student_states:
                        state_data = self.student_states[name]
                        # Student left their seat!
                        if student["state"] != "Absent":
                            student["state"] = "Absent"
                            student["seat_leaving_count"] += 1
                            log_msg = f"{name} đã rời khỏi vị trí ngồi"
                            self.session_manager.offline_activity_logs.append({
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "message": log_msg,
                                "type": "warning"
                            })
                        
                        student["seat_leaving_duration"] += 1 # Accumulate duration in seconds
                        # Focus score drops quickly when absent
                        state_data["focus_score"] = max(0, state_data["focus_score"] - 0.5)
                        student["focus_score"] = int(state_data["focus_score"])
                    else:
                        # Never arrived (Vắng mặt)
                        student["state"] = "Offline"
                        student["attendance"] = "Vắng mặt"
                        student["focus_score"] = 0
                        
        ret, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes(), False, "OK"
