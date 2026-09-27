import os
os.environ.setdefault("GRPC_ENABLE_FORK_SUPPORT", "0")

import base64
import functools
import json
import threading
import time

from flask import (Flask, Response, abort, jsonify, redirect, render_template, request, session, url_for)
from flask_socketio import SocketIO, disconnect, emit, join_room

from repository import load_dotenv
from focusguard import authz, realtime
from focusguard import runtime_state as rs
from focusguard.security import build_flask_config

load_dotenv()

LEGACY_CAMERA_STATE = {
    rs.FOCUS_FOCUSED: "TAP TRUNG",
    rs.FOCUS_DROWSY: "BUON NGU",
    rs.FOCUS_PHONE: "DUNG DIEN THOAI",
    rs.FOCUS_HEAD_AWAY: "NGOANH MAT DI",
    rs.FOCUS_TEMPORARILY_NOT_VISIBLE: "KHONG THAY KHUON MAT",
    rs.FOCUS_AWAY: "KHONG THAY KHUON MAT",
}
MSG_FORBIDDEN = "Không có quyền truy cập"


class CameraHub:
    """At most one physical camera pipeline per process.

    * viewers of the same pipeline key share it (reference counted); closing
      one browser tab does not stop the stream for the others;
    * acquiring a different key closes the old pipeline and bumps the
      generation, so generators still holding the old pipeline stop instead
      of re-opening the device;
    * ``read`` serialises ``get_frame`` (tracker and IdentityManager are not
      thread-safe).

    A browser disconnecting only releases the camera device; the
    authoritative SessionRuntime keeps running (it reports NO_CAMERA_SIGNAL
    until frames resume).
    """

    def __init__(self):
        self.lock = threading.RLock()
        self.frame_lock = threading.Lock()
        self.pipeline = None
        self.key = None
        self.users = 0
        self.generation = 0

    def acquire(self, key, factory):
        with self.lock:
            if self.pipeline is not None and self.key != key:
                self._close()
            if self.pipeline is None:
                self.pipeline = factory()
                self.key = key
                self.users = 0
                self.generation += 1
            self.users += 1
            return self.pipeline, self.generation

    def is_current(self, generation):
        return self.pipeline is not None and self.generation == generation

    def read(self, generation):
        with self.frame_lock:
            pipeline = self.pipeline
            if pipeline is None or self.generation != generation:
                return None
            return pipeline.get_frame()

    def release(self, generation):
        """A viewer of ``generation`` left."""
        with self.lock:
            if self.pipeline is None or generation != self.generation:
                return
            self.users -= 1
            if self.users <= 0:
                self._close()

    def force_release(self, predicate=None):
        """Close the pipeline now (e.g. class ended) if its key matches."""
        with self.lock:
            if self.pipeline is not None and (predicate is None or predicate(self.key)):
                self._close()

    def _close(self):
        try:
            self.pipeline.release()
        except Exception as exc:
            print("[CAMERA] release error:", exc)
        self.pipeline = None
        self.key = None
        self.users = 0
        self.generation += 1


