import os
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

from flask import Flask, render_template, Response, jsonify, session, redirect, url_for, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from camera_ai import FocusAI
from session_manager import SessionManager
import threading
import os
import json
import time

app = Flask(__name__)
app.secret_key = 'focusguard_ai_secret_key'

# Initialize SocketIO with eventlet for proper async support
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=False, engineio_logger=False)

# Global instances
session_manager = SessionManager()
camera_ai = None
camera_lock = threading.Lock()
camera_init_lock = threading.Lock()

def get_camera():
    global camera_ai
    with camera_init_lock:
        if camera_ai is None:
            if getattr(session_manager, 'offline_class_active', False):
                from classroom_ai import ClassroomAI
                class_id = getattr(session_manager, 'offline_class_id', 1)
                camera_ai = ClassroomAI(session_manager, class_id=class_id)
            else:
                camera_ai = FocusAI(session_manager)
    return camera_ai

def release_camera():
    global camera_ai
    with camera_init_lock:
        if camera_ai is not None:
            try:
                camera_ai.release()
                print("[CAMERA] Camera released successfully.")
            except Exception as e:
                print("[CAMERA] Error releasing camera:", e)
            camera_ai = None

def generate_frames():
    cam = get_camera()
    last_emit_time = 0
    last_frame_push_time = 0  # Track when we last pushed a frame snapshot
    FRAME_PUSH_INTERVAL = 3.0  # Push frame every 3 seconds
    try:
        while True:
            # Throttle the loop to target ~20 fps and yield control to eventlet scheduler
            socketio.sleep(0.05)
            with camera_lock:
                frame, is_alert, alert_text = cam.get_frame()
                if frame is None:
                    continue
            
            if getattr(session_manager, 'offline_class_active', False):
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                continue
            
            current_state = cam.current_state
            # Map camera state to display state
            state_map = {
                'DUNG DIEN THOAI': 'Phone',
                'BUON NGU': 'Sleepy',
                'NGOANH MAT DI': 'Distracted',
                'KHONG THAY KHUON MAT': 'Distracted',
                'TAP TRUNG': 'Focused'
            }
            display_state = state_map.get(current_state, 'Normal')
            focus_score = int(session_manager.focus_score)
            student_name = session_manager.current_student_name or 'Nguyễn Văn An'
            
            # Update session_manager mock_students directly on server for polling accuracy
            if student_name in session_manager.mock_students:
                student = session_manager.mock_students[student_name]
                student['state'] = display_state
                student['focus_score'] = focus_score
                student['distractions'] = session_manager.distractions
                student['online'] = True
                
                # Keep history updated
                if len(student.get('focus_history', [])) == 0 or student['focus_history'][-1] != focus_score:
                    student['focus_history'].append(focus_score)
                    if len(student['focus_history']) > 10:
                        student['focus_history'].pop(0)

            # Push WebSocket event to rooms every 1 second (independent of state changes)
            now = time.time()
            if (now - last_emit_time) >= 1.0:
                last_emit_time = now
                stats = session_manager.get_stats()
                
                # Emit to teacher room with student data update
                socketio.emit('student_update', {
                    'name': student_name,
                    'state': display_state,
                    'focus_score': focus_score,
                    'distractions': session_manager.distractions,
                    'online': True,
                    'emotion': stats.get('current_emotion', 'Neutral'),
                    'emotion_icon': stats.get('emotion_icon', '😐'),
                    'emotion_confidence': stats.get('emotion_confidence', 90),
                    'emotion_history': stats.get('emotion_history', ['Neutral'])
                }, room='teachers')
                
                # Also emit to the student's own room for their dashboard
                student_room = f"student_{student_name}"
                socketio.emit('my_stats_update', {
                    'focus_score': focus_score,
                    'state': display_state,
                    'distractions': session_manager.distractions
                }, room=student_room)

            # -------------------------------------------------------
            # Server-side frame snapshot: push to teachers every 3s
            # -------------------------------------------------------
            if (now - last_frame_push_time) >= FRAME_PUSH_INTERVAL and session_manager.is_active:
                last_frame_push_time = now
                try:
                    import base64
                    # frame is already a JPEG-encoded bytes object from cam.get_frame()
                    frame_b64 = base64.b64encode(frame).decode('utf-8')
                    socketio.emit('student_frame', {
                        'name': student_name,
                        'frame': f'data:image/jpeg;base64,{frame_b64}'
                    }, room='teachers')
                except Exception as fe:
                    pass  # Never let frame push crash the stream
                
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    except GeneratorExit:
        print("[CAMERA] Browser disconnected from feed.")
    finally:
        release_camera()

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    role = session.get('role', 'student')
    if role == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    elif role == 'admin':
        return redirect(url_for('admin_root'))
    return render_template('index.html', active_tab='dashboard')

