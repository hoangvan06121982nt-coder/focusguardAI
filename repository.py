import os
import sqlite3
import json
from datetime import datetime

# Load environment variables from .env file manually if it exists
if os.path.exists(".env"):
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    val = val.strip().strip("'\"")
                    os.environ[key.strip()] = val
    except Exception as e:
        print(f"Error loading .env file: {e}")

def _seed_sessions_and_events(conn_or_db, is_firestore):
    import random
    import json
    from datetime import datetime, timedelta
    
    # We will seed history for the past 5 days, plus today.
    students = [
        (3, "hocsinh", "Nguyễn Văn An", 1, 88, 95),
        (4, "diyasharma", "Trần Thị Bình", 1, 80, 90),
        (5, "rohanverma", "Lê Hoàng Giang", 1, 30, 45),
        (6, "ananyapatel", "Phạm Minh Hải", 1, 40, 55),
        (7, "vivaankapoor", "Vũ Tiến Khoa", 1, 93, 98),
        (8, "krishjain", "Đỗ Minh Quân", 1, 91, 96)
    ]
    
    subjects = ["Toán", "Văn", "Anh", "Lý", "Hóa"]
    
    if is_firestore:
        # Check if already seeded
        try:
            doc = conn_or_db.collection("sessions").document("1").get()
            if doc.exists:
                return
        except Exception:
            pass
    else:
        cursor = conn_or_db.cursor()
        cursor.execute("SELECT COUNT(id) FROM sessions")
        if cursor.fetchone()[0] > 0:
            return
            
    now = datetime.now()
    next_session_id = 1
    next_event_id = 1
    
    for day_offset in range(5, -1, -1): # 5 days ago to today
        date_val = now - timedelta(days=day_offset)
        for user_id, username, display_name, class_id, min_s, max_s in students:
            # Seed 1 or 2 sessions per student per day
            num_sessions = 1 if day_offset > 0 else (2 if user_id in [3, 7] else 1)
            for s_idx in range(num_sessions):
                # Pick an hour: let's pick 9:00 or 14:00
                hour = 9 + s_idx * 5 # 9 or 14
                start_dt = date_val.replace(hour=hour, minute=random.randint(0, 45), second=0)
                start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
                
                duration = random.randint(1800, 3600) # 30 to 60 mins
                end_dt = start_dt + timedelta(seconds=duration)
                end_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
                
                # Low focus in the afternoon for some students
                if hour == 14 and user_id in [5, 6]:
                    score = random.randint(min_s - 15, min_s)
                else:
                    score = random.randint(min_s, max_s)
                    
                distractions = random.randint(0, 2) if score > 80 else random.randint(3, 8)
                subject = random.choice(subjects)
                
                # History json list
                history = []
                hist_score = 100
                for m in range(0, duration // 60, 5): # every 5 mins
                    check_dt = start_dt + timedelta(minutes=m)
                    if hist_score > score:
                        hist_score -= random.randint(1, 4)
                    elif hist_score < score:
                        hist_score += random.randint(0, 2)
                    history.append({
                        "time": check_dt.strftime("%H:%M:%S"),
                        "score": max(0, min(100, int(hist_score)))
                    })
                history_str = json.dumps(history)
                
                # Create session
                if is_firestore:
                    conn_or_db.collection("sessions").document(str(next_session_id)).set({
                        "id": next_session_id,
                        "user_id": user_id,
                        "start_time": start_str,
                        "end_time": end_str,
                        "duration_seconds": duration,
                        "final_score": score,
                        "total_distractions": distractions,
                        "history_json": history_str,
                        "subject": subject
                    })
                else:
                    cursor.execute("""
                        INSERT INTO sessions (id, user_id, start_time, end_time, duration_seconds, final_score, total_distractions, history_json, subject)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (next_session_id, user_id, start_str, end_str, duration, score, distractions, history_str, subject))
                    
                # Create focus events
                for _ in range(distractions):
                    event_type = random.choice(["Dùng điện thoại", "Buồn ngủ / Ngủ gật", "Ngoảnh mặt đi"])
                    event_offset = random.randint(60, duration - 60)
                    event_dt = start_dt + timedelta(seconds=event_offset)
                    event_str = event_dt.strftime("%Y-%m-%d %H:%M:%S")
                    
                    if is_firestore:
                        conn_or_db.collection("focus_events").document(str(next_event_id)).set({
                            "id": next_event_id,
                            "session_id": next_session_id,
                            "type": event_type,
                            "timestamp": event_str
                        })
                    else:
                        cursor.execute("""
                            INSERT INTO focus_events (id, session_id, type, timestamp)
                            VALUES (?, ?, ?, ?)
                        """, (next_event_id, next_session_id, event_type, event_str))
                    next_event_id += 1
                    
                next_session_id += 1
    if not is_firestore:
        conn_or_db.commit()


class BaseRepository:
    def init_db(self):
        pass

    def seed_data(self):
        pass

    # Class operations
    def get_classes_list(self):
        pass

    def get_class_name(self, class_id):
        pass

    def create_class(self, class_name):
        pass

    def update_class(self, class_id, new_name):
        pass

    def delete_class(self, class_id):
        pass

    # User operations
    def get_users_list(self):
        pass

    def create_user(self, username, password, display_name, role, class_id, student_id=None):
        pass

    def update_user(self, user_id, username, password, display_name, role, class_id, student_id=None):
        pass

    def delete_user(self, user_id):
        pass

    def save_face_embedding(self, user_id, embedding_json):
        pass

    def get_student_embeddings_by_class(self, class_id):
        pass

    def authenticate_user(self, username, password):
        pass

    def get_students_by_role(self):
        pass

    def get_student_id_for_parent(self, parent_id):
        pass

    def get_user_by_id(self, user_id):
        pass

    # Session operations
    def create_session(self, user_id, start_time, subject=None):
        pass

    def update_session(self, session_id, end_time, duration_seconds, final_score, total_distractions, history_json):
        pass

    def get_all_sessions(self, username=None):
        pass

    def get_latest_session(self):
        pass

    def get_recommendations_data(self, username):
        pass

    # Focus event & Class sessions operations
    def create_focus_event(self, session_id, event_type, timestamp):
        pass

    def create_class_session(self, class_id, started_at):
        pass

    def update_class_session(self, class_session_id, ended_at):
        pass

    # Analytics & Insights (Phases 1, 2 & 3)
    def get_daily_leaderboard(self, class_id):
        pass

    def get_student_heatmap_data(self, user_id, days=7):
        pass

    def get_session_distraction_breakdown(self, session_id):
        pass

    def get_classroom_watchlist(self, class_id):
        pass

    def get_classroom_danger_hour(self, class_id):
        pass

    def get_student_subject_analytics(self, user_id):
        pass

    def get_student_profile_stats(self, user_id):
        pass

    def get_session_comparison(self, user_id, limit=5):
        pass



class SQLiteRepository(BaseRepository):
    def __init__(self, db_path="focusguard.db"):
        self.db_path = db_path

    def init_db(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            pass
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT UNIQUE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                display_name TEXT,
                role TEXT,
                class_id INTEGER,
                student_id INTEGER,
                face_embedding TEXT,
                FOREIGN KEY (class_id) REFERENCES classes(id),
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
        ''')
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN face_embedding TEXT")
        except sqlite3.OperationalError:
            pass
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                start_time TEXT,
                end_time TEXT,
                duration_seconds INTEGER,
                final_score INTEGER,
                total_distractions INTEGER,
                history_json TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS focus_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                type TEXT,
                timestamp TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS class_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER,
                started_at TEXT,
                ended_at TEXT,
                FOREIGN KEY (class_id) REFERENCES classes(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Migrations
        conn_mig = None
        try:
            conn_mig = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn_mig.cursor()
            cursor.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER")
            conn_mig.commit()
        except sqlite3.OperationalError:
            pass
        finally:
            if conn_mig:
                conn_mig.close()

        conn_mig = None
        try:
            conn_mig = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn_mig.cursor()
            cursor.execute("ALTER TABLE users ADD COLUMN student_id INTEGER")
            conn_mig.commit()
        except sqlite3.OperationalError:
            pass
        finally:
            if conn_mig:
                conn_mig.close()
        
        conn_mig = None
        try:
            conn_mig = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn_mig.cursor()
            cursor.execute("ALTER TABLE sessions ADD COLUMN subject TEXT")
            conn_mig.commit()
        except sqlite3.OperationalError:
            pass
        finally:
            if conn_mig:
                conn_mig.close()
            
        self.seed_data()

    def seed_data(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO classes (id, class_name) VALUES (1, '10A1')")
            cursor.execute("INSERT OR IGNORE INTO classes (id, class_name) VALUES (2, '10A2')")
            cursor.execute("INSERT OR IGNORE INTO classes (id, class_name) VALUES (3, '10A3')")
            
            cursor.execute('''
                INSERT OR IGNORE INTO users (id, username, password, display_name, role, class_id)
                VALUES (1, 'admin', '123', 'Quản trị viên', 'admin', NULL)
            ''')
            
            cursor.execute('''
                INSERT OR IGNORE INTO users (id, username, password, display_name, role, class_id)
                VALUES (2, 'teacher', '123', 'Thầy Minh', 'teacher', 1)
            ''')
            
            cursor.execute('''
                INSERT OR IGNORE INTO users (id, username, password, display_name, role, class_id)
                VALUES (3, 'hocsinh', '123', 'Nguyễn Văn An', 'student', 1)
            ''')
            
            cursor.execute('''
                INSERT OR IGNORE INTO users (id, username, password, display_name, role, class_id, student_id)
                VALUES (100, 'phuhuynh', '123', 'Phụ huynh Nguyễn Văn An', 'parent', NULL, 3)
            ''')
            
            mock_students_data = [
                ('diyasharma', '123', 'Trần Thị Bình', 'student', 1),
                ('rohanverma', '123', 'Lê Hoàng Giang', 'student', 1),
                ('ananyapatel', '123', 'Phạm Minh Hải', 'student', 1),
                ('vivaankapoor', '123', 'Vũ Tiến Khoa', 'student', 1),
                ('meeranair', '123', 'Ngô Khánh Linh', 'student', 1),
                ('arjunsingh', '123', 'Hoàng Đức Minh', 'student', 1),
                ('ishitayadav', '123', 'Bùi Thị Ngọc', 'student', 1),
                ('krishjain', '123', 'Đỗ Minh Quân', 'student', 1)
            ]
            for idx, (username, password, display_name, role, class_id) in enumerate(mock_students_data, start=4):
                cursor.execute('''
                    INSERT OR IGNORE INTO users (id, username, password, display_name, role, class_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (idx, username, password, display_name, role, class_id))
                
            conn.commit()
            _seed_sessions_and_events(conn, is_firestore=False)
        except Exception as e:
            print(f"Error seeding database: {e}")
        finally:
            conn.close()

    def get_classes_list(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.id, c.class_name, COUNT(u.id) 
                FROM classes c 
                LEFT JOIN users u ON u.class_id = c.id AND u.role = 'student' 
                GROUP BY c.id 
                ORDER BY c.class_name
            ''')
            rows = cursor.fetchall()
            return [{"id": r[0], "class_name": r[1], "student_count": r[2]} for r in rows]
        except Exception as e:
            print(f"Error reading classes: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_class_name(self, class_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("SELECT class_name FROM classes WHERE id = ?", (class_id,))
            row = cursor.fetchone()
            return row[0] if row else "Chưa gán lớp"
        except Exception:
            return "Chưa gán lớp"
        finally:
            if conn:
                conn.close()

    def create_class(self, class_name):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO classes (class_name) VALUES (?)", (class_name,))
            conn.commit()
            return True, "Tạo lớp học thành công"
        except sqlite3.IntegrityError:
            return False, "Tên lớp học đã tồn tại"
        except Exception as e:
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def update_class(self, class_id, new_name):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("UPDATE classes SET class_name = ? WHERE id = ?", (new_name, class_id))
            conn.commit()
            return True, "Cập nhật tên lớp học thành công"
        except sqlite3.IntegrityError:
            return False, "Tên lớp học đã tồn tại"
        except Exception as e:
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def delete_class(self, class_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET class_id = NULL WHERE class_id = ?", (class_id,))
            cursor.execute("DELETE FROM classes WHERE id = ?", (class_id,))
            conn.commit()
            return True, "Xóa lớp học thành công"
        except Exception as e:
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def get_users_list(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.id, u.username, u.display_name, u.role, c.class_name, u.class_id, u.face_embedding
                FROM users u
                LEFT JOIN classes c ON u.class_id = c.id
                ORDER BY u.role, u.display_name
            ''')
            rows = cursor.fetchall()
            return [{"id": r[0], "username": r[1], "display_name": r[2], "role": r[3], "class_name": r[4] or "N/A", "class_id": r[5], "has_face": bool(r[6])} for r in rows]
        except Exception as e:
            print(f"Error reading users: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def create_user(self, username, password, display_name, role, class_id, student_id=None):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            c_id = int(class_id) if class_id and str(class_id).isdigit() else None
            s_id = int(student_id) if student_id and str(student_id).isdigit() else None
            cursor.execute('''
                INSERT INTO users (username, password, display_name, role, class_id, student_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, password, display_name, role, c_id, s_id))
            conn.commit()
            return True, "Tạo tài khoản thành công"
        except sqlite3.IntegrityError:
            return False, "Tên đăng nhập đã tồn tại"
        except Exception as e:
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def update_user(self, user_id, username, password, display_name, role, class_id, student_id=None):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            c_id = int(class_id) if class_id and str(class_id).isdigit() else None
            s_id = int(student_id) if student_id and str(student_id).isdigit() else None
            
            if password and password.strip():
                cursor.execute('''
                    UPDATE users 
                    SET username = ?, password = ?, display_name = ?, role = ?, class_id = ?, student_id = ?
                    WHERE id = ?
                ''', (username, password, display_name, role, c_id, s_id, user_id))
            else:
                cursor.execute('''
                    UPDATE users 
                    SET username = ?, display_name = ?, role = ?, class_id = ?, student_id = ?
                    WHERE id = ?
                ''', (username, display_name, role, c_id, s_id, user_id))
                
            conn.commit()
            return True, "Cập nhật tài khoản thành công"
        except sqlite3.IntegrityError:
            return False, "Tên đăng nhập đã tồn tại"
        except Exception as e:
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def delete_user(self, user_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return True, "Xóa tài khoản thành công"
        except Exception as e:
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def save_face_embedding(self, user_id, embedding_json):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET face_embedding=? WHERE id=?", (embedding_json, user_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving face embedding: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_student_embeddings_by_class(self, class_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("SELECT id, display_name, username, face_embedding FROM users WHERE role='student' AND class_id=?", (class_id,))
            rows = cursor.fetchall()
            return [{"student_id": r[0], "full_name": r[1], "username": r[2], "embedding": json.loads(r[3])} for r in rows if r[3]]
        except Exception as e:
            print(f"Error reading class student embeddings: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def authenticate_user(self, username, password):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, display_name, role, class_id FROM users WHERE username = ? AND password = ?", (username, password))
            user = cursor.fetchone()
            return user
        except Exception:
            return None
        finally:
            if conn:
                conn.close()

    def get_students_by_role(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("SELECT username, display_name, class_id FROM users WHERE role = 'student'")
            rows = cursor.fetchall()
            return rows
        except Exception:
            return []
        finally:
            if conn:
                conn.close()

    def get_student_id_for_parent(self, parent_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("SELECT student_id FROM users WHERE id = ?", (parent_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception:
            return None
        finally:
            if conn:
                conn.close()

    def get_user_by_id(self, user_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("SELECT username, display_name, role, class_id FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return {"username": row[0], "display_name": row[1], "role": row[2], "class_id": row[3]}
            return None
        except Exception:
            return None
        finally:
            if conn:
                conn.close()

    def create_session(self, user_id, start_time, subject=None):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sessions (user_id, start_time, end_time, duration_seconds, final_score, total_distractions, history_json, subject)
                VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, ?)
            ''', (user_id, start_time, subject or "Toán"))
            session_id = cursor.lastrowid
            conn.commit()
            return session_id
        except Exception as e:
            print(f"Error creating session: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def update_session(self, session_id, end_time, duration_seconds, final_score, total_distractions, history_json):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE sessions
                SET end_time = ?, duration_seconds = ?, final_score = ?, total_distractions = ?, history_json = ?
                WHERE id = ?
            ''', (end_time, duration_seconds, final_score, total_distractions, history_json, session_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating session: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_all_sessions(self, username=None):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            if username:
                cursor.execute('''
                    SELECT s.start_time, s.end_time, s.duration_seconds, s.final_score, s.total_distractions
                    FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE u.username = ?
                    ORDER BY s.id DESC
                ''', (username,))
            else:
                cursor.execute('''
                    SELECT start_time, end_time, duration_seconds, final_score, total_distractions
                    FROM sessions
                    ORDER BY id DESC
                ''')
            rows = cursor.fetchall()
            
            sessions = []
            for row in rows:
                sessions.append({
                    "start_time": row[0],
                    "end_time": row[1],
                    "duration_seconds": row[2],
                    "final_score": row[3],
                    "total_distractions": row[4]
                })
            return sessions
        except Exception as e:
            print(f"Lỗi khi đọc lịch sử SQLite: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_latest_session(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT start_time, end_time, duration_seconds, final_score, total_distractions
                FROM sessions
                ORDER BY id DESC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            
            if row:
                return {
                    "start_time": row[0],
                    "end_time": row[1],
                    "duration_seconds": row[2],
                    "final_score": row[3],
                    "total_distractions": row[4]
                }
            return None
        except Exception as e:
            print(f"Lỗi khi lấy phiên mới nhất: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_recommendations_data(self, username):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.display_name, s.final_score, s.start_time
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE u.username = ?
                ORDER BY s.id DESC
            """, (username,))
            rows = cursor.fetchall()
            
            display_name = "Học sinh"
            if rows:
                display_name = rows[0][0]
            return display_name, rows
        except Exception:
            return "Học sinh", []
        finally:
            if conn:
                conn.close()

    def create_focus_event(self, session_id, event_type, timestamp):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO focus_events (session_id, type, timestamp)
                VALUES (?, ?, ?)
            ''', (session_id, event_type, timestamp))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error logging focus event: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def create_class_session(self, class_id, started_at):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO class_sessions (class_id, started_at)
                VALUES (?, ?)
            ''', (class_id, started_at))
            session_id = cursor.lastrowid
            conn.commit()
            return session_id
        except Exception as e:
            print(f"Error starting class session: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def update_class_session(self, class_session_id, ended_at):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE class_sessions SET ended_at = ? WHERE id = ?
            ''', (ended_at, class_session_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error ending class session: {e}")
            return False

    def get_daily_leaderboard(self, class_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT u.display_name, AVG(s.final_score) as avg_score
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE u.class_id = ? AND s.start_time >= ? AND s.final_score IS NOT NULL
                GROUP BY u.id
                ORDER BY avg_score DESC
            """, (class_id, today + " 00:00:00"))
            rows = cursor.fetchall()
            return [{"display_name": r[0], "score": int(r[1])} for r in rows]
        except Exception as e:
            print(f"Error getting daily leaderboard: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_student_heatmap_data(self, user_id, days=7):
        conn = None
        try:
            import datetime as dt_mod
            cutoff_date = (dt_mod.datetime.now() - dt_mod.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT strftime('%H', start_time) as hour, AVG(final_score) as avg_score
                FROM sessions
                WHERE user_id = ? AND final_score IS NOT NULL AND start_time >= ?
                GROUP BY hour
                ORDER BY hour ASC
            """, (user_id, cutoff_date))
            rows = cursor.fetchall()
            
            result = {}
            for hour_num in range(8, 23): # 08:00 to 22:00
                result[f"{hour_num:02d}:00"] = {"score": None, "status": "none"}
                
            for row in rows:
                hour_str = f"{int(row[0]):02d}:00"
                if hour_str in result:
                    score = int(row[1])
                    status = "high" if score >= 80 else ("med" if score >= 50 else "low")
                    result[hour_str] = {"score": score, "status": status}
            return result
        except Exception as e:
            print(f"Error getting heatmap data: {e}")
            return {}
        finally:
            if conn:
                conn.close()

    def get_session_distraction_breakdown(self, session_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT type, COUNT(id)
                FROM focus_events
                WHERE session_id = ?
                GROUP BY type
            """, (session_id,))
            rows = cursor.fetchall()
            
            counts = {
                "phone": 0,
                "drowsy": 0,
                "distracted": 0,
                "multiple_people": 0
            }
            for row in rows:
                t = row[0]
                c = row[1]
                if "điện thoại" in t.lower():
                    counts["phone"] = c
                elif "buồn ngủ" in t.lower() or "ngủ gật" in t.lower():
                    counts["drowsy"] = c
                elif "ngoảnh mặt" in t.lower() or "mất tập trung" in t.lower():
                    counts["distracted"] = c
                elif "nhiều người" in t.lower():
                    counts["multiple_people"] = c
            return counts
        except Exception as e:
            print(f"Error getting session breakdown: {e}")
            return {"phone": 0, "drowsy": 0, "distracted": 0, "multiple_people": 0}
        finally:
            if conn:
                conn.close()

    def get_classroom_watchlist(self, class_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.id, u.display_name, AVG(s.final_score) as avg_score
                FROM users u
                JOIN sessions s ON s.user_id = u.id
                WHERE u.class_id = ? AND u.role = 'student' AND s.final_score IS NOT NULL
                GROUP BY u.id
                HAVING avg_score < 70
                ORDER BY avg_score ASC
            """, (class_id,))
            rows = cursor.fetchall()
            return [{"id": r[0], "display_name": r[1], "score": int(r[2])} for r in rows]
        except Exception as e:
            print(f"Error getting watchlist: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_classroom_danger_hour(self, class_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT strftime('%H', s.start_time) as hour, AVG(s.final_score) as avg_score
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE u.class_id = ? AND s.final_score IS NOT NULL
                GROUP BY hour
                ORDER BY avg_score ASC
                LIMIT 1
            """, (class_id,))
            row = cursor.fetchone()
            if row:
                hour = int(row[0])
                return f"{hour:02d}:00 - {(hour+1)%24:02d}:00"
            return "Chưa có dữ liệu"
        except Exception as e:
            print(f"Error getting danger hour: {e}")
            return "Chưa có dữ liệu"
        finally:
            if conn:
                conn.close()

    def get_student_subject_analytics(self, user_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(subject, 'Toán') as sub, AVG(final_score) as avg_score
                FROM sessions
                WHERE user_id = ? AND final_score IS NOT NULL
                GROUP BY sub
            """, (user_id,))
            rows = cursor.fetchall()
            return [{"subject": r[0], "score": int(r[1])} for r in rows]
        except Exception as e:
            print(f"Error getting subject analytics: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_student_profile_stats(self, user_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(id), SUM(duration_seconds), AVG(final_score)
                FROM sessions
                WHERE user_id = ? AND final_score IS NOT NULL
            """, (user_id,))
            row = cursor.fetchone()
            
            total_sessions = row[0] if row and row[0] is not None else 0
            total_duration = row[1] if row and row[1] is not None else 0
            avg_score = int(row[2]) if row and row[2] is not None else 100
            
            cursor.execute("""
                SELECT final_score FROM sessions
                WHERE user_id = ? AND final_score IS NOT NULL
                ORDER BY id DESC LIMIT 6
            """, (user_id,))
            scores = [r[0] for r in cursor.fetchall()]
            
            trend = "stable"
            if len(scores) >= 2:
                recent = scores[:3]
                older = scores[3:]
                recent_avg = sum(recent) / len(recent)
                older_avg = sum(older) / len(older) if older else recent_avg
                if recent_avg - older_avg > 2:
                    trend = "up"
                elif older_avg - recent_avg > 2:
                    trend = "down"
            
            return {
                "total_sessions": total_sessions,
                "total_duration_seconds": total_duration,
                "average_focus_score": avg_score,
                "trend": trend
            }
        except Exception as e:
            print(f"Error getting profile stats: {e}")
            return {"total_sessions": 0, "total_duration_seconds": 0, "average_focus_score": 100, "trend": "stable"}
        finally:
            if conn:
                conn.close()

    def get_session_comparison(self, user_id, limit=5):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, start_time, final_score, COALESCE(subject, 'Toán')
                FROM sessions
                WHERE user_id = ? AND final_score IS NOT NULL
                ORDER BY id DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            rows.reverse()
            return [{"id": r[0], "start_time": r[1], "score": r[2], "subject": r[3]} for r in rows]
        except Exception as e:
            print(f"Error getting session comparison: {e}")
            return []
        finally:
            if conn:
                conn.close()



class FirestoreRepository(BaseRepository):
    def __init__(self):
        # The firebase initialization must occur here
        self.db = None
        self.connect()

    def connect(self):
        try:
            from google.cloud import firestore
            
            # Read USE_EMULATOR setting (defaults to True for local development)
            use_emulator = os.environ.get("USE_EMULATOR", "true").lower() == "true"
            
            if use_emulator:
                from google.auth import credentials as auth_credentials
                self.db = firestore.Client(
                    project="focusguard-ai",
                    credentials=auth_credentials.AnonymousCredentials()
                )
                print("[FIRESTORE] Connected to Firestore Emulator successfully.")
            else:
                self.db = firestore.Client()
                print("[FIRESTORE] Connected to Production Firestore Cloud successfully.")
            
            # Initialize firebase-admin for Auth Emulator/Cloud
            import firebase_admin
            from firebase_admin import credentials
            if not firebase_admin._apps:
                if use_emulator:
                    cred = credentials.Certificate({
                        "type": "service_account",
                        "project_id": "focusguard-ai",
                        "private_key_id": "dummy_id",
                        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCgsllafKXQ3pOw\nZrYS3jfzwNSccVnn7bxTzPUHAC3zGG+NPUheeUDSTrLTZzlwLKEEb+hUkdL/9txo\nP2TjguhNGm8ffH0A6ZjZBwOpvduKZHsj32g1E5HwP5P9CNmYVQ3YDO48uozXkNna\naRxhY0vkQEtvpRTUugUDWeAi04J0+l7MGkIP/r0z4k3R/Xsncm8s/sgdOW+A9jyH\nyyRKIZpOHxnqVrxVQzMwMvzfPsBFectRp2WQm4B7kGo67x/GFAuTg1HOpg14Ivfz\n4/hpjC0kB00PXK2wQ4Ux2EA87HWnAtwGN+DC63aqUoJChRaocei9xfML5aWFxgfY\n1HIfoOFZAgMBAAECggEAMI7kEENFKdHwJ+hJkXcDykzVEjbwV3SPqXTv/78Oo3wZ\nTUEc6qtSKpqsT9RL13ks6LXWKyPrcfxLCtdJKbSHdLENriKEdW+hB8emVDbyLaYC\nTcs25n705PeZROdVNUJSThxOKxyl7YewRN7pPAZwytag1Oo52rQhSqtwXqWyMJ1y\nxdRNlPX1KpeE1duqLnGsd998xs/gUP2rGvQXG2C9BpKYceLgfpWhFtQoI0EOIQ29\nijatyW+dvClSeSwN1USRv588nAFEKbz50GSIaZ1vu2rJ4WlzyrMMdYBghkf0nnUz\nPyXeOX+46Rpc4GKQtRh5zgVIsk0mC2zSst55lUSBnwKBgQDPsPCmta+51/zV+i/q\nU/dgWMn4RKJ6Fz03Q6u9daCHF/k7SqroF/KCXcvyLt+MeQhiyPBxu0p+HIVvC3MM\nlsfcOOeiMU/aD1l+vipW5V0m5Qy4RTmJWuYTm+wpqV9nIKEyZGL1aWkmpiKzmCIL\nUB8jABVLJ5IPjJ22y3Hdqi8N6wKBgQDGExn/pmcovJ0keMobdDQ9Ctltz2p+mkHj\n9u0vmZDFCbJkdrbbeqihgqi5bKoIJi8ZGSHiei6qnNifTo3rrPgBDAMbA/jpMFiM\nhkZ5Iw1WrgPdi/KV4Dj31Pt261hUKfFbSjygvj5RUwFx4PcpKLlFnxc3RUzq4Hzt\nweiTT8SIywKBgF2YYXrfWceofDp5uuog2NREbxBA7e+TVXT4PAbvYV5AAYMkzQw2\n7oStfGExmnCVgp/x6dl3C8T1WXSHdltv/7VQt6IyEsg0LqKdVDtAtc/3XNoV6C3s\nFs8zbyP/Pg0deUdaUfZCgK54JB9HKeBrRPzi5rWtqXb0aYac/D1mmjntAoGAO2OK\nzg5Uq/AxpbfZ0XV8HDlejAA+zArwaquk3jrLH2kS5fB6T0Btw09ry3z7VkosoPfa\nIw/DYkB46vsgrmNEUPwLClSckz59rlSsWLHb0/uFCS5m4+1A534ij7ts1n9k8JxH\npWKlSLj8m+p58QtW0bsruNS8hUgd7SPQ2ip2oRUCgYBMDrxIEuHxHmAMLKjNGrBs\nZKutF8yjgWVw0B3DD6xDEX63RHhnl/jGeQy1y5aw+PP5OBNI2eWjByogF7HMws3X\nNsXlMcGy/r0pG6N+a0MjF0CXUdQVdlamYHMrzWwjnxpj0iQ/fNuE420elIi+LbuH\n2JDkrpAfFP6Xj+9ukur91Q==\n-----END PRIVATE KEY-----\n",
                        "client_email": "firebase-adminsdk-dummy@focusguard-ai.iam.gserviceaccount.com",
                        "client_id": "1234567890",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-dummy%40focusguard-ai.iam.gserviceaccount.com"
                    })
                    firebase_admin.initialize_app(cred)
                else:
                    firebase_admin.initialize_app()
            print("[FIRESTORE] Initialized firebase-admin successfully.")
        except Exception as e:
            print(f"[FIRESTORE] Connection error: {e}")

    def _get_next_id(self, collection_name):
        try:
            docs = self.db.collection(collection_name).stream()
            max_id = 0
            for doc in docs:
                try:
                    doc_id = int(doc.id)
                    if doc_id > max_id:
                        max_id = doc_id
                except ValueError:
                    pass
            return max_id + 1
        except Exception as e:
            print(f"Error fetching next ID for {collection_name}: {e}")
            return 1

    def _get_auth_password(self, password):
        if password and len(password) < 6:
            return password.ljust(6, '0')
        return password

    def _sync_user_to_firebase_auth(self, user_id, username, password, display_name, role, class_id):
        try:
            from firebase_admin import auth
            email = f"{username}@focusguard.ai"
            uid = str(user_id)
            padded_pw = self._get_auth_password(password)
            try:
                # Update user in Auth Emulator if exists
                auth.update_user(
                    uid,
                    email=email,
                    password=padded_pw,
                    display_name=display_name
                )
            except Exception:
                try:
                    # Create user if does not exist
                    auth.create_user(
                        uid=uid,
                        email=email,
                        password=padded_pw,
                        display_name=display_name
                    )
                except Exception as ce:
                    print(f"Error creating user {username} in Auth: {ce}")
            
            # Set Custom User Claims for role/metadata tracking
            auth.set_custom_user_claims(uid, {
                "role": role,
                "display_name": display_name,
                "class_id": class_id
            })
        except Exception as e:
            print(f"Error syncing user {username} to Firebase Auth: {e}")

    def _sync_all_users_to_auth(self):
        try:
            docs = self.db.collection("users").stream()
            count = 0
            for doc in docs:
                data = doc.to_dict()
                user_id = data.get("id")
                username = data.get("username")
                password = data.get("password", "123")
                display_name = data.get("display_name")
                role = data.get("role")
                class_id = data.get("class_id")
                if user_id and username:
                    self._sync_user_to_firebase_auth(user_id, username, password, display_name, role, class_id)
                    count += 1
            print(f"[FIRESTORE] Synced {count} users from Firestore to Auth.")
        except Exception as e:
            print(f"[FIRESTORE] Error syncing all users: {e}")

    def init_db(self):
        try:
            users_ref = self.db.collection("users").limit(1).get()
            if len(users_ref) == 0:
                print("[FIRESTORE] Seeding default data...")
                self.seed_data()
            else:
                # If Firestore is already populated, sync users to Auth Emulator (handling local emulator restarts)
                from firebase_admin import auth
                try:
                    auth_users = auth.list_users(max_results=1).users
                    if not auth_users:
                        print("[FIRESTORE] Auth Emulator is empty. Syncing users from Firestore...")
                        self._sync_all_users_to_auth()
                except Exception as ae:
                    print(f"[FIRESTORE] Error checking Auth users: {ae}")
        except Exception as e:
            print(f"[FIRESTORE] Error initializing database: {e}")

    def seed_data(self):
        try:
            # Classes
            self.db.collection("classes").document("1").set({"id": 1, "class_name": "10A1"})
            self.db.collection("classes").document("2").set({"id": 2, "class_name": "10A2"})
            self.db.collection("classes").document("3").set({"id": 3, "class_name": "10A3"})

            # Users in DB & Auth Emulator
            self.db.collection("users").document("1").set({
                "id": 1, "username": "admin", "password": "123", "display_name": "Quản trị viên", "role": "admin", "class_id": None, "student_id": None
            })
            self._sync_user_to_firebase_auth(1, "admin", "123", "Quản trị viên", "admin", None)

            self.db.collection("users").document("2").set({
                "id": 2, "username": "teacher", "password": "123", "display_name": "Thầy Minh", "role": "teacher", "class_id": 1, "student_id": None
            })
            self._sync_user_to_firebase_auth(2, "teacher", "123", "Thầy Minh", "teacher", 1)

            self.db.collection("users").document("3").set({
                "id": 3, "username": "hocsinh", "password": "123", "display_name": "Nguyễn Văn An", "role": "student", "class_id": 1, "student_id": None
            })
            self._sync_user_to_firebase_auth(3, "hocsinh", "123", "Nguyễn Văn An", "student", 1)

            self.db.collection("users").document("100").set({
                "id": 100, "username": "phuhuynh", "password": "123", "display_name": "Phụ huynh Nguyễn Văn An", "role": "parent", "class_id": None, "student_id": 3
            })
            self._sync_user_to_firebase_auth(100, "phuhuynh", "123", "Phụ huynh Nguyễn Văn An", "parent", None)

            mock_students_data = [
                ('diyasharma', '123', 'Trần Thị Bình', 'student', 1),
                ('rohanverma', '123', 'Lê Hoàng Giang', 'student', 1),
                ('ananyapatel', '123', 'Phạm Minh Hải', 'student', 1),
                ('vivaankapoor', '123', 'Vũ Tiến Khoa', 'student', 1),
                ('meeranair', '123', 'Ngô Khánh Linh', 'student', 1),
                ('arjunsingh', '123', 'Hoàng Đức Minh', 'student', 1),
                ('ishitayadav', '123', 'Bùi Thị Ngọc', 'student', 1),
                ('krishjain', '123', 'Đỗ Minh Quân', 'student', 1)
            ]
            for idx, (username, password, display_name, role, class_id) in enumerate(mock_students_data, start=4):
                self.db.collection("users").document(str(idx)).set({
                    "id": idx,
                    "username": username,
                    "password": password,
                    "display_name": display_name,
                    "role": role,
                    "class_id": class_id,
                    "student_id": None
                })
                self._sync_user_to_firebase_auth(idx, username, password, display_name, role, class_id)

            _seed_sessions_and_events(self.db, is_firestore=True)
            print("[FIRESTORE] Seeding data and Auth syncing completed.")
        except Exception as e:
            print(f"[FIRESTORE] Error seeding database: {e}")

    def get_classes_list(self):
        try:
            classes_ref = self.db.collection("classes").stream()
            classes = []
            for doc in classes_ref:
                data = doc.to_dict()
                classes.append({
                    "id": data.get("id"),
                    "class_name": data.get("class_name"),
                    "student_count": 0
                })
            
            users_ref = self.db.collection("users").where("role", "==", "student").stream()
            for doc in users_ref:
                data = doc.to_dict()
                class_id = data.get("class_id")
                if class_id is not None:
                    for c in classes:
                        if c["id"] == class_id:
                            c["student_count"] += 1
            classes.sort(key=lambda x: x["class_name"])
            return classes
        except Exception as e:
            print(f"Firestore error reading classes: {e}")
            return []

    def get_class_name(self, class_id):
        if class_id is None:
            return "Chưa gán lớp"
        try:
            doc = self.db.collection("classes").document(str(class_id)).get()
            if doc.exists:
                return doc.to_dict().get("class_name", "Chưa gán lớp")
            return "Chưa gán lớp"
        except Exception:
            return "Chưa gán lớp"

    def create_class(self, class_name):
        try:
            # Check unique
            exists = self.db.collection("classes").where("class_name", "==", class_name).limit(1).get()
            if len(exists) > 0:
                return False, "Tên lớp học đã tồn tại"
            
            new_id = self._get_next_id("classes")
            self.db.collection("classes").document(str(new_id)).set({
                "id": new_id,
                "class_name": class_name
            })
            return True, "Tạo lớp học thành công"
        except Exception as e:
            return False, str(e)

    def update_class(self, class_id, new_name):
        try:
            exists = self.db.collection("classes").where("class_name", "==", new_name).limit(1).get()
            for doc in exists:
                if doc.to_dict().get("id") != class_id:
                    return False, "Tên lớp học đã tồn tại"
            
            self.db.collection("classes").document(str(class_id)).update({
                "class_name": new_name
            })
            return True, "Cập nhật tên lớp học thành công"
        except Exception as e:
            return False, str(e)

    def delete_class(self, class_id):
        try:
            # Dissociate users
            users_ref = self.db.collection("users").where("class_id", "==", class_id).stream()
            for doc in users_ref:
                self.db.collection("users").document(doc.id).update({
                    "class_id": None
                })
            
            self.db.collection("classes").document(str(class_id)).delete()
            return True, "Xóa lớp học thành công"
        except Exception as e:
            return False, str(e)

    def get_users_list(self):
        try:
            classes_ref = self.db.collection("classes").stream()
            class_map = {data.get("id"): data.get("class_name") for doc in classes_ref for data in [doc.to_dict()] if "id" in data}
            
            users_ref = self.db.collection("users").stream()
            users = []
            for doc in users_ref:
                data = doc.to_dict()
                class_id = data.get("class_id")
                class_name = class_map.get(class_id, "N/A") if class_id is not None else "N/A"
                users.append({
                    "id": data.get("id"),
                    "username": data.get("username"),
                    "display_name": data.get("display_name"),
                    "role": data.get("role"),
                    "class_name": class_name,
                    "class_id": class_id,
                    "has_face": bool(data.get("face_embedding"))
                })
            users.sort(key=lambda x: (x["role"], x["display_name"]))
            return users
        except Exception as e:
            print(f"Firestore error reading users: {e}")
            return []

    def create_user(self, username, password, display_name, role, class_id, student_id=None):
        try:
            exists = self.db.collection("users").where("username", "==", username).limit(1).get()
            if len(exists) > 0:
                return False, "Tên đăng nhập đã tồn tại"
            
            new_id = self._get_next_id("users")
            c_id = int(class_id) if class_id and str(class_id).isdigit() else None
            s_id = int(student_id) if student_id and str(student_id).isdigit() else None
            
            self.db.collection("users").document(str(new_id)).set({
                "id": new_id,
                "username": username,
                "password": password,
                "display_name": display_name,
                "role": role,
                "class_id": c_id,
                "student_id": s_id
            })
            
            # Sync user to Firebase Auth Emulator
            self._sync_user_to_firebase_auth(new_id, username, password, display_name, role, c_id)
            
            return True, "Tạo tài khoản thành công"
        except Exception as e:
            return False, str(e)

    def update_user(self, user_id, username, password, display_name, role, class_id, student_id=None):
        try:
            exists = self.db.collection("users").where("username", "==", username).limit(1).get()
            for doc in exists:
                if doc.to_dict().get("id") != user_id:
                    return False, "Tên đăng nhập đã tồn tại"
            
            c_id = int(class_id) if class_id and str(class_id).isdigit() else None
            s_id = int(student_id) if student_id and str(student_id).isdigit() else None
            
            doc_ref = self.db.collection("users").document(str(user_id))
            update_data = {
                "username": username,
                "display_name": display_name,
                "role": role,
                "class_id": c_id,
                "student_id": s_id
            }
            if password and password.strip():
                update_data["password"] = password
            
            doc_ref.update(update_data)
            
            # Sync update to Firebase Auth Emulator
            pw_to_sync = password
            if not pw_to_sync or not pw_to_sync.strip():
                current_doc = doc_ref.get()
                if current_doc.exists:
                    pw_to_sync = current_doc.to_dict().get("password", "123")
                else:
                    pw_to_sync = "123"
            self._sync_user_to_firebase_auth(user_id, username, pw_to_sync, display_name, role, c_id)
            
            return True, "Cập nhật tài khoản thành công"
        except Exception as e:
            return False, str(e)

    def delete_user(self, user_id):
        try:
            self.db.collection("users").document(str(user_id)).delete()
            # Delete from Firebase Auth Emulator
            try:
                from firebase_admin import auth
                auth.delete_user(str(user_id))
            except Exception:
                pass
            return True, "Xóa tài khoản thành công"
        except Exception as e:
            return False, str(e)

    def save_face_embedding(self, user_id, embedding_json):
        try:
            doc_ref = self.db.collection("users").document(str(user_id))
            if doc_ref.get().exists:
                doc_ref.update({"face_embedding": embedding_json})
                return True
            else:
                docs = self.db.collection("users").where("id", "==", int(user_id)).stream()
                for doc in docs:
                    doc.reference.update({"face_embedding": embedding_json})
                return True
        except Exception as e:
            print(f"Error saving Firestore face embedding: {e}")
            return False

    def get_student_embeddings_by_class(self, class_id):
        try:
            users_ref = self.db.collection("users").where("role", "==", "student").where("class_id", "==", int(class_id)).stream()
            students = []
            for doc in users_ref:
                data = doc.to_dict()
                emb = data.get("face_embedding")
                if emb:
                    try:
                        embedding = json.loads(emb) if isinstance(emb, str) else emb
                        students.append({
                            "student_id": data.get("id"),
                            "full_name": data.get("display_name"),
                            "username": data.get("username"),
                            "embedding": embedding
                        })
                    except Exception:
                        pass
            return students
        except Exception as e:
            print(f"Error reading Firestore student embeddings: {e}")
            return []

    def authenticate_user(self, username, password):
        try:
            import urllib.request
            import urllib.error
            import json
            
            email = f"{username}@focusguard.ai"
            emulator_host = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
            url = f"http://{emulator_host}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=dummy-key"
            
            padded_pw = self._get_auth_password(password)
            payload = json.dumps({
                "email": email,
                "password": padded_pw,
                "returnSecureToken": True
            }).encode("utf-8")
            
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            try:
                with urllib.request.urlopen(req, timeout=5.0) as f:
                    res_body = f.read().decode("utf-8")
                    data = json.loads(res_body)
                    id_token = data.get("idToken")
                    
                # Verify token with firebase-admin SDK
                from firebase_admin import auth
                decoded_token = auth.verify_id_token(id_token)
                
                uid = int(decoded_token.get("uid"))
                
                # Fetch fields from custom claims
                display_name = decoded_token.get("display_name")
                role = decoded_token.get("role")
                class_id = decoded_token.get("class_id")
                
                # In case claims are empty, retrieve from DB
                if display_name is None or role is None:
                    db_user = self.get_user_by_id(uid)
                    if db_user:
                        display_name = db_user.get("display_name")
                        role = db_user.get("role")
                        class_id = db_user.get("class_id")
                
                return (uid, username, display_name, role, class_id)
            except Exception as ae:
                print(f"[FIRESTORE AUTH] Auth call failed for {username}: {ae}")
                # Fallback to local DB password check (only if emulator auth returns error)
                docs = self.db.collection("users").where("username", "==", username).where("password", "==", password).limit(1).stream()
                for doc in docs:
                    data = doc.to_dict()
                    uid = data.get("id")
                    # Dynamically register them in Firebase Auth
                    self._sync_user_to_firebase_auth(uid, username, password, data.get("display_name"), data.get("role"), data.get("class_id"))
                    return (uid, username, data.get("display_name"), data.get("role"), data.get("class_id"))
                return None
        except Exception as e:
            print(f"[FIRESTORE AUTH] Error during authentication: {e}")
            return None

    def get_students_by_role(self):
        try:
            docs = self.db.collection("users").where("role", "==", "student").stream()
            res = []
            for doc in docs:
                data = doc.to_dict()
                res.append((data.get("username"), data.get("display_name"), data.get("class_id")))
            return res
        except Exception:
            return []

    def get_student_id_for_parent(self, parent_id):
        try:
            doc = self.db.collection("users").document(str(parent_id)).get()
            if doc.exists:
                return doc.to_dict().get("student_id")
            return None
        except Exception:
            return None

    def get_user_by_id(self, user_id):
        try:
            doc = self.db.collection("users").document(str(user_id)).get()
            if doc.exists:
                data = doc.to_dict()
                return {"username": data.get("username"), "display_name": data.get("display_name"), "role": data.get("role"), "class_id": data.get("class_id")}
            return None
        except Exception:
            return None

    def create_session(self, user_id, start_time, subject=None):
        try:
            new_id = self._get_next_id("sessions")
            self.db.collection("sessions").document(str(new_id)).set({
                "id": new_id,
                "user_id": user_id,
                "start_time": start_time,
                "end_time": None,
                "duration_seconds": None,
                "final_score": None,
                "total_distractions": None,
                "history_json": None,
                "subject": subject or "Toán"
            })
            return new_id
        except Exception as e:
            print(f"Error creating session in Firestore: {e}")
            return None

    def update_session(self, session_id, end_time, duration_seconds, final_score, total_distractions, history_json):
        try:
            self.db.collection("sessions").document(str(session_id)).update({
                "end_time": end_time,
                "duration_seconds": duration_seconds,
                "final_score": final_score,
                "total_distractions": total_distractions,
                "history_json": history_json
            })
            return True
        except Exception as e:
            print(f"Error updating session in Firestore: {e}")
            return False

    def get_all_sessions(self, username=None):
        try:
            if username:
                # Find user first
                users_ref = self.db.collection("users").where("username", "==", username).limit(1).get()
                if len(users_ref) == 0:
                    return []
                user_id = users_ref[0].to_dict().get("id")
                docs = self.db.collection("sessions").where("user_id", "==", user_id).stream()
            else:
                docs = self.db.collection("sessions").stream()
                
            sessions = []
            for doc in docs:
                data = doc.to_dict()
                sessions.append({
                    "id": data.get("id"),
                    "start_time": data.get("start_time"),
                    "end_time": data.get("end_time"),
                    "duration_seconds": data.get("duration_seconds"),
                    "final_score": data.get("final_score"),
                    "total_distractions": data.get("total_distractions")
                })
            # Sort by ID desc
            sessions.sort(key=lambda x: x["id"], reverse=True)
            return sessions
        except Exception as e:
            print(f"Lỗi khi đọc lịch sử Firestore: {e}")
            return []

    def get_latest_session(self):
        try:
            docs = self.db.collection("sessions").stream()
            sessions = []
            for doc in docs:
                data = doc.to_dict()
                sessions.append(data)
            if sessions:
                sessions.sort(key=lambda x: x["id"], reverse=True)
                latest = sessions[0]
                return {
                    "start_time": latest.get("start_time"),
                    "end_time": latest.get("end_time"),
                    "duration_seconds": latest.get("duration_seconds"),
                    "final_score": latest.get("final_score"),
                    "total_distractions": latest.get("total_distractions")
                }
            return None
        except Exception as e:
            print(f"Lỗi khi lấy phiên mới nhất Firestore: {e}")
            return None

    def get_recommendations_data(self, username):
        try:
            users_ref = self.db.collection("users").where("username", "==", username).limit(1).get()
            if len(users_ref) == 0:
                return "Học sinh", []
            user_data = users_ref[0].to_dict()
            user_id = user_data.get("id")
            
            docs = self.db.collection("sessions").where("user_id", "==", user_id).stream()
            rows = []
            for doc in docs:
                data = doc.to_dict()
                rows.append((user_data.get("display_name"), data.get("final_score"), data.get("start_time"), data.get("id")))
            # sort by ID descending
            rows.sort(key=lambda x: x[3], reverse=True)
            # transform to tuple expected by helper
            res_rows = [(r[0], r[1], r[2]) for r in rows]
            return user_data.get("display_name"), res_rows
        except Exception:
            return "Học sinh", []

    def create_focus_event(self, session_id, event_type, timestamp):
        try:
            new_id = self._get_next_id("focus_events")
            self.db.collection("focus_events").document(str(new_id)).set({
                "id": new_id,
                "session_id": session_id,
                "type": event_type,
                "timestamp": timestamp
            })
            return True
        except Exception as e:
            print(f"Error logging focus event in Firestore: {e}")
            return False

    def create_class_session(self, class_id, started_at):
        try:
            new_id = self._get_next_id("class_sessions")
            # For started_at, format it as time string if float
            started_at_str = datetime.fromtimestamp(started_at).strftime("%Y-%m-%d %H:%M:%S") if isinstance(started_at, (int, float)) else started_at
            self.db.collection("class_sessions").document(str(new_id)).set({
                "id": new_id,
                "class_id": class_id,
                "started_at": started_at_str,
                "ended_at": None
            })
            return new_id
        except Exception as e:
            print(f"Error starting class session in Firestore: {e}")
            return None

    def update_class_session(self, class_session_id, ended_at):
        try:
            ended_at_str = datetime.fromtimestamp(ended_at).strftime("%Y-%m-%d %H:%M:%S") if isinstance(ended_at, (int, float)) else ended_at
            self.db.collection("class_sessions").document(str(class_session_id)).update({
                "ended_at": ended_at_str
            })
            return True
        except Exception as e:
            print(f"Error ending class session in Firestore: {e}")
            return False

    def get_daily_leaderboard(self, class_id):
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            cutoff = today + " 00:00:00"
            students = self.db.collection("users").where("class_id", "==", class_id).where("role", "==", "student").stream()
            student_map = {}
            for doc in students:
                data = doc.to_dict()
                student_map[data.get("id")] = data.get("display_name")
                
            if not student_map:
                return []
                
            sessions_ref = self.db.collection("sessions").where("start_time", ">=", cutoff).stream()
            scores_by_user = {}
            for doc in sessions_ref:
                data = doc.to_dict()
                u_id = data.get("user_id")
                final_score = data.get("final_score")
                if u_id in student_map and final_score is not None:
                    if u_id not in scores_by_user:
                        scores_by_user[u_id] = []
                    scores_by_user[u_id].append(final_score)
                    
            leaderboard = []
            for u_id, display_name in student_map.items():
                if u_id in scores_by_user:
                    avg_score = sum(scores_by_user[u_id]) / len(scores_by_user[u_id])
                    leaderboard.append({"display_name": display_name, "score": int(avg_score)})
                    
            leaderboard.sort(key=lambda x: x["score"], reverse=True)
            return leaderboard
        except Exception as e:
            print(f"Error getting daily leaderboard Firestore: {e}")
            return []

    def get_student_heatmap_data(self, user_id, days=7):
        try:
            import datetime as dt_mod
            cutoff = (dt_mod.datetime.now() - dt_mod.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            docs = self.db.collection("sessions").where("user_id", "==", user_id).where("start_time", ">=", cutoff).stream()
            
            hour_scores = {}
            for doc in docs:
                data = doc.to_dict()
                final_score = data.get("final_score")
                start_time_str = data.get("start_time")
                if final_score is not None and start_time_str:
                    try:
                        dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                        hour = dt.hour
                        if hour not in hour_scores:
                            hour_scores[hour] = []
                        hour_scores[hour].append(final_score)
                    except Exception:
                        pass
                        
            result = {}
            for hour_num in range(8, 23): # 08:00 to 22:00
                result[f"{hour_num:02d}:00"] = {"score": None, "status": "none"}
                
            for hour, scores in hour_scores.items():
                hour_str = f"{hour:02d}:00"
                if hour_str in result:
                    score = int(sum(scores) / len(scores))
                    status = "high" if score >= 80 else ("med" if score >= 50 else "low")
                    result[hour_str] = {"score": score, "status": status}
            return result
        except Exception as e:
            print(f"Error getting heatmap data Firestore: {e}")
            return {}

    def get_session_distraction_breakdown(self, session_id):
        try:
            docs = self.db.collection("focus_events").where("session_id", "==", session_id).stream()
            counts = {
                "phone": 0,
                "drowsy": 0,
                "distracted": 0,
                "multiple_people": 0
            }
            for doc in docs:
                data = doc.to_dict()
                t = data.get("type", "")
                if "điện thoại" in t.lower():
                    counts["phone"] += 1
                elif "buồn ngủ" in t.lower() or "ngủ gật" in t.lower():
                    counts["drowsy"] += 1
                elif "ngoảnh mặt" in t.lower() or "mất tập trung" in t.lower():
                    counts["distracted"] += 1
                elif "nhiều người" in t.lower():
                    counts["multiple_people"] += 1
            return counts
        except Exception as e:
            print(f"Error getting session breakdown Firestore: {e}")
            return {"phone": 0, "drowsy": 0, "distracted": 0, "multiple_people": 0}

    def get_classroom_watchlist(self, class_id):
        try:
            students = self.db.collection("users").where("class_id", "==", class_id).where("role", "==", "student").stream()
            student_map = {}
            for doc in students:
                data = doc.to_dict()
                student_map[data.get("id")] = data.get("display_name")
                
            if not student_map:
                return []
                
            docs = self.db.collection("sessions").stream()
            user_scores = {}
            for doc in docs:
                data = doc.to_dict()
                u_id = data.get("user_id")
                final_score = data.get("final_score")
                if u_id in student_map and final_score is not None:
                    if u_id not in user_scores:
                        user_scores[u_id] = []
                    user_scores[u_id].append(final_score)
                    
            watchlist = []
            for u_id, display_name in student_map.items():
                if u_id in user_scores:
                    avg_score = sum(user_scores[u_id]) / len(user_scores[u_id])
                    if avg_score < 70:
                        watchlist.append({"id": u_id, "display_name": display_name, "score": int(avg_score)})
                        
            watchlist.sort(key=lambda x: x["score"])
            return watchlist
        except Exception as e:
            print(f"Error getting watchlist Firestore: {e}")
            return []

    def get_classroom_danger_hour(self, class_id):
        try:
            students = self.db.collection("users").where("class_id", "==", class_id).where("role", "==", "student").stream()
            student_ids = {doc.to_dict().get("id") for doc in students}
            
            if not student_ids:
                return "Chưa có dữ liệu"
                
            docs = self.db.collection("sessions").stream()
            hour_scores = {}
            for doc in docs:
                data = doc.to_dict()
                u_id = data.get("user_id")
                final_score = data.get("final_score")
                start_time_str = data.get("start_time")
                if u_id in student_ids and final_score is not None and start_time_str:
                    try:
                        dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                        hour = dt.hour
                        if hour not in hour_scores:
                            hour_scores[hour] = []
                        hour_scores[hour].append(final_score)
                    except Exception:
                        pass
                        
            if not hour_scores:
                return "Chưa có dữ liệu"
                
            worst_hour = min(hour_scores.keys(), key=lambda h: sum(hour_scores[h])/len(hour_scores[h]))
            return f"{worst_hour:02d}:00 - {(worst_hour+1)%24:02d}:00"
        except Exception as e:
            print(f"Error getting danger hour Firestore: {e}")
            return "Chưa có dữ liệu"

    def get_student_subject_analytics(self, user_id):
        try:
            docs = self.db.collection("sessions").where("user_id", "==", user_id).stream()
            sub_scores = {}
            for doc in docs:
                data = doc.to_dict()
                final_score = data.get("final_score")
                subject = data.get("subject", "Toán")
                if final_score is not None:
                    if subject not in sub_scores:
                        sub_scores[subject] = []
                    sub_scores[subject].append(final_score)
            
            result = []
            for sub, scores in sub_scores.items():
                result.append({"subject": sub, "score": int(sum(scores)/len(scores))})
            return result
        except Exception as e:
            print(f"Error getting subject analytics Firestore: {e}")
            return []

    def get_student_profile_stats(self, user_id):
        try:
            docs = self.db.collection("sessions").where("user_id", "==", user_id).stream()
            scores = []
            durations = []
            sessions_list = []
            
            for doc in docs:
                data = doc.to_dict()
                final_score = data.get("final_score")
                duration = data.get("duration_seconds")
                s_id = data.get("id")
                if final_score is not None:
                    scores.append(final_score)
                    durations.append(duration or 0)
                    sessions_list.append((s_id, final_score))
            
            total_sessions = len(scores)
            total_duration = sum(durations)
            avg_score = int(sum(scores)/len(scores)) if scores else 100
            
            sessions_list.sort(key=lambda x: x[0], reverse=True)
            trend = "stable"
            if len(sessions_list) >= 2:
                recent_scores = [x[1] for x in sessions_list[:3]]
                older_scores = [x[1] for x in sessions_list[3:6]]
                recent_avg = sum(recent_scores) / len(recent_scores)
                older_avg = sum(older_scores) / len(older_scores) if older_scores else recent_avg
                if recent_avg - older_avg > 2:
                    trend = "up"
                elif older_avg - recent_avg > 2:
                    trend = "down"
                    
            return {
                "total_sessions": total_sessions,
                "total_duration_seconds": total_duration,
                "average_focus_score": avg_score,
                "trend": trend
            }
        except Exception as e:
            print(f"Error getting profile stats Firestore: {e}")
            return {"total_sessions": 0, "total_duration_seconds": 0, "average_focus_score": 100, "trend": "stable"}

    def get_session_comparison(self, user_id, limit=5):
        try:
            docs = self.db.collection("sessions").where("user_id", "==", user_id).stream()
            sessions = []
            for doc in docs:
                data = doc.to_dict()
                final_score = data.get("final_score")
                if final_score is not None:
                    sessions.append({
                        "id": data.get("id"),
                        "start_time": data.get("start_time"),
                        "score": final_score,
                        "subject": data.get("subject", "Toán")
                    })
            
            sessions.sort(key=lambda x: x["id"], reverse=True)
            subset = sessions[:limit]
            subset.reverse()
            return subset
        except Exception as e:
            print(f"Error getting session comparison Firestore: {e}")
            return []



def get_repository():
    db_type = os.environ.get("DATABASE_TYPE", "firestore")
    use_emulator = os.environ.get("USE_EMULATOR", "true").lower() == "true"
    
    if db_type == "firestore":
        if use_emulator:
            if "FIRESTORE_EMULATOR_HOST" not in os.environ:
                os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
            if "FIREBASE_AUTH_EMULATOR_HOST" not in os.environ:
                os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "127.0.0.1:9099"
        else:
            # Clear emulator variables for production config
            os.environ.pop("FIRESTORE_EMULATOR_HOST", None)
            os.environ.pop("FIREBASE_AUTH_EMULATOR_HOST", None)
            
        print(f"[DATABASE] Using Firestore Repository (Emulator={use_emulator})")
        return FirestoreRepository()
    else:
        print("[DATABASE] Using SQLite Repository")
        return SQLiteRepository()