def create_app(repo=None, env=None, async_mode=None, start_background=True, session_manager=None):
    cfg = build_flask_config(env)
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=cfg["SECRET_KEY"],
        SESSION_COOKIE_HTTPONLY=cfg["SESSION_COOKIE_HTTPONLY"],
        SESSION_COOKIE_SAMESITE=cfg["SESSION_COOKIE_SAMESITE"],
        SESSION_COOKIE_SECURE=cfg["SESSION_COOKIE_SECURE"],
        PERMANENT_SESSION_LIFETIME=cfg["PERMANENT_SESSION_LIFETIME"],
        MAX_CONTENT_LENGTH=cfg["MAX_CONTENT_LENGTH"],
        FOCUSGUARD=cfg,
    )

    if async_mode is None:
        async_mode = os.environ.get("SOCKETIO_ASYNC_MODE")
    if async_mode is None:
        try:
            import eventlet  # noqa: F401
            async_mode = "eventlet"
        except ImportError:
            async_mode = "threading"
    socketio = SocketIO(app, cors_allowed_origins=cfg["SOCKETIO_CORS_ORIGINS"], async_mode=async_mode,
                        logger=False, engineio_logger=False)

    def notifier(kind, payload):
        class_id = payload.get("class_id")
        if class_id is not None:
            socketio.emit("log_update", payload, room=realtime.teacher_room(class_id))

    if session_manager is None:
        from session_manager import SessionManager
        session_manager = SessionManager(repo=repo, notifier=notifier,
                                         seed_demo_accounts=cfg["SEED_DEMO_ACCOUNTS"])
    else:
        session_manager.notifier = notifier
    sm = session_manager
    repo = sm.repo
    cameras = CameraHub()
    teacher_settings = {}
    app.extensions["focusguard"] = {"session_manager": sm, "socketio": socketio, "cameras": cameras}

    # ------------------------------------------------------------ auth helpers
    def current_principal():
        if "user_id" not in session:
            return None
        return authz.build_principal(session.get("user_id"), session.get("role"), repo)

    def api_error(message=MSG_FORBIDDEN, code=403):
        return jsonify({"status": "error", "message": message}), code

    def login_required_page(role=None):
        def deco(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                p = current_principal()
                if p is None:
                    session.clear()
                    return redirect(url_for("login"))
                if role and p.role != role:
                    return redirect(url_for("index"))
                return fn(p, *args, **kwargs)
            return wrapper
        return deco

    def api_auth(*roles):
        def deco(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                p = current_principal()
                if p is None:
                    return api_error(MSG_FORBIDDEN, 401)
                if roles and p.role not in roles:
                    return api_error()
                return fn(p, *args, **kwargs)
            return wrapper
        return deco

    def int_arg(name, default=None, source=None):
        src = source if source is not None else request.args
        try:
            return int(src.get(name))
        except (TypeError, ValueError):
            return default

    def teacher_class_id(p, source=None):
        """Class requested by a teacher, defaulting to their first class; None if not allowed."""
        cid = int_arg("class_id", None, source)
        if cid is None:
            cid = session.get("class_id") if session.get("class_id") in p.class_ids else \
                (sorted(p.class_ids)[0] if p.class_ids else None)
        return cid if authz.can_manage_class(p, cid) else None

    def subject_student_id(p):
        """Whose personal analytics are requested: own (student), linked (parent) or
        ?student_id= for teachers/admin with an ownership check."""
        if p.role == authz.ROLE_STUDENT:
            return p.user_id
        if p.role == authz.ROLE_PARENT:
            return p.linked_student_id
        sid = int_arg("student_id")
        if sid is None:
            return None
        user = repo.get_user_by_id(sid)
        if not user or user.get("role") != "student":
            return None
        return sid if authz.can_view_student(p, sid, user.get("class_id")) else None

    # ------------------------------------------------------------------ pages
    @app.route("/")
    def index():
        p = current_principal()
        if p is None:
            session.clear()
            return redirect(url_for("login"))
        if p.role == authz.ROLE_TEACHER:
            return redirect(url_for("teacher_dashboard"))
        if p.role == authz.ROLE_ADMIN:
            return redirect(url_for("admin_root"))
        if p.role == authz.ROLE_PARENT:
            return redirect(url_for("parent_dashboard"))
        return render_template("index.html", active_tab="dashboard")

    def student_page(tab):
        @login_required_page(authz.ROLE_STUDENT)
        def view(p):
            return render_template("index.html", active_tab=tab)
        view.__name__ = f"student_{tab}"
        return view

    app.add_url_rule("/stats", "stats", student_page("stats"))
    app.add_url_rule("/reports", "reports", student_page("reports"))
    app.add_url_rule("/settings", "settings", student_page("settings"))

    @app.route("/alerts")
    def alerts():
        return redirect(url_for("reports"))

    def teacher_page(tab):
        @login_required_page(authz.ROLE_TEACHER)
        def view(p):
            classes = [{"id": cid, "class_name": repo.get_class_name(cid)} for cid in sorted(p.class_ids)]
            current = teacher_class_id(p)
            return render_template("teacher_dashboard.html", active_tab=tab,
                                   teacher_name=session.get("display_name", "Giáo viên"),
                                   class_name=repo.get_class_name(current), teacher_classes=classes,
                                   current_class_id=current)
        view.__name__ = f"teacher_{tab}"
        return view

    for tab in ("dashboard", "students", "analytics", "reports", "alerts", "settings", "attendance"):
        endpoint = "teacher_dashboard" if tab == "dashboard" else f"teacher_{tab}"
        app.add_url_rule(f"/teacher/{tab}", endpoint, teacher_page(tab))

    @app.route("/parent/dashboard")
    @login_required_page(authz.ROLE_PARENT)
    def parent_dashboard(p):
        sid = p.linked_student_id
        student = repo.get_user_by_id(sid) if sid else None
        if not student:
            return render_template("parent_dashboard.html", student_name="Chưa liên kết học sinh",
                                   profile_stats=sm.student_profile(-1), recommendations=None,
                                   heatmap_data={}, comparison=[], attendance=[], attendance_summary=None)
        attendance = sm.student_attendance_history(sid)
        attended = sum(1 for a in attendance if not a["missed"])
        attendance_summary = None if not attendance else {
            "attended": attended, "total": len(attendance),
            "rate": int(round(100.0 * attended / len(attendance))),
            "away_count": sum(a.get("away_count") or 0 for a in attendance),
        }
        return render_template(
            "parent_dashboard.html", student_name=student.get("display_name"),
            profile_stats=sm.student_profile(sid), recommendations=sm.student_recommendation(sid),
            heatmap_data=sm.student_heatmap(sid), comparison=sm.student_session_comparison(sid, 7),
            attendance=attendance[:10], attendance_summary=attendance_summary)

    @app.route("/mobile")
    @login_required_page()
    def mobile_simulator(p):
        return render_template("mobile_simulator.html")

    # ----------------------------------------------------------- authentication
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_principal() is not None:
            return redirect(url_for("index"))
        error = None
        if request.method == "POST":
            user = repo.authenticate_user(request.form.get("username", "").strip(), request.form.get("password", ""))
            if user:
                session.clear()
                session.permanent = True
                session["user"], session["user_id"] = user[1], user[0]
                session["display_name"], session["role"], session["class_id"] = user[2], user[3], user[4]
                return redirect(url_for("index"))
            error = "Tên đăng nhập hoặc mật khẩu không đúng!"
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ----------------------------------------------------------- video stream
    def stream(pipeline_key, factory, keep_running):
        def gen():
            generation = None
            try:
                _, generation = cameras.acquire(pipeline_key, factory)
                while keep_running() and cameras.is_current(generation):
                    socketio.sleep(0.05)
                    out = cameras.read(generation)
                    if out is None or out[0] is None:
                        continue
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + out[0] + b"\r\n"
            except GeneratorExit:
                pass
            finally:
                if generation is not None:
                    cameras.release(generation)
        return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/video_feed")
    def video_feed():
        p = current_principal()
        if p is None:
            return api_error(MSG_FORBIDDEN, 401)
        if request.args.get("mode") == "classroom" or p.role in (authz.ROLE_TEACHER, authz.ROLE_ADMIN):
            cid = int_arg("class_id") or teacher_class_id(p)
            if not authz.can_view_video_feed(p, "classroom", cid):
                return api_error()
            rt = sm.classroom_runtime(cid)
            if rt is None:
                return api_error("Lớp học chưa bắt đầu giám sát bằng camera.", 409)
            cs_id = rt.class_session_id

            def factory():
                from classroom_ai import ClassroomAI
                return ClassroomAI(sm, cid, class_session_id=cs_id)
            # Bound to this exact classroom session: stops if the class ends or
            # another (e.g. online) session replaces it.
            return stream(("classroom", cid, cs_id), factory,
                          lambda: sm.classroom_runtime(cid, cs_id) is not None)

        if not authz.can_view_video_feed(p, "personal"):
            return api_error()
        if sm.runtime_for_student(p.user_id) is None:
            return api_error("Chưa bắt đầu phiên học.", 409)
        sid = p.user_id

        def factory():
            from camera_ai import FocusAI
            return FocusAI(sm, sid)
        return stream(("personal", sid), factory, lambda: sm.runtime_for_student(sid) is not None)

    # ------------------------------------------------------- student live API
    def history_for(student_id):
        rt = sm.runtime_for_student(student_id)
        return rt.history(student_id) if rt is not None else []

    @app.route("/api/stats")
    @api_auth(authz.ROLE_STUDENT)
    def get_stats(p):
        live = sm.student_live_view(p.user_id)
        s = live.get("student") or {}
        focus_state = s.get("focus_state", rs.FOCUS_UNKNOWN)
        return jsonify({
            "is_active": live["is_active"],
            "seconds_elapsed": live["seconds_elapsed"],
            "camera_status": live.get("camera_status"),
            "focus_score": s.get("focus_score"),
            "average_focus_score": s.get("average_focus_score"),
            "focus_state": focus_state,
            "current_state": LEGACY_CAMERA_STATE.get(focus_state, "CHUA CO DU LIEU"),
            "visibility_status": s.get("visibility_status"),
            "attendance_status": s.get("attendance_status"),
            "labels": s.get("labels"),
            "distractions": s.get("distractions", 0),
            "event_counts": s.get("event_counts", {}),
            "seat_leaving_count": s.get("away_count", 0),
            "seat_leaving_duration": s.get("away_seconds", 0),
            "visible_seconds": s.get("visible_seconds", 0),
            "history": history_for(p.user_id),
            "evaluation_status": "NOT_EVALUATED",
        })

    @app.route("/api/start_session", methods=["POST"])
    @api_auth(authz.ROLE_STUDENT)
    def start_session(p):
        data = request.get_json(silent=True) or {}
        subject = (data.get("subject") or "").strip()[:40] or None
        session_id = sm.start_personal_session(p.user_id, subject=subject)
        return jsonify({"status": "success", "session_id": session_id})

    @app.route("/api/stop_session", methods=["POST"])
    @api_auth(authz.ROLE_STUDENT)
    def stop_session(p):
        result = sm.stop_personal_session(p.user_id)
        cameras.force_release(lambda key: key == ("personal", p.user_id))
        return jsonify({"status": "success", "result": result})

    # ------------------------------------------------ personal analytics (own)
    def personal_endpoint(fn):
        @functools.wraps(fn)
        @api_auth(authz.ROLE_STUDENT, authz.ROLE_PARENT, authz.ROLE_TEACHER, authz.ROLE_ADMIN)
        def wrapper(p, *args, **kwargs):
            sid = subject_student_id(p)
            if sid is None:
                return api_error()
            return fn(p, sid, *args, **kwargs)
        return wrapper

    @app.route("/api/sessions")
    @personal_endpoint
    def get_all_sessions(p, sid):
        return jsonify(sm.student_sessions(sid))

    @app.route("/api/latest_session")
    @personal_endpoint
    def get_latest_session(p, sid):
        done = [s for s in sm.student_sessions(sid) if s.get("end_time")]
        if not done:
            return jsonify({"status": "empty", "message": "Chưa có phiên học nào"})
        return jsonify(done[0])

    @app.route("/api/session/<int:session_id>/breakdown")
    @api_auth()
    def api_session_breakdown(p, session_id):
        row = repo.get_session(session_id)
        owner = repo.get_user_by_id(row.get("user_id")) if row else None
        if not row or not authz.can_view_personal_session(p, row, (owner or {}).get("class_id")):
            return api_error(code=404 if not row else 403)
        return jsonify(sm.session_breakdown(session_id))

    @app.route("/api/student/heatmap")
    @personal_endpoint
    def api_student_heatmap(p, sid):
        return jsonify(sm.student_heatmap(sid))

    @app.route("/api/student/subject_analytics")
    @personal_endpoint
    def api_student_subject_analytics(p, sid):
        return jsonify(sm.student_subject_analytics(sid))

    @app.route("/api/student/profile")
    @personal_endpoint
    def api_student_profile(p, sid):
        return jsonify(sm.student_profile(sid))

    @app.route("/api/student/session_comparison")
    @personal_endpoint
    def api_student_session_comparison(p, sid):
        return jsonify(sm.student_session_comparison(sid))

    @app.route("/api/student/recommendations")
    @personal_endpoint
    def api_student_recommendations(p, sid):
        return jsonify(sm.student_recommendation(sid))

    @app.route("/api/student/attendance_history")
    @personal_endpoint
    def api_student_attendance_history(p, sid):
        return jsonify(sm.student_attendance_history(sid))

    @app.route("/api/leaderboard")
    @api_auth(authz.ROLE_TEACHER, authz.ROLE_ADMIN)
    def api_leaderboard(p):
        cid = teacher_class_id(p)
        if cid is None:
            return api_error()
        return jsonify(sm.class_leaderboard_today(cid))

    @app.route("/api/settings", methods=["GET", "POST"])
    @api_auth()
    def manage_settings(p):
        beh = sm.config.behavior
        current = {"ear_threshold": beh.ear_threshold, "drowsy_threshold": beh.drowsy_min_seconds,
                   "distraction_threshold": beh.head_away_min_seconds,
                   "phone_threshold": beh.phone_min_seconds, "editable": p.is_admin}
        if request.method == "GET":
            return jsonify(current)
        if not p.is_admin:
            # Personal preferences (sound, volume) live in the browser; AI thresholds
            # are centralised and cannot be changed by students/teachers/parents.
            return jsonify({"status": "success", "thresholds_changed": False,
                            "message": "Đã lưu tuỳ chọn cá nhân. Ngưỡng nhận diện do quản trị viên cấu hình."})
        data = request.get_json(silent=True) or {}
        try:
            sm.config = sm.config.with_behavior(
                ear_threshold=float(data.get("ear_threshold", beh.ear_threshold)),
                drowsy_min_seconds=float(data.get("drowsy_threshold", beh.drowsy_min_seconds)),
                head_away_min_seconds=float(data.get("distraction_threshold", beh.head_away_min_seconds)))
        except (TypeError, ValueError):
            return api_error("Giá trị không hợp lệ", 400)
        return jsonify({"status": "success", "message": "Cấu hình áp dụng cho phiên học mới."})

    # ----------------------------------------------------------- teacher API
    @app.route("/api/teacher/class_status")
    @api_auth(authz.ROLE_TEACHER, authz.ROLE_ADMIN)
    def api_class_status(p):
        cid = teacher_class_id(p)
        if cid is None:
            return api_error()
        view = sm.class_live_view(cid)
        return jsonify({"status": "success", "students": view["students"], "statistics": view["statistics"],
                        "class_session_active": view["active"], "mode": view["mode"],
                        "camera_status": view["camera_status"], "elapsed_seconds": view["elapsed_seconds"],
                        "logs": view["logs"], "class_id": cid})

    def _start_class(p, mode):
        data = request.get_json(silent=True) or {}
        cid = teacher_class_id(p, data) if data.get("class_id") is not None else teacher_class_id(p)
        if cid is None:
            return api_error()
        rt = sm.start_class(cid, mode=mode, started_by=p.user_id)
        socketio.emit("class_started", {"message": "Giáo viên đã bắt đầu lớp học", "class_id": cid},
                      room=realtime.class_students_room(cid))
        return jsonify({"status": "success", "class_session_id": rt.class_session_id, "class_id": cid,
                        "message": "Lớp học đã bắt đầu."})

    def _end_class(p, mode):
        data = request.get_json(silent=True) or {}
        cid = teacher_class_id(p, data) if data.get("class_id") is not None else teacher_class_id(p)
        if cid is None:
            return api_error()
        rt = sm.class_runtime(cid)
        if rt is None:
            return jsonify({"status": "success", "message": "Không có lớp học đang diễn ra."})
        cameras.force_release(lambda key: key[:2] == ("classroom", cid))
        result = sm.end_class(cid)
        socketio.emit("class_ended", {"message": "Giáo viên đã kết thúc lớp học", "class_id": cid},
                      room=realtime.class_students_room(cid))
        return jsonify({"status": "success", "class_session_id": result["class_session_id"],
                        "message": "Lớp học đã kết thúc."})

    @app.route("/api/teacher/start_class", methods=["POST"])
    @api_auth(authz.ROLE_TEACHER)
    def start_class(p):
        return _start_class(p, "online")

    @app.route("/api/teacher/end_class", methods=["POST"])
    @api_auth(authz.ROLE_TEACHER)
    def end_class(p):
        return _end_class(p, "online")

    @app.route("/api/teacher/start_offline_class", methods=["POST"])
    @api_auth(authz.ROLE_TEACHER)
    def start_offline_class(p):
        return _start_class(p, "classroom")

    @app.route("/api/teacher/end_offline_class", methods=["POST"])
    @api_auth(authz.ROLE_TEACHER)
    def end_offline_class(p):
        return _end_class(p, "classroom")

    @app.route("/api/teacher/offline_classroom_status")
    @api_auth(authz.ROLE_TEACHER, authz.ROLE_ADMIN)
    def api_offline_classroom_status(p):
        cid = teacher_class_id(p)
        if cid is None:
            return api_error()
        view = sm.class_live_view(cid)
        st = view["statistics"]
        facts = []
        if view["active"]:
            facts.append(f"Camera: {view['camera_status']}. Đang thấy {st['visible']}/{st['enrolled']} học sinh.")
            if st["phone"]:
                facts.append(f"{st['phone']} học sinh có hành vi dùng điện thoại kéo dài.")
            if st["drowsy"]:
                facts.append(f"{st['drowsy']} học sinh nhắm mắt kéo dài (dấu hiệu buồn ngủ).")
            if st["head_away"]:
                facts.append(f"{st['head_away']} học sinh quay đầu khỏi hướng bảng kéo dài.")
            if st["away"]:
                facts.append(f"{st['away']} học sinh đang rời chỗ.")
        return jsonify({
            "status": "success", "students": view["students"],
            "statistics": {"present": st["present"], "enrolled": st["enrolled"], "visible": st["visible"],
                           "distracted": st["phone"] + st["head_away"], "drowsy": st["drowsy"],
                           "focus_score": st["average_focus_score"]},
            "analyses": facts, "suggestions": [], "logs": view["logs"],
            "offline_class_active": view["active"] and view["mode"] == "classroom",
            "camera_status": view["camera_status"], "elapsed_seconds": view["elapsed_seconds"],
        })

    @app.route("/api/teacher/logs")
    @api_auth(authz.ROLE_TEACHER, authz.ROLE_ADMIN)
    def api_teacher_logs(p):
        cid = teacher_class_id(p)
        if cid is None:
            return api_error()
        return jsonify(sm.class_live_view(cid)["logs"])

    @app.route("/api/teacher/interventions")
    @api_auth(authz.ROLE_TEACHER, authz.ROLE_ADMIN)
    def api_teacher_interventions(p):
        cid = teacher_class_id(p)
        if cid is None:
            return api_error()
        st = sm.class_live_view(cid)["statistics"]
        avg = st["average_focus_score"]
        threshold = teacher_settings.get(p.user_id, {}).get("min_focus_threshold", 65)
        if avg is None:
            return jsonify({"status": "insufficient_data", "average_score": None, "needs_intervention": False,
                            "message": "Không đủ dữ liệu", "recommendations": []})
        needs = avg < threshold
        return jsonify({"status": "success", "average_score": avg, "needs_intervention": needs,
                        "measured_students": st["measured_students"],
                        "message": (f"Điểm tập trung trung bình ({st['measured_students']} học sinh đo được) là {avg}, "
                                    f"dưới ngưỡng {threshold}.") if needs else "Lớp học trên ngưỡng tập trung.",
                        "recommendations": []})

    @app.route("/api/teacher/analytics_summary")
    @api_auth(authz.ROLE_TEACHER, authz.ROLE_ADMIN)
    def api_teacher_analytics_summary(p):
        cid = teacher_class_id(p)
        if cid is None:
            return api_error()
        data = sm.class_analytics(cid)
        live = sm.class_live_view(cid)["statistics"]
        bd = data["breakdown"]
        pct = bd.get("percentages")
        return jsonify({
            "status": "success", "class_id": cid,
            "average_score": live["average_focus_score"],
            "danger_hour": data["danger_hour"]["label"],
            "danger_hour_detail": data["danger_hour"],
            "watchlist": data["watchlist"],
            "breakdown": bd,
            "root_cause": None if pct is None else {
                "phone_pct": pct["PHONE"], "drowsy_pct": pct["DROWSY"],
                "distracted_pct": pct["HEAD_AWAY"], "away_pct": pct["AWAY"]},
            "class_sessions": data["class_sessions"],
        })

    @app.route("/api/teacher/class_summary")
    @api_auth(authz.ROLE_TEACHER, authz.ROLE_ADMIN)
    def api_teacher_class_summary(p):
        cid = teacher_class_id(p)
        if cid is None:
            return api_error()
        cs_id = int_arg("class_session_id") or sm.latest_class_session_id(cid)
        if cs_id is None:
            return jsonify({"status": "insufficient_data", "summary_text": "Không đủ dữ liệu"})
        row = repo.get_class_session(cs_id)
        if not authz.can_view_class_session(p, row):
            return api_error()
        summary = sm.class_session_summary(cs_id, cid)
        summary["danger_hour"] = sm.class_analytics(cid)["danger_hour"]["label"]
        summary["status"] = "success" if summary.get("status") == "ok" else summary.get("status")
        return jsonify(summary)

    @app.route("/api/teacher/settings", methods=["POST"])
    @api_auth(authz.ROLE_TEACHER)
    def save_teacher_settings(p):
        data = request.get_json(silent=True) or {}
        display_name = (data.get("display_name") or "").strip()
        if not display_name:
            return api_error("Tên giáo viên không được để trống.", 400)
        repo.update_display_name(p.user_id, display_name[:80])
        session["display_name"] = display_name[:80]
        try:
            threshold = max(0, min(100, int(data.get("min_focus_threshold", 65))))
        except (TypeError, ValueError):
            threshold = 65
        teacher_settings[p.user_id] = {"min_focus_threshold": threshold}
        return jsonify({"status": "success", "message": "Cấu hình đã được lưu thành công!"})

    # ------------------------------------------------------------- admin API
    @app.route("/admin")
    @app.route("/admin/")
    @app.route("/admin/dashboard")
    @login_required_page(authz.ROLE_ADMIN)
    def admin_root(p):
        return redirect(url_for("admin_accounts"))

    @app.route("/admin/accounts")
    @login_required_page(authz.ROLE_ADMIN)
    def admin_accounts(p):
        return render_template("admin_dashboard.html", active_tab="accounts")

    @app.route("/admin/classes")
    @login_required_page(authz.ROLE_ADMIN)
    def admin_classes_page(p):
        return render_template("admin_dashboard.html", active_tab="classes")

    @app.route("/api/admin/classes")
    @api_auth(authz.ROLE_ADMIN)
    def admin_classes(p):
        return jsonify(repo.get_classes_list())

    @app.route("/api/admin/users")
    @api_auth(authz.ROLE_ADMIN)
    def admin_users(p):
        return jsonify(repo.get_users_list())

    @app.route("/api/admin/create_class", methods=["POST"])
    @api_auth(authz.ROLE_ADMIN)
    def admin_create_class(p):
        name = ((request.get_json(silent=True) or {}).get("class_name") or "").strip()
        if not name:
            return api_error("Tên lớp không được trống", 400)
        ok, msg = repo.create_class(name)
        return jsonify({"status": "success" if ok else "error", "message": msg})

    @app.route("/api/admin/edit_class/<int:class_id>", methods=["POST"])
    @api_auth(authz.ROLE_ADMIN)
    def admin_edit_class(p, class_id):
        name = ((request.get_json(silent=True) or {}).get("class_name") or "").strip()
        if not name:
            return api_error("Tên lớp không được trống", 400)
        ok, msg = repo.update_class(class_id, name)
        return jsonify({"status": "success" if ok else "error", "message": msg})

    @app.route("/api/admin/delete_class/<int:class_id>", methods=["POST", "DELETE"])
    @api_auth(authz.ROLE_ADMIN)
    def admin_delete_class(p, class_id):
        ok, msg = repo.delete_class(class_id)
        return jsonify({"status": "success" if ok else "error", "message": msg})

    def _user_payload():
        d = request.get_json(silent=True) or {}
        return ((d.get("username") or "").strip(), (d.get("password") or "").strip(),
                (d.get("display_name") or "").strip(), (d.get("role") or "").strip(),
                d.get("class_id"), d.get("student_id"))

    @app.route("/api/admin/create_user", methods=["POST"])
    @api_auth(authz.ROLE_ADMIN)
    def admin_create_user(p):
        username, password, display_name, role, class_id, student_id = _user_payload()
        if not username or not password or not display_name or not role:
            return api_error("Vui lòng nhập đầy đủ thông tin", 400)
        ok, msg = repo.create_user(username, password, display_name, role, class_id, student_id)
        return jsonify({"status": "success" if ok else "error", "message": msg})

    @app.route("/api/admin/edit_user/<int:user_id>", methods=["POST"])
    @api_auth(authz.ROLE_ADMIN)
    def admin_edit_user(p, user_id):
        username, password, display_name, role, class_id, student_id = _user_payload()
        if not username or not display_name or not role:
            return api_error("Vui lòng nhập đầy đủ thông tin", 400)
        ok, msg = repo.update_user(user_id, username, password, display_name, role, class_id, student_id)
        return jsonify({"status": "success" if ok else "error", "message": msg})

    @app.route("/api/admin/delete_user/<int:user_id>", methods=["POST", "DELETE"])
    @api_auth(authz.ROLE_ADMIN)
    def admin_delete_user(p, user_id):
        if user_id == p.user_id:
            return api_error("Không thể tự xóa tài khoản đang đăng nhập.", 400)
        ok, msg = repo.delete_user(user_id)
        return jsonify({"status": "success" if ok else "error", "message": msg})

    def _decode_image(b64):
        import cv2
        import numpy as np
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        arr = np.frombuffer(base64.b64decode(b64), np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def _refresh_classroom_gallery():
        pipeline = cameras.pipeline
        if pipeline is not None and getattr(pipeline, "mode", None) == "classroom":
            pipeline.reload_gallery()

    @app.route("/api/admin/register_face", methods=["POST"])
    @api_auth(authz.ROLE_ADMIN)
    def admin_register_face(p):
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")
        images = data.get("images") or []
        target = repo.get_user_by_id(user_id) if user_id is not None else None
        if not target or target.get("role") != "student" or not images:
            return api_error("Thiếu thông tin học sinh hoặc hình ảnh", 400)
        imgs = []
        for b64 in images[:10]:
            try:
                img = _decode_image(b64)
                if img is not None:
                    imgs.append(img)
            except Exception:
                continue
        if not imgs:
            return api_error("Không có hình ảnh hợp lệ để trích xuất", 400)
        from face_recognition import FaceRecognizer
        embedding = FaceRecognizer().register_student(imgs)
        if embedding is None:
            return api_error("Không phát hiện thấy khuôn mặt rõ ràng trong các bức ảnh", 400)
        # Only the embedding is stored; no face photo is written to disk.
        if not repo.save_face_embedding(target["id"], json.dumps(embedding)):
            return api_error("Không thể lưu đặc trưng vào cơ sở dữ liệu", 500)
        _refresh_classroom_gallery()
        return jsonify({"status": "success", "message": "Đăng ký khuôn mặt thành công. Chỉ lưu vector đặc trưng."})

    @app.route("/api/admin/reset_face", methods=["POST"])
    @api_auth(authz.ROLE_ADMIN)
    def admin_reset_face(p):
        try:
            user_id = int((request.get_json(silent=True) or {}).get("user_id"))
        except (TypeError, ValueError):
            return api_error("Thiếu thông tin user_id", 400)
        repo.save_face_embedding(user_id, None)
        legacy = os.path.join(app.static_folder, "uploads", "avatars", f"student_{user_id}.jpg")
        if os.path.exists(legacy):
            os.remove(legacy)
        _refresh_classroom_gallery()
        return jsonify({"status": "success", "message": "Đã xóa dữ liệu khuôn mặt thành công."})

    @app.route("/api/admin/detect_face", methods=["POST"])
    @api_auth(authz.ROLE_ADMIN)
    def admin_detect_face(p):
        b64 = (request.get_json(silent=True) or {}).get("image")
        if not b64:
            return api_error("Thiếu dữ liệu hình ảnh", 400)
        try:
            import cv2
            img = _decode_image(b64)
            if img is None:
                return api_error("Ảnh không hợp lệ", 400)
            from face_recognition import FaceRecognizer
            faces = FaceRecognizer().app.get(img)
            if not faces:
                return jsonify({"status": "no_face", "message": "Không tìm thấy khuôn mặt"})
            f = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
            x1, y1, x2, y2 = map(int, f.bbox)
            fw, fh = x2 - x1, y2 - y1
            if fw < 80 or fh < 80:
                return jsonify({"status": "low_quality", "message": "Khuôn mặt quá nhỏ hoặc quá xa camera"})
            crop = img[max(0, y1 - fh // 4):min(img.shape[0], y2 + fh // 4), max(0, x1 - fw // 4):min(img.shape[1], x2 + fw // 4)]
            _, buf = cv2.imencode(".jpg", crop)
            return jsonify({"status": "success",
                            "cropped_image": "data:image/jpeg;base64," + base64.b64encode(buf).decode("ascii")})
        except Exception as exc:
            print(f"Error in detect_face: {exc}")
            return api_error("Lỗi xử lý ảnh", 500)

    # ------------------------------------------------------------- Socket.IO
    def socket_principal():
        return current_principal()

    @socketio.on("connect")
    def on_connect(auth=None):
        p = socket_principal()
        if p is None:
            return False  # reject unauthenticated sockets
        if p.role == authz.ROLE_STUDENT:
            join_room(realtime.student_room(p.user_id))
            for cid in p.class_ids:
                join_room(realtime.class_students_room(cid))
            rt = sm.runtime_for_student(p.user_id)
            if rt is not None:
                rt.set_connection(p.user_id, True)
        elif p.role == authz.ROLE_PARENT and p.linked_student_id:
            join_room(realtime.student_room(p.linked_student_id))

    @socketio.on("disconnect")
    def on_disconnect(*args):
        p = socket_principal()
        if p is not None and p.role == authz.ROLE_STUDENT:
            rt = sm.runtime_for_student(p.user_id)
            if rt is not None:
                rt.set_connection(p.user_id, False)

    @socketio.on("join_teacher_room")
    def on_join_teacher_room(data=None):
        p = socket_principal()
        if p is None or p.role not in (authz.ROLE_TEACHER, authz.ROLE_ADMIN):
            emit("error", {"code": "forbidden", "message": MSG_FORBIDDEN})
            return
        requested = (data or {}).get("class_id")
        targets = [requested] if requested is not None else sorted(p.class_ids)
        joined = []
        for cid in targets:
            if authz.can_manage_class(p, cid):
                join_room(realtime.teacher_room(cid))
                joined.append(int(cid))
        if not joined:
            emit("error", {"code": "forbidden", "message": MSG_FORBIDDEN})
            return
        emit("joined", {"rooms": [realtime.teacher_room(c) for c in joined],
                        "message": "Đã kết nối realtime với lớp học"})

    @socketio.on("join_student_room")
    def on_join_student_room(data=None):
        # Identity comes from the authenticated Flask session; any client
        # supplied "name" is ignored.
        p = socket_principal()
        if p is None or p.role != authz.ROLE_STUDENT:
            emit("error", {"code": "forbidden", "message": MSG_FORBIDDEN})
            return
        join_room(realtime.student_room(p.user_id))
        emit("joined", {"rooms": [realtime.student_room(p.user_id)], "message": "Đã kết nối"})

    @socketio.on("request_class_snapshot")
    def on_request_class_snapshot(data=None):
        p = socket_principal()
        cid = (data or {}).get("class_id")
        if p is not None and cid is None and p.class_ids:
            cid = session.get("class_id") if session.get("class_id") in p.class_ids else sorted(p.class_ids)[0]
        if p is None or not authz.can_manage_class(p, cid):
            emit("error", {"code": "forbidden", "message": MSG_FORBIDDEN})
            return
        view = sm.class_live_view(int(cid))
        emit("class_snapshot", _snapshot_payload(view))

    def _reject_client_state(event):
        def handler(data=None):
            p = socket_principal()
            emit("error", {"code": "client_state_rejected", "event": event,
                           "rejected_fields": realtime.rejected_fields(data),
                           "message": "Trạng thái AI, danh tính và điểm chỉ do máy chủ tạo ra."})
            if p is None:
                disconnect()
        return handler

    socketio.on_event("student_data_push", _reject_client_state("student_data_push"))
    socketio.on_event("student_frame_push", _reject_client_state("student_frame_push"))

    @socketio.on("student_tab_switch")
    def on_student_tab_switch(data=None):
        # Client-reported browser signal: logged for the authenticated student
        # with source=client_report. It never changes AI state or score.
        p = socket_principal()
        if p is None or p.role != authz.ROLE_STUDENT:
            emit("error", {"code": "forbidden", "message": MSG_FORBIDDEN})
            return
        rt = sm.runtime_for_student(p.user_id)
        if rt is not None and rt.class_id is not None:
            socketio.emit("log_update", {"type": "client_report", "student_id": p.user_id,
                                         "time": time.time(), "class_id": rt.class_id,
                                         "message": f"{session.get('display_name')} chuyển tab trình duyệt (client báo cáo)"},
                          room=realtime.teacher_room(rt.class_id))

    def _snapshot_payload(view):
        return {"students": view["students"], "statistics": view["statistics"],
                "class_session_active": view["active"], "mode": view["mode"],
                "camera_status": view["camera_status"], "elapsed_seconds": view["elapsed_seconds"],
                "logs": view["logs"], "class_id": view["class_id"]}

    def broadcaster():
        while True:
            socketio.sleep(1.0)
            try:
                for cid, rt in sm.registry.active_classes().items():
                    view = sm.class_live_view(cid)
                    socketio.emit("class_snapshot", _snapshot_payload(view), room=realtime.teacher_room(cid))
                for sid in list(sm._personal_sessions.keys()):
                    live = sm.student_live_view(sid)
                    socketio.emit("my_stats_update", realtime.student_self_view(live.get("student")),
                                  room=realtime.student_room(sid))
            except Exception as exc:
                print("[BG] broadcaster error:", exc)

    if start_background:
        socketio.start_background_task(broadcaster)

    app.extensions["focusguard"]["broadcaster"] = broadcaster
    return app, socketio


if __name__ == "__main__":
    application, sio = create_app()
    cfg = application.config["FOCUSGUARD"]
    run_kwargs = {}
    if sio.async_mode == "threading":
        # Werkzeug dev server: only acceptable outside production.
        run_kwargs["allow_unsafe_werkzeug"] = not cfg["IS_PRODUCTION"]
    sio.run(application, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5001")),
            debug=False, use_reloader=False, **run_kwargs)