@app.route('/stats')
def stats():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', active_tab='stats')

@app.route('/alerts')
def alerts():
    return redirect(url_for('reports'))

@app.route('/reports')
def reports():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', active_tab='reports')

@app.route('/settings')
def settings():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', active_tab='settings')

# --- Teacher Routes ---
def get_teacher_details():
    class_id = session.get('class_id')
    teacher_name = session.get('display_name', 'Giáo viên')
    class_name = session_manager.repo.get_class_name(class_id)
    return teacher_name, class_name

@app.route('/teacher/dashboard')
def teacher_dashboard():
    if 'user' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    teacher_name, class_name = get_teacher_details()
    return render_template('teacher_dashboard.html', active_tab='dashboard', teacher_name=teacher_name, class_name=class_name)

@app.route('/teacher/students')
def teacher_students():
    if 'user' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    teacher_name, class_name = get_teacher_details()
    return render_template('teacher_dashboard.html', active_tab='students', teacher_name=teacher_name, class_name=class_name)

@app.route('/teacher/analytics')
def teacher_analytics():
    if 'user' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    teacher_name, class_name = get_teacher_details()
    return render_template('teacher_dashboard.html', active_tab='analytics', teacher_name=teacher_name, class_name=class_name)

@app.route('/teacher/reports')
def teacher_reports():
    if 'user' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    teacher_name, class_name = get_teacher_details()
    return render_template('teacher_dashboard.html', active_tab='reports', teacher_name=teacher_name, class_name=class_name)

@app.route('/teacher/alerts')
def teacher_alerts():
    if 'user' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    teacher_name, class_name = get_teacher_details()
    return render_template('teacher_dashboard.html', active_tab='alerts', teacher_name=teacher_name, class_name=class_name)

@app.route('/teacher/settings')
def teacher_settings():
    if 'user' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    teacher_name, class_name = get_teacher_details()
    return render_template('teacher_dashboard.html', active_tab='settings', teacher_name=teacher_name, class_name=class_name)

@app.route('/teacher/attendance')
def teacher_attendance():
    if 'user' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    teacher_name, class_name = get_teacher_details()
    return render_template('teacher_dashboard.html', active_tab='attendance', teacher_name=teacher_name, class_name=class_name)

@app.route('/api/teacher/class_status')
def api_class_status():
    if 'user' not in session or session.get('role') != 'teacher':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    
    # Sync active student camera state to session manager
    global camera_ai
    if camera_ai is not None:
        session_manager.current_state = camera_ai.current_state
    else:
        session_manager.current_state = "TAP TRUNG"
        
    class_id = session.get('class_id')
    students = session_manager.get_class_status(class_id)
    
    elapsed = 0
    if session_manager.class_session_active and session_manager.class_session_start_time:
        elapsed = int(time.time() - session_manager.class_session_start_time)
        
    return jsonify({
        "status": "success",
        "students": students,
        "class_session_active": session_manager.class_session_active,
        "elapsed_seconds": elapsed
    })

@app.route('/api/teacher/start_class', methods=['POST'])
def start_class():
    if 'user' not in session or session.get('role') != 'teacher':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    class_id = session.get('class_id', 1)
    session_manager.start_class_session(class_id)
    # Broadcast class started to all connected clients
    socketio.emit('class_started', {'message': 'Giáo viên đã bắt đầu lớp học'}, room='students')
    return jsonify({"status": "success", "message": "Lớp học đã bắt đầu."})

@app.route('/api/teacher/end_class', methods=['POST'])
def end_class():
    if 'user' not in session or session.get('role') != 'teacher':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    session_manager.end_class_session()
    socketio.emit('class_ended', {'message': 'Giáo viên đã kết thúc lớp học'}, room='students')
    return jsonify({"status": "success", "message": "Lớp học đã kết thúc."})

@app.route('/api/teacher/offline_classroom_status')
def api_offline_classroom_status():
    if 'user' not in session or session.get('role') != 'teacher':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    class_id = session.get('class_id', 1)
    req_class_id = request.args.get('class_id')
    if req_class_id:
        try:
            class_id = int(req_class_id)
        except ValueError:
            pass
    data = session_manager.get_offline_classroom_data(class_id)
    return jsonify({
        "status": "success",
        **data
    })

