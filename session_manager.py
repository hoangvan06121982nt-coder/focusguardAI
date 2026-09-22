import json
import time
from datetime import datetime
from repository import get_repository

class SessionManager:
    def __init__(self, db_path="focusguard.db"):
        self.db_path = db_path
        self.is_active = False
        self.start_time = None
        self.focus_score = 100
        self.distractions = 0
        self.history = []
        self.last_history_update = 0
        self._last_penalty_time = 0       # rate-limit score deduction
        self._last_distraction_time = 0   # rate-limit distraction counter
        self.current_session_id = None
        self.current_class_session_id = None
        
        # Risk Event Trackers
        self.phone_events = 0
        self.drowsy_events = 0
        self.looking_away_events = 0
        self.negative_emotion_ticks = 0
        
        # Risk Event Timestamp Queues (Last 10 minutes)
        self.phone_event_times = []
        self.drowsy_event_times = []
        self.looking_away_event_times = []
        self.negative_emotion_times = []
        self.emotion_history_list = []
        
        # Classroom Session States (Online)
        self.class_session_active = False
        self.class_session_start_time = None
        
        # Classroom Session States (Offline)
        self.offline_class_active = False
        self.offline_class_start_time = None
        self.offline_activity_logs = []
        
        self.activity_logs = []
        self.mock_students = {}
        self.current_student_name = None  # Set when a student connects via WebSocket
        
        self.repo = get_repository()
        self.repo.init_db()
        self.init_mock_students()
        
    def start_session(self, user_id=None, subject=None):
        self.is_active = True
        self.start_time = datetime.now()
        self.focus_score = 100
        self.distractions = 0
        self.history = []
        self.last_history_update = time.time()
        self._last_penalty_time = 0
        self._last_distraction_time = 0
        
        self.seat_leaving_count = 0
        self.seat_leaving_total_duration = 0
        self.seat_leaving_start_time = None
        self.looking_at_screen_seconds = 0
        self.total_gaze_seconds = 0
        
        # Reset event counters
        self.phone_events = 0
        self.drowsy_events = 0
        self.looking_away_events = 0
        self.negative_emotion_ticks = 0
        
        # Reset event timestamp queues
        self.phone_event_times = []
        self.drowsy_event_times = []
        self.looking_away_event_times = []
        self.negative_emotion_times = []
        self.emotion_history_list = []
        
        # Create session placeholder in DB
        start_time_str = self.start_time.strftime("%Y-%m-%d %H:%M:%S")
        self.current_session_id = self.repo.create_session(user_id, start_time_str, subject)
        
        # Mark attendance
        is_late = False
        if self.class_session_active and self.class_session_start_time:
            # More than 10 seconds is considered late for demo purposes
            if time.time() - self.class_session_start_time > 10.0:
                is_late = True
        
        self.attendance_status = "Đi muộn" if is_late else "Có mặt"
        if "Nguyễn Văn An" in self.mock_students:
            self.mock_students["Nguyễn Văn An"]["attendance"] = self.attendance_status
            self.mock_students["Nguyễn Văn An"]["online"] = True
            
        self.record_history("TAP TRUNG")
        
    def stop_session(self, user_id=None):
        if not self.is_active:
            return
        
        self.is_active = False
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        history_str = json.dumps(self.history)
        
        if self.current_session_id is not None:
            self.repo.update_session(
                session_id=self.current_session_id,
                end_time=end_time_str,
                duration_seconds=int(duration),
                final_score=int(self.focus_score),
                total_distractions=self.distractions,
                history_json=history_str
            )
        
    def update_score(self, penalty, distraction_type=None):
        """Apply score penalty at most once per second (frame-rate independent).
        Count distraction events at most once per 20 seconds per event.

        Penalty values from camera_ai are designed as per-second rates:
          phone=1.5, drowsy=1.0, distracted=0.5
        With auto-recovery of +0.1/s the net rates are:
          phone ≈ -1.4/s, drowsy ≈ -0.9/s, distracted ≈ -0.4/s
        """
        if not self.is_active:
            return

        SCORE_INTERVAL    = 1.0   # apply score penalty at most once per second
        EVENT_COOLDOWN    = 20.0  # count as a new distraction event every 20 s
        now = time.time()

        if penalty > 0:
            # Rate-limited score deduction
            if now - self._last_penalty_time >= SCORE_INTERVAL:
                self._last_penalty_time = now
                self.focus_score = max(0, self.focus_score - penalty)
                print(f"[PENALTY] {distraction_type}: -{penalty:.1f} → score={self.focus_score:.1f}")

            # Count as a new distraction event
            if now - self._last_distraction_time >= EVENT_COOLDOWN:
                self._last_distraction_time = now
                self.distractions += 1
                print(f"[EVENT] {distraction_type} | distractions={self.distractions}")
                
                # Increment event type counters
                if distraction_type == "Dùng điện thoại":
                    self.phone_events = getattr(self, 'phone_events', 0) + 1
                    if not hasattr(self, 'phone_event_times'): self.phone_event_times = []
                    self.phone_event_times.append(now)
                elif distraction_type == "Buồn ngủ / Ngủ gật":
                    self.drowsy_events = getattr(self, 'drowsy_events', 0) + 1
                    if not hasattr(self, 'drowsy_event_times'): self.drowsy_event_times = []
                    self.drowsy_event_times.append(now)
                elif distraction_type == "Ngoảnh mặt đi":
                    self.looking_away_events = getattr(self, 'looking_away_events', 0) + 1
                    if not hasattr(self, 'looking_away_event_times'): self.looking_away_event_times = []
                    self.looking_away_event_times.append(now)
                
                # Log event in DB if active session exists
                if self.current_session_id is not None:
                    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.repo.create_focus_event(
                        session_id=self.current_session_id,
                        event_type=distraction_type or "DISTRACTION",
                        timestamp=timestamp_str
                    )
        
    def record_history(self, state_val=None):
        if not self.is_active:
            return
            
        current_time = time.time()
        # Record history once every second
        if current_time - self.last_history_update >= 1.0:
            if state_val is None:
                state_val = getattr(self, 'current_state', 'TAP TRUNG')
            self.current_state = state_val
            
            # Map state to emotion
            if state_val == 'TAP TRUNG':
                if self.focus_score > 92 and (int(current_time) % 10 in [0, 1, 2]):
                    emo = "Happy"
                else:
                    emo = "Neutral"
            elif state_val == 'BUON NGU':
                emo = "Tired"
            elif state_val in ['NGOANH MAT DI', 'KHONG THAY KHUON MAT', 'DUNG DIEN THOAI']:
                emo = "Stressed"
            else:
                emo = "Neutral"

            self.history.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "score": int(self.focus_score),
                "emotion": emo
            })
            
            if not hasattr(self, 'emotion_history_list') or self.emotion_history_list is None:
                self.emotion_history_list = []
            self.emotion_history_list.append(emo)
            if len(self.emotion_history_list) > 15:
                self.emotion_history_list.pop(0)

            dt = current_time - self.last_history_update
            self.last_history_update = current_time
            
            is_face_present = (state_val != 'KHONG THAY KHUON MAT')
            is_focused = (state_val == 'TAP TRUNG')
            
            if not hasattr(self, 'total_gaze_seconds') or self.total_gaze_seconds is None:
                self.total_gaze_seconds = 0
                self.looking_at_screen_seconds = 0
                self.seat_leaving_count = 0
                self.seat_leaving_total_duration = 0
                self.seat_leaving_start_time = None
                
            self.total_gaze_seconds += dt
            if is_focused:
                self.looking_at_screen_seconds += dt
                
            # Track negative emotions per second
            score = self.focus_score
            if not is_face_present:
                emotion_check = "Rời vị trí"
            elif score >= 85:
                emotion_check = "Bình thường"
            elif score >= 70:
                emotion_check = "Mệt mỏi"
            elif score >= 50:
                emotion_check = "Căng thẳng"
            else:
                emotion_check = "Mất tập trung"
                
            if emotion_check in ["Mệt mỏi", "Căng thẳng", "Mất tập trung"]:
                self.negative_emotion_ticks = getattr(self, 'negative_emotion_ticks', 0) + 1
                if not hasattr(self, 'negative_emotion_times'): self.negative_emotion_times = []
                self.negative_emotion_times.append(current_time)
                
            if not is_face_present:
                if self.seat_leaving_start_time is None:
                    self.seat_leaving_start_time = current_time
                    self.seat_leaving_count += 1
                    self.activity_logs.append({
                        "time": datetime.now().strftime("%I:%M %p"),
                        "message": f"{self.current_student_name or 'Nguyễn Văn An'} rời vị trí",
                        "type": "warning"
                    })
                else:
                    self.seat_leaving_total_duration += dt
            else:
                if self.seat_leaving_start_time is not None:
                    self.seat_leaving_start_time = None
                    self.activity_logs.append({
                        "time": datetime.now().strftime("%I:%M %p"),
                        "message": f"{self.current_student_name or 'Nguyễn Văn An'} đã quay lại vị trí",
                        "type": "info"
                    })
            
            # Auto-recover score slightly if no penalties (reward for focusing)
            if self.focus_score < 100:
                self.focus_score = min(100, self.focus_score + 0.1)
        
    def get_stats(self):
        elapsed = 0
        if self.is_active and self.start_time:
            elapsed = int((datetime.now() - self.start_time).total_seconds())
            
        sa_pct = 100
        if getattr(self, 'total_gaze_seconds', 0) > 0:
            sa_pct = int((getattr(self, 'looking_at_screen_seconds', 0) / self.total_gaze_seconds) * 100)
            
        # Determine emotion
        state = getattr(self, 'current_state', 'TAP TRUNG')
        if hasattr(self, 'emotion_history_list') and self.emotion_history_list:
            emotion = self.emotion_history_list[-1]
        else:
            if state == 'TAP TRUNG':
                emotion = "Neutral"
            elif state == 'BUON NGU':
                emotion = "Tired"
            elif state in ['NGOANH MAT DI', 'KHONG THAY KHUON MAT', 'DUNG DIEN THOAI']:
                emotion = "Stressed"
            else:
                emotion = "Neutral"
                
        emotion_icons = {"Happy": "😊", "Neutral": "😐", "Tired": "😴", "Stressed": "😰"}
        emotion_icon = emotion_icons.get(emotion, "😐")
        
        # Fluctuate confidence score smoothly using sine
        import math
        base_conf = {"Happy": 88, "Neutral": 90, "Tired": 85, "Stressed": 82}
        conf_calc = base_conf.get(emotion, 90) + int(3 * math.sin(time.time() / 10.0))
        emotion_confidence = max(60, min(99, conf_calc))
        
        emotion_history = getattr(self, 'emotion_history_list', [emotion])
        if not emotion_history:
            emotion_history = [emotion]
            
        # AI Predictions
        drowsy_risk = 5
        phone_risk = 5
        if state == 'BUON NGU':
            drowsy_risk = 95
        elif state == 'DUNG DIEN THOAI':
            phone_risk = 95
        elif self.distractions > 0:
            drowsy_risk = int(min(90, 5 + self.distractions * 10))
            phone_risk = int(min(90, 5 + self.distractions * 12))
            
        # Learning Risk Score: 40% Phone + 30% Drowsiness + 20% Looking Away + 10% Negative Emotion
        phone_ev = getattr(self, 'phone_events', 0)
        drowsy_ev = getattr(self, 'drowsy_events', 0)
        away_ev = getattr(self, 'looking_away_events', 0)
        neg_emo = getattr(self, 'negative_emotion_ticks', 0)

        phone_comp = min(100, phone_ev * 20) * 0.40
        drowsy_comp = min(100, drowsy_ev * 20) * 0.30
        away_comp = min(100, away_ev * 10) * 0.20
        emo_comp = min(100, neg_emo * 5) * 0.10

        learning_risk = int(phone_comp + drowsy_comp + away_comp + emo_comp)

        # Risk Level
        if learning_risk < 30:
            risk_level = "Low"
        elif learning_risk < 70:
            risk_level = "Medium"
        else:
            risk_level = "High"

        # Dynamic explainable reasons
        reasons = []
        reasons.append(f"{phone_ev} sự kiện dùng điện thoại")
        reasons.append(f"{drowsy_ev} sự kiện ngủ gật / buồn ngủ")
        reasons.append(f"{away_ev} sự kiện ngoảnh mặt đi")
        
        # Attention trend
        attention_trend = "Xu hướng tập trung ổn định"
        if len(self.history) >= 15:
            recent_scores = [h["score"] for h in self.history[-15:]]
            if recent_scores[0] - recent_scores[-1] > 10:
                attention_trend = "Độ tập trung giảm nhanh"
            elif recent_scores[-1] - recent_scores[0] > 10:
                attention_trend = "Độ tập trung cải thiện tốt"
        reasons.append(attention_trend)
        
        # Trend-Based Predictions (next 10 minutes)
        now = time.time()
        # Prune event times queues
        self.phone_event_times = [t for t in getattr(self, 'phone_event_times', []) if now - t <= 600]
        self.drowsy_event_times = [t for t in getattr(self, 'drowsy_event_times', []) if now - t <= 600]
        self.looking_away_event_times = [t for t in getattr(self, 'looking_away_event_times', []) if now - t <= 600]
        self.negative_emotion_times = [t for t in getattr(self, 'negative_emotion_times', []) if now - t <= 600]

        recent_phone = len(self.phone_event_times)
        recent_drowsy = len(self.drowsy_event_times)
        recent_away = len(self.looking_away_event_times)
        recent_neg_ticks = len(self.negative_emotion_times)

        # 1. Compute trend slope of focus_score in history (last 10 minutes)
        # Using a robust window-based comparison: average of last 30s vs prior 9.5m
        history_10m = self.history[-600:] if len(self.history) >= 2 else self.history
        trend_projection = 0.0
        if len(history_10m) >= 10:
            # last 30 seconds (or half if history is too short)
            recent_scores = [h["score"] for h in history_10m[-30:]]
            older_scores = [h["score"] for h in history_10m[:-30]]
            if not older_scores:
                half = len(history_10m) // 2
                recent_scores = [h["score"] for h in history_10m[half:]]
                older_scores = [h["score"] for h in history_10m[:half]]
            
            avg_recent = sum(recent_scores) / len(recent_scores) if recent_scores else 100.0
            avg_older = sum(older_scores) / len(older_scores) if older_scores else 100.0
            
            # project trend change over next 10 minutes (scaled and clamped)
            trend_projection = (avg_recent - avg_older) * 1.5
            trend_projection = max(-25.0, min(10.0, trend_projection))

        # 2. Predicted focus score
        phone_penalty = recent_phone * 8
        drowsy_penalty = recent_drowsy * 6
        away_penalty = recent_away * 4
        emotion_penalty = (recent_neg_ticks / 600.0) * 15

        predicted_focus = self.focus_score + trend_projection - phone_penalty - drowsy_penalty - away_penalty - emotion_penalty
        
        # Apply current state penalties
        if state == 'DUNG DIEN THOAI':
            predicted_focus -= 10
        elif state == 'BUON NGU':
            predicted_focus -= 8
        elif state in ['NGOANH MAT DI', 'KHONG THAY KHUON MAT']:
            predicted_focus -= 5

        predicted_score = max(10, min(100, int(predicted_focus)))

        # 3. Predicted drowsiness risk
        pred_drowsy_risk = 5 + (recent_drowsy * 25) + (recent_neg_ticks / 600.0 * 30)
        if state == 'BUON NGU':
            pred_drowsy_risk += 40
        predicted_drowsy_risk = max(5, min(95, int(pred_drowsy_risk)))

        # 4. Predicted phone risk
        pred_phone_risk = 5 + (recent_phone * 30) + (recent_away * 10)
        if state == 'DUNG DIEN THOAI':
            pred_phone_risk += 45
        predicted_phone_risk = max(5, min(95, int(pred_phone_risk)))
        
        # Dynamic AI Insight Generation
        ai_insight = "Độ tập trung xuất sắc được ghi nhận. Hãy tiếp tục cố gắng!"
        if self.is_active:
            if state == 'DUNG DIEN THOAI':
                ai_insight = "Vui lòng cất điện thoại để duy trì sự tập trung."
            elif state == 'BUON NGU':
                ai_insight = "Phát hiện buồn ngủ. Hãy nghỉ ngơi ngắn hoặc uống nước."
            elif learning_risk > 60:
                ai_insight = "Cảnh báo rủi ro học tập cao! Phát hiện nhiều hành vi xao nhãng."
            elif self.focus_score > 90 and elapsed > 90:
                ai_insight = "Độ tập trung của bạn đã duy trì trên 90% trong 15 phút qua."
            elif predicted_score < 75:
                ai_insight = "Dự báo tập trung cho thấy xu hướng giảm. Hãy tập trung lại nhé!"
            elif predicted_drowsy_risk < 15 and predicted_phone_risk < 15:
                ai_insight = "Nguy cơ buồn ngủ và sử dụng điện thoại vẫn ở mức rất thấp."
            elif len(self.history) >= 20:
                recent_scores = [h["score"] for h in self.history[-20:]]
                if recent_scores[-1] > recent_scores[0]:
                    ai_insight = "Xu hướng tập trung đang cải thiện so với các phiên học trước."
        else:
            ai_insight = "Hệ thống đã sẵn sàng giám sát. Bấm Bắt đầu học để bắt đầu."

        early_warning = False
        if len(self.history) >= 5:
            recent_scores = [h["score"] for h in self.history[-5:]]
            if all(recent_scores[i] >= recent_scores[i+1] for i in range(len(recent_scores)-1)) and recent_scores[0] > recent_scores[-1]:
                early_warning = True

        return {
            "is_active": self.is_active,
            "seconds_elapsed": elapsed,
            "focus_score": int(self.focus_score),
            "distractions": self.distractions,
            "seat_leaving_count": getattr(self, 'seat_leaving_count', 0),
            "seat_leaving_duration": int(getattr(self, 'seat_leaving_total_duration', 0)),
            "screen_attention_percent": sa_pct,
            "attendance": getattr(self, 'attendance_status', 'Có mặt'),
            "history": self.history[-60:],
            "current_emotion": emotion,
            "emotion_icon": emotion_icon,
            "emotion_confidence": emotion_confidence,
            "emotion_history": emotion_history,
            "drowsiness_risk": drowsy_risk,
            "phone_risk": phone_risk,
            "learning_risk": learning_risk,
            "learning_risk_level": risk_level,
            "learning_risk_reasons": reasons,
            "predicted_score": predicted_score,
            "predicted_drowsy_risk": predicted_drowsy_risk,
            "predicted_phone_risk": predicted_phone_risk,
            "prediction_explanation": "Dự báo được tạo từ phân tích xu hướng chú ý trong lịch sử.",
            "early_warning": early_warning,
            "ai_insight": ai_insight
        }

    def get_all_sessions(self):
        return self.repo.get_all_sessions()

    def get_latest_session(self):
        return self.repo.get_latest_session()

    # --- Seeding & Roles Management ---
    def seed_data(self):
        self.repo.seed_data()

    def get_users_list(self):
        return self.repo.get_users_list()

    def get_classes_list(self):
        return self.repo.get_classes_list()

    def create_class(self, class_name):
        return self.repo.create_class(class_name)

    def update_class(self, class_id, new_name):
        return self.repo.update_class(class_id, new_name)

    def delete_class(self, class_id):
        return self.repo.delete_class(class_id)

    def create_user(self, username, password, display_name, role, class_id):
        return self.repo.create_user(username, password, display_name, role, class_id)

    def update_user(self, user_id, username, password, display_name, role, class_id):
        return self.repo.update_user(user_id, username, password, display_name, role, class_id)

    def delete_user(self, user_id):
        return self.repo.delete_user(user_id)

    # --- Classroom sessions lifecycle ---
    def start_class_session(self, class_id):
        self.class_session_active = True
        self.class_session_start_time = time.time()
        self.class_session_id = class_id
        self.current_class_session_id = self.repo.create_class_session(class_id, self.class_session_start_time)

    def end_class_session(self):
        self.class_session_active = False
        if self.current_class_session_id is not None:
            self.repo.update_class_session(self.current_class_session_id, time.time())
        self.class_session_start_time = None
        self.current_class_session_id = None

    # --- Live Classroom Mock Drift Simulation ---
    def init_mock_students(self):
        # We define a standard set of 28 students (matching Mr. Sharma's classroom)
        names = [
            ("Nguyễn Văn An", "07", "hocsinh"), # Real student user
            ("Trần Thị Bình", "08", None),
            ("Lê Hoàng Giang", "09", None),
            ("Phạm Minh Hải", "10", None),
            ("Vũ Tiến Khoa", "11", None),
            ("Ngô Khánh Linh", "12", None),
            ("Hoàng Đức Minh", "13", None),
            ("Bùi Thị Ngọc", "14", None),
            ("Đỗ Minh Quân", "15", None),
            ("Phan Thanh Sơn", "16", None),
            ("Dương Tuấn Tú", "17", None),
            ("Lâm Khánh Vân", "18", None),
            ("Trịnh Xuân Việt", "19", None),
            ("Đặng Thu Trang", "20", None),
            ("Mai Thúy Quỳnh", "21", None),
            ("Đỗ Tuấn Anh", "22", None),
            ("Hoàng Mỹ Linh", "23", None),
            ("Phan Huy Hoàng", "24", None),
            ("Trần Lan Anh", "25", None),
            ("Nguyễn Minh Triết", "26", None),
            ("Phạm Ngọc Diệp", "27", None),
            ("Nguyễn Thế Anh", "28", None),
            ("Lê Quang Huy", "29", None),
            ("Nguyễn Phương Thảo", "30", None),
            ("Phan Anh Tuấn", "31", None),
            ("Bùi Hoàng Nam", "32", None),
            ("Vũ Trà My", "33", None),
            ("Nguyễn Việt Hoàng", "34", None)
        ]
        
        # Populate mock_students dict
        import random
        for idx, (name, roll, username) in enumerate(names):
            is_active_student = (username is not None)
            
            # Seed starting metrics
            base_score = random.randint(75, 95) if name != "Lê Hoàng Giang" else 32
            base_state = "Focused" if name != "Lê Hoàng Giang" else "Distracted"
            if name == "Phạm Minh Hải" or name == "Bùi Thị Ngọc":
                base_score = 45 if name == "Phạm Minh Hải" else 41
                base_state = "Sleepy"
                
            r_val = int(roll) if roll.isdigit() else 7
            if r_val <= 15:
                c_id = 1
            elif r_val <= 25:
                c_id = 2
            else:
                c_id = 3
                
            self.mock_students[name] = {
                "name": name,
                "roll": roll,
                "username": username,
                "focus_score": base_score,
                "state": base_state,
                "distractions": random.randint(0, 3) if base_state != "Focused" else 0,
                "warnings": random.randint(0, 4),
                "study_time": "00:45:00",
                "is_active_student": is_active_student,
                "online": True if (is_active_student or random.random() > 0.15) else False,
                "class_id": c_id,
                "attendance": "Có mặt" if (is_active_student or random.random() > 0.2) else "Vắng mặt",
                "seat_leaving_count": random.randint(0, 2) if random.random() > 0.8 else 0,
                "seat_leaving_duration": random.randint(15, 120) if random.random() > 0.8 else 0,
                "screen_attention_percent": random.randint(75, 98),
                "seat_row": idx // 4,
                "seat_col": idx % 4,
                # Historical data for mini charts (last 10 updates)
                "focus_history": [random.randint(65, 98) for _ in range(10)]
            }
            
        # Add initial logs
        self.activity_logs = [
            {"time": datetime.now().strftime("%I:%M %p"), "message": "Hệ thống giám sát bắt đầu hoạt động", "type": "info"}
        ]

    def sync_students_from_db(self):
        try:
            rows = self.repo.get_students_by_role()
        except Exception as e:
            print(f"Error syncing students: {e}")
            rows = []

        import random
        # Get existing usernames to avoid duplicates
        existing_usernames = {s["username"] for s in self.mock_students.values() if s.get("username")}

        for username, display_name, class_id in rows:
            if username not in existing_usernames:
                is_active_student = (username == 'hocsinh')
                
                # Seed starting metrics
                base_score = random.randint(75, 95) if username != "rohanverma" else 32
                base_state = "Focused" if username != "rohanverma" else "Distracted"
                if username == "ananyapatel" or username == "ishitayadav":
                    base_score = 45 if username == "ananyapatel" else 41
                    base_state = "Sleepy"
                    
                self.mock_students[display_name] = {
                    "name": display_name,
                    "roll": "07" if is_active_student else str(random.randint(10, 99)),
                    "username": username,
                    "focus_score": base_score,
                    "state": base_state,
                    "distractions": random.randint(0, 3) if base_state != "Focused" else 0,
                    "warnings": random.randint(0, 4),
                    "study_time": "00:45:00",
                    "is_active_student": is_active_student,
                    "online": True if (is_active_student or random.random() > 0.1) else False,
                    "focus_history": [random.randint(65, 98) for _ in range(10)],
                    "class_id": class_id,
                    "attendance": "Có mặt" if (is_active_student or random.random() > 0.2) else "Vắng mặt",
                    "seat_leaving_count": random.randint(0, 2) if random.random() > 0.8 else 0,
                    "seat_leaving_duration": random.randint(15, 120) if random.random() > 0.8 else 0,
                    "screen_attention_percent": random.randint(75, 98)
                }
            else:
                # Update class_id and display_name in case it was changed/updated by Admin
                for s in self.mock_students.values():
                    if s.get("username") == username:
                        s["class_id"] = class_id
                        s["name"] = display_name
                        break

    def get_class_status(self, class_id=None):
        self.sync_students_from_db()
        
        import random
        
        # If class_id is None, return empty list
        if class_id is None:
            class_students = []
        else:
            try:
                c_id_int = int(class_id)
            except Exception:
                c_id_int = class_id
            class_students = [s for s in self.mock_students.values() if s.get("class_id") == c_id_int]
            
        # Drift logic: if class session is active, simulate student updates
        if self.class_session_active:
            for data in class_students:
                name = data["name"]
                if data["is_active_student"]:
                    # Real active student: bind actual live state
                    data["online"] = self.is_active
                    data["focus_score"] = int(self.focus_score)
                    data["distractions"] = self.distractions
                    data["seat_leaving_count"] = getattr(self, 'seat_leaving_count', 0)
                    data["seat_leaving_duration"] = int(getattr(self, 'seat_leaving_total_duration', 0))
                    
                    sa_pct = 100
                    if getattr(self, 'total_gaze_seconds', 0) > 0:
                        sa_pct = int((getattr(self, 'looking_at_screen_seconds', 0) / self.total_gaze_seconds) * 100)
                    data["screen_attention_percent"] = sa_pct
                    data["attendance"] = getattr(self, 'attendance_status', 'Có mặt')
                    
                    # Map state
                    st = "Focused"
                    if self.is_active:
                        current_cstate = getattr(self, 'current_state', 'TAP TRUNG')
                        if current_cstate == 'DUNG DIEN THOAI':
                            st = 'Phone'
                        elif current_cstate == 'BUON NGU':
                            st = 'Sleepy'
                        elif current_cstate == 'PHAT HIEN NHIEU NGUOI':
                            st = 'Cheating'
                        elif current_cstate in ['NGOANH MAT DI', 'KHONG THAY KHUON MAT']:
                            st = 'Distracted'
                        elif current_cstate == 'TAP TRUNG':
                            st = 'Focused'
                        else:
                            st = 'Normal'
                    data["state"] = st

                    # Add active student emotion stats
                    stats = self.get_stats()
                    data["emotion"] = stats["current_emotion"]
                    data["emotion_icon"] = stats["emotion_icon"]
                    data["emotion_confidence"] = stats["emotion_confidence"]
                    data["emotion_history"] = stats["emotion_history"]
                else:
                    # Mock student: random drift
                    if not data["online"]:
                        continue
                        
                    # Drifting scores
                    drift = random.choice([-3, -2, -1, 0, 1, 2, 3])
                    data["focus_score"] = max(0, min(100, data["focus_score"] + drift))
                    
                    # Mini history update
                    data["focus_history"].append(data["focus_score"])
                    if len(data["focus_history"]) > 10:
                        data["focus_history"].pop(0)
                        
                    # Update mock student emotion fields
                    m_state = data.get("state", "Normal")
                    if m_state == "Focused":
                        m_emo = "Happy" if random.random() > 0.8 else "Neutral"
                    elif m_state == "Normal":
                        m_emo = "Neutral"
                    elif m_state == "Sleepy":
                        m_emo = "Tired"
                    else: # Distracted, Phone, Cheating
                        m_emo = "Stressed"
                        
                    m_icons = {"Happy": "😊", "Neutral": "😐", "Tired": "😴", "Stressed": "😰"}
                    data["emotion"] = m_emo
                    data["emotion_icon"] = m_icons.get(m_emo, "😐")
                    
                    base_conf = {"Happy": 88, "Neutral": 90, "Tired": 85, "Stressed": 82}
                    data["emotion_confidence"] = base_conf.get(m_emo, 90) + random.randint(-2, 2)
                    
                    if "emotion_history" not in data or not data["emotion_history"]:
                        data["emotion_history"] = [m_emo for _ in range(10)]
                    else:
                        data["emotion_history"].append(m_emo)
                        if len(data["emotion_history"]) > 10:
                            data["emotion_history"].pop(0)

                    # Calculate mock student learning risk score based on state and warnings
                    # Formula components: Phone state: +100, Sleepy state: +100, Distracted state: +100, Stressed/Tired emotion: +100
                    phone_val = 100 if m_state == "Phone" else (40 if random.random() > 0.95 else 0)
                    drowsy_val = 100 if m_state == "Sleepy" else (40 if random.random() > 0.95 else 0)
                    away_val = 100 if m_state == "Distracted" else (30 if random.random() > 0.95 else 0)
                    neg_val = 100 if m_emo in ["Tired", "Stressed"] else 0
                    
                    m_risk = int(phone_val * 0.40 + drowsy_val * 0.30 + away_val * 0.20 + neg_val * 0.10)
                    data["learning_risk"] = max(0, min(100, m_risk + random.randint(-5, 5)))
                    
                    if data["learning_risk"] < 30:
                        data["learning_risk_level"] = "Low"
                    elif data["learning_risk"] < 70:
                        data["learning_risk_level"] = "Medium"
                    else:
                        data["learning_risk_level"] = "High"
                        
                    # Seat leaving simulation for mock students
                    if random.random() < 0.01:
                        data["seat_leaving_count"] = data.get("seat_leaving_count", 0) + 1
                        add_duration = random.randint(10, 80)
                        data["seat_leaving_duration"] = data.get("seat_leaving_duration", 0) + add_duration
                        # Log seat leaving for mock student
                        self.activity_logs.append({
                            "time": datetime.now().strftime("%I:%M %p"),
                            "message": f"{name} rời vị trí",
                            "type": "warning"
                        })
                        if len(self.activity_logs) > 30:
                            self.activity_logs.pop(0)
                            
                    # Update screen attention % slightly
                    if random.random() < 0.1:
                        data["screen_attention_percent"] = max(60, min(100, data.get("screen_attention_percent", 90) + random.choice([-2, -1, 1, 2])))
                        
                    # State transitions (very low probability)
                    if random.random() < 0.05:
                        states = ["Focused", "Normal", "Sleepy", "Distracted", "Phone", "Cheating"]
                        weights = [0.55, 0.2, 0.08, 0.08, 0.05, 0.04]
                        new_state = random.choices(states, weights=weights)[0]
                        
                        if new_state != data["state"]:
                            data["state"] = new_state
                            now_str = datetime.now().strftime("%I:%M %p")
                            
                            log_type = "info"
                            if new_state == "Focused":
                                log_msg = f"{name} cải thiện mức tập trung"
                            elif new_state == "Sleepy":
                                log_msg = f"{name} có dấu hiệu buồn ngủ"
                                log_type = "warning"
                                data["warnings"] += 1
                            elif new_state == "Distracted":
                                log_msg = f"{name} bị mất tập trung"
                                log_type = "danger"
                                data["distractions"] += 1
                            elif new_state == "Phone":
                                log_msg = f"{name} đang sử dụng điện thoại"
                                log_type = "danger"
                                data["distractions"] += 1
                            elif new_state == "Cheating":
                                log_msg = f"{name} có nguy cơ gian lận (nhiều người/chuyển tab)"
                                log_type = "danger"
                                data["distractions"] += 1
                            else:
                                log_msg = f"{name} trạng thái bình thường"
                                
                            self.activity_logs.append({
                                "time": now_str,
                                "message": log_msg,
                                "type": log_type
                            })
                            # Keep logs small
                            if len(self.activity_logs) > 30:
                                self.activity_logs.pop(0)

        # Guarantee emotion fields exist on all mock students
        for data in self.mock_students.values():
            if "emotion" not in data:
                m_state = data.get("state", "Normal")
                if m_state == "Focused":
                    m_emo = "Happy" if random.random() > 0.8 else "Neutral"
                elif m_state == "Normal":
                    m_emo = "Neutral"
                elif m_state == "Sleepy":
                    m_emo = "Tired"
                else:
                    m_emo = "Stressed"
                m_icons = {"Happy": "😊", "Neutral": "😐", "Tired": "😴", "Stressed": "😰"}
                data["emotion"] = m_emo
                data["emotion_icon"] = m_icons.get(m_emo, "😐")
                data["emotion_confidence"] = 85 + random.randint(0, 10)
                data["emotion_history"] = [m_emo for _ in range(10)]
        return class_students

    def get_recommendations(self, username="hocsinh"):
        display_name, rows = self.repo.get_recommendations_data(username)
        
        best_time_start = "08:00"
        best_time_end = "10:00"
        recommended_break = 45
        
        if len(rows) > 0:
            hour_scores = {}
            for row in rows:
                final_score = row[1]
                start_time_str = row[2]
                try:
                    dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                    hour = dt.hour
                    if hour not in hour_scores:
                        hour_scores[hour] = []
                    hour_scores[hour].append(final_score)
                except Exception:
                    pass
            if hour_scores:
                best_hour = max(hour_scores, key=lambda h: sum(hour_scores[h])/len(hour_scores[h]))
                best_time_start = f"{best_hour:02d}:00"
                best_time_end = f"{(best_hour+2)%24:02d}:00"
        else:
            if username == "hocsinh":
                best_time_start = "08:00"
                best_time_end = "10:00"
                recommended_break = 45
        
        return {
            "student_name": display_name,
            "best_time_range": f"{best_time_start} - {best_time_end}",
            "recommended_break_minutes": recommended_break,
            "text": f"Dựa trên phân tích thói quen học tập của {display_name}, AI phát hiện học sinh học hiệu quả nhất vào khung giờ {best_time_start} - {best_time_end} với điểm tập trung trung bình cao nhất. Đề xuất thiết lập lịch học trong khoảng thời gian này và áp dụng phương pháp Pomodoro: học {recommended_break} phút, nghỉ ngơi 5 phút để bảo vệ mắt và tái tạo năng lượng."
        }

    # --- Offline Classroom Mode Simulation ---
    def start_offline_class_session(self, class_id):
        self.offline_class_active = True
        self.offline_class_start_time = time.time()
        self.offline_class_id = class_id
        # Reset log and student states
        self.offline_activity_logs = [
            {"time": datetime.now().strftime("%H:%M:%S"), "message": "Hệ thống giám sát bằng camera lớp học đã kích hoạt", "type": "info"}
        ]
        
        # Initialize seat coordinates for all students in this class
        import random
        try:
            c_id = int(class_id)
        except Exception:
            c_id = 1
        students_in_class = [s for s in self.mock_students.values() if s.get("class_id") == c_id]
        for i, s in enumerate(students_in_class):
            s["seat_row"] = i // 4
            s["seat_col"] = i % 4
            s["state"] = "Focused"
            s["focus_score"] = random.randint(85, 98)
            s["distractions"] = 0

    def end_offline_class_session(self):
        self.offline_class_active = False
        self.offline_class_start_time = None
        
    def get_offline_classroom_data(self, class_id=1):
        import random
        # Ensure we have class_id as int
        try:
            c_id = int(class_id)
        except Exception:
            c_id = 1
            
        students = [s for s in self.mock_students.values() if s.get("class_id") == c_id]
        
        # Ensure all students have row/col
        for i, s in enumerate(students):
            if "seat_row" not in s or "seat_col" not in s:
                s["seat_row"] = i // 4
                s["seat_col"] = i % 4
            if "state" not in s:
                s["state"] = "Focused"
            if "focus_score" not in s:
                s["focus_score"] = random.randint(80, 95)
            if "distractions" not in s:
                s["distractions"] = 0

        # If offline class is active, the student states are updated in real-time by ClassroomAI.
        # No random mock drift logic is executed.

        # Compute stats
        total_students = len(students)
        active_students = [s for s in students if s.get("online", False)]
        present_count = len(active_students)
        distracted_count = sum(1 for s in active_students if s.get("state") in ["Distracted", "Phone"])
        drowsy_count = sum(1 for s in active_students if s.get("state") == "Sleepy")
        
        avg_focus = 100
        if present_count > 0:
            avg_focus = sum(s.get("focus_score", 100) for s in active_students) / present_count
        
        # Compute AI Analyses
        analyses = []
        # Back row analysis (row >= 4)
        back_row_distracted = sum(1 for s in students if s["seat_row"] >= 4 and s["state"] in ["Distracted", "Phone", "Sleepy"])
        if back_row_distracted >= 2:
            analyses.append("Khu vực hàng ghế sau đang có dấu hiệu giảm chú ý.")
        
        if distracted_count > 0:
            analyses.append(f"AI phát hiện {distracted_count} học sinh có vẻ bị phân tâm hoặc làm việc riêng.")
            
        # Time-based analysis
        elapsed = 0
        if self.offline_class_active and self.offline_class_start_time:
            elapsed = int(time.time() - self.offline_class_start_time)
        if elapsed > 30:
            analyses.append(f"Mức độ tập trung của lớp có xu hướng giảm sau {int(elapsed/60) + 15} phút.")
        else:
            analyses.append("Độ tập trung toàn lớp học ở mức ổn định trong thời gian vừa qua.")
            
        if drowsy_count > 1:
            analyses.append(f"Phát hiện {drowsy_count} học sinh buồn ngủ ở các vị trí khác nhau.")
        elif drowsy_count == 1:
            analyses.append("Phát hiện 1 học sinh buồn ngủ, cần nhắc nhở.")

        # Teacher suggestions
        suggestions = []
        if avg_focus < 75:
            suggestions.append("AI Đề xuất: Cho lớp nghỉ giải lao ngắn 3 phút để tái tạo năng lượng.")
            suggestions.append("AI Đề xuất: Tổ chức một trò chơi nhỏ hoặc câu hỏi trắc nghiệm nhanh.")
        elif avg_focus < 85:
            suggestions.append("AI Đề xuất: Đặt một câu hỏi tương tác ngẫu nhiên để khuấy động lớp học.")
            suggestions.append("AI Đề xuất: Di chuyển xung quanh lớp học, đặc biệt là khu vực hàng ghế cuối.")
        else:
            suggestions.append("AI Đề xuất: Lớp học đang tập trung tốt. Tiếp tục tiến trình bài giảng hiện tại.")
            suggestions.append("AI Đề xuất: Khuyến khích học sinh thảo luận cặp đôi về nội dung vừa học.")

        return {
            "students": students,
            "statistics": {
                "present": present_count,
                "distracted": distracted_count,
                "drowsy": drowsy_count,
                "focus_score": int(avg_focus)
            },
            "analyses": analyses,
            "suggestions": suggestions,
            "logs": self.offline_activity_logs,
            "offline_class_active": self.offline_class_active,
            "elapsed_seconds": elapsed
        }