@app.route('/api/teacher/start_offline_class', methods=['POST'])
def start_offline_class():
    if 'user' not in session or session.get('role') != 'teacher':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    class_id = session.get('class_id', 1)
    session_manager.start_offline_class_session(class_id)
    release_camera()
    return jsonify({"status": "success", "message": "Lớp học trực tiếp đã bắt đầu giám sát."})

@app.route('/api/teacher/end_offline_class', methods=['POST'])
def end_offline_class():
    if 'user' not in session or session.get('role') != 'teacher':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    session_manager.end_offline_class_session()
    release_camera()
    return jsonify({"status": "success", "message": "Lớp học trực tiếp đã kết thúc giám sát."})

@app.route('/api/teacher/logs')
def api_teacher_logs():
    if 'user' not in session or session.get('role') != 'teacher':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    return jsonify(session_manager.activity_logs)

@app.route('/api/teacher/settings', methods=['POST'])
def save_teacher_settings():
    if 'user' not in session or session.get('role') != 'teacher':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    
    data = request.get_json() or {}
    display_name = data.get('display_name', '').strip()
    
    if not display_name:
        return jsonify({"status": "error", "message": "Tên giáo viên không được để trống."}), 400
        
    try:
        user_id = session.get('user_id')
        user_info = session_manager.repo.get_user_by_id(user_id)
        if not user_info:
            return jsonify({"status": "error", "message": "Không tìm thấy người dùng."}), 404
            
        success, msg = session_manager.repo.update_user(
            user_id=user_id,
            username=user_info.get('username'),
            password=None,
            display_name=display_name,
            role=user_info.get('role'),
            class_id=user_info.get('class_id')
        )
        if not success:
            return jsonify({"status": "error", "message": msg}), 400
        
        # Update current session variables
        session['display_name'] = display_name
        
        # Save threshold in session manager settings
        min_focus = int(data.get('min_focus_threshold', 65))
        if not hasattr(session_manager, 'settings') or session_manager.settings is None:
            session_manager.settings = {}
        session_manager.settings['min_focus_threshold'] = min_focus
        
        return jsonify({"status": "success", "message": "Cấu hình đã được lưu thành công!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Admin Routes ---
@app.route('/admin')
@app.route('/admin/')
@app.route('/admin/dashboard')
def admin_root():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return redirect(url_for('admin_accounts'))

@app.route('/admin/accounts')
def admin_accounts():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html', active_tab='accounts')

@app.route('/admin/classes')
def admin_classes_page():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html', active_tab='classes')

@app.route('/api/admin/classes')
def admin_classes():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    return jsonify(session_manager.get_classes_list())

@app.route('/api/admin/users')
def admin_users():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    return jsonify(session_manager.get_users_list())

@app.route('/api/admin/create_class', methods=['POST'])
def admin_create_class():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    data = request.get_json() or {}
    class_name = data.get('class_name', '').strip()
    if not class_name:
        return jsonify({"status": "error", "message": "Tên lớp không được trống"}), 400
    success, msg = session_manager.create_class(class_name)
    return jsonify({"status": "success" if success else "error", "message": msg})

@app.route('/api/admin/edit_class/<int:class_id>', methods=['POST'])
def admin_edit_class(class_id):
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    data = request.get_json() or {}
    class_name = data.get('class_name', '').strip()
    if not class_name:
        return jsonify({"status": "error", "message": "Tên lớp không được trống"}), 400
    success, msg = session_manager.update_class(class_id, class_name)
    return jsonify({"status": "success" if success else "error", "message": msg})

@app.route('/api/admin/delete_class/<int:class_id>', methods=['POST', 'DELETE'])
def admin_delete_class(class_id):
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    success, msg = session_manager.delete_class(class_id)
    return jsonify({"status": "success" if success else "error", "message": msg})

@app.route('/api/admin/create_user', methods=['POST'])
def admin_create_user():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    display_name = data.get('display_name', '').strip()
    role = data.get('role', '').strip()
    class_id = data.get('class_id', None)
    
    if not username or not password or not display_name or not role:
        return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ thông tin"}), 400
        
    success, msg = session_manager.create_user(username, password, display_name, role, class_id)
    return jsonify({"status": "success" if success else "error", "message": msg})

@app.route('/api/admin/edit_user/<int:user_id>', methods=['POST'])
def admin_edit_user(user_id):
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    display_name = data.get('display_name', '').strip()
    role = data.get('role', '').strip()
    class_id = data.get('class_id', None)
    
    if not username or not display_name or not role:
        return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ thông tin"}), 400
        
    success, msg = session_manager.update_user(user_id, username, password, display_name, role, class_id)
    return jsonify({"status": "success" if success else "error", "message": msg})

@app.route('/api/admin/delete_user/<int:user_id>', methods=['POST', 'DELETE'])
def admin_delete_user(user_id):
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    success, msg = session_manager.delete_user(user_id)
    return jsonify({"status": "success" if success else "error", "message": msg})

@app.route('/api/admin/register_face', methods=['POST'])
def admin_register_face():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    
    data = request.get_json() or {}
    user_id = data.get("user_id")
    images_base64 = data.get("images", [])
    
    if not user_id or not images_base64:
        return jsonify({"status": "error", "message": "Thiếu thông tin user_id hoặc hình ảnh"}), 400
        
    import base64
    import numpy as np
    import cv2
    
    images_list = []
    for idx, img_b64 in enumerate(images_base64):
        try:
            if ',' in img_b64:
                img_b64 = img_b64.split(',')[1]
            nparr = np.frombuffer(base64.b64decode(img_b64), np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                images_list.append(img)
        except Exception as e:
            print(f"Error decoding image {idx}: {e}")
            
    if not images_list:
        return jsonify({"status": "error", "message": "Không có hình ảnh hợp lệ để trích xuất"}), 400
        
    from face_recognition import FaceRecognizer
    try:
        recognizer = FaceRecognizer()
        embedding = recognizer.register_student(images_list)
        if embedding is None:
            return jsonify({"status": "error", "message": "Không phát hiện thấy khuôn mặt rõ ràng trong các bức ảnh"}), 400
            
        success = session_manager.repo.save_face_embedding(user_id, json.dumps(embedding))
        if success:
            # Crop the face of the first image to save as avatar portrait
            try:
                import os
                first_img = images_list[0]
                faces_detected = recognizer.app.get(first_img)
                if len(faces_detected) > 0:
                    largest_face = max(faces_detected, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
                    fx1, fy1, fx2, fy2 = map(int, largest_face.bbox)
                    fw = fx2 - fx1
                    fh = fy2 - fy1
                    # Add margin for portrait padding
                    ax1 = max(0, fx1 - fw // 4)
                    ay1 = max(0, fy1 - fh // 4)
                    ax2 = min(first_img.shape[1], fx2 + fw // 4)
                    ay2 = min(first_img.shape[0], fy2 + fh // 4)
                    
                    cropped_avatar = first_img[ay1:ay2, ax1:ax2]
                    avatar_dir = os.path.join(app.static_folder, 'uploads', 'avatars')
                    os.makedirs(avatar_dir, exist_ok=True)
                    avatar_path = os.path.join(avatar_dir, f'student_{user_id}.jpg')
                    cv2.imwrite(avatar_path, cropped_avatar)
                    print(f"[REGISTER FACE] Saved cropped avatar to {avatar_path}")
            except Exception as ae:
                print(f"Error saving cropped avatar: {ae}")

            global camera_ai
            if camera_ai is not None and hasattr(camera_ai, 'known_students'):
                camera_ai.known_students = session_manager.repo.get_student_embeddings_by_class(camera_ai.class_id)
            return jsonify({"status": "success", "message": "Đăng ký khuôn mặt thành công. Đã trích xuất đặc trưng."})
        else:
            return jsonify({"status": "error", "message": "Không thể lưu đặc trưng vào cơ sở dữ liệu"}), 500
    except Exception as ex:
        print(f"Face registration exception: {ex}")
        return jsonify({"status": "error", "message": f"Lỗi xử lý trích xuất: {str(ex)}"}), 500

@app.route('/api/admin/reset_face', methods=['POST'])
def admin_reset_face():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    
    data = request.get_json() or {}
    user_id = data.get("user_id")
    
    if not user_id:
        return jsonify({"status": "error", "message": "Thiếu thông tin user_id"}), 400
        
    success = session_manager.repo.save_face_embedding(user_id, None)
    if success:
        # Delete avatar file if exists
        try:
            import os
            avatar_path = os.path.join(app.static_folder, 'uploads', 'avatars', f'student_{user_id}.jpg')
            if os.path.exists(avatar_path):
                os.remove(avatar_path)
                print(f"[RESET FACE] Deleted avatar at {avatar_path}")
        except Exception as de:
            print(f"Error deleting avatar: {de}")

        global camera_ai
        if camera_ai is not None and hasattr(camera_ai, 'known_students'):
            camera_ai.known_students = session_manager.repo.get_student_embeddings_by_class(camera_ai.class_id)
        return jsonify({"status": "success", "message": "Đã xóa dữ liệu khuôn mặt thành công."})
    else:
        return jsonify({"status": "error", "message": "Không thể xóa dữ liệu khuôn mặt khỏi cơ sở dữ liệu"}), 500

@app.route('/api/admin/detect_face', methods=['POST'])
def admin_detect_face():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    
    data = request.get_json() or {}
    img_b64 = data.get("image")
    if not img_b64:
        return jsonify({"status": "error", "message": "Thiếu dữ liệu hình ảnh"}), 400
        
    import base64
    import numpy as np
    import cv2
    
    try:
        if ',' in img_b64:
            img_b64 = img_b64.split(',')[1]
        nparr = np.frombuffer(base64.b64decode(img_b64), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"status": "error", "message": "Ảnh không hợp lệ"}), 400
            
        from face_recognition import FaceRecognizer
        recognizer = FaceRecognizer()
        faces = recognizer.app.get(img)
        
        if len(faces) == 0:
            return jsonify({"status": "no_face", "message": "Không tìm thấy khuôn mặt"})
            
        # Get largest face
        largest_face = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
        fx1, fy1, fx2, fy2 = map(int, largest_face.bbox)
        
        # Quality check: min size 80x80 px
        fw = fx2 - fx1
        fh = fy2 - fy1
        if fw < 80 or fh < 80:
            return jsonify({"status": "low_quality", "message": "Khuôn mặt quá nhỏ hoặc quá xa camera"})
            
        # Crop face region
        ax1 = max(0, fx1 - fw // 4)
        ay1 = max(0, fy1 - fh // 4)
        ax2 = min(img.shape[1], fx2 + fw // 4)
        ay2 = min(img.shape[0], fy2 + fh // 4)
        cropped = img[ay1:ay2, ax1:ax2]
        
        _, buffer = cv2.imencode('.jpg', cropped)
        cropped_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            "status": "success",
            "cropped_image": f"data:image/jpeg;base64,{cropped_b64}"
        })
    except Exception as e:
        print(f"Error in detect_face: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Authentication ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        role = session.get('role')
        if role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        elif role == 'admin':
            return redirect(url_for('admin_root'))
        elif role == 'parent':
            return redirect(url_for('parent_dashboard'))
        return redirect(url_for('index'))
        
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = session_manager.repo.authenticate_user(username, password)
        
        if user:
            session['user'] = user[1]
            session['user_id'] = user[0]
            session['display_name'] = user[2]
            session['role'] = user[3]
            session['class_id'] = user[4]
            
            if user[3] == 'admin':
                return redirect(url_for('admin_root'))
            elif user[3] == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            elif user[3] == 'parent':
                return redirect(url_for('parent_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            error = 'Tên đăng nhập hoặc mật khẩu không đúng!'
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/parent/dashboard')
def parent_dashboard():
    if 'user' not in session or session.get('role') != 'parent':
        return redirect(url_for('login'))
        
    user_id = session.get('user_id')
    student_id = session_manager.repo.get_student_id_for_parent(user_id)
    
    student_name = "Nguyễn Văn An"
    student_username = "hocsinh"
    student_user_id = 3
    if student_id:
        student_user_id = student_id
        s_info = session_manager.repo.get_user_by_id(student_id)
        if s_info:
            student_username = s_info.get("username", "hocsinh")
            student_name = s_info.get("display_name", "Nguyễn Văn An")
    
    stats = session_manager.get_stats()
    recs = session_manager.get_recommendations(student_username)
    profile_stats = session_manager.repo.get_student_profile_stats(student_user_id)
    heatmap_data = session_manager.repo.get_student_heatmap_data(student_user_id)
    comparison = session_manager.repo.get_session_comparison(student_user_id, limit=7)
    
    return render_template(
        'parent_dashboard.html',
        student_name=student_name,
        stats=stats,
        recommendations=recs,
        profile_stats=profile_stats,
        heatmap_data=heatmap_data,
        comparison=comparison
    )

@app.route('/mobile')
def mobile_simulator():
    return render_template('mobile_simulator.html')

@app.route('/api/teacher/interventions')
def api_teacher_interventions():
    if 'user' not in session or session.get('role') != 'teacher':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
        
    class_id = session.get('class_id')
    students = session_manager.get_class_status(class_id)
    
    avg_score = 100
    if len(students) > 0:
        avg_score = sum(s.get("focus_score", 100) for s in students) / len(students)
        
    needs_intervention = avg_score < 75.0
    recommendations = []
    message = "Lớp học đang tập trung tốt."
    
    if needs_intervention:
        message = f"Cảnh báo: Lớp học đang giảm tập trung! Điểm trung bình chỉ đạt {int(avg_score)}."
        recommendations = [
            {"action": "Cho lớp nghỉ giải lao 5 phút", "icon": "fa-circle-pause"},
            {"action": "Đặt câu hỏi tương tác để khuấy động lớp học", "icon": "fa-circle-question"}
        ]
        
    return jsonify({
        "status": "success",
        "average_score": int(avg_score),
        "needs_intervention": needs_intervention,
        "message": message,
        "recommendations": recommendations
    })

@app.route('/api/student/recommendations')
def api_student_recommendations():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    username = session.get('user')
    recs = session_manager.get_recommendations(username)
    return jsonify(recs)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/stats')
def get_stats():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    stats = session_manager.get_stats()
    global camera_ai
    stats["current_state"] = camera_ai.current_state if camera_ai is not None else "TAP TRUNG"
    return jsonify(stats)

@app.route('/api/start_session', methods=['POST'])
def start_session():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    data = request.get_json() or {}
    subject = data.get("subject", "Toán")
    session_manager.start_session(session.get('user_id'), subject=subject)
    return jsonify({"status": "success", "message": "Session started"})

@app.route('/api/stop_session', methods=['POST'])
def stop_session():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    session_manager.stop_session(session.get('user_id'))
    return jsonify({"status": "success", "message": "Session stopped"})

@app.route('/api/leaderboard')
def api_leaderboard():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    class_id = session.get('class_id') or 1
    leaderboard = session_manager.repo.get_daily_leaderboard(class_id)
    return jsonify(leaderboard)

@app.route('/api/student/heatmap')
def api_student_heatmap():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    user_id = session.get('user_id')
    heatmap = session_manager.repo.get_student_heatmap_data(user_id)
    return jsonify(heatmap)

@app.route('/api/session/<int:session_id>/breakdown')
def api_session_breakdown(session_id):
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    breakdown = session_manager.repo.get_session_distraction_breakdown(session_id)
    return jsonify(breakdown)

@app.route('/api/student/subject_analytics')
def api_student_subject_analytics():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    user_id = session.get('user_id')
    analytics = session_manager.repo.get_student_subject_analytics(user_id)
    return jsonify(analytics)

@app.route('/api/student/profile')
def api_student_profile():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    user_id = session.get('user_id')
    profile = session_manager.repo.get_student_profile_stats(user_id)
    return jsonify(profile)

@app.route('/api/student/session_comparison')
def api_student_session_comparison():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    user_id = session.get('user_id')
    comparison = session_manager.repo.get_session_comparison(user_id)
    return jsonify(comparison)

@app.route('/api/teacher/analytics_summary')
def api_teacher_analytics_summary():
    if 'user' not in session or session.get('role') != 'teacher':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    class_id = session.get('class_id') or 1
    watchlist = session_manager.repo.get_classroom_watchlist(class_id)
    danger_hour = session_manager.repo.get_classroom_danger_hour(class_id)
    students = session_manager.get_class_status(class_id)
    
    avg_score = 100
    if len(students) > 0:
        avg_score = sum(s.get("focus_score", 100) for s in students) / len(students)
        
    total_phone = 0
    total_drowsy = 0
    total_distracted = 0
    for s in students:
        state = s.get("state", "Focused")
        if state == "Distracted":
            total_distracted += 3
        elif state == "Sleepy":
            total_drowsy += 3
        elif state == "Phone":
            total_phone += 3
        dist = s.get("distractions", 0)
        total_phone += int(dist * 0.3)
        total_drowsy += int(dist * 0.3)
        total_distracted += int(dist * 0.4)
        
    if total_phone == 0 and total_drowsy == 0 and total_distracted == 0:
        total_phone = 5
        total_drowsy = 3
        total_distracted = 12
        
    total = total_phone + total_drowsy + total_distracted
    breakdown = {
        "phone_pct": int((total_phone / total) * 100),
        "drowsy_pct": int((total_drowsy / total) * 100),
        "distracted_pct": int((total_distracted / total) * 100)
    }
    
    return jsonify({
        "status": "success",
        "average_score": int(avg_score),
        "danger_hour": danger_hour,
        "watchlist": watchlist,
        "root_cause": breakdown
    })

@app.route('/api/teacher/class_summary')
def api_teacher_class_summary():
    if 'user' not in session or session.get('role') != 'teacher':
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    class_id = session.get('class_id') or 1
    students = session_manager.get_class_status(class_id)
    if not students:
        return jsonify({"status": "empty"})
        
    avg_score = int(sum(s.get("focus_score", 100) for s in students) / len(students))
    sorted_students = sorted(students, key=lambda x: x.get("focus_score", 100), reverse=True)
    top_3 = [{"name": s.get("name"), "score": int(s.get("focus_score", 100))} for s in sorted_students[:3]]
    danger_hour = session_manager.repo.get_classroom_danger_hour(class_id)
    
    top_3_str = ", ".join([f"{s['name']} ({s['score']})" for s in top_3])
    summary_text = (
        f"Buổi học đã kết thúc. Điểm trung bình toàn lớp đạt {avg_score}/100. "
        f"Top 3 học sinh tập trung xuất sắc nhất gồm: {top_3_str}. "
        f"Khung giờ học sinh bị sa sút tập trung nhiều nhất được xác định là {danger_hour}."
    )
    
    return jsonify({
        "status": "success",
        "average_score": avg_score,
        "top_students": top_3,
        "danger_hour": danger_hour,
        "summary_text": summary_text
    })

@app.route('/api/sessions')
def get_all_sessions():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    return jsonify(session_manager.get_all_sessions())

@app.route('/api/latest_session')
def get_latest_session():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    
    latest = session_manager.get_latest_session()
    if latest:
        return jsonify(latest)
    return jsonify({"status": "empty", "message": "No sessions found"})

@app.route('/api/settings', methods=['GET', 'POST'])
def manage_settings():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Không có quyền truy cập"}), 401
    
    global camera_ai
    if request.method == 'POST':
        data = request.get_json()
        ear = float(data.get('ear_threshold', 0.22))
        drowsy = float(data.get('drowsy_threshold', 1.5))
        distract = float(data.get('distraction_threshold', 2.0))
        display_name = data.get('display_name', 'Học sinh')
        
        session['display_name'] = display_name
        
        session_manager.settings = {
            'ear_threshold': ear,
            'drowsy_threshold': drowsy,
            'distraction_threshold': distract
        }
        
        if camera_ai is not None:
            camera_ai.EAR_THRESHOLD = ear
            camera_ai.DROWSY_TIME_THRESH = drowsy
            camera_ai.DISTRACTION_TIME_THRESH = distract
            
        return jsonify({"status": "success", "message": "Cấu hình đã được lưu"})
    
    current_settings = getattr(session_manager, 'settings', {
        'ear_threshold': 0.22,
        'drowsy_threshold': 1.5,
        'distraction_threshold': 2.0
    })
    return jsonify(current_settings)

# ============================================================
# WebSocket (SocketIO) Event Handlers
# ============================================================

@socketio.on('connect')
def on_connect():
    print(f"[WS] Client connected")

@socketio.on('disconnect')
def on_disconnect():
    print(f"[WS] Client disconnected")

@socketio.on('join_teacher_room')
def on_join_teacher_room(data):
    """Teacher joins 'teachers' room to receive student updates."""
    join_room('teachers')
    emit('joined', {'room': 'teachers', 'message': 'Đã kết nối realtime với lớp học'})
    print("[WS] Teacher joined room: teachers")

@socketio.on('join_student_room')
def on_join_student_room(data):
    """Student joins their own room + global students room."""
    name = data.get('name', 'Unknown')
    join_room('students')
    join_room(f"student_{name}")
    # Store current student name in session_manager for camera push
    session_manager.current_student_name = name
    emit('joined', {'room': 'students', 'message': f'Chào mừng {name} đã kết nối lớp học'})
    print(f"[WS] Student '{name}' joined rooms: students, student_{name}")
    
    # Notify teacher a new student came online
    socketio.emit('student_came_online', {
        'name': name,
        'message': f'{name} vừa kết nối vào lớp học'
    }, room='teachers')

@socketio.on('student_data_push')
def on_student_data_push(data):
    """
    Student pushes their AI focus data to server.
    Server immediately re-emits to all teachers.
    This is the WebSocket alternative to HTTP polling.
    """
    name = data.get('name', 'Unknown')
    state = data.get('state', 'Normal')
    focus_score = data.get('focus_score', 80)
    distractions = data.get('distractions', 0)
    early_warning = data.get('early_warning', False)
    emotion = data.get('emotion', 'Bình thường')
    
    # Update session_manager mock_students in real-time
    if name in session_manager.mock_students:
        student = session_manager.mock_students[name]
        student['state'] = state
        student['focus_score'] = focus_score
        student['distractions'] = distractions
        student['online'] = True
        student['current_emotion'] = emotion
        student['focus_history'].append(focus_score)
        if len(student['focus_history']) > 10:
            student['focus_history'].pop(0)
        
        # Log state changes
        if state in ['Sleepy', 'Distracted', 'Phone']:
            from datetime import datetime
            log_type = 'warning' if state == 'Sleepy' else 'danger'
            state_vi = {'Sleepy': 'ngủ gật', 'Distracted': 'mất tập trung', 'Phone': 'dùng điện thoại'}
            session_manager.activity_logs.append({
                'time': datetime.now().strftime('%I:%M %p'),
                'student': name,
                'message': f'{name} {state_vi.get(state, state)}',
                'type': log_type
            })
            if len(session_manager.activity_logs) > 30:
                session_manager.activity_logs.pop(0)
    
    # Push directly to all teacher dashboards (no polling needed!)
    socketio.emit('student_update', {
        'name': name,
        'state': state,
        'focus_score': focus_score,
        'distractions': distractions,
        'online': True,
        'emotion': emotion,
        'early_warning': early_warning
    }, room='teachers')

    if early_warning:
        socketio.emit('early_warning_alert', {
            'name': name,
            'message': f'Cảnh báo sớm: {name} đang có xu hướng giảm tập trung nhanh chóng!'
        }, room='teachers')

@socketio.on('request_class_snapshot')
def on_request_class_snapshot(data):
    """Teacher requests current full class status snapshot (on initial load)."""
    class_id = session.get('class_id')
    if class_id:
        session_manager.class_session_id = class_id
    students = session_manager.get_class_status(class_id)
    elapsed = 0
    if session_manager.class_session_active and session_manager.class_session_start_time:
        elapsed = int(time.time() - session_manager.class_session_start_time)
    emit('class_snapshot', {
        'students': students,
        'class_session_active': session_manager.class_session_active,
        'elapsed_seconds': elapsed,
        'logs': session_manager.activity_logs
    })

@socketio.on('student_frame_push')
def on_student_frame_push(data):
    """
    Student pushes a base64-encoded JPEG frame snapshot.
    Server immediately forwards it to all teacher dashboards.
    """
    name = data.get('name', 'Unknown')
    frame = data.get('frame', '')
    if frame:
        # Relay directly to teacher room
        socketio.emit('student_frame', {
            'name': name,
            'frame': frame
        }, room='teachers')

@socketio.on('student_tab_switch')
def on_student_tab_switch(data):
    name = data.get('name', 'Unknown')
    tab_switches = data.get('tab_switches', 1)
    
    from datetime import datetime
    session_manager.activity_logs.append({
        'time': datetime.now().strftime('%I:%M %p'),
        'student': name,
        'message': f'{name} chuyển tab trình duyệt ({tab_switches} lần)',
        'type': 'danger'
    })
    if len(session_manager.activity_logs) > 30:
        session_manager.activity_logs.pop(0)
        
    if name in session_manager.mock_students:
        session_manager.mock_students[name]['state'] = 'Cheating'
        
    socketio.emit('student_update', {
        'name': name,
        'state': 'Cheating',
        'focus_score': int(session_manager.focus_score),
        'distractions': session_manager.distractions,
        'online': True
    }, room='teachers')


def background_class_drift_thread():
    """Background task to simulate student state drift and broadcast to teachers."""
    print("[BG] Classroom drift thread started.")
    while True:
        socketio.sleep(2)
        if session_manager.class_session_active:
            class_id = getattr(session_manager, 'class_session_id', None)
            if class_id is None:
                class_id = 2  # Default to class_id 2
            
            students = session_manager.get_class_status(class_id)
            elapsed = 0
            if session_manager.class_session_start_time:
                elapsed = int(time.time() - session_manager.class_session_start_time)
                
            socketio.emit('class_snapshot', {
                'students': students,
                'class_session_active': True,
                'elapsed_seconds': elapsed,
                'logs': session_manager.activity_logs
            }, room='teachers')


if __name__ == '__main__':
    # Run with eventlet for WebSocket support
    socketio.start_background_task(background_class_drift_thread)
    socketio.run(app, debug=True, port=5001, use_reloader=False)
